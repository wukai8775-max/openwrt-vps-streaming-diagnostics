"""Offline checks for completion, denominators, bounds and CLI validation."""

import importlib.util
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_tool(filename):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


download = load_tool("download-test.py")
upload = load_tool("upload-test.py")
summarize = load_tool("summarize.py")


def metrics(byte_count=10000000, seconds=10, status=200, local="192.0.2.2"):
    return {"received_bytes": byte_count, "sent_bytes": 0, "total_seconds": seconds,
            "http_status": status, "local_ipv4": local, "remote_ipv4": "198.51.100.2",
            "first_byte_seconds": 0.2, "connect_seconds": 0.1, "tls_seconds": 0.15}


def result_row(observed, exit_code=0, group="A0"):
    return dict(schema_version=1, type="attempt", mode="download", group=group,
                source_ipv4="192.0.2.2", interface=None, target_ipv4=None,
                endpoint={"scheme": "https", "host": "example.com", "port": 443},
                object_id="example-10m", timeout_seconds=90,
                limit_bytes_per_second=None,
                **download.evaluate_result(observed, exit_code, 10000000, "download", "192.0.2.2"))


class CompletionTests(unittest.TestCase):
    def test_complete_needs_all_evidence(self):
        self.assertTrue(download.evaluate_result(metrics(), 0, 10000000, "download", "192.0.2.2")["completed"])
        for data, code in ((metrics(status=503), 0), (metrics(byte_count=9999999), 0),
                           (metrics(local="192.0.2.3"), 0), (metrics(), 28), (None, 0),
                           (metrics(seconds=0), 0)):
            self.assertFalse(download.evaluate_result(data, code, 10000000, "download", "192.0.2.2")["completed"])

    def test_partial_timeout_has_no_task_goodput(self):
        row = download.evaluate_result(metrics(byte_count=2500000, seconds=90), 28,
                                       10000000, "download", "192.0.2.2")
        self.assertEqual(row["outcome"], "timeout_partial")
        self.assertIsNone(row["task_goodput_mbps"])

    def test_upload_uses_sent_bytes(self):
        data = metrics(byte_count=0)
        data["sent_bytes"] = 10000000
        self.assertTrue(download.evaluate_result(data, 0, 10000000, "upload")["completed"])

    def test_parser_rejects_nan_boolean_missing_and_negative(self):
        self.assertIsNotNone(download.parse_metrics(json.dumps(metrics())))
        for data in (dict(metrics(), received_bytes=float("nan")), dict(metrics(), received_bytes=True),
                     dict(metrics(), sent_bytes=-1), dict(metrics(), total_seconds="1"), {}):
            self.assertIsNone(download.parse_metrics(json.dumps(data)))

    def test_summary_retains_failed_denominator(self):
        rows = [result_row(metrics(seconds=10)), result_row(metrics(seconds=20)),
                result_row(metrics(byte_count=100, seconds=90), 28)]
        summary = summarize.summarize_records(rows)[0]
        self.assertEqual((summary["attempted"], summary["complete"], summary["failed"]), (3, 2, 1))
        self.assertAlmostEqual(summary["completion_rate"], 2 / 3)
        self.assertEqual(summary["completed_time_seconds_median"], 15)
        self.assertEqual(summary["completed_task_goodput_mbps_median"], 6)

    def test_summary_does_not_merge_object_sizes_or_bindings(self):
        other = result_row(metrics())
        other["expected_bytes"] = 5000000
        other["metrics"]["received_bytes"] = 5000000
        self.assertEqual(len(summarize.summarize_records([result_row(metrics()), other])), 2)

    def test_summary_separates_timeouts_and_manual_object_identity(self):
        timeout_row = dict(result_row(metrics()), timeout_seconds=45)
        object_row = dict(result_row(metrics()), object_id="other-10m-object")
        self.assertEqual(len(summarize.summarize_records([result_row(metrics()), timeout_row, object_row])), 3)

    def test_peer_variation_is_reported_without_losing_failed_denominator(self):
        second = result_row(metrics())
        second["metrics"]["remote_ipv4"] = "198.51.100.3"
        summary = summarize.summarize_records([result_row(metrics()), second, result_row(None, 7)])[0]
        self.assertEqual(summary["attempted"], 3)
        self.assertEqual(len(summary["observed_remote_ipv4s"]), 2)
        self.assertTrue(any("varied" in warning for warning in summary["comparison_warnings"]))

    def test_summary_rejects_false_completion_claim(self):
        row = result_row(metrics(byte_count=100), 28)
        row["completed"] = True
        with self.assertRaises(ValueError):
            summarize.summarize_records([row])

    def test_all_failures_have_no_success_stats(self):
        summary = summarize.summarize_records([result_row(None, 7)])[0]
        self.assertEqual(summary["failed"], 1)
        self.assertIsNone(summary["completed_time_seconds_median"])


class BoundsTests(unittest.TestCase):
    def test_default_upload_budget(self):
        count, rate = upload.upload_budget(600, 5, 3)
        self.assertEqual(count * 3, 1119375000)
        self.assertEqual(rate, 625000)

    def test_reject_oversized_or_unbounded_upload(self):
        for args in ((601, 5, 3), (600, 0, 3), (600, 20, 3), (60, 5, 4), (60, 5, 3, 100000000)):
            with self.assertRaises(ValueError):
                upload.upload_budget(*args)

    def test_url_credentials_controls_and_http_rejected(self):
        credential_url = "https://" + "u:p" + "@example.com/test"
        for url in ("http://example.com/test", credential_url, "https://example.com/\n--insecure",
                    "https://example.com:bad/test", "https://example.com/test#fragment", "file:///tmp/test"):
            with self.assertRaises(ValueError):
                download.validated_url(url)

    def test_source_and_target_cannot_silently_use_unspecified_or_multicast(self):
        for value in ("0.0.0.0", "224.0.0.1", "255.255.255.255"):
            with self.assertRaises(ValueError):
                download.concrete_ipv4(value)
            with self.assertRaises(ValueError):
                download.validated_url("https://" + value + "/test")
        self.assertEqual(download.concrete_ipv4("127.0.0.1"), "127.0.0.1")

    def test_endpoint_log_excludes_query_and_path(self):
        _, endpoint = download.validated_url("https://example.com/path?bytes=100&token=private")
        self.assertNotIn("private", json.dumps(endpoint))
        self.assertNotIn("path", json.dumps(endpoint))

    def test_dry_run_is_offline_and_limits_payload(self):
        command = [sys.executable, str(ROOT / "tools" / "download-test.py"),
                   "--url", "https://example.invalid/fixed", "--source", "192.0.2.2",
                   "--bytes", "10000000", "--repeat", "5", "--dry-run"]
        process = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(process.returncode, 0, process.stderr)
        plan = json.loads(process.stdout)
        self.assertEqual(plan["network_requests"], 0)
        self.assertEqual(plan["maximum_object_payload_bytes"], 50000000)

    def test_curl_disables_url_globbing_and_forces_interface(self):
        class Args:
            source = None
            interface = "eth0"
            resolve = "198.51.100.2"
            endpoint = {"host": "example.com", "port": 443}

        command = download.curl_base(Args(), "curl", 30)
        self.assertIn("--globoff", command)
        self.assertEqual(command[command.index("--interface") + 1], "if!eth0")
        self.assertEqual(command[command.index("--noproxy") + 1], "*")
        self.assertNotIn("--insecure", command)
        self.assertNotIn("--location", command)

    def test_invalid_cli_options_fail_without_traffic(self):
        base = [sys.executable, str(ROOT / "tools" / "download-test.py"),
                "--url", "https://example.invalid/fixed", "--source", "192.0.2.2", "--bytes", "100", "--dry-run"]
        for extras in (("--timeout", "nan"), ("--repeat", "0"), ("--bytes", "67108865"),
                       ("--source", "$(touch /tmp/unwanted)")):
            process = subprocess.run(base + list(extras), capture_output=True, text=True, timeout=5)
            self.assertEqual(process.returncode, 2)


class FakeCurl:
    def __init__(self, stdout="", returncode=0, interrupted=False):
        self.stdout, self.final_returncode = stdout, returncode
        self.returncode, self.interrupted = None, interrupted

    def communicate(self, timeout=None):
        if self.interrupted:
            raise KeyboardInterrupt
        self.returncode = self.final_returncode
        return self.stdout, "discarded potentially sensitive stderr"

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class OfflineLifecycleTests(unittest.TestCase):
    def test_download_end_to_end_keeps_timeout_and_source_mismatch(self):
        children = [FakeCurl(json.dumps(metrics(byte_count=500, seconds=90)), 28),
                    FakeCurl(json.dumps(metrics(local="192.0.2.3")), 0)]
        output = io.StringIO()
        with patch.object(download, "checked_curl", return_value="curl"), \
                patch.object(download.subprocess, "Popen", side_effect=children), \
                patch.object(download, "install_cancel_handlers"), redirect_stdout(output):
            code = download.main(["--url", "https://example.invalid/fixed", "--source", "192.0.2.2",
                                  "--bytes", "10000000", "--repeat", "2"])
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(code, 1)
        self.assertEqual(rows[-1]["failed"], 2)
        self.assertEqual(summarize.summarize_records(rows)[0]["attempted"], 2)
        self.assertEqual({row["outcome"] for row in rows if row["type"] == "attempt"},
                         {"timeout_partial", "source_mismatch"})

    def test_cancelled_upload_reaps_children_and_removes_private_payload(self):
        payloads, children = [], []

        def launch(command, **_kwargs):
            payload = Path(command[command.index("--upload-file") + 1])
            payloads.append(payload)
            self.assertEqual(payload.stat().st_mode & 0o777, 0o600)
            self.assertEqual(payload.stat().st_size, 875)
            self.assertIn("--request", command)
            self.assertNotIn("--data-binary", command)
            child = FakeCurl(interrupted=True)
            children.append(child)
            return child

        output = io.StringIO()
        with patch.object(upload.core, "checked_curl", return_value="curl"), \
                patch.object(upload.subprocess, "Popen", side_effect=launch), \
                patch.object(upload.core, "install_cancel_handlers"), redirect_stdout(output):
            code = upload.main(["--url", "https://example.invalid/receiver", "--source", "192.0.2.2",
                                "--flows", "3", "--duration", "10", "--mbps", "0.001"])
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(code, 130)
        self.assertEqual(rows[-1]["attempted"], 3)
        self.assertEqual(rows[-1]["failed"], 3)
        self.assertIsNone(rows[-1]["transferred_bytes"])
        self.assertFalse(rows[-1]["transferred_bytes_complete_accounting"])
        self.assertTrue(all(child.returncode == -15 for child in children))
        self.assertTrue(all(not payload.exists() for payload in payloads))
        self.assertTrue(all(row["outcome"] == "cancelled" for row in rows if row["type"] == "flow"))

    def test_upload_start_failure_keeps_launched_flow_and_removes_payload(self):
        payloads, children = [], []

        def launch(command, **_kwargs):
            payloads.append(Path(command[command.index("--upload-file") + 1]))
            if children:
                raise OSError("mock launch failure")
            child = FakeCurl()
            children.append(child)
            return child

        output = io.StringIO()
        with patch.object(upload.core, "checked_curl", return_value="curl"), \
                patch.object(upload.subprocess, "Popen", side_effect=launch), \
                patch.object(upload.core, "install_cancel_handlers"), redirect_stdout(output):
            code = upload.main(["--url", "https://example.invalid/receiver", "--source", "192.0.2.2",
                                "--flows", "3", "--duration", "10", "--mbps", "0.001"])
        summary = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(code, 1)
        self.assertEqual((summary["attempted"], summary["failed"], summary["skipped"]), (1, 1, 2))
        self.assertTrue(all(not payload.exists() for payload in payloads))
        self.assertEqual(children[0].returncode, -15)

    def test_duplicate_summary_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text(json.dumps(result_row(metrics())) + "\n", encoding="utf-8")
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                summarize.main([str(path), str(path)])
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
