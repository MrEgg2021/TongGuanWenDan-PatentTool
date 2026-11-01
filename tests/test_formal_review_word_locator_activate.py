import unittest
from pathlib import Path


class FormalReviewWordLocatorActivateTests(unittest.TestCase):
    def test_locator_supports_activation_flag(self) -> None:
        text = Path("core/formal_review/word_locator.py").read_text(encoding="utf-8")
        self.assertIn("def locate_issue_in_word(", text)
        self.assertIn("projections: ProjectionBundle | None = None,", text)
        self.assertIn("activate_window: bool = False,", text)
        self.assertIn("if activate_window:", text)
        self.assertIn("_activate_word_window(session)", text)


if __name__ == "__main__":
    unittest.main()
