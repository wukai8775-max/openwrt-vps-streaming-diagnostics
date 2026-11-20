"""Offline regression checks for concurrent upload timing."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("upload_timing_tool", ROOT / "tools/upload-test.py")
upload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload)


class UploadTimingTests(unittest.TestCase):
    def test_later_flow_finishing_first_keeps_its_own_elapsed_time(self):
        # Real local subprocesses emulate curl; no network request is made.
        # The first sleeps longer, so sequential collection used to assign its
        # wait time to the second flow as well.
        real_popen = subprocess.Popen
        delays = iter((0.8, 0.05))
        metrics = {"received_bytes": 0, "sent_bytes": 100, "total_seconds": 0.05,
                   "first_byte_seconds": 0.01, "connect_seconds": 0.01,
                   "tls_seconds": 0.01, "http_status": 200,
                   "local_ipv4": "192.0.2.2", "remote_ipv4": "192.0.2.3"}
        code = "import sys,time; time.sleep(float(sys.argv[1])); print(sys.argv[2])"

        def launch(_command, **kwargs):
            return real_popen([sys.executable, "-c", code, str(next(delays)), json.dumps(metrics)], **kwargs)

        output = io.StringIO()
        with patch.object(upload.core, "checked_curl", return_value="curl"), \
                patch.object(upload.subprocess, "Popen", side_effect=launch), \
                patch.object(upload.core, "install_cancel_handlers"), redirect_stdout(output):
            result = upload.main(["--url", "https://example.invalid/receiver", "--source", "192.0.2.2",
                                  "--flows", "2", "--duration", "10", "--mbps", "0.001", "--bytes", "100"])

        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        flows = [row for row in rows if row["type"] == "flow"]
        self.assertEqual(result, 0)
        self.assertEqual(len(flows), 2)
        self.assertTrue(all(row["completed"] for row in flows))
        self.assertLess(flows[1]["elapsed_seconds"] + 0.3, flows[0]["elapsed_seconds"])
        self.assertLess(datetime.fromisoformat(flows[1]["ended_at"]),
                        datetime.fromisoformat(flows[0]["ended_at"]))
        self.assertEqual(rows[-1]["complete"], 2)

    def test_completed_flow_is_retained_if_next_launch_fails(self):
        real_popen = subprocess.Popen
        collected = threading.Event()
        real_collect = upload.collect_flow
        metrics = {"received_bytes": 0, "sent_bytes": 100, "total_seconds": 0.05,
                   "first_byte_seconds": 0.01, "connect_seconds": 0.01,
                   "tls_seconds": 0.01, "http_status": 200,
                   "local_ipv4": "192.0.2.2", "remote_ipv4": "192.0.2.3"}
        launches = []

        def launch(_command, **kwargs):
            if launches:
                if not collected.wait(timeout=5):
                    raise AssertionError("first child was not collected")
                raise OSError("simulated launch failure")
            child = real_popen([sys.executable, "-c", "import sys; print(sys.argv[1])",
                                json.dumps(metrics)], **kwargs)
            launches.append(child)
            return child

        def collect(flow, deadline):
            real_collect(flow, deadline)
            collected.set()

        output = io.StringIO()
        with patch.object(upload.core, "checked_curl", return_value="curl"), \
                patch.object(upload.subprocess, "Popen", side_effect=launch), \
                patch.object(upload, "collect_flow", side_effect=collect), \
                patch.object(upload.core, "install_cancel_handlers"), redirect_stdout(output):
            result = upload.main(["--url", "https://example.invalid/receiver", "--source", "192.0.2.2",
                                  "--flows", "2", "--duration", "10", "--mbps", "0.001", "--bytes", "100"])

        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        flow = next(row for row in rows if row["type"] == "flow")
        summary = rows[-1]
        self.assertEqual(result, 1)
        self.assertTrue(flow["completed"])
        self.assertEqual(flow["outcome"], "complete")
        self.assertEqual((summary["attempted"], summary["complete"], summary["failed"], summary["skipped"]),
                         (1, 1, 0, 1))
        self.assertEqual(summary["error"], "test_setup_or_collection_failed")
        self.assertIsNone(summary["aggregate_task_goodput_mbps"])


if __name__ == "__main__":
    unittest.main()
