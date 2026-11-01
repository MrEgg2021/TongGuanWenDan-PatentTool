import unittest
from pathlib import Path


class LayoutSplittersAllPagesWiringTests(unittest.TestCase):
    def test_all_target_pages_define_splitters_with_non_collapsible_children(self) -> None:
        ui_layout = Path("gui/ui_layout.py").read_text(encoding="utf-8")
        single_panel = Path("gui/ui_layout_impl/single_panel.py").read_text(encoding="utf-8")
        batch_panel = Path("gui/ui_layout_impl/batch_panel.py").read_text(encoding="utf-8")
        task_panel = Path("gui/ui_layout_impl/official_docs_page_parts/task_panel.py").read_text(encoding="utf-8")
        preview_page = Path("gui/ui_layout_impl/preview_page.py").read_text(encoding="utf-8")

        self.assertIn('home_splitter.setObjectName("WorkflowHomeSplitter")', ui_layout)
        self.assertIn("home_splitter.setChildrenCollapsible(False)", ui_layout)
        self.assertIn("home_splitter.addWidget(content_row)", ui_layout)
        self.assertIn("home_splitter.addWidget(bottom_card)", ui_layout)
        self.assertIn('workflow_footer_splitter.setObjectName("WorkflowFooterSplitter")', ui_layout)
        self.assertIn("workflow_footer_splitter.setChildrenCollapsible(False)", ui_layout)
        self.assertIn("workflow_footer_splitter.addWidget(home_splitter)", ui_layout)

        self.assertIn('single_main_splitter.setObjectName("SingleMainSplitter")', single_panel)
        self.assertIn("single_main_splitter.setChildrenCollapsible(False)", single_panel)

        self.assertIn('batch_main_splitter.setObjectName("BatchMainSplitter")', batch_panel)
        self.assertIn("batch_main_splitter.setChildrenCollapsible(False)", batch_panel)

        self.assertIn('task_vertical_splitter.setObjectName("OfficialDocsTaskVerticalSplitter")', task_panel)
        self.assertIn("task_vertical_splitter.setChildrenCollapsible(False)", task_panel)
        self.assertIn('body_splitter.setObjectName("OfficialDocsTaskSplitter")', task_panel)

        self.assertIn('main_vertical_splitter.setObjectName("PreviewMainVerticalSplitter")', preview_page)
        self.assertIn("main_vertical_splitter.setChildrenCollapsible(False)", preview_page)
        self.assertIn('main_horizontal_splitter.setObjectName("PreviewMainHorizontalSplitter")', preview_page)
        self.assertIn("main_horizontal_splitter.setChildrenCollapsible(False)", preview_page)


if __name__ == "__main__":
    unittest.main()
