import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "summarize.py"
EXAMPLES = ROOT / "examples" / "synthetic-downloads.jsonl"


class SummaryLifecycleTests(unittest.TestCase):
    def run_summary(self, files):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, files)],
                                capture_output=True, text=True, check=False)
        return result.returncode, json.loads(result.stdout)

    def write_jsonl(self, directory, name, rows):
        path = Path(directory) / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_setup_error_and_unstarted_work_are_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_jsonl(directory, "setup.jsonl", [
                {"type": "plan", "mode": "download", "planned_attempts": 5, "dry_run": False},
                {"type": "summary", "mode": "download", "attempted": 0, "complete": 0,
                 "failed": 0, "skipped": 5, "error": "curl_setup_failed"},
            ])
            code, report = self.run_summary([path])
        self.assertEqual(code, 1)
        self.assertEqual(report["groups"], [])
        run = report["inputs"][0]["runs"][0]
        self.assertEqual((run["planned"], run["recorded_attempts"], run["recorded_failed"],
                          run["reported_skipped"]), (5, 0, 0, 5))
        self.assertEqual(run["error"], "curl_setup_failed")

    def test_multiple_files_preserve_separate_cancellation_and_rate_limit(self):
        attempt = json.loads(EXAMPLES.read_text(encoding="utf-8").splitlines()[0])
        with tempfile.TemporaryDirectory() as directory:
            first = self.write_jsonl(directory, "first.jsonl", [
                {"type": "plan", "mode": "download", "planned_attempts": 3}, attempt,
                {"type": "summary", "mode": "download", "attempted": 1, "complete": 1,
                 "failed": 0, "skipped": 2, "cancelled": True},
            ])
            second = self.write_jsonl(directory, "second.jsonl", [
                {"type": "plan", "mode": "download", "planned_attempts": 3},
                {"type": "summary", "mode": "download", "attempted": 0, "complete": 0,
                 "failed": 0, "skipped": 3, "stop_reason": "http_429"},
            ])
            code, report = self.run_summary([first, second])
        self.assertEqual(code, 1)
        first_run, second_run = (entry["runs"][0] for entry in report["inputs"])
        self.assertTrue(first_run["cancelled"])
        self.assertEqual(first_run["reported_skipped"], 2)
        self.assertEqual(second_run["stop_reason"], "http_429")
        self.assertEqual(second_run["reported_skipped"], 3)
        self.assertEqual(report["groups"][0]["attempted"], 1)

    def test_truncated_run_does_not_guess_unstarted_count(self):
        attempt = json.loads(EXAMPLES.read_text(encoding="utf-8").splitlines()[0])
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_jsonl(directory, "truncated.jsonl", [
                {"type": "plan", "mode": "download", "planned_attempts": 3}, attempt,
            ])
            code, report = self.run_summary([path])
        self.assertEqual(code, 1)
        run = report["inputs"][0]["runs"][0]
        self.assertIsNone(run["reported_skipped"])
        self.assertEqual(run["recorded_attempts"], 1)
        self.assertIn("missing_final_summary_unrecorded_work_unknown", run["warnings"])

    def test_concatenated_runs_are_accounted_separately(self):
        attempt = json.loads(EXAMPLES.read_text(encoding="utf-8").splitlines()[0])
        one_run = [{"type": "plan", "mode": "download", "planned_attempts": 1}, attempt,
                   {"type": "summary", "mode": "download", "attempted": 1, "complete": 1,
                    "failed": 0, "skipped": 0}]
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_jsonl(directory, "runs.jsonl", one_run + one_run)
            code, report = self.run_summary([path])
        self.assertEqual(code, 0)
        self.assertEqual(len(report["inputs"][0]["runs"]), 2)
        self.assertEqual(report["groups"][0]["attempted"], 2)

    def test_record_only_example_remains_supported_and_dry_run_is_not_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            dry = self.write_jsonl(directory, "dry.jsonl", [
                {"type": "plan", "mode": "upload", "planned_flows": 3, "dry_run": True},
            ])
            code, report = self.run_summary([EXAMPLES, dry])
        self.assertEqual(code, 0)
        self.assertIn("missing_plan_total_work_unknown", report["inputs"][0]["runs"][0]["warnings"])
        self.assertTrue(report["inputs"][1]["runs"][0]["dry_run"])

    def test_inconsistent_or_empty_input_is_not_silent_success(self):
        with tempfile.TemporaryDirectory() as directory:
            inconsistent = self.write_jsonl(directory, "inconsistent.jsonl", [
                {"type": "plan", "mode": "upload", "planned_flows": 3},
                {"type": "summary", "mode": "upload", "attempted": 2, "complete": 0,
                 "failed": 2, "skipped": 1},
            ])
            empty = self.write_jsonl(directory, "empty.jsonl", [])
            code, report = self.run_summary([inconsistent, empty])
        self.assertEqual(code, 1)
        self.assertIn("reported_attempted_differs_from_recorded_rows",
                      report["inputs"][0]["runs"][0]["warnings"])
        self.assertEqual(report["inputs"][1]["warnings"], ["empty_input"])


if __name__ == "__main__":
    unittest.main()
