from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source


class OfficialDocsTypeGroupConfigSyncTests(unittest.TestCase):
    def test_mixin_has_member_keys_role_and_resolver(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("TYPE_MEMBER_KEYS_ROLE = Qt.UserRole + 103", text)
        self.assertIn("def _resolve_type_group_member_keys(self, primary_key: str) -> list[str]:", text)
        self.assertIn("item.setData(TYPE_MEMBER_KEYS_ROLE, member_keys)", text)

    def test_sync_group_member_only_writes_alias_rules_to_selected_type(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("target_keys = [kind] if node_kind == TYPE_NODE_KIND_GROUP_MEMBER and kind else list(member_keys)", text)
        self.assertIn('serialized["alias_rules"] = list(alias_rows)', text)
        self.assertIn('if node_kind == TYPE_NODE_KIND_UNGROUPED_TYPE:', text)
        self.assertIn("member_keys = self._resolve_type_group_member_keys(kind)", text)


if __name__ == "__main__":
    unittest.main()
