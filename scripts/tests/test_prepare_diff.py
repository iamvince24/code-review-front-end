import argparse
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from helpers import load, make_repo


prepare_diff = load("prepare_diff")


class PrepareDiffTest(unittest.TestCase):
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

    def args(self, **overrides):
        data = dict(repo=self.repo, base=None, head=None, mode=None, focus=None, spec=None)
        data.update(overrides)
        return argparse.Namespace(**data)

    def write(self, path, text):
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_empty_and_non_frontend_diff(self):
        self.assertEqual(prepare_diff.prepare(self.args())["status"], "empty")
        self.write("README.md", "changed\n")
        self.assertEqual(prepare_diff.prepare(self.args())["status"], "empty")

    def test_untracked_frontend_diff_and_cleanup(self):
        self.write("src/App.tsx", "export const App = () => <main>Hello</main>;\n")
        result = prepare_diff.prepare(self.args())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "standard")
        self.assertIn("src/App.tsx", result["files"])
        self.assertTrue(os.path.exists(result["context"]))
        cleaned = prepare_diff.cleanup(result["dir"], result["token"])
        self.assertEqual(cleaned["status"], "cleaned")
        self.assertFalse(os.path.exists(result["dir"]))

    def test_secret_and_env_values_are_redacted(self):
        self.write("src/key.ts", "const token = 'sk-abcdefghijklmnop';\n")
        self.write(".env.local", "PASSWORD=do-not-leak\n")
        result = prepare_diff.prepare(self.args())
        with open(result["diff"], encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("abcdefghijklmnop", text)
        self.assertNotIn("do-not-leak", text)
        self.assertIn("環境變數內容已省略", text)
        prepare_diff.cleanup(result["dir"], result["token"])

    def test_mode_boundaries_and_signals(self):
        self.assertEqual(prepare_diff.choose_mode(None, "standard", 499, 19, [])[0], "standard")
        self.assertEqual(prepare_diff.choose_mode(None, "standard", 500, 20, [])[0], "standard")
        self.assertEqual(prepare_diff.choose_mode(None, "standard", 501, 20, [])[0], "deep")
        self.assertEqual(prepare_diff.choose_mode(None, "standard", 500, 21, [])[0], "deep")
        for signal in ("auth", "secret", "html_sink", "server_boundary", "config"):
            self.assertEqual(prepare_diff.choose_mode(None, "standard", 1, 1, [signal])[0], "deep")
        self.assertEqual(prepare_diff.choose_mode("standard", "deep", 999, 99, ["auth"])[0], "standard")

    def test_behavior_cases_route_without_creating_findings(self):
        xss = "dangerouslySetInnerHTML={{__html: html}}"
        safe_html = "dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(html)}}"
        effect_cleanup = "useEffect(() => { const id = setInterval(tick); return () => clearInterval(id); }, [])"
        prop_change = "type Props = { customerId: string }"
        self.assertIn("html_sink", prepare_diff.detect_signals(xss, ["src/App.tsx"]))
        self.assertIn("html_sink", prepare_diff.detect_signals(safe_html, ["src/App.tsx"]))
        self.assertEqual(prepare_diff.detect_signals(effect_cleanup, ["src/App.tsx"]), [])
        self.assertEqual(prepare_diff.detect_signals(prop_change, ["src/App.tsx"]), [])
        self.assertEqual(prepare_diff.choose_mode(None, "standard", 8, 1, [])[0], "standard")

    def test_failed_local_checks_do_not_abort_prepare(self):
        bin_dir = os.path.join(self.repo, "node_modules", ".bin")
        os.makedirs(bin_dir, exist_ok=True)
        for name in ("eslint", "tsc"):
            path = os.path.join(bin_dir, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\necho simulated failure >&2\nexit 1\n")
            os.chmod(path, 0o755)
        self.write("tsconfig.json", "{}\n")
        self.write("src/App.tsx", "export const App = () => <main>Hello</main>;\n")
        result = prepare_diff.prepare(self.args(mode="standard"))
        self.assertEqual(result["lint"]["status"], "failed")
        self.assertEqual(result["typecheck"]["status"], "failed")
        prepare_diff.cleanup(result["dir"], result["token"])

    def test_focus_does_not_expand(self):
        self.write("src/App.tsx", "export const App = () => <main>Hello</main>;\n")
        result = prepare_diff.prepare(self.args(focus="maintainability"))
        self.assertEqual(result["focus"], ["maintainability"])
        prepare_diff.cleanup(result["dir"], result["token"])

    def test_base_head_creates_and_removes_worktree(self):
        base = prepare_diff.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.write("src/App.tsx", "export const App = () => <main>Hello</main>;\n")
        prepare_diff.git(self.repo, "add", ".")
        prepare_diff.git(self.repo, "commit", "-m", "feature")
        head = prepare_diff.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        result = prepare_diff.prepare(self.args(base=base, head=head))
        self.assertTrue(os.path.isdir(result["review_root"]))
        self.assertEqual(result["lint"]["status"], "skipped")
        review_root = result["review_root"]
        prepare_diff.cleanup(result["dir"], result["token"])
        self.assertFalse(os.path.exists(review_root))

    def test_removed_interface_returns_clear_error(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = prepare_diff.main(["prepare", "--repo", self.repo, "--since-last"])
        self.assertEqual(status, 2)
        self.assertIn("已移除，不再支援", output.getvalue())


if __name__ == "__main__":
    unittest.main()
