import unittest
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewCompanionWorkspaceWiringTests(unittest.TestCase):
    def test_page_does_not_build_companion_center_workspace(self) -> None:
        text = read_formal_review_page_source()
        self.assertNotIn('center_mode_stack = QStackedWidget()', text)
        self.assertNotIn('companion_workspace = QWidget()', text)
        self.assertNotIn('FormalReviewCompanionWorkspace', text)
        self.assertIn("window.formal_review_plain_center_panel = center_panel", text)

    def test_word_mode_detaches_center_panel_from_splitter(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _detach_plain_center_panel(self) -> None:", text)
        self.assertIn("def _set_splitter_order(splitter, widgets: list[QWidget]) -> None:", text)
        self.assertIn("widget.setParent(None)", text)
        self.assertIn("def _apply_companion_workspace_layout(self) -> None:", text)
        self.assertIn("self._set_splitter_order(splitter, [right_panel, left_panel])", text)
        self.assertIn("self._detach_plain_center_panel()", text)


if __name__ == "__main__":
    unittest.main()
