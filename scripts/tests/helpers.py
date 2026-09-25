import importlib.util
import os
import subprocess
import tempfile


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    path = os.path.join(ROOT, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command(repo, *args):
    return subprocess.run(args, cwd=repo, text=True, capture_output=True, check=True)


def make_repo():
    root = tempfile.mkdtemp(prefix="fe-review-test.")
    command(root, "git", "init", "-q")
    command(root, "git", "config", "user.email", "test@example.com")
    command(root, "git", "config", "user.name", "Test")
    with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as handle:
        handle.write('{"dependencies":{"react":"19.0.0"}}\n')
    command(root, "git", "add", ".")
    command(root, "git", "commit", "-qm", "initial")
    return root
