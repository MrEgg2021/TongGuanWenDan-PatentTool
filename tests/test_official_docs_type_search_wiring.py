from __future__ import annotations

import unittest
from pathlib import Path
from tests.official_docs_source_loader import read_official_docs_page_source


class OfficialDocsTypeSearchWiringTests(unittest.TestCase):
    def test_settings_page_wires_type_search_box(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('type_search_edit.setObjectName("OfficialDocsTypeSearch")', text)
        self.assertIn("window.official_docs_settings_type_search_edit = type_search_edit", text)
        self.assertIn("type_search_edit.textChanged.connect(window.on_official_docs_type_search_changed)", text)

    def test_settings_type_widget_uses_tree(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('type_tree = OfficialDocsNamingTypeTree()', text)
        self.assertIn('type_tree.setObjectName("OfficialDocsTypeTree")', text)
        self.assertIn("window.official_docs_settings_type_tree = type_tree", text)


if __name__ == "__main__":
    unittest.main()
