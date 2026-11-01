import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimPreviewStackWiringTests(unittest.TestCase):
    def test_claim_tree_uses_editor_only_without_preview_stack(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn("content_stack = QStackedWidget()", text)
        self.assertNotIn('content_preview = QTextBrowser()', text)
        self.assertIn("tree.setItemWidget(content_item, 0, content_editor)", text)
        self.assertNotIn("_formal_review_claim_preview_views", text)
        self.assertNotIn("_formal_review_claim_content_stacks[claim_num]", text)


if __name__ == "__main__":
    unittest.main()
