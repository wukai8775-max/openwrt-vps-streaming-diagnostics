#!/usr/bin/env python3
"""Check complete, fixed-size HTTPS objects; failures remain in the denominator.

Requires Python 3.9+ and curl 8.4+ for the streaming --max-filesize guard.
An explicit source address or interface is required. --dry-run makes no request.
Output is JSONL: one plan, one attempt per started request, one summary.
"""

import argparse
from datetime import datetime, timezone
import ipaddress
import json
import math
import re
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
CURL_FORMAT = (
    '{"http_status":"%{http_code}","received_bytes":%{size_download},'
    '"sent_bytes":%{size_upload},"total_seconds":%{time_total},'
    '"first_byte_seconds":%{time_starttransfer},'
    '"connect_seconds":%{time_connect},"tls_seconds":%{time_appconnect},'
    '"local_ipv4":"%{local_ip}","remote_ipv4":"%{remote_ip}"}'
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def emit(record):
    print(json.dumps(record, ensure_ascii=False, allow_nan=False), flush=True)


def finite_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("value must be finite")
    return number


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return number


def concrete_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as error:
        raise ValueError("invalid IPv4 address") from error
    if address.is_unspecified or address.is_multicast or int(address) == 0xFFFFFFFF:
        raise ValueError("use a concrete unicast IPv4 address, not unspecified/multicast/broadcast")
    return str(address)


def validated_url(value):
    """Return the actual URL plus a log-safe endpoint identity without its query."""
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("URL must not contain control characters")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("--url must be an explicit HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are not allowed; use a token-free test endpoint")
    if parsed.fragment:
        raise ValueError("URL fragments are not allowed")
    try:
        port = parsed.port or 443
    except ValueError as error:
        raise ValueError("invalid HTTPS port") from error
    host = parsed.hostname.encode("idna").decode("ascii")
    if not 1 <= port <= 65535:
        raise ValueError("invalid HTTPS port")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise ValueError("use a hostname or IPv4 address for the IPv4 test")
    try:
        ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        pass
    else:
        concrete_ipv4(host)
    return value, {"scheme": "https", "host": host, "port": port}


def add_connection_arguments(parser):
    parser.add_argument("--url", required=True, help="Exact token-free HTTPS object/receiver URL")
    binding = parser.add_mutually_exclusive_group(required=True)
    binding.add_argument("--source", help="Bind curl to this local IPv4 address; verify local_ip")
    binding.add_argument("--interface", help="Force this network interface; curl fails if unavailable")
    parser.add_argument("--resolve", help="Optional IPv4 target pin; TLS hostname verification stays enabled")
    parser.add_argument("--group", default="A0", help="Comparison label, e.g. A0 or B0")
    parser.add_argument("--object-id", default="fixed-object",
                        help="Safe manual identity for the exact object/receiver; keep constant only for the same endpoint and query")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the payload/time budget only")


def validate_connection(args, parser):
    try:
        args.url, args.endpoint = validated_url(args.url)
        if args.source:
            args.source = concrete_ipv4(args.source)
        if args.resolve:
            args.resolve = concrete_ipv4(args.resolve)
        if args.interface and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", args.interface):
            raise ValueError("invalid interface name")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", args.group):
            raise ValueError("invalid group label")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", args.object_id):
            raise ValueError("invalid object identity label")
    except (ValueError, UnicodeError) as error:
        parser.error(str(error))


def connection_fields(args):
    return {"schema_version": SCHEMA_VERSION, "group": args.group,
            "object_id": args.object_id,
            "endpoint": args.endpoint, "source_ipv4": args.source,
            "interface": args.interface, "target_ipv4": args.resolve}


def checked_curl():
    executable = shutil.which("curl")
    if executable is None:
        raise RuntimeError("curl_not_installed")
    output = subprocess.check_output([executable, "-q", "--version"], text=True, timeout=5)
    match = re.match(r"curl (\d+)\.(\d+)\.(\d+)", output)
    if not match or tuple(map(int, match.groups())) < (8, 4, 0):
        raise RuntimeError("curl_8_4_or_newer_required")
    return executable


def curl_base(args, executable, timeout):
    binding = args.source if args.source else "if!" + args.interface
    command = [executable, "-q", "-4", "--noproxy", "*", "--globoff", "--http1.1",
               "--silent", "--show-error", "--interface", binding,
               "--connect-timeout", str(min(5, timeout)), "--max-time", str(timeout),
               "--output", "/dev/null", "--write-out", CURL_FORMAT]
    if args.resolve:
        command += ["--resolve", f"{args.endpoint['host']}:{args.endpoint['port']}:{args.resolve}"]
    return command


def parse_metrics(stdout):
    try:
        row = json.loads(stdout)
        required = ("received_bytes", "sent_bytes", "total_seconds", "first_byte_seconds",
                    "connect_seconds", "tls_seconds")
        for field in required:
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("invalid numeric field")
            if not math.isfinite(value) or value < 0:
                raise ValueError("invalid numeric field")
        for field in ("received_bytes", "sent_bytes"):
            if row[field] != int(row[field]):
                raise ValueError("fractional byte counter")
            row[field] = int(row[field])
        row["http_status"] = int(row["http_status"])
        for field in ("local_ipv4", "remote_ipv4"):
            if row[field]:
                row[field] = str(ipaddress.IPv4Address(row[field]))
        return row
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OverflowError):
        return None


def evaluate_result(metrics, process_exit, expected_bytes, mode, source=None, error=None):
    field = "received_bytes" if mode == "download" else "sent_bytes"
    observed = metrics.get(field) if metrics else None
    source_verified = metrics.get("local_ipv4") == source if metrics and source else None
    completed = (error is None and process_exit == 0 and metrics is not None
                 and metrics["http_status"] == 200 and observed == expected_bytes
                 and metrics["total_seconds"] > 0 and (source is None or source_verified))
    if completed:
        reason = "complete"
    elif error:
        reason = error
    elif metrics is None:
        reason = "metrics_missing_or_invalid"
    elif process_exit == 28:
        reason = "timeout_partial" if observed else "timeout_no_payload"
    elif process_exit != 0:
        reason = "curl_failure"
    elif source and not source_verified:
        reason = "source_mismatch"
    elif metrics["http_status"] != 200:
        reason = "unexpected_http_status"
    elif observed != expected_bytes:
        reason = "unexpected_object_size"
    else:
        reason = "invalid_completion_time"
    return {"completed": bool(completed), "outcome": reason,
            "process_exit": process_exit, "source_verified": source_verified,
            "expected_bytes": expected_bytes, "transferred_bytes": observed,
            "metrics": metrics,
            "task_goodput_mbps": (expected_bytes * 8 / metrics["total_seconds"] / 1e6
                                  if completed else None)}


def stop_processes(processes):
    """Terminate and reap only curl children created by this process."""
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def install_cancel_handlers():
    def cancel(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, cancel)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_connection_arguments(parser)
    parser.add_argument("--bytes", dest="byte_count", type=positive_int, required=True,
                        help="Expected complete object bytes, at most 64 MiB")
    parser.add_argument("--repeat", type=positive_int, default=5, help="1..10 sequential requests")
    parser.add_argument("--timeout", type=finite_number, default=90, help="1..90 seconds per request")
    args = parser.parse_args(argv)
    validate_connection(args, parser)
    if args.byte_count > MAX_DOWNLOAD_BYTES or args.repeat > 10 or not 1 <= args.timeout <= 90:
        parser.error("--bytes <= 67108864, --repeat <= 10, --timeout 1..90 are required")
    common = dict(connection_fields(args), mode="download", expected_bytes=args.byte_count,
                  timeout_seconds=args.timeout,
                  limit_bytes_per_second=None)
    plan = dict(common, type="plan", planned_attempts=args.repeat,
                maximum_object_payload_bytes=args.byte_count * args.repeat,
                timeout_seconds_per_attempt=args.timeout,
                maximum_curl_time_seconds=args.timeout * args.repeat,
                teardown_allowance_seconds=7 * args.repeat,
                comparison_warnings=["object_id_is_manual_keep_the_actual_object_constant"]
                + ([] if args.resolve else ["target_not_pinned_check_observed_remote_ips"]),
                dry_run=args.dry_run, network_requests=0 if args.dry_run else None)
    emit(plan)
    if args.dry_run:
        return 0
    install_cancel_handlers()
    try:
        executable = checked_curl()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        emit(dict(common, type="summary", attempted=0, complete=0, failed=0,
                  skipped=args.repeat, error=str(error) if isinstance(error, RuntimeError) else "curl_setup_failed"))
        return 2
    rows = []
    interrupted = False
    for index in range(args.repeat):
        child = None
        started_at, started = utc_now(), time.monotonic()
        metrics, returncode, error = None, None, None
        try:
            command = curl_base(args, executable, args.timeout)
            command += ["--max-filesize", str(args.byte_count), "--url", args.url]
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, _stderr = child.communicate(timeout=args.timeout + 3)
            metrics, returncode = parse_metrics(stdout), child.returncode
        except subprocess.TimeoutExpired:
            error = "outer_timeout"
        except KeyboardInterrupt:
            error, interrupted = "cancelled", True
        except OSError:
            error = "curl_launch_failed"
        finally:
            if child:
                stop_processes([child])
                if returncode is None:
                    returncode = child.returncode
        row = dict(common, type="attempt", attempt=index + 1, started_at=started_at,
                   ended_at=utc_now(), elapsed_seconds=time.monotonic() - started,
                   **evaluate_result(metrics, returncode, args.byte_count, "download", args.source, error))
        emit(row)
        rows.append(row)
        if interrupted or error == "curl_launch_failed":
            break
    complete = sum(row["completed"] for row in rows)
    emit(dict(common, type="summary", attempted=len(rows), complete=complete,
              failed=len(rows) - complete, skipped=args.repeat - len(rows), cancelled=interrupted))
    return 130 if interrupted else (0 if complete == args.repeat else 1)


if __name__ == "__main__":
    raise SystemExit(main())
