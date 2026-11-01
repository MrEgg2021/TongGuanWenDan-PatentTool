import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewIssuePreviewSingleBoxTests(unittest.TestCase):
    def test_right_panel_uses_single_preview_box(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        page_text = read_formal_review_page_source(repo_root)
        self.assertIn("context_before.setVisible(False)", page_text)
        self.assertIn("context_hit.setVisible(False)", page_text)
        self.assertIn("context_after.setVisible(False)", page_text)
        self.assertNotIn("right_layout.addWidget(context_before", page_text)
        self.assertNotIn("right_layout.addWidget(context_hit", page_text)
        self.assertNotIn("right_layout.addWidget(context_after", page_text)

    def test_preview_window_uses_10_char_context_and_underlined_hit(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("_CONTEXT_RADIUS = 10", text)
        self.assertIn("before_text = source[max(0, start - _CONTEXT_RADIUS) : start]", text)
        self.assertIn("after_text = source[end : min(len(source), end + _CONTEXT_RADIUS)]", text)
        self.assertIn("text-decoration: underline", text)


if __name__ == "__main__":
    unittest.main()
