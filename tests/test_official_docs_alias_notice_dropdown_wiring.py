from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsAliasNoticeDropdownWiringTests(unittest.TestCase):
    def test_alias_notice_name_uses_dropdown_not_free_text(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        mixin_text = read_official_docs_mixin_source(repo_root)
        page_text = read_official_docs_page_source(repo_root)
        self.assertIn("class _AliasNoticeNameDelegate(QStyledItemDelegate):", page_text)
        self.assertIn("table.setItemDelegateForColumn(1, _AliasNoticeNameDelegate(table))", page_text)
        self.assertIn("def _set_alias_notice_item(", mixin_text)
        self.assertIn("notice_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)", mixin_text)
        self.assertIn("notice_item.setData(Qt.UserRole, clean_options)", mixin_text)
        self.assertNotIn("table.setCellWidget(row, 1", mixin_text)

    def test_add_alias_rule_defaults_to_current_type_notice_name(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("options = self._current_type_alias_notice_options(", text)
        self.assertIn("default_notice_name = options[0] if options else \"\"", text)
        self.assertIn("self._set_alias_notice_item(", text)


if __name__ == "__main__":
    unittest.main()
