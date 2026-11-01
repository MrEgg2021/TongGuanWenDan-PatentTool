import unittest
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewPlainWorkspaceWiringTests(unittest.TestCase):
    def test_page_keeps_plain_text_tabs_on_center_panel(self) -> None:
        text = read_formal_review_page_source()
        self.assertIn('tabs.addTab(claims_tab, "权利要求书")', text)
        self.assertIn('tabs.addTab(desc_tab, "说明书")', text)
        self.assertIn("center_layout.addWidget(tabs, 1)", text)
        self.assertIn("window.formal_review_plain_center_panel = center_panel", text)

    def test_plain_mode_attaches_center_panel_back(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _attach_plain_center_panel(self) -> None:", text)
        self.assertIn("self._apply_plain_workspace_layout()", text)
        self.assertIn("self._set_splitter_order(splitter, [left_panel, center_panel, right_panel])", text)
        self.assertIn("self.formal_review_center_panel_attached = True", text)
        self.assertIn("self._attach_plain_center_panel()", text)


if __name__ == "__main__":
    unittest.main()
