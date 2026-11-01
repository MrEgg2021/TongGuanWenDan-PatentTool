import unittest
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewSingleSectionNoChangePlaceholderTests(unittest.TestCase):
    def test_page_removes_single_section_no_change_placeholders(self) -> None:
        text = read_formal_review_page_source()
        self.assertNotIn('desc_no_change_label = QLabel("本Tab无改动")', text)
        self.assertNotIn('abstract_no_change_label = QLabel("本Tab无改动")', text)
        self.assertNotIn('drawings_no_change_label = QLabel("本Tab无改动")', text)
        self.assertIn("window.formal_review_description_no_change_label = None", text)
        self.assertIn("window.formal_review_abstract_no_change_label = None", text)
        self.assertIn("window.formal_review_drawings_no_change_label = None", text)

    def test_mixin_removes_placeholder_visibility_logic(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn("show_empty = bool(only_changed_active and not section_changed)", text)
        self.assertNotIn("stack.setVisible(not show_empty)", text)
        self.assertNotIn("label.setVisible(show_empty)", text)


if __name__ == "__main__":
    unittest.main()
