import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_page_source


class OfficialDocsLayoutCompactWiringTests(unittest.TestCase):
    def test_task_footer_start_button_is_fixed_and_centered(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('task_footer.setObjectName("OfficialDocsTaskFooter")', text)
        self.assertIn('body_splitter.setObjectName("OfficialDocsTaskSplitter")', text)
        self.assertIn("task_footer_row.addStretch(1)", text)
        self.assertIn("task_footer_row.addWidget(btn_start, 0)", text)
        self.assertIn("task_footer_row.addWidget(btn_start, 0)\n    task_footer_row.addStretch(1)", text)
        self.assertIn("window.official_docs_start_button = btn_start", text)
        self.assertNotIn("detail_layout.addWidget(btn_start)", text)

    def test_detail_panel_is_info_only_and_source_actions_removed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('detail_title = QLabel("命名预览 / 处理结果")', text)
        self.assertIn('pdf_sources_text.setObjectName("OfficialDocsPdfSourcesText")', text)
        self.assertIn("window.official_docs_pdf_sources_text = pdf_sources_text", text)
        self.assertNotIn("btn_open_location = QPushButton(", text)
        self.assertNotIn("btn_open_pdf = QPushButton(", text)
        self.assertNotIn("OfficialDocsPdfList", text)
        self.assertNotIn("on_official_docs_open_selected_location", text)
        self.assertNotIn("on_official_docs_open_selected_pdf", text)

    def test_subtitle_removed_under_title(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertNotIn("导入官方通知书 ZIP", text)

    def test_task_tree_compact_spacing_and_selection_visual_wiring(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        page_text = read_official_docs_page_source(repo_root)
        qss_text = (repo_root / "gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn("tree.setIndentation(6)", page_text)
        self.assertIn("QTreeWidget#OfficialDocsTree::item", qss_text)
        self.assertIn("QTreeWidget#OfficialDocsTree::item:selected", qss_text)
        self.assertNotIn("QListWidget#OfficialDocsPdfList::item", qss_text)


if __name__ == "__main__":
    unittest.main()
