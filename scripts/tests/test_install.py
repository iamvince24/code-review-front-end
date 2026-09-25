import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "scripts", "install.sh")
NAME = "code-review-front-end"


def run_install(home, script=SCRIPT):
    env = os.environ.copy()
    env["HOME"] = home
    return subprocess.run(["sh", script], env=env, text=True, capture_output=True)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="fe-review-install.")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def dest(self, host):
        return os.path.join(self.home, host, "skills", NAME)

    def test_links_three_skill_dirs(self):
        result = run_install(self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        source = os.path.realpath(ROOT)
        for host in (".cursor", ".claude", ".agents"):
            dest = self.dest(host)
            self.assertTrue(os.path.islink(dest))
            self.assertEqual(os.path.realpath(dest), source)

    def test_skips_existing_directory_and_keeps_the_others(self):
        blocked = self.dest(".claude")
        os.makedirs(blocked)
        result = run_install(self.home)
        self.assertEqual(result.returncode, 1)
        self.assertIn("skip", result.stderr)
        self.assertFalse(os.path.islink(blocked))
        self.assertTrue(os.path.islink(self.dest(".cursor")))
        self.assertTrue(os.path.islink(self.dest(".agents")))

    def test_inplace_dir_is_ok_and_other_hosts_link_to_it(self):
        skill = self.dest(".cursor")
        script_dir = os.path.join(skill, "scripts")
        os.makedirs(script_dir)
        script = os.path.join(script_dir, "install.sh")
        shutil.copy(SCRIPT, script)
        result = run_install(self.home, script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(os.path.islink(skill))
        self.assertIn(f"ok {skill}", result.stdout)
        for host in (".claude", ".agents"):
            dest = self.dest(host)
            self.assertTrue(os.path.islink(dest))
            self.assertEqual(os.path.realpath(dest), os.path.realpath(skill))


if __name__ == "__main__":
    unittest.main()
