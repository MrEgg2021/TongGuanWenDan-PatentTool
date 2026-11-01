from __future__ import annotations

import unittest
from pathlib import Path

from tests.official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsTypeGroupingWiringTests(unittest.TestCase):
    def test_settings_type_uses_group_tree_with_search(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('type_search_edit.setObjectName("OfficialDocsTypeSearch")', text)
        self.assertIn('type_tree = OfficialDocsNamingTypeTree()', text)
        self.assertIn('type_tree.setObjectName("OfficialDocsTypeTree")', text)
        self.assertIn("type_tree.setIndentation(18)", text)
        self.assertIn('type_guide_label = QLabel("先选分组或类型，再在下方管理。")', text)
        self.assertIn('group_actions_card = QFrame()', text)
        self.assertIn('group_scope_title = QLabel("分组操作")', text)
        self.assertIn('group_member_title = QLabel("成员操作")', text)
        self.assertNotIn('group_actions_title = QLabel("分组管理")', text)
        self.assertNotIn('group_actions_hint = QLabel("先选分组或类型，再在下方管理。")', text)
        self.assertNotIn('group_status_title_label = QLabel("当前选中：未选择")', text)
        self.assertNotIn('group_status_card.setObjectName("OfficialDocsGroupStatusCard")', text)
        self.assertNotIn("window.official_docs_group_status_title_label =", text)
        self.assertNotIn("window.official_docs_naming_focus_status_label =", text)
        self.assertIn("type_search_edit.textChanged.connect(window.on_official_docs_type_search_changed)", text)
        self.assertIn("type_tree.itemChanged.connect(window.on_official_docs_type_tree_item_changed)", text)
        self.assertIn('btn_create_group = QPushButton("新建")', text)
        self.assertIn('btn_add_member = QPushButton("加成员...")', text)
        self.assertIn('button.setProperty("officialDocsGroupAction", True)', text)
        self.assertIn('alias_title.setObjectName("OfficialDocsAliasTitleLabel")', text)
        self.assertIn("mode_layout.addWidget(config_hint_label)", text)

    def test_mixin_contains_tree_roles_and_group_management_handlers(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('self._official_docs_type_search_text = ""', text)
        self.assertIn("def on_official_docs_type_search_changed(self, text: str)", text)
        self.assertIn("TYPE_NODE_KIND_GROUP =", text)
        self.assertIn("TYPE_NODE_KIND_UNGROUPED_ROOT =", text)
        self.assertIn("TYPE_NODE_KIND_GROUP_MEMBER =", text)
        self.assertIn(
            "def on_official_docs_type_tree_item_changed(self, item: QTreeWidgetItem | None, column: int) -> None:",
            text,
        )
        self.assertIn("def _collect_checked_type_tree_targets(self) -> dict[str, Any]:", text)
        self.assertIn("def _clear_checked_type_tree_targets(self) -> None:", text)
        self.assertIn("def _build_type_action_button_states(", text)
        self.assertNotIn("_refresh_official_docs_checked_type_status", text)
        self.assertIn('_OFFICIAL_DOCS_STATIC_METHOD_NAMES = {"_type_tree_context_from_item"}', text)
        self.assertIn("def on_official_docs_create_naming_group(self) -> None:", text)
        self.assertIn("def on_official_docs_add_group_member(self) -> None:", text)
        self.assertIn("def on_official_docs_move_type_to_group(self) -> None:", text)
        self.assertIn("def on_official_docs_remove_type_from_group(self) -> None:", text)


if __name__ == "__main__":
    unittest.main()
