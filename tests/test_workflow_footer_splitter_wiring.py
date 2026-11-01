import unittest
from pathlib import Path


class WorkflowFooterSplitterWiringTests(unittest.TestCase):
    def test_ui_layout_contains_footer_splitter_with_expected_children(self) -> None:
        source = Path("gui/ui_layout.py").read_text(encoding="utf-8")
        self.assertIn('workflow_footer_splitter.setObjectName("WorkflowFooterSplitter")', source)
        self.assertIn("workflow_footer_splitter.setChildrenCollapsible(False)", source)
        self.assertIn("workflow_footer_splitter.setHandleWidth(8)", source)
        self.assertIn("workflow_footer_splitter.addWidget(home_splitter)", source)
        self.assertIn("workflow_footer_splitter.addWidget(workflow_footer_panel)", source)
        self.assertIn("scroll_content_layout.addWidget(workflow_footer_splitter)", source)
        self.assertIn("workflow_footer_layout.addWidget(warn_frame)", source)
        self.assertIn("workflow_footer_layout.addWidget(actions)", source)
        self.assertIn("self.workflow_footer_splitter = workflow_footer_splitter", source)


if __name__ == "__main__":
    unittest.main()
