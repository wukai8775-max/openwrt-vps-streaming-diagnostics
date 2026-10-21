"""Offline product checks for the bounded, privacy-preserving beginner entry."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("quick_check", ROOT / "tools" / "quick-check.py")
quick = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quick)


def metrics(byte_count=0, status=204, seconds=0.4):
    return {"http_status": status, "received_bytes": byte_count, "sent_bytes": 0,
            "total_seconds": seconds, "first_byte_seconds": 0.2, "connect_seconds": 0.1,
            "tls_seconds": 0.15, "local_ipv4": "192.0.2.2", "remote_ipv4": "198.51.100.2",
            "untrusted_extra_field": "private-must-not-leak"}


class FakeCurl:
    def __init__(self, data=None, code=0, interrupted=False, outer_timeout=False):
        self.data = data if data is not None else metrics()
        self.code, self.returncode = code, None
        self.interrupted, self.outer_timeout = interrupted, outer_timeout
        self.terminated = False

    def communicate(self, timeout=None):
        if self.interrupted:
            raise KeyboardInterrupt
        if self.outer_timeout:
            raise subprocess.TimeoutExpired("redacted-child", timeout)
        self.returncode = self.code
        return json.dumps(self.data), "private-must-not-leak URL credentials and tokens"

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated, self.returncode = True, -15

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class QuickCheckTests(unittest.TestCase):
    def invoke(self, argv, children=None):
        output = io.StringIO()
        with patch.object(quick.core, "checked_curl", return_value="curl") as check, \
                patch.object(quick.subprocess, "Popen", side_effect=children or []) as popen, \
                patch.object(quick.core, "install_cancel_handlers"), redirect_stdout(output):
            code = quick.main(argv + ["--json"])
        return code, json.loads(output.getvalue()), output.getvalue(), check, popen

    def test_default_is_offline_and_explains_partial_failure(self):
        code, data, text, check, popen = self.invoke([])
        self.assertEqual(code, 0)
        check.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(data["mode"], "demo")
        self.assertEqual(data["network_requests"], 0)
        self.assertEqual(data["started_child_attempts"], 0)
        self.assertTrue(data["synthetic"])
        self.assertEqual(data["budget"]["download_requests"], data["download"]["planned"])
        self.assertEqual(data["budget"]["maximum_download_object_bytes"], data["download"]["expected_bytes"])
        self.assertEqual(data["budget"]["maximum_response_body_bytes"], 3 * 65536 + 2 * 1048576)
        self.assertEqual(data["overall_status"], "example_only")
        self.assertEqual((data["download"]["complete"], data["download"]["failed"]), (1, 1))
        self.assertIsNone(data["download"]["attempts"][1]["task_goodput_mbps"])
        self.assertIn("合成", text)

    def test_live_probe_success_is_not_node_verification(self):
        code, data, text, _, popen = self.invoke(["--execute"], [FakeCurl() for _ in range(3)])
        self.assertEqual(code, 0)
        self.assertEqual(data["probe"]["complete"], 3)
        self.assertIsNone(data["download"])
        self.assertFalse(data["route_verified"])
        self.assertEqual(data["route"], "client-current-route")
        self.assertIsNone(data["network_requests"])
        self.assertEqual(data["started_child_attempts"], 3)
        self.assertFalse(data["synthetic"])
        self.assertEqual(data["binding_mode"], "current_route")
        self.assertFalse(data["interface_name_recorded"])
        self.assertEqual(popen.call_count, 3)
        for forbidden in ("192.0.2.2", "198.51.100.2", "private-must-not-leak", "gstatic.com", "local_ipv4", "remote_ipv4"):
            self.assertNotIn(forbidden, text)

    def test_429_stops_probe_branch_without_hiding_skips(self):
        code, data, _, _, popen = self.invoke(["--execute"], [FakeCurl(metrics(40, 429))])
        self.assertEqual(code, 1)
        self.assertEqual(popen.call_count, 1)
        item = data["probe"]
        self.assertEqual((item["planned"], item["attempted"], item["failed"], item["skipped"]), (3, 1, 1, 2))
        self.assertEqual(item["attempts"][0]["classification"], "http_rejected")

    def test_full_object_reuses_core_and_partial_has_no_goodput(self):
        children = [FakeCurl() for _ in range(3)] + [FakeCurl(metrics(1000, 200, 1)), FakeCurl(metrics(200, 200, 15), 28)]
        with patch.object(quick.core, "evaluate_result", wraps=quick.core.evaluate_result) as evaluator:
            code, data, text, _, _ = self.invoke(
                ["--execute", "--download-url", "https://example.invalid/private-path?token=private-must-not-leak", "--bytes", "1000"], children)
        self.assertEqual(code, 1)
        self.assertEqual(evaluator.call_count, 2)
        item = data["download"]
        self.assertEqual((item["attempted"], item["complete"], item["failed"]), (2, 1, 1))
        self.assertEqual(item["attempts"][1]["classification"], "timeout_partial")
        self.assertIsNone(item["attempts"][1]["task_goodput_mbps"])
        self.assertEqual(item["attempts"][0]["task_goodput_mbps"], 0.008)
        for secret in ("example.invalid", "private-path", "private-must-not-leak"):
            self.assertNotIn(secret, text)

    def test_wrong_object_size_stops_download_branch(self):
        children = [FakeCurl() for _ in range(3)] + [FakeCurl(metrics(99, 200, 1))]
        code, data, _, _, popen = self.invoke(
            ["--execute", "--download-url", "https://example.invalid/fixed", "--bytes", "100"], children)
        self.assertEqual(code, 1)
        self.assertEqual(popen.call_count, 4)
        self.assertEqual(data["download"]["skipped"], 1)
        self.assertEqual(data["download"]["attempts"][0]["classification"], "object_size_mismatch")

    def test_403_stops_download_branch(self):
        children = [FakeCurl() for _ in range(3)] + [FakeCurl(metrics(0, 403))]
        _, data, _, _, popen = self.invoke(
            ["--execute", "--download-url", "https://example.invalid/fixed", "--bytes", "100"], children)
        self.assertEqual(popen.call_count, 4)
        self.assertEqual(data["download"]["skipped"], 1)
        self.assertEqual(data["download"]["attempts"][0]["classification"], "http_rejected")

    def test_streaming_body_guard_stops_probe_branch(self):
        code, data, _, _, popen = self.invoke(["--execute"], [FakeCurl(metrics(65536, 200), 63)])
        self.assertEqual(code, 1)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(data["probe"]["skipped"], 2)
        self.assertEqual(data["probe"]["attempts"][0]["classification"], "body_limit")

    def test_command_guards_route_tls_and_time(self):
        args = quick.arguments(["--execute"])
        cmd = quick.command(args, "curl", quick.PROBE_URL, quick.PROBE_BYTES, quick.PROBE_SECONDS)
        self.assertEqual(cmd[:3], ["curl", "-q", "-4"])
        for flag in ("--http1.1", "--globoff", "--silent", "--show-error"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--noproxy") + 1], "*")
        self.assertEqual(cmd[cmd.index("--max-filesize") + 1], "65536")
        self.assertEqual(cmd[cmd.index("--max-time") + 1], "5")
        self.assertEqual(cmd[cmd.index("--output") + 1], os.devnull)
        for unsafe in ("--location", "--insecure", "--interface", "--retry"):
            self.assertNotIn(unsafe, cmd)
        args.interface = "wlan0"
        forced = quick.command(args, "curl", quick.PROBE_URL, quick.PROBE_BYTES, 5)
        self.assertEqual(forced[forced.index("--interface") + 1], "if!wlan0")

    def test_plan_is_offline_and_budget_is_finite(self):
        code, data, text, check, popen = self.invoke(
            ["--plan", "--interface", "private-name", "--download-url", "https://example.invalid/private-path?key=secret", "--bytes", "8388608"])
        self.assertEqual(code, 0)
        check.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(data["network_requests"], 0)
        self.assertEqual(data["started_child_attempts"], 0)
        self.assertEqual(data["binding_mode"], "interface_forced")
        self.assertFalse(data["interface_name_recorded"])
        self.assertEqual(data["budget"]["maximum_curl_time_seconds"], 45)
        self.assertEqual(data["budget"]["maximum_wall_time_seconds"], 85)
        self.assertEqual(data["budget"]["maximum_response_body_bytes"], 3 * 65536 + 2 * 8388608)
        for secret in ("private-name", "private-path", "secret", "example.invalid"):
            self.assertNotIn(secret, text)

    def test_bad_arguments_fail_before_curl_without_echoing_secrets(self):
        invalid = [
            ["--execute", "--demo"], ["--bytes", "100"],
            ["--execute", "--download-url", "https://example.invalid/private-must-not-leak"],
            ["--execute", "--download-url", "https://example.invalid/fixed", "--bytes", "8388609"],
            ["--execute", "--download-url", "https://" + "private-must-not-leak:pw" + "@example.invalid/fixed", "--bytes", "100"],
            ["--execute", "--download-url", "http://example.invalid/fixed", "--bytes", "100"],
            ["--download-url", "https://example.invalid/fixed", "--bytes", "100"],
            ["--execute", "--interface", "private-must-not-leak;"],
            ["--execute", "--interface", ""],
            ["--execute", "--private-must-not-leak"],
        ]
        for argv in invalid:
            with self.subTest(argv=argv), patch.object(quick.core, "checked_curl") as check, \
                    patch.object(quick.subprocess, "Popen") as popen, redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as error:
                    quick.main(argv)
                self.assertEqual(error.exception.code, 2)
                self.assertNotIn("private-must-not-leak", stderr.getvalue())
                check.assert_not_called()
                popen.assert_not_called()

    def test_failures_are_classified_without_root_cause_claim(self):
        cases = [(6, metrics(0, 0), "dns_failure"), (7, metrics(0, 0), "connect_failure"),
                 (60, metrics(0, 0), "tls_failure"), (28, metrics(0, 0), "timeout_unresolved_stage"),
                 (0, metrics(0, 503), "http_unexpected"), (63, metrics(65536, 200), "body_limit")]
        for code, data, expected in cases:
            with self.subTest(expected=expected):
                row = quick.result(data, code)
                self.assertFalse(row["completed"])
                self.assertEqual(row["classification"], expected)
                self.assertIsNone(row["task_goodput_mbps"])

    def test_cancel_only_reaps_own_child_and_skips_download(self):
        child = FakeCurl(interrupted=True)
        code, data, _, _, popen = self.invoke(
            ["--execute", "--download-url", "https://example.invalid/fixed", "--bytes", "100"], [child])
        self.assertEqual(code, 130)
        self.assertTrue(child.terminated)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(data["overall_status"], "cancelled")
        self.assertEqual(data["probe"]["skipped"], 2)
        self.assertEqual(data["download"]["skipped"], 2)

    def test_outer_timeout_is_bounded_and_not_false_partial(self):
        children = [FakeCurl(outer_timeout=True) for _ in range(3)]
        code, data, _, _, popen = self.invoke(["--execute"], children)
        self.assertEqual(code, 1)
        self.assertEqual(data["probe"]["failed"], 3)
        self.assertTrue(all(child.terminated for child in children))
        self.assertEqual(data["classifications"], {"timeout_unresolved_stage": 3})
        self.assertTrue(all(child_args.kwargs["stderr"] == subprocess.PIPE for child_args in popen.call_args_list))

    def test_setup_error_is_whitelisted(self):
        output = io.StringIO()
        with patch.object(quick.core, "checked_curl", side_effect=RuntimeError("private-must-not-leak")), \
                patch.object(quick.core, "install_cancel_handlers"), redirect_stdout(output):
            code = quick.main(["--execute", "--json"])
        data = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(data["overall_status"], "setup_failed")
        self.assertEqual(data["setup_error"], "curl_setup_failed")
        self.assertEqual(data["network_requests"], 0)
        self.assertNotIn("private-must-not-leak", output.getvalue())

    def test_launch_failure_is_not_counted_as_started_or_http_request(self):
        output = io.StringIO()
        with patch.object(quick.core, "checked_curl", return_value="curl"), \
                patch.object(quick.subprocess, "Popen", side_effect=OSError("private-must-not-leak")), \
                patch.object(quick.core, "install_cancel_handlers"), redirect_stdout(output):
            code = quick.main(["--execute", "--json"])
        data = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(data["probe"]["attempted"], 1)
        self.assertEqual(data["probe"]["failed"], 1)
        self.assertEqual(data["probe"]["started_child_attempts"], 0)
        self.assertEqual(data["started_child_attempts"], 0)
        self.assertEqual(data["network_requests"], 0)
        self.assertNotIn("private-must-not-leak", output.getvalue())

    def test_dns_failure_started_child_does_not_claim_sent_http(self):
        code, data, _, _, _ = self.invoke(["--execute"], [FakeCurl(metrics(0, 0), 6) for _ in range(3)])
        self.assertEqual(code, 1)
        self.assertEqual(data["started_child_attempts"], 3)
        self.assertIsNone(data["network_requests"])
        self.assertEqual(data["classifications"], {"dns_failure": 3})

    def test_cancel_between_branches_renders_consistent_result(self):
        output = io.StringIO()
        original = quick.run_branch

        def branch_then_cancel(target, *args):
            if target["expected_bytes"] is not None:
                raise KeyboardInterrupt
            return original(target, *args)

        with patch.object(quick.core, "checked_curl", return_value="curl"), \
                patch.object(quick.subprocess, "Popen", side_effect=[FakeCurl() for _ in range(3)]), \
                patch.object(quick.core, "install_cancel_handlers"), \
                patch.object(quick, "run_branch", side_effect=branch_then_cancel), redirect_stdout(output):
            code = quick.main(["--execute", "--download-url", "https://example.invalid/fixed", "--bytes", "100", "--json"])
        data = json.loads(output.getvalue())
        self.assertEqual(code, 130)
        self.assertEqual(data["overall_status"], "cancelled")
        self.assertTrue(data["cancelled"])
        self.assertEqual(data["started_child_attempts"], 3)
        self.assertEqual(data["download"]["attempted"], 0)
        self.assertEqual(data["download"]["skipped"], 2)

    def test_human_result_does_not_call_child_count_real_http_requests(self):
        args = quick.arguments([])
        data = quick.demonstration(args)
        output = io.StringIO()
        with redirect_stdout(output):
            quick.render(data, False)
        text = output.getvalue()
        self.assertIn("已启动请求任务 0 个", text)
        self.assertNotIn("真实网络请求", text)
        for note in data["notes"]:
            self.assertEqual(text.count(note), 1)


if __name__ == "__main__":
    unittest.main()
