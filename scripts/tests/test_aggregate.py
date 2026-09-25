import unittest

from helpers import load


aggregate = load("aggregate")


class AggregateTest(unittest.TestCase):
    def setUp(self):
        self.context = {
            "focus": ["correctness", "risk", "maintainability"],
            "review_lines": {"src/App.tsx": [10, 11, 12]},
        }

    def finding(self, **overrides):
        item = {
            "severity": "high",
            "confidence": "high",
            "file": "src/App.tsx",
            "line": 10,
            "summary": "提交時會重複建立資料",
            "impact": "連點兩次時送出兩個請求",
            "suggestion": "送出期間拒絕重入",
        }
        item.update(overrides)
        return item

    def test_validates_deduplicates_and_sorts(self):
        payload = {"results": [
            {"lens": "correctness", "status": "ok", "findings": [self.finding()]},
            {"lens": "risk", "status": "ok", "findings": [self.finding(summary="重複提交會建立兩筆資料")]},
            {"lens": "maintainability", "status": "ok", "findings": [self.finding(severity="low", line=12, summary="名稱與行為矛盾")]},
        ]}
        result = aggregate.aggregate(payload, self.context)
        self.assertEqual(result["verdict"], "block")
        self.assertEqual(len(result["findings"]), 2)
        self.assertEqual(result["findings"][0]["severity"], "high")

    def test_rejects_bad_line_and_lens_outside_focus(self):
        self.context["focus"] = ["correctness"]
        payload = {"results": [
            {"lens": "correctness", "status": "ok", "findings": [self.finding(line=99)]},
            {"lens": "risk", "status": "ok", "findings": []},
        ]}
        result = aggregate.aggregate(payload, self.context)
        self.assertEqual(result["findings"], [])
        self.assertEqual(len(result["invalid"]), 2)

    def test_medium_requires_fix_and_partial_is_reported(self):
        payload = {"results": [{
            "lens": "correctness", "status": "partial", "notes": "缺少 API schema",
            "findings": [self.finding(severity="medium")],
        }]}
        result = aggregate.aggregate(payload, self.context)
        self.assertEqual(result["verdict"], "fix-first")
        self.assertEqual(result["incomplete"][0]["lens"], "correctness")


if __name__ == "__main__":
    unittest.main()
