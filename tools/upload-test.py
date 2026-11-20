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
import threading
import time


_spec = importlib.util.spec_from_file_location("download_tool", Path(__file__).with_name("download-test.py"))
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)
MAX_TOTAL_PAYLOAD_BYTES = 2 * 1024 * 1024 * 1024


def collect_flow(flow, deadline):
    """Drain one child concurrently and timestamp when its output is collected."""
    try:
        stdout, _stderr = flow["child"].communicate(timeout=max(0.01, deadline - time.monotonic()))
        flow["metrics"] = core.parse_metrics(stdout)
        flow["returncode"] = flow["child"].returncode
    except subprocess.TimeoutExpired:
        flow["error"] = "outer_timeout"
    except KeyboardInterrupt:
        # Real signals are delivered to the main thread; this also supports a
        # child collector reporting interruption without losing cleanup.
        flow["error"] = "cancelled"
    except (OSError, subprocess.SubprocessError):
        flow["error"] = "test_setup_or_collection_failed"
    finally:
        flow["ended_at"] = core.utc_now()
        flow["elapsed_seconds"] = time.monotonic() - flow["started"]
        flow["done"].set()


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
        deadline = started + args.duration + 3
        # Each request has the same complete object and its own explicit rate cap.
        for index in range(args.flows):
            command = core.curl_base(args, executable, args.duration)
            command += ["--limit-rate", str(rate), "--max-filesize", "65536",
                        "--header", "Content-Type: application/octet-stream",
                        "--header", "Expect:", "--request", "POST", "--upload-file", str(payload), "--url", args.url]
            child_started_at, child_started = core.utc_now(), time.monotonic()
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            flow = {"child": child, "started_at": child_started_at, "started": child_started,
                    "done": threading.Event(), "metrics": None, "returncode": None,
                    "error": None, "thread": None}
            children.append(flow)
            thread = threading.Thread(target=collect_flow, args=(flow, deadline), daemon=True)
            thread.start()
            flow["thread"] = thread
        for index, flow in enumerate(children):
            flow["done"].wait()
            if flow["error"] == "cancelled":
                raise KeyboardInterrupt
            if flow["error"] == "outer_timeout":
                core.stop_processes([item["child"] for item in children])
                flow["returncode"] = flow["child"].returncode
            row = dict(common, type="flow", flow=index + 1, started_at=flow["started_at"],
                       ended_at=flow["ended_at"], elapsed_seconds=flow["elapsed_seconds"],
                       **core.evaluate_result(flow["metrics"], flow["returncode"], count,
                                              "upload", args.source, flow["error"]))
            core.emit(row)
            rows.append(row)
    except KeyboardInterrupt:
        interrupted, group_error = True, "cancelled"
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        group_error = str(error) if isinstance(error, RuntimeError) else "test_setup_or_collection_failed"
    finally:
        # Keep results collected before a later launch failure or cancellation.
        # Children still running at this point are marked with the group error.
        collected_before_cleanup = [item["done"].is_set() for item in children]
        core.stop_processes([item["child"] for item in children])
        for flow in children:
            if flow["thread"] is not None:
                flow["thread"].join()
        # Cancellation and setup failures are retained for every launched flow.
        for index in range(len(rows), len(children)):
            flow = children[index]
            collected = collected_before_cleanup[index] and flow["error"] != "cancelled"
            metrics = flow["metrics"] if collected else None
            returncode = flow["returncode"] if collected else flow["child"].returncode
            error = flow["error"] if collected else (group_error or "collection_failed")
            row = dict(common, type="flow", flow=index + 1, started_at=flow["started_at"],
                       ended_at=flow.get("ended_at", core.utc_now()),
                       elapsed_seconds=flow.get("elapsed_seconds", time.monotonic() - flow["started"]),
                       **core.evaluate_result(metrics, returncode, count, "upload", args.source, error))
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
