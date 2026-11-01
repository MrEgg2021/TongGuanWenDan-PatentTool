from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_page_source
from gui_source_loader import read_official_docs_dialogs_source


class OfficialDocsCheckboxStyleWiringTests(unittest.TestCase):
    def test_page_checkboxes_use_official_docs_class(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('chk.setProperty("class", "OfficialDocsCheck")', text)

    def test_dialog_checkboxes_use_official_docs_class(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_dialogs_source(repo_root)
        self.assertIn('apply_all.setProperty("class", "OfficialDocsCheck")', text)
        self.assertIn('agree_chk.setProperty("class", "OfficialDocsCheck")', text)

    def test_theme_has_official_docs_checkbox_rules(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn('QCheckBox[class="OfficialDocsCheck"]', text)
        self.assertIn('QCheckBox[class="OfficialDocsCheck"]::indicator:checked', text)
        self.assertIn("QTreeView::indicator", text)
        self.assertIn("QTableView::indicator", text)
        self.assertIn("QListView::indicator", text)


if __name__ == "__main__":
    unittest.main()
