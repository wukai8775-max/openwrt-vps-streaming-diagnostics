import importlib.util
import ipaddress
import threading
from types import SimpleNamespace
from pathlib import Path
import struct
import subprocess
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools" / "probe.py"
spec = importlib.util.spec_from_file_location("probe", PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def response(self, tx):
        address = int(ipaddress.IPv4Address("203.0.113.8")) ^ probe.COOKIE
        value = struct.pack("!BBHI", 0, 1, 5000 ^ (probe.COOKIE >> 16), address)
        attr = struct.pack("!HH", 0x0020, len(value)) + value
        return struct.pack("!HHI12s", 0x0101, len(attr), probe.COOKIE, tx) + attr

    def test_xor_mapping_and_transaction(self):
        _, tx = probe.stun_request()
        packet = self.response(tx)
        self.assertEqual(probe.parse_stun(packet, tx),
                         {"exit_ipv4": "203.0.113.8", "mapped_port": 5000})
        with self.assertRaises(ValueError):
            probe.parse_stun(packet, b"x" * 12)

    def test_truncation_and_length(self):
        _, tx = probe.stun_request()
        packet = self.response(tx)
        for length in (0, 19, 21, len(packet) - 1):
            with self.assertRaises(ValueError):
                probe.parse_stun(packet[:length], tx)

    def test_failure_denominator(self):
        rows = [{"ok": True, "elapsed_ms": 230},
                {"ok": False, "error_type": "TimeoutError", "elapsed_ms": 2500}]
        summary = probe.summarize(rows)
        self.assertEqual((summary["attempts"], summary["successes"], summary["timeouts"]), (2, 1, 1))
        self.assertEqual(summary["success_max_ms"], 230)
        self.assertNotIn("success_p95_ms", summary)

    def test_https_deadline_covers_response_body(self):
        closed = threading.Event()

        class FakeSocket:
            def shutdown(self, how):
                closed.set()
            def close(self):
                closed.set()
            def settimeout(self, timeout):
                pass

        class FakeResponse:
            status = 204
            def read(self, count):
                if not closed.wait(timeout=2):
                    raise AssertionError("whole-request timer did not close body read")
                return b""

        class FakeConnection:
            sock = FakeSocket()
            connections = 1
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return FakeResponse()
            def close(self):
                self.sock.close()

        row = probe.https_probe(FakeConnection(), SimpleNamespace(timeout=.05, path="/", status=204))
        self.assertFalse(row["ok"])
        self.assertEqual(row["error_type"], "TimeoutError")
        self.assertTrue(closed.is_set())

    def test_late_stun_reply_is_not_current_success(self):
        outer = self

        class FakeUDP:
            def send(self, packet):
                self.tx = packet[8:20]
                self.first = True
            def settimeout(self, timeout):
                pass
            def recv(self, count):
                if self.first:
                    self.first = False
                    return outer.response(b"x" * 12)
                return outer.response(self.tx)

        row = probe.udp_probe(FakeUDP(), SimpleNamespace(timeout=.1, expect_exit="203.0.113.8"))
        self.assertTrue(row["ok"])
        self.assertEqual(row["ignored_packets"], 1)

    def test_dry_run_does_not_bind_or_connect(self):
        result = subprocess.run([sys.executable, str(PATH), "stun", "--source", "192.0.2.9",
                                 "--server-ip", "203.0.113.8", "--dry-run"],
                                text=True, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"dry_run": true', result.stdout)

    def test_budget_rejected_before_network(self):
        result = subprocess.run([sys.executable, str(PATH), "stun", "--source", "192.0.2.9",
                                 "--server-ip", "203.0.113.8", "--samples", "600",
                                 "--timeout", "10", "--dry-run"], capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 2)

    def test_unspecified_source_and_zero_port_rejected(self):
        for extra in (["--source", "0.0.0.0"], ["--source", "224.0.0.1"],
                      ["--source", "192.0.2.9", "--port", "0"]):
            result = subprocess.run([sys.executable, str(PATH), "stun", "--server-ip",
                                     "203.0.113.8", "--dry-run", *extra],
                                    capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
