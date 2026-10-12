#!/usr/bin/env python3
"""Upload synthetic zero bytes through a bounded set of HTTPS flows.

Requires Python 3.9+ and curl 8.4+. --dry-run validates the budget without traffic.
The receiver must accept a POST body and return HTTP 200. Output is JSONL.
Defaults: 3 flows, 5 Mbps per flow, 60 seconds (not a production bandwidth cap).
"""

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import time


_spec = importlib.util.spec_from_file_location("download_tool", Path(__file__).with_name("download-test.py"))
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)
MAX_TOTAL_PAYLOAD_BYTES = 2 * 1024 * 1024 * 1024


def upload_budget(duration, mbps, flows, byte_count=None):
    if not 10 <= duration <= 600 or not 0 < mbps <= 20 or not 1 <= flows <= 3:
        raise ValueError("--duration must be 10..600, --mbps >0..20, --flows 1..3")
    rate = int(mbps * 1e6 / 8)
    if rate < 1:
        raise ValueError("--mbps is too small for a positive byte-per-second cap")
    maximum_per_flow = int((duration - 3) * rate)
    count = maximum_per_flow if byte_count is None else byte_count
    if count < 1 or count > maximum_per_flow:
        raise ValueError("--bytes must fit the per-flow rate and duration minus 3 seconds")
    if count * flows > MAX_TOTAL_PAYLOAD_BYTES:
        raise ValueError("total synthetic payload must not exceed 2 GiB; reduce duration/rate/flows")
    return count, rate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    core.add_connection_arguments(parser)
    parser.add_argument("--duration", type=core.finite_number, default=60, help="10..600 seconds per group")
    parser.add_argument("--mbps", type=core.finite_number, default=5, help="Positive per-flow Mbps cap, at most 20")
    parser.add_argument("--flows", type=core.positive_int, default=3, help="1..3 parallel flows")
    parser.add_argument("--bytes", dest="byte_count", type=core.positive_int,
                        help="Optional bytes per flow; default uses the rate for duration minus 3 seconds")
    args = parser.parse_args(argv)
    core.validate_connection(args, parser)
    try:
        count, rate = upload_budget(args.duration, args.mbps, args.flows, args.byte_count)
    except ValueError as error:
        parser.error(str(error))
    common = dict(core.connection_fields(args), mode="upload", expected_bytes=count,
                  timeout_seconds=args.duration,
                  limit_bytes_per_second=rate)
    plan = dict(common, type="plan", planned_flows=args.flows,
                maximum_object_payload_bytes=count * args.flows,
                aggregate_target_mbps=rate * args.flows * 8 / 1e6,
                timeout_seconds=args.duration, teardown_allowance_seconds=3 + 4 * args.flows,
                comparison_warnings=["object_id_is_manual_keep_the_actual_receiver_constant"]
                + ([] if args.resolve else ["target_not_pinned_check_observed_remote_ips"]),
                dry_run=args.dry_run, network_requests=0 if args.dry_run else None)
    core.emit(plan)
    if args.dry_run:
        return 0
    core.install_cancel_handlers()
    children, payload, rows = [], None, []
    interrupted, group_error = False, None
    started_at, started = core.utc_now(), time.monotonic()
    try:
        executable = core.checked_curl()
        with tempfile.NamedTemporaryFile(prefix="stream-diagnostic-", suffix=".bin", delete=False) as handle:
            payload = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            handle.truncate(count)
        # Each request has the same complete object and its own explicit rate cap.
        for index in range(args.flows):
            command = core.curl_base(args, executable, args.duration)
            command += ["--limit-rate", str(rate), "--max-filesize", "65536",
                        "--header", "Content-Type: application/octet-stream",
                        "--header", "Expect:", "--request", "POST", "--upload-file", str(payload), "--url", args.url]
            child_started_at, child_started = core.utc_now(), time.monotonic()
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            children.append((child, child_started_at, child_started))
        deadline = started + args.duration + 3
        for index, (child, child_started_at, child_started) in enumerate(children):
            metrics, returncode, error = None, None, None
            try:
                stdout, _stderr = child.communicate(timeout=max(0.01, deadline - time.monotonic()))
                metrics, returncode = core.parse_metrics(stdout), child.returncode
            except subprocess.TimeoutExpired:
                error = "outer_timeout"
                core.stop_processes([item[0] for item in children])
                returncode = child.returncode
            row = dict(common, type="flow", flow=index + 1, started_at=child_started_at,
                       ended_at=core.utc_now(), elapsed_seconds=time.monotonic() - child_started,
                       **core.evaluate_result(metrics, returncode, count, "upload", args.source, error))
            core.emit(row)
            rows.append(row)
    except KeyboardInterrupt:
        interrupted, group_error = True, "cancelled"
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        group_error = str(error) if isinstance(error, RuntimeError) else "test_setup_or_collection_failed"
    finally:
        core.stop_processes([item[0] for item in children])
        # Cancellation and setup failures are retained for every launched flow.
        for index in range(len(rows), len(children)):
            child, child_started_at, child_started = children[index]
            row = dict(common, type="flow", flow=index + 1, started_at=child_started_at,
                       ended_at=core.utc_now(), elapsed_seconds=time.monotonic() - child_started,
                       **core.evaluate_result(None, child.returncode, count, "upload", args.source,
                                              group_error or "collection_failed"))
            core.emit(row)
            rows.append(row)
        if payload:
            payload.unlink(missing_ok=True)
    elapsed = time.monotonic() - started
    completed = sum(row["completed"] for row in rows)
    known_transferred = sum(row["transferred_bytes"] for row in rows if row["transferred_bytes"] is not None)
    accounting_complete = all(row["transferred_bytes"] is not None for row in rows)
    all_completed = completed == args.flows and group_error is None
    core.emit(dict(common, type="summary", started_at=started_at, ended_at=core.utc_now(),
                   elapsed_seconds=elapsed, attempted=len(rows), complete=completed,
                   failed=len(rows) - completed, skipped=args.flows - len(rows),
                   transferred_bytes=known_transferred if accounting_complete else None,
                   known_transferred_bytes=known_transferred,
                   transferred_bytes_complete_accounting=accounting_complete,
                   error=group_error, cancelled=interrupted,
                   aggregate_task_goodput_mbps=(count * args.flows * 8 / elapsed / 1e6
                                                if all_completed and elapsed > 0 else None)))
    return 130 if interrupted else (0 if all_completed else (1 if rows else 2))


if __name__ == "__main__":
    raise SystemExit(main())
