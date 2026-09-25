import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SkillShapeTest(unittest.TestCase):
    def test_runtime_shape_stays_small(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "agents")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "scripts", "aggregate.py")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "scripts", "profile_repos.py")))
        self.assertEqual(sorted(os.listdir(os.path.join(ROOT, "references"))), [
            "framework-notes.md",
            "review-checklist.md",
        ])

    def test_skill_entrypoint_is_concise(self):
        with open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertLessEqual(len(text.splitlines()), 70)
        self.assertNotIn("profile", text.lower())
        self.assertNotIn("aggregate", text.lower())


if __name__ == "__main__":
    unittest.main()
