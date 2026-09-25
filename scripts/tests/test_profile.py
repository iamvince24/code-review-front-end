import os
import shutil
import tempfile
import unittest

from helpers import load, make_repo


profiles = load("profile_repos")


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        self.home = tempfile.mkdtemp(prefix="fe-review-home.")
        self.old_home = os.environ.get("FE_REVIEW_HOME")
        os.environ["FE_REVIEW_HOME"] = self.home

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("FE_REVIEW_HOME", None)
        else:
            os.environ["FE_REVIEW_HOME"] = self.old_home
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)

    def test_missing_does_not_create_profile(self):
        result = profiles.load(self.repo)
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["mode"], "standard")
        self.assertFalse(os.path.exists(result["path"]))

    def test_legacy_modes(self):
        path = profiles.profile_path(self.repo)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for old, expected in (("low", "standard"), ("medium", "standard"), ("high", "standard"), ("max", "deep")):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(f"- 預設強度：{old}\n\n## 備註\n\n保留我\n")
            result = profiles.load(self.repo)
            self.assertEqual(result["mode"], expected)
            self.assertTrue(result["legacy"])

    def test_review_home_defaults_to_config_dir(self):
        home = tempfile.mkdtemp(prefix="fe-review-user.")
        old_user = os.environ.get("HOME")
        os.environ.pop("FE_REVIEW_HOME", None)
        os.environ["HOME"] = home
        try:
            self.assertEqual(
                profiles.review_home(),
                os.path.join(home, ".config", "code-review-front-end"),
            )
        finally:
            os.environ["FE_REVIEW_HOME"] = self.home
            if old_user is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_user
            shutil.rmtree(home, ignore_errors=True)

    def test_review_home_reads_legacy_cursor_dir_until_config_exists(self):
        home = tempfile.mkdtemp(prefix="fe-review-user.")
        legacy = os.path.join(home, ".cursor", "code-review-front-end")
        os.makedirs(legacy)
        old_user = os.environ.get("HOME")
        os.environ.pop("FE_REVIEW_HOME", None)
        os.environ["HOME"] = home
        try:
            self.assertEqual(profiles.review_home(), legacy)
            os.makedirs(os.path.join(home, ".config", "code-review-front-end"))
            self.assertEqual(
                profiles.review_home(),
                os.path.join(home, ".config", "code-review-front-end"),
            )
        finally:
            os.environ["FE_REVIEW_HOME"] = self.home
            if old_user is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_user
            shutil.rmtree(home, ignore_errors=True)

    def test_config_migrates_and_preserves_notes(self):
        path = profiles.profile_path(self.repo)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("- 預設強度：max\n\n## 備註\n\nlegacy/ 不審查\n")
        result = profiles.configure(self.repo, "standard")
        self.assertEqual(result["mode"], "standard")
        self.assertEqual(result["notes"], "legacy/ 不審查")
        self.assertFalse(result["legacy"])


if __name__ == "__main__":
    unittest.main()
