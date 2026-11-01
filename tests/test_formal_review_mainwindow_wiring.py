import unittest
from pathlib import Path


class FormalReviewMainWindowWiringTests(unittest.TestCase):
    def test_mainwindow_includes_formal_review_mixin(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui_app.py").read_text(encoding="utf-8")
        self.assertIn("from gui.main_window.mixins.formal_review_mixin import FormalReviewMixin", text)
        self.assertIn("OfficialDocsMixin,", text)
        self.assertIn("FormalReviewMixin,", text)


if __name__ == "__main__":
    unittest.main()
