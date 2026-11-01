import unittest
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewCompanionNoCenterPanelTests(unittest.TestCase):
    def test_page_removes_center_mode_stack_nodes(self) -> None:
        text = read_formal_review_page_source()
        self.assertNotIn("FormalReviewCenterModeStack", text)
        self.assertNotIn("FormalReviewCompanionWorkspace", text)
        self.assertIn("window.formal_review_plain_center_panel = center_panel", text)

    def test_mixin_has_attach_detach_panel_helpers(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _attach_plain_center_panel(self) -> None:", text)
        self.assertIn("def _detach_plain_center_panel(self) -> None:", text)


if __name__ == "__main__":
    unittest.main()
