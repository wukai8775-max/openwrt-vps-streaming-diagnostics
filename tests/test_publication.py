import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("publication", Path(__file__).resolve().parents[1] /
                                            "tools" / "check-publication.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.git("init", "-q")

    def tearDown(self):
        self.directory.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL)

    def test_staged_secret_detected_after_working_copy_cleaned(self):
        path = self.root / "example.txt"
        path.write_text("https://" + "fixture:dummy" + "@example.invalid/\n")
        self.git("add", path.name)
        path.write_text("Clean working copy\n")
        checked, failures = guard.scan_index(self.root)
        self.assertEqual(checked, 1)
        self.assertEqual(failures, [(path.name, "credential URL")])

    def test_unstaged_changes_do_not_change_commit_check(self):
        path = self.root / "example.txt"
        path.write_text("Clean staged content\n")
        self.git("add", path.name)
        path.write_text("https://" + "fixture:dummy" + "@example.invalid/\n")
        checked, failures = guard.scan_index(self.root)
        self.assertEqual((checked, failures), (1, []))

    def test_private_artifact_path_and_symlink_rejected(self):
        path = self.root / "backups" / "config.txt"
        path.parent.mkdir()
        path.write_text("synthetic fixture\n")
        (self.root / "link.txt").symlink_to("backups/config.txt")
        self.git("add", ".")
        checked, failures = guard.scan_index(self.root)
        self.assertEqual(checked, 2)
        self.assertEqual(len(failures), 2)


if __name__ == "__main__":
    unittest.main()
