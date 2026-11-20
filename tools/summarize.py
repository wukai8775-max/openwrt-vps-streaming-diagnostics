#!/usr/bin/env python3
"""Summarize JSONL completion tests offline, retaining every recorded failure.

Groups also include object size, endpoint, binding and upload rate so unlike
tests are not averaged together. No p95/p99 is inferred from a small sample.
"""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import median
import sys


def summarize_records(records):
    groups = defaultdict(list)
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("every JSONL record must be an object")
        if row.get("type") not in ("attempt", "flow"):
            continue
        if row.get("schema_version") != 1 or row.get("mode") not in ("download", "upload"):
            raise ValueError("unsupported test schema or mode")
        if not isinstance(row.get("completed"), bool):
            raise ValueError("result is missing a boolean completed field")
        expected = row.get("expected_bytes")
        if isinstance(expected, bool) or not isinstance(expected, int) or expected <= 0:
            raise ValueError("expected_bytes must be a positive integer")
        if not isinstance(row.get("endpoint"), dict) or not row["endpoint"].get("host"):
            raise ValueError("endpoint identity is missing")
        if row["completed"]:
            metrics = row.get("metrics")
            byte_field = "received_bytes" if row["mode"] == "download" else "sent_bytes"
            seconds = metrics.get("total_seconds") if isinstance(metrics, dict) else None
            if (row.get("process_exit") != 0 or not isinstance(metrics, dict)
                    or metrics.get("http_status") != 200 or metrics.get(byte_field) != expected
                    or not isinstance(seconds, (int, float)) or isinstance(seconds, bool)
                    or not math.isfinite(seconds) or seconds <= 0
                    or (row.get("source_ipv4") and metrics.get("local_ipv4") != row["source_ipv4"])):
                raise ValueError("completed record contradicts its observed completion metrics")
        if not isinstance(row.get("timeout_seconds"), (int, float)) or not math.isfinite(row["timeout_seconds"]):
            raise ValueError("timeout_seconds is missing or invalid")
        if not isinstance(row.get("object_id"), str) or not row["object_id"]:
            raise ValueError("manual object identity is missing")
        key = (row["mode"], row.get("group", "A0"), expected,
               json.dumps(row["endpoint"], sort_keys=True), row.get("source_ipv4"),
               row.get("interface"), row.get("target_ipv4"), row.get("limit_bytes_per_second"),
               row["object_id"], row["timeout_seconds"])
        groups[key].append(row)
    results = []
    for key, rows in sorted(groups.items(), key=lambda item: str(item[0])):
        times = [row["metrics"]["total_seconds"] for row in rows if row["completed"]]
        goodputs = [key[2] * 8 / seconds / 1e6 for seconds in times]
        result = {"mode": key[0], "group": key[1], "expected_bytes": key[2],
                  "endpoint": json.loads(key[3]), "source_ipv4": key[4], "interface": key[5],
                  "target_ipv4": key[6], "limit_bytes_per_second": key[7],
                  "object_id": key[8], "timeout_seconds": key[9],
                  "attempted": len(rows), "complete": len(times), "failed": len(rows) - len(times),
                  "completion_rate": len(times) / len(rows),
                  "completed_time_seconds_median": median(times) if times else None,
                  "completed_time_seconds_min": min(times) if times else None,
                  "completed_time_seconds_max": max(times) if times else None,
                  "completed_task_goodput_mbps_median": median(goodputs) if goodputs else None,
                  "failure_outcomes": {}}
        peers = sorted({row["metrics"]["remote_ipv4"] for row in rows
                        if isinstance(row.get("metrics"), dict) and row["metrics"].get("remote_ipv4")})
        result["observed_remote_ipv4s"] = peers
        result["comparison_warnings"] = ["Object identity is a manual label; URLs and query parameters are intentionally not logged."]
        if len(peers) > 1:
            result["comparison_warnings"].append("Observed remote target varied; rebuild a fixed-target baseline before interpreting A/B.")
        elif not key[6]:
            result["comparison_warnings"].append("Target was not pinned; check target consistency across comparison groups.")
        for row in rows:
            if not row["completed"]:
                outcome = row.get("outcome", "unspecified_failure")
                result["failure_outcomes"][outcome] = result["failure_outcomes"].get(outcome, 0) + 1
        results.append(result)
    return results


def summarize_runs(records):
    """Preserve lifecycle evidence without inferring missing results as failures.

    A file may contain multiple concatenated runs or just individual records
    (as with the synthetic example). A missing summary is not treated as proof
    that any unrecorded requests did or did not run.
    """
    runs, current = [], []

    def finish():
        if not current:
            return
        plan = next((row for row in current if row.get("type") == "plan"), None)
        summary = next((row for row in current if row.get("type") == "summary"), None)
        attempts = [row for row in current if row.get("type") in ("attempt", "flow")]
        planned = None
        if plan:
            planned = plan.get("planned_attempts", plan.get("planned_flows"))
        warnings = []
        for name, value in (("planned", planned),
                            ("reported_attempted", summary.get("attempted") if summary else None),
                            ("reported_complete", summary.get("complete") if summary else None),
                            ("reported_failed", summary.get("failed") if summary else None),
                            ("reported_skipped", summary.get("skipped") if summary else None)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer")

        recorded_complete = sum(row["completed"] for row in attempts)
        recorded_failed = len(attempts) - recorded_complete
        if summary:
            for field, observed in (("attempted", len(attempts)), ("complete", recorded_complete),
                                    ("failed", recorded_failed)):
                if field in summary and summary[field] != observed:
                    warnings.append(f"reported_{field}_differs_from_recorded_rows")
            if (planned is not None and summary.get("attempted") is not None
                    and summary.get("skipped") is not None
                    and summary["attempted"] + summary["skipped"] != planned):
                warnings.append("reported_counts_do_not_match_plan")
        if plan and not summary and not plan.get("dry_run"):
            warnings.append("missing_final_summary_unrecorded_work_unknown")
        if not plan:
            warnings.append("missing_plan_total_work_unknown")

        runs.append({
            "mode": (plan or summary or (attempts[0] if attempts else {})).get("mode"),
            "planned": planned,
            "recorded_attempts": len(attempts),
            "recorded_complete": recorded_complete,
            "recorded_failed": recorded_failed,
            "reported_attempted": summary.get("attempted") if summary else None,
            "reported_complete": summary.get("complete") if summary else None,
            "reported_failed": summary.get("failed") if summary else None,
            "reported_skipped": summary.get("skipped") if summary else None,
            "cancelled": summary.get("cancelled") if summary else None,
            "error": summary.get("error") if summary else None,
            "stop_reason": summary.get("stop_reason") if summary else None,
            "dry_run": plan.get("dry_run") if plan else None,
            "final_summary_present": summary is not None,
            "warnings": warnings,
        })

    for row in records:
        if not isinstance(row, dict):
            raise ValueError("every JSONL record must be an object")
        if row.get("type") == "plan" and current:
            finish()
            current = []
        current.append(row)
        if row.get("type") == "summary":
            finish()
            current = []
    finish()
    return runs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+", help="JSONL result files; do not include the same file twice")
    args = parser.parse_args(argv)
    if len({path.resolve() for path in args.files}) != len(args.files):
        parser.error("duplicate input file would inflate the denominator")
    records, inputs = [], []
    try:
        for input_index, path in enumerate(args.files, 1):
            if path.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("each input must be at most 20 MiB")
            file_records = []
            with path.open(encoding="utf-8") as handle:
                for index, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    try:
                        file_records.append(json.loads(line))
                    except json.JSONDecodeError as error:
                        raise ValueError(f"invalid JSON at {path.name}:{index}") from error
            # Validate attempt/flow records before lifecycle accounting, including
            # row completion types. Files are independent run boundaries.
            summarize_records(file_records)
            inputs.append({"input_index": input_index, "input_file": path.name,
                           "runs": summarize_runs(file_records),
                           "warnings": [] if file_records else ["empty_input"]})
            records.extend(file_records)
        groups = summarize_records(records)
        print(json.dumps({"schema_version": 1, "type": "offline_summary", "groups": groups,
                          "inputs": inputs,
                          "recorded_attempts": sum(group["attempted"] for group in groups),
                          "note": "Failures remain in the denominator; unstarted work is not counted as failure. Missing final summaries leave unrecorded work unknown. Upload rows are individual flows, not independent group-level capacity estimates."},
                         ensure_ascii=False, indent=2, allow_nan=False))
        incomplete = any(item["warnings"] for item in inputs) or any(
                         run["error"] or run["cancelled"] or run["stop_reason"]
                         or "missing_final_summary_unrecorded_work_unknown" in run["warnings"]
                         or any(w.startswith("reported_") for w in run["warnings"])
                         for item in inputs for run in item["runs"])
        return 1 if incomplete else 0
    except (OSError, ValueError) as error:
        print(f"Summary failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
