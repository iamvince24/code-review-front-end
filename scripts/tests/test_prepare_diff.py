import argparse
import os
import shutil
import unittest

from helpers import load, make_repo


prepare_diff = load("prepare_diff")


class PrepareDiffTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def args(self, **overrides):
        data = dict(repo=self.repo, base=None, head=None, mode=None, focus=None, spec=None, checks=False)
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
        self.assertEqual(prepare_diff.choose_mode(None, 499, 19, [])[0], "standard")
        self.assertEqual(prepare_diff.choose_mode(None, 500, 20, [])[0], "standard")
        self.assertEqual(prepare_diff.choose_mode(None, 501, 20, [])[0], "deep")
        self.assertEqual(prepare_diff.choose_mode(None, 500, 21, [])[0], "deep")
        for signal in ("auth", "secret", "html_sink", "server_boundary", "config"):
            self.assertEqual(prepare_diff.choose_mode(None, 1, 1, [signal])[0], "deep")
        self.assertEqual(prepare_diff.choose_mode("standard", 999, 99, ["auth"])[0], "standard")

    def test_risk_signals_only_scan_changed_content(self):
        unchanged_secret = (
            "diff --git a/src/App.tsx b/src/App.tsx\n"
            "--- a/src/App.tsx\n+++ b/src/App.tsx\n"
            "@@ -1,2 +1,2 @@\n const token = session.token\n-old\n+new\n"
        )
        self.assertEqual(prepare_diff.detect_signals(unchanged_secret, ["src/App.tsx"]), [])
        changed_sink = unchanged_secret.replace("+new", "+dangerouslySetInnerHTML={{__html: html}}")
        self.assertEqual(prepare_diff.detect_signals(changed_sink, ["src/App.tsx"]), ["html_sink"])
        removed_auth = unchanged_secret.replace("-old", "-if (!session) return null")
        self.assertEqual(prepare_diff.detect_signals(removed_auth, ["src/App.tsx"]), ["auth"])
        self.assertEqual(prepare_diff.detect_signals("", ["app/api/order/route.ts"]), ["server_boundary"])
        self.assertEqual(prepare_diff.detect_signals("", ["package.json"]), [])
        self.assertEqual(prepare_diff.detect_signals("", ["next.config.js"]), ["config"])

    def test_local_checks_are_opt_in(self):
        self.write("src/App.tsx", "export const App = () => <main>Hello</main>;\n")
        result = prepare_diff.prepare(self.args())
        self.assertEqual(result["lint"]["status"], "skipped")
        self.assertEqual(result["lint"]["reason"], "未要求執行本機檢查")
        prepare_diff.cleanup(result["dir"], result["token"])

    def test_failed_requested_checks_do_not_abort_prepare(self):
        bin_dir = os.path.join(self.repo, "node_modules", ".bin")
        os.makedirs(bin_dir, exist_ok=True)
        for name in ("eslint", "tsc"):
            path = os.path.join(bin_dir, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\necho simulated failure >&2\nexit 1\n")
            os.chmod(path, 0o755)
        self.write("tsconfig.json", "{}\n")
        self.write("src/App.tsx", "export const App = () => <main>Hello</main>;\n")
        result = prepare_diff.prepare(self.args(mode="standard", checks=True))
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
        result = prepare_diff.prepare(self.args(base=base, head=head, checks=True))
        self.assertTrue(os.path.isdir(result["review_root"]))
        self.assertEqual(result["lint"]["status"], "skipped")
        review_root = result["review_root"]
        prepare_diff.cleanup(result["dir"], result["token"])
        self.assertFalse(os.path.exists(review_root))

    def test_default_base_uses_remote_default_not_feature_upstream(self):
        prepare_diff.git(self.repo, "branch", "-M", "main")
        main = prepare_diff.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        prepare_diff.git(self.repo, "update-ref", "refs/remotes/origin/main", main)
        prepare_diff.git(self.repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        prepare_diff.git(self.repo, "checkout", "-b", "feature")
        self.write("src/App.tsx", "export const App = () => <main>Feature</main>;\n")
        prepare_diff.git(self.repo, "add", ".")
        prepare_diff.git(self.repo, "commit", "-m", "feature")
        feature = prepare_diff.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        prepare_diff.git(self.repo, "update-ref", "refs/remotes/origin/feature", feature)
        prepare_diff.git(self.repo, "config", "branch.feature.remote", "origin")
        prepare_diff.git(self.repo, "config", "branch.feature.merge", "refs/heads/feature")
        self.assertEqual(prepare_diff.default_base(self.repo), main)


if __name__ == "__main__":
    unittest.main()
