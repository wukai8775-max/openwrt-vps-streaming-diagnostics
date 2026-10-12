#!/usr/bin/env python3
"""Check tracked files for common accidental secrets and private artifacts."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATH = re.compile(r"(^|/)(results|private|backups|\.ssh)(/|$)|(^|/)\.env($|\.)|\.(pcapng?|pem|key|p12|pfx|tar\.gz|zip)$")
PATTERNS = [
    ("private key", re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("credential URL", re.compile(rb"https?://[^\s/@]+:[^\s/@]+@")),
    ("node share link", re.compile(rb"\b(?:vless|vmess|trojan|ss)://[^\s`]+")),
    ("personal absolute path", re.compile(rb"/(?:Users|home)/[A-Za-z0-9_.-]+/")),
]


def scan_index(root):
    files = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=root).split(b"\0")
    failures = []
    checked = 0
    for raw in files:
        if not raw:
            continue
        header, path = raw.split(b"\t", 1)
        mode, oid, stage = header.decode("ascii").split()
        name = path.decode("utf-8")
        checked += 1
        if mode not in ("100644", "100755") or stage != "0":
            failures.append((name, "symlink, submodule or conflicted index entry"))
            continue
        if PRIVATE_PATH.search(name):
            failures.append((name, "private artifact path"))
        # Scan what will be committed, even when the working copy differs.
        data = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=root)
        for label, pattern in PATTERNS:
            if pattern.search(data):
                failures.append((name, label))
    return checked, failures


def main():
    checked, failures = scan_index(ROOT)
    for name, reason in failures:
        # Never print the matched value.
        print(f"BLOCKED {name}: {reason}", file=sys.stderr)
    if not checked:
        print("No tracked files; stage the intended public files first.", file=sys.stderr)
        return 2
    print(f"Checked {checked} tracked files; {len(failures)} findings. Manual redaction is still required.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
