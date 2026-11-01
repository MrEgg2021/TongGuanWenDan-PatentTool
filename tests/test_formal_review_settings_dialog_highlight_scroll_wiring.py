import unittest

from tests.formal_review_settings_dialog_source_loader import load_formal_review_settings_dialog_source


class FormalReviewSettingsDialogHighlightScrollWiringTests(unittest.TestCase):
    def test_highlight_tab_uses_vertical_scroll_area(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn("scroll = QScrollArea()", source)
        self.assertIn("scroll.setWidgetResizable(True)", source)
        self.assertIn("scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)", source)
        self.assertIn("scroll.setWidget(card)", source)
        self.assertIn("layout.addWidget(scroll, 1)", source)


if __name__ == "__main__":
    unittest.main()
