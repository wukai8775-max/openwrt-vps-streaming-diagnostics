"""Offline collector contract tests; commands are fake, not host telemetry."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAKE_COMMAND = r'''
import json
import os
from pathlib import Path
import sys
import time

name = Path(sys.argv[0]).name
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps([name, *sys.argv[1:]]) + "\n")
if os.environ.get("FAKE_FAIL_COMMAND") == name:
    print("fixture command failure", file=sys.stderr)
    sys.exit(7)
if name == "uname":
    print("Linux" if sys.argv[1:] == ["-s"] else "Linux fixture 6.8 fixture")
elif name == "date":
    print("1720000000" if sys.argv[-1] == "+%s" else "2026-01-01T00:00:00Z")
elif name == "cat":
    if not sys.argv[1:]:
        sys.stdout.write(sys.stdin.read())
    elif sys.argv[-1] == "/proc/stat":
        print("cpu 100 0 50 1000 0 0 0 0 0 0\ncpu0 50 0 25 500 0 0 0 0 0 0")
    else:
        print("fixture raw counters")
elif name == "ss":
    print("ESTAB 0 0 192.0.2.10:443 198.51.100.20:50000")
    print(" ts sack bbr wscale:7,7 rtt:230/2 cwnd:10 bytes_retrans:54")
elif name == "tc":
    print("qdisc fq_codel 0: dev test0 root")
elif name == "ip":
    print("fixture interface and route data")
elif name == "systemctl":
    print("ActiveState=active\nSubState=running\nMainPID=42")
elif name == "sleep":
    time.sleep(float(os.environ.get("FAKE_SLEEP_SECONDS", "0")))
'''


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.log = self.base / "commands.jsonl"
        self.env = dict(os.environ, PATH=str(self.base), FAKE_LOG=str(self.log))
        for name in ("uname", "date", "cat", "ss", "tc", "ip", "systemctl", "sleep"):
            command = self.base / name
            command.write_text(f"#!{sys.executable}\n{FAKE_COMMAND}", encoding="utf-8")
            command.chmod(0o700)

    def run_collector(self, script, *args, **env):
        return subprocess.run(
            ["/bin/sh", str(ROOT / "tools" / script), *args],
            env={**self.env, **env}, text=True, capture_output=True, timeout=15,
        )

    def commands(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_shell_syntax(self):
        for script in ("snapshot.sh", "sample.sh"):
            with self.subTest(script=script):
                result = subprocess.run(["/bin/sh", "-n", str(ROOT / "tools" / script)], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_dry_run_never_collects_or_sleeps(self):
        for script in ("snapshot.sh", "sample.sh"):
            with self.subTest(script=script):
                if self.log.exists():
                    self.log.unlink()
                result = self.run_collector(script, "--port", "443", "--dry-run")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("status=planned", result.stdout)
                self.assertEqual(self.commands(), [])

    def test_invalid_arguments_fail_before_collection(self):
        cases = [
            ("sample.sh", []),
            ("sample.sh", ["--port", "443", "--count", "301"]),
            ("sample.sh", ["--port", "443", "--count", "100", "--interval", "7"]),
            ("sample.sh", ["--port", "443", "--interval", "0.5"]),
            ("snapshot.sh", ["--port", "65536"]),
            ("snapshot.sh", ["--interface", "--all"]),
            ("snapshot.sh", ["--unit", "test;touch"]),
            ("snapshot.sh", ["--port"]),
            ("snapshot.sh", ["--port", ""]),
        ]
        for script, args in cases:
            with self.subTest(script=script, args=args):
                if self.log.exists():
                    self.log.unlink()
                result = self.run_collector(script, *args)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("collector=", result.stdout)
                self.assertEqual(self.commands(), [])

    def test_snapshot_preserves_actual_socket_flags_and_filters(self):
        result = self.run_collector("snapshot.sh", "--port", "443", "--interface", "test0", "--unit", "proxy.service")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ts sack bbr", result.stdout)
        self.assertIn("snapshot_end status=complete", result.stdout)
        commands = self.commands()
        self.assertIn(["ss", "-H", "-tinp", "( sport = :443 or dport = :443 )"], commands)
        self.assertIn(["tc", "-s", "qdisc", "show", "dev", "test0"], commands)
        systemd = [command for command in commands if command[0] == "systemctl"]
        self.assertEqual(len(systemd), 1)
        self.assertNotIn("ExecStart", " ".join(systemd[0]))
        self.assertTrue(all(command[0] not in ("curl", "ssh", "sysctl", "uci", "iptables", "nft") for command in commands))

    def test_snapshot_without_port_skips_socket_collection(self):
        result = self.run_collector("snapshot.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status=skipped reason=port-not-specified", result.stdout)
        self.assertFalse(any(command[0] == "ss" and "-tinp" in command for command in self.commands()))
        self.assertFalse(any(command[0] == "systemctl" for command in self.commands()))

    def test_missing_tools_and_failure_are_explicit(self):
        (self.base / "tc").unlink()
        result = self.run_collector("sample.sh", "--port", "443", "--count", "1", FAKE_FAIL_COMMAND="ss")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status=unavailable reason=missing-tool tool=tc", result.stdout)
        self.assertIn("status=failed exit=7", result.stdout)
        self.assertIn("sampler_end status=complete samples=1 requested=1", result.stdout)
        self.assertNotIn("bytes_retrans:0", result.stdout)

    def test_count_and_leading_zero_intervals(self):
        result = self.run_collector("sample.sh", "--port", "00443", "--count", "02", "--interval", "01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("sample_begin index="), 2)
        self.assertIn("sampler_end status=complete samples=2 requested=2", result.stdout)
        self.assertEqual(sum(command[0] == "sleep" for command in self.commands()), 1)

    def test_sigterm_is_interrupted_not_complete(self):
        process = subprocess.Popen(
            ["/bin/sh", str(ROOT / "tools" / "sample.sh"), "--port", "443", "--count", "3", "--interval", "1"],
            env={**self.env, "FAKE_SLEEP_SECONDS": "1"}, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if any(command[0] == "sleep" for command in self.commands()):
                    break
                time.sleep(0.02)
            else:
                self.fail("fixture did not reach sleep")
            process.send_signal(signal.SIGTERM)
            output, error = process.communicate(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        self.assertEqual(process.returncode, 143, error)
        self.assertIn("sampler_end status=interrupted signal=TERM samples=1 requested=3", output)
        self.assertNotIn("sampler_end status=complete", output)


if __name__ == "__main__":
    unittest.main()
