import unittest
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewDiffPreviewToggleWiringTests(unittest.TestCase):
    def test_page_removes_preview_toggle_and_signal(self) -> None:
        text = read_formal_review_page_source()
        self.assertNotIn('preview_toggle = QPushButton("修订预览")', text)
        self.assertNotIn("on_formal_review_diff_preview_toggled", text)
        self.assertIn("window.formal_review_diff_preview_toggle = None", text)

    def test_page_no_longer_mounts_section_preview_stacks(self) -> None:
        text = read_formal_review_page_source()
        self.assertNotIn("desc_stack = QStackedWidget()", text)
        self.assertNotIn("abstract_stack = QStackedWidget()", text)
        self.assertNotIn("drawings_stack = QStackedWidget()", text)
        self.assertIn("window.formal_review_description_preview = None", text)
        self.assertIn("window.formal_review_abstract_preview = None", text)
        self.assertIn("window.formal_review_drawings_preview = None", text)


if __name__ == "__main__":
    unittest.main()
