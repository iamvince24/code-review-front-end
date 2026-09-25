import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SkillShapeTest(unittest.TestCase):
    def test_only_three_review_agents(self):
        agents = sorted(name for name in os.listdir(os.path.join(ROOT, "agents")) if name.endswith(".md"))
        self.assertEqual(agents, [
            "fe-review-correctness.md",
            "fe-review-maintainability.md",
            "fe-review-risk.md",
        ])

    def test_removed_interfaces_are_only_documented_as_removed(self):
        with open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("已移除", text)
        self.assertLessEqual(len(text.splitlines()), 100)


if __name__ == "__main__":
    unittest.main()
