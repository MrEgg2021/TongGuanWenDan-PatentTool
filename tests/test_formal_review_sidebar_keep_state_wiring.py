import unittest
from pathlib import Path


class FormalReviewSidebarKeepStateWiringTests(unittest.TestCase):
    def test_entry_window_state_no_longer_auto_clicks_sidebar_toggle(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/workspace_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _apply_formal_review_entry_window_state(self) -> None:", source)
        self.assertIn("get_formal_review_auto_maximize", source)
        self.assertIn("if auto_maximize:", source)
        self.assertNotIn("toggle.click()", source)
        self.assertNotIn("sidebar_toggle", source)


if __name__ == "__main__":
    unittest.main()
