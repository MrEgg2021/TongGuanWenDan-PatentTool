import unittest

from tests.formal_review_settings_dialog_source_loader import load_formal_review_settings_dialog_source


class FormalReviewSettingsDialogCompactLayoutWiringTests(unittest.TestCase):
    def test_tabs_are_non_stretched_and_scrollable(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn("tabs.tabBar().setExpanding(False)", source)
        self.assertIn("tabs.tabBar().setUsesScrollButtons(True)", source)

    def test_compact_sizes_and_single_line_constraints_exist(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn("self.setMinimumSize(860, 620)", source)
        self.assertIn("self.resize(980, 700)", source)
        self.assertIn("self._comment_author_edit.setMaximumWidth(420)", source)
        self.assertIn("self._claim1_word_limit_edit.setMaximumWidth(240)", source)
        self.assertIn("self._claim1_marker_limit_edit.setMaximumWidth(240)", source)

    def test_wordlist_panel_is_two_by_two_compact(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn("top_splitter = QSplitter(Qt.Horizontal)", source)
        self.assertIn("bottom_splitter = QSplitter(Qt.Horizontal)", source)
        self.assertIn("wordlist_splitter = QSplitter(Qt.Vertical)", source)


if __name__ == "__main__":
    unittest.main()
