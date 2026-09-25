#!/usr/bin/env python3
"""Read or update the lightweight per-repository frontend review profile."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys


MODES = ("standard", "deep")
NOTES_HEADER = "## 備註"


def review_home() -> str:
    override = os.environ.get("FE_REVIEW_HOME")
    if override:
        return os.path.expanduser(override)
    home = os.path.expanduser("~/.config/code-review-front-end")
    legacy = os.path.expanduser("~/.cursor/code-review-front-end")
    if not os.path.isdir(home) and os.path.isdir(legacy):
        return legacy
    return home


def repo_root(path: str) -> str:
    result = subprocess.run(
        ["git", "-C", os.path.abspath(os.path.expanduser(path)), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError("找不到 git repo")
    return os.path.realpath(result.stdout.strip())


def profile_path(repo: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(repo)).strip("-") or "repo"
    return os.path.join(review_home(), "profiles", f"{name}.md")


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""


def extract_notes(text: str) -> str:
    match = re.search(r"^## 備註\s*$([\s\S]*)", text, re.M)
    return match.group(1).strip() if match else ""


def parse_mode(text: str) -> tuple[str, bool]:
    current = re.search(r"^- 預設模式：\s*(standard|deep)\s*$", text, re.M)
    if current:
        return current.group(1), False
    legacy = re.search(r"^- 預設強度：\s*(low|medium|high|max)\b", text, re.M)
    if legacy:
        return ("deep" if legacy.group(1) == "max" else "standard"), True
    return "standard", False


def load(repo: str) -> dict:
    path = profile_path(repo)
    text = read_text(path)
    mode, legacy = parse_mode(text)
    return {
        "status": "ok" if text else "missing",
        "repo": repo,
        "path": path,
        "mode": mode,
        "notes": extract_notes(text),
        "legacy": legacy,
    }


def render(repo: str, mode: str, notes: str) -> str:
    body = [
        f"# {os.path.basename(repo)}：code review 設定",
        "",
        f"- repo: `{repo}`",
        f"- 預設模式：{mode}",
        "",
        NOTES_HEADER,
        "",
        notes.strip(),
    ]
    return "\n".join(body).rstrip() + "\n"


def configure(repo: str, mode: str) -> dict:
    old = load(repo)
    path = old["path"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render(repo, mode, old["notes"]))
    return load(repo)


def main(argv=None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "setup":
        print(json.dumps({"status": "error", "error": "舊介面 setup 已移除，不再支援；profile 不需要預先建立"}, ensure_ascii=False))
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "config", "path"))
    parser.add_argument("repo")
    parser.add_argument("--mode", choices=MODES)
    args = parser.parse_args(raw_args)
    try:
        repo = repo_root(args.repo)
        if args.command == "config":
            if not args.mode:
                parser.error("config 需要 --mode standard|deep")
            result = configure(repo, args.mode)
        elif args.command == "path":
            result = {"repo": repo, "path": profile_path(repo)}
        else:
            result = load(repo)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
