#!/usr/bin/env python3
"""Prepare a small, sanitized context package for frontend code review."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile


FRONTEND_SUFFIXES = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".css", ".scss", ".sass", ".less",
}
CONFIG_NAMES = {"package.json", "angular.json", ".npmrc"}
EXCLUDED_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",
}
EXCLUDED_PARTS = {"node_modules", "dist", "build", ".next", "coverage", "vendor"}
LENSES = ("correctness", "risk", "maintainability")
SIGNALS = {
    "auth": re.compile(r"\b(auth|authorization|permission|role|session|login|logout|requireAdmin)\b", re.I),
    "secret": re.compile(r"\b(secret|token|password|api[_-]?key|NEXT_PUBLIC_)\b", re.I),
    "html_sink": re.compile(r"dangerouslySetInnerHTML|\.innerHTML\b|bypassSecurityTrust|ng-bind-html", re.I),
    "server_boundary": re.compile(r"['\"]use server['\"]|server\s+action|route\.(?:ts|js)\b", re.I),
}
SECRET_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "sk-****"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{12,}\b"), "gh*_****"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA****"),
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)(\s*[:=]\s*)('[^']*'|\"[^\"]*\"|[^\s,;]+)"), r"\1\2<REDACTED>"),
    (re.compile(r"(?i)://([^/@:\s]+):([^/@\s]+)@"), r"://\1:<REDACTED>@"),
)


def run(command, *, cwd=None, timeout=30, check=True):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise ValueError((result.stderr or result.stdout or "指令執行失敗").strip().splitlines()[0])
    return result


def git(repo, *args, timeout=30, check=True):
    return run(["git", "-C", repo, *args], timeout=timeout, check=check)


def repo_root(path):
    result = git(os.path.abspath(os.path.expanduser(path)), "rev-parse", "--show-toplevel")
    return os.path.realpath(result.stdout.strip())


def safe_ref(value):
    if value and value.startswith("-"):
        raise ValueError("git ref 不能以 - 開頭")
    return value


def default_base(repo):
    remote_head = git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False)
    candidates = [remote_head.stdout.strip()] if remote_head.returncode == 0 else []
    candidates += ["origin/main", "origin/master", "main", "master"]
    for candidate in candidates:
        if not candidate:
            continue
        exists = git(repo, "rev-parse", "--verify", candidate, check=False)
        if exists.returncode == 0:
            merge = git(repo, "merge-base", "HEAD", candidate, check=False)
            if merge.returncode == 0:
                return merge.stdout.strip()
    return "HEAD"


def path_from_chunk(chunk):
    match = re.search(r"^\+\+\+ b/(.+)$", chunk, re.M)
    if not match:
        match = re.search(r"^--- a/(.+)$", chunk, re.M)
    return match.group(1).strip().strip('"') if match else ""


def split_chunks(patch):
    starts = [match.start() for match in re.finditer(r"(?m)^diff --git ", patch)]
    if not starts:
        return []
    starts.append(len(patch))
    return [patch[starts[i]:starts[i + 1]] for i in range(len(starts) - 1)]


def is_config(path):
    name = os.path.basename(path)
    return name in CONFIG_NAMES or name.startswith("tsconfig") and name.endswith(".json") or name.startswith("next.config.") or name.startswith(".env")


def is_frontend(path):
    parts = set(path.replace("\\", "/").split("/"))
    if parts & EXCLUDED_PARTS or os.path.basename(path) in EXCLUDED_NAMES:
        return False
    return os.path.splitext(path)[1].lower() in FRONTEND_SUFFIXES or is_config(path)


def redact(text):
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_chunk(chunk, path):
    if os.path.basename(path).startswith(".env"):
        kept = []
        for line in chunk.splitlines():
            if line.startswith(("diff --git ", "index ", "--- ", "+++ ", "@@")):
                kept.append(line)
        kept.append("# 環境變數內容已省略")
        return "\n".join(kept) + "\n"
    return redact(chunk)


def number_patch(patch):
    output = []
    old_line = new_line = None
    header = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for line in patch.splitlines():
        match = header.match(line)
        if match:
            old_line, new_line = int(match.group(1)), int(match.group(2))
            output.append(line)
        elif old_line is None or line.startswith(("diff --git ", "index ", "--- ", "+++ ", "Binary files ")):
            output.append(line)
        elif line.startswith("+"):
            output.append(f"{'':>6}|{new_line:>6}|{line}")
            new_line += 1
        elif line.startswith("-"):
            output.append(f"{old_line:>6}|{'':>6}|{line}")
            old_line += 1
        elif line.startswith("\\"):
            output.append(line)
        else:
            output.append(f"{old_line:>6}|{new_line:>6}|{line}")
            old_line += 1
            new_line += 1
    return "\n".join(output) + ("\n" if output else "")


def changed_count(patch):
    return sum(1 for line in patch.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))


def untracked_patch(repo):
    files = git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    chunks = []
    for rel in files:
        if not rel or not is_frontend(rel):
            continue
        result = git(repo, "diff", "--no-index", "--", "/dev/null", rel, check=False)
        chunks.append(result.stdout)
    return "".join(chunks)


def collect_patch(repo, base, head):
    if head:
        raw = git(repo, "diff", "--find-renames", "--no-color", "--unified=40", f"{base}...{head}", "--", timeout=90).stdout
    else:
        raw = git(repo, "diff", "--find-renames", "--no-color", "--unified=40", base, "--", timeout=90).stdout
        raw += untracked_patch(repo)
    included, excluded = [], []
    chunks = []
    for chunk in split_chunks(raw):
        path = path_from_chunk(chunk)
        if is_frontend(path):
            included.append(path)
            chunks.append(sanitize_chunk(chunk, path))
        elif path:
            excluded.append(path)
    return "".join(chunks), sorted(set(included)), sorted(set(excluded))


def detect_frameworks(repo, files):
    text = ""
    package = os.path.join(repo, "package.json")
    try:
        with open(package, encoding="utf-8") as handle:
            text = handle.read(256_000)
    except OSError:
        pass
    frameworks = []
    if re.search(r'"next"\s*:', text):
        frameworks.append("nextjs")
    elif re.search(r'"react"\s*:', text) or any(path.endswith((".jsx", ".tsx")) for path in files):
        frameworks.append("react")
    if re.search(r'"@angular/core"\s*:', text) or "angular.json" in files:
        frameworks.append("angular")
    if re.search(r'"angular"\s*:', text) and "@angular/core" not in text:
        frameworks.append("angularjs")
    return frameworks


def changed_text(patch):
    return "\n".join(
        line[1:] for line in patch.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )


def is_risk_config(path):
    name = os.path.basename(path)
    return name in {".npmrc", "angular.json"} or name.startswith(".env") or name.startswith("next.config.")


def detect_signals(patch, files):
    changed = changed_text(patch)
    signals = [name for name, pattern in SIGNALS.items() if pattern.search(changed)]
    if any(re.search(r"(^|/)route\.(?:ts|js)$", path) for path in files):
        signals.append("server_boundary")
    if any(is_risk_config(path) for path in files):
        signals.append("config")
    return sorted(set(signals))


def choose_mode(explicit, line_count, file_count, signals):
    if explicit:
        return explicit, f"使用者指定 {explicit}"
    reasons = []
    if line_count > 500:
        reasons.append(f"前端 diff {line_count} 行")
    if file_count > 20:
        reasons.append(f"前端 diff {file_count} 個檔案")
    if signals:
        reasons.append("高風險訊號：" + "、".join(signals))
    return ("deep", "；".join(reasons)) if reasons else ("standard", "一般規模且未偵測到高風險訊號")


def best_effort_checks(repo, files, use_worktree):
    if use_worktree:
        return ({"status": "skipped", "reason": "range worktree 不執行本機 lint"},
                {"status": "skipped", "reason": "range worktree 不執行本機 typecheck"})
    eslint = os.path.join(repo, "node_modules", ".bin", "eslint")
    lint_files = [path for path in files if os.path.splitext(path)[1] in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"} and os.path.exists(os.path.join(repo, path))]
    if os.path.isfile(eslint) and lint_files:
        try:
            result = run([eslint, "--format", "json", *lint_files], cwd=repo, timeout=120, check=False)
            lint = {"status": "passed" if result.returncode == 0 else "failed", "output": redact((result.stdout or result.stderr)[-20000:])}
        except subprocess.TimeoutExpired:
            lint = {"status": "timeout", "reason": "超過 120 秒"}
    else:
        lint = {"status": "skipped", "reason": "找不到本機 ESLint 或可檢查檔案"}
    tsc = os.path.join(repo, "node_modules", ".bin", "tsc")
    tsconfig = os.path.join(repo, "tsconfig.json")
    if os.path.isfile(tsc) and os.path.isfile(tsconfig) and any(path.endswith((".ts", ".tsx")) for path in files):
        try:
            result = run([tsc, "--noEmit", "--pretty", "false", "-p", tsconfig], cwd=repo, timeout=120, check=False)
            output = redact((result.stdout or result.stderr)[-20000:])
            typecheck = {"status": "passed" if result.returncode == 0 else "failed", "output": output}
        except subprocess.TimeoutExpired:
            typecheck = {"status": "timeout", "reason": "超過 120 秒"}
    else:
        typecheck = {"status": "skipped", "reason": "找不到本機 tsc、tsconfig 或 TypeScript 變更"}
    return lint, typecheck


def add_worktree(repo, head, outdir):
    path = os.path.join(outdir, "worktree")
    result = git(repo, "-c", "core.hooksPath=/dev/null", "worktree", "add", "--detach", path, head, timeout=120, check=False)
    if result.returncode:
        raise ValueError("無法建立 review worktree")
    return path


def prepare(args):
    repo = repo_root(args.repo)
    base = safe_ref(args.base) or default_base(repo)
    head = safe_ref(args.head)
    if head and not args.base:
        raise ValueError("--head 必須搭配 --base")
    focus = args.focus.split(",") if args.focus else list(LENSES)
    if not focus or any(item not in LENSES for item in focus) or len(set(focus)) != len(focus):
        raise ValueError("--focus 只接受 correctness,risk,maintainability")
    token = secrets.token_hex(16)
    outdir = tempfile.mkdtemp(prefix="fe-review.")
    marker = {"token": token, "repo": repo, "worktree": None}
    try:
        patch, files, excluded = collect_patch(repo, base, head)
        if not patch.strip():
            shutil.rmtree(outdir)
            return {"status": "empty", "repo": repo, "excluded_files": excluded}
        review_root = repo
        if head:
            review_root = add_worktree(repo, head, outdir)
            marker["worktree"] = review_root
        lines = changed_count(patch)
        signals = detect_signals(patch, files)
        mode, reason = choose_mode(args.mode, lines, len(files), signals)
        if args.checks:
            lint, typecheck = best_effort_checks(repo, files, bool(head))
        else:
            lint = {"status": "skipped", "reason": "未要求執行本機檢查"}
            typecheck = {"status": "skipped", "reason": "未要求執行本機檢查"}
        numbered = number_patch(patch)
        diff_path = os.path.join(outdir, "diff.patch")
        with open(diff_path, "w", encoding="utf-8") as handle:
            handle.write(numbered)
        spec_path = None
        if args.spec:
            with open(os.path.abspath(os.path.expanduser(args.spec)), encoding="utf-8") as handle:
                spec = redact(handle.read(65_537))
            if len(spec) > 65_536:
                raise ValueError("Spec 超過 64KB")
            spec_path = os.path.join(outdir, "spec.md")
            with open(spec_path, "w", encoding="utf-8") as handle:
                handle.write(spec)
        context = {
            "repo": repo,
            "review_root": review_root,
            "base": base,
            "head": head,
            "mode": mode,
            "mode_reason": reason,
            "focus": focus,
            "frameworks": detect_frameworks(review_root, files),
            "files": files,
            "excluded_files": excluded,
            "changed_line_count": lines,
            "risk_signals": signals,
            "lint": lint,
            "typecheck": typecheck,
            "spec": spec_path,
        }
        context_path = os.path.join(outdir, "context.json")
        with open(context_path, "w", encoding="utf-8") as handle:
            json.dump(context, handle, ensure_ascii=False, indent=2)
        with open(os.path.join(outdir, ".fe-review-marker.json"), "w", encoding="utf-8") as handle:
            json.dump(marker, handle)
        return {"status": "ok", "dir": outdir, "token": token, "context": context_path, "diff": diff_path, **context}
    except Exception:
        if marker["worktree"]:
            git(repo, "worktree", "remove", "--force", marker["worktree"], timeout=60, check=False)
        shutil.rmtree(outdir, ignore_errors=True)
        raise


def cleanup(path, token):
    real = os.path.realpath(path)
    temp_root = os.path.realpath(tempfile.gettempdir())
    if os.path.dirname(real) != temp_root or not os.path.basename(real).startswith("fe-review."):
        raise ValueError("拒絕清理非 review 暫存目錄")
    marker_path = os.path.join(real, ".fe-review-marker.json")
    with open(marker_path, encoding="utf-8") as handle:
        marker = json.load(handle)
    if marker.get("token") != token:
        raise ValueError("cleanup token 不符")
    worktree = marker.get("worktree")
    repo = marker.get("repo")
    if worktree and repo:
        git(repo, "worktree", "remove", "--force", worktree, timeout=60, check=False)
    shutil.rmtree(real)
    return {"status": "cleaned", "dir": real}


def main(argv=None):
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cleanup"))
    parser.add_argument("--repo")
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--mode", choices=("standard", "deep"))
    parser.add_argument("--focus")
    parser.add_argument("--spec")
    parser.add_argument("--checks", action="store_true")
    parser.add_argument("--dir")
    parser.add_argument("--token")
    args = parser.parse_args(raw_args)
    try:
        if args.command == "prepare":
            if not args.repo:
                parser.error("prepare 需要 --repo")
            result = prepare(args)
        else:
            if not args.dir or not args.token:
                parser.error("cleanup 需要 --dir 與 --token")
            result = cleanup(args.dir, args.token)
    except (OSError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
