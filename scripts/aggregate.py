#!/usr/bin/env python3
"""Validate, deduplicate, and order frontend review findings."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys


SEVERITY = {"critical": 0, "high": 1, "medium": 2, "low": 3}
CONFIDENCE = {"high": 0, "medium": 1, "low": 2}
LENSES = {"correctness", "risk", "maintainability"}
REQUIRED = ("severity", "confidence", "file", "line", "summary", "impact", "suggestion")


def normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def validate_finding(raw, lens, context):
    if not isinstance(raw, dict) or any(key not in raw for key in REQUIRED):
        return None, "finding 欄位不完整"
    if raw["severity"] not in SEVERITY or raw["confidence"] not in CONFIDENCE:
        return None, "severity 或 confidence 無效"
    if not isinstance(raw["file"], str) or raw["file"] not in context["review_lines"]:
        return None, "file 不在審查範圍"
    if not isinstance(raw["line"], int) or raw["line"] not in context["review_lines"][raw["file"]]:
        return None, "line 不是 diff 變更行"
    if any(not isinstance(raw[key], str) or not raw[key].strip() for key in ("summary", "impact", "suggestion")):
        return None, "文字欄位不可為空"
    finding = {key: raw[key] for key in REQUIRED}
    finding["lens"] = lens
    return finding, None


def same_problem(left, right):
    if left["file"] != right["file"] or abs(left["line"] - right["line"]) > 2:
        return False
    return difflib.SequenceMatcher(None, normalize(left["summary"]), normalize(right["summary"])).ratio() >= 0.65


def stronger(left, right):
    return min((left, right), key=lambda item: (SEVERITY[item["severity"]], CONFIDENCE[item["confidence"]]))


def aggregate(payload, context):
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise ValueError("results 必須是陣列")
    findings = []
    invalid = []
    incomplete = []
    allowed = set(context.get("focus") or LENSES)
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            invalid.append({"result": index, "reason": "result 不是物件"})
            continue
        lens = result.get("lens")
        if lens not in LENSES or lens not in allowed:
            invalid.append({"result": index, "reason": "lens 不在審查範圍"})
            continue
        if result.get("status") == "partial":
            incomplete.append({"lens": lens, "notes": str(result.get("notes", "未說明"))})
        items = result.get("findings")
        if not isinstance(items, list):
            invalid.append({"result": index, "reason": "findings 不是陣列"})
            continue
        for item_index, raw in enumerate(items):
            finding, reason = validate_finding(raw, lens, context)
            if reason:
                invalid.append({"result": index, "finding": item_index, "reason": reason})
                continue
            duplicate = next((pos for pos, old in enumerate(findings) if same_problem(old, finding)), None)
            if duplicate is None:
                findings.append(finding)
            else:
                findings[duplicate] = stronger(findings[duplicate], finding)
    findings.sort(key=lambda item: (SEVERITY[item["severity"]], item["file"], item["line"]))
    if any(item["severity"] in ("critical", "high") for item in findings):
        verdict = "block"
    elif any(item["severity"] == "medium" for item in findings):
        verdict = "fix-first"
    else:
        verdict = "ok"
    return {"verdict": verdict, "findings": findings, "invalid": invalid, "incomplete": incomplete}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.context, encoding="utf-8") as handle:
            context = json.load(handle)
        payload = json.load(sys.stdin)
        result = aggregate(payload, context)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
