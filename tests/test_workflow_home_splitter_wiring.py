import unittest
from pathlib import Path


class WorkflowHomeSplitterWiringTests(unittest.TestCase):
    def test_ui_layout_uses_home_splitter_for_content_and_bottom_cards(self) -> None:
        source = Path("gui/ui_layout.py").read_text(encoding="utf-8")
        self.assertIn('home_splitter.setObjectName("WorkflowHomeSplitter")', source)
        self.assertIn("home_splitter.setChildrenCollapsible(False)", source)
        self.assertIn("home_splitter.setHandleWidth(8)", source)
        self.assertIn("home_splitter.addWidget(content_row)", source)
        self.assertIn("home_splitter.addWidget(bottom_card)", source)
        self.assertIn("workflow_footer_splitter.addWidget(home_splitter)", source)
        self.assertNotIn("scroll_content_layout.addWidget(content_row)", source)
        self.assertNotIn("scroll_content_layout.addWidget(bottom_card)", source)
        self.assertIn("self.workflow_home_splitter = home_splitter", source)
        self.assertIn("self.workflow_footer_splitter = workflow_footer_splitter", source)
        self.assertIn("self._workflow_widgets = [workflow_footer_splitter]", source)
        self.assertIn("self._conversion_widgets = [workflow_footer_splitter]", source)


if __name__ == "__main__":
    unittest.main()
