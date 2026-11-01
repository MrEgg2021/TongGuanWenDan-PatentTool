import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsTreeHorizontalScrollWiringTests(unittest.TestCase):
    def test_tree_horizontal_scroll_enabled_as_needed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)", text)
        self.assertIn("tree.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)", text)
        self.assertIn("tree.setTextElideMode(Qt.ElideNone)", text)
        self.assertIn("header = tree.header()", text)
        self.assertIn("header.setStretchLastSection(False)", text)
        self.assertIn("header.setSectionResizeMode(0, QHeaderView.Interactive)", text)

    def test_tree_column_width_is_refreshed_after_render(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("tree.resizeColumnToContents(0)", text)
        self.assertIn("tree.sizeHintForColumn(0)", text)
        self.assertIn("font_metrics = tree.fontMetrics()", text)
        self.assertIn("max_text_width = 0", text)
        self.assertIn("tree.setColumnWidth(0, target_width + 24)", text)


if __name__ == "__main__":
    unittest.main()
