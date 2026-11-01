from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QTreeWidget

    from gui.main_window.mixins.official_docs_ops import state_ops, type_list_ops
    from gui.main_window.mixins.official_docs_ops.shared import TYPE_NODE_KIND_UNGROUPED_ROOT

    _PYSIDE6_AVAILABLE = True
except Exception:
    QApplication = None  # type: ignore[assignment]
    QTreeWidget = object  # type: ignore[assignment]
    state_ops = None  # type: ignore[assignment]
    type_list_ops = None  # type: ignore[assignment]
    TYPE_NODE_KIND_UNGROUPED_ROOT = "ungrouped_root"
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:
    class _NamingTreeHost:
        _current_type_selection_context = type_list_ops._current_type_selection_context
        _set_type_selection_context = type_list_ops._set_type_selection_context
        _build_type_tree_payload = type_list_ops._build_type_tree_payload
        _refresh_official_docs_type_list = type_list_ops._refresh_official_docs_type_list
        _normalize_naming_groups_payload = state_ops._normalize_naming_groups_payload
        _serialize_naming_group = state_ops._serialize_naming_group

        def __init__(self) -> None:
            self._official_docs_working_settings = {
                "naming_groups": [
                    {
                        "id": "group-a",
                        "name": "审查通知类",
                        "member_type_keys": ["exam_opinion", "rectification"],
                        "group_config": {},
                    }
                ],
                "type_group_membership": {
                    "exam_opinion": "group-a",
                    "rectification": "group-a",
                },
                "type_configs": {},
            }
            self._official_docs_current_type = "exam_opinion"
            self._official_docs_type_search_text = ""
            self._official_docs_type_members_by_primary = {}
            self._official_docs_type_tree_rebuilding = False
            self._official_docs_type_tree_checked_state = {
                "group_ids": [],
                "type_keys": [],
                "ungrouped_root_checked": False,
            }
            self._official_docs_type_selection_context = {
                "node_kind": TYPE_NODE_KIND_UNGROUPED_ROOT,
                "group_id": "",
                "type_key": "",
                "member_keys": [],
                "display_name": "",
            }
            self.official_docs_settings_type_tree = QTreeWidget()
            self.official_docs_settings_type_tree.setColumnCount(1)

        def _get_official_docs_settings_snapshot(self, sync_current_type: bool = False) -> dict[str, object]:
            return self._official_docs_working_settings

        def _serialize_type_cfg(self, cfg):
            return state_ops._serialize_type_cfg(self, cfg)

        def _collect_available_type_entries(self) -> list[dict[str, object]]:
            return [
                {"key": "exam_opinion", "display_name": "审查意见通知书", "processable": True, "disabled_reason": "", "is_new": False},
                {"key": "rectification", "display_name": "补正通知书", "processable": True, "disabled_reason": "", "is_new": False},
                {"key": "certificate", "display_name": "证书类", "processable": True, "disabled_reason": "", "is_new": False},
            ]

        def _refresh_official_docs_type_action_buttons(self) -> None:
            return None
else:
    class _NamingTreeHost:
        pass


@unittest.skipUnless(_PYSIDE6_AVAILABLE, "PySide6 not installed")
class OfficialDocsNamingTreeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_group_nodes_show_member_count_but_leaf_nodes_stay_simple(self) -> None:
        host = _NamingTreeHost()
        host._refresh_official_docs_type_list()
        self._app.processEvents()

        tree = host.official_docs_settings_type_tree
        self.assertGreaterEqual(tree.topLevelItemCount(), 2)
        self.assertEqual(tree.topLevelItem(0).text(0), "审查通知类 (2)")
        self.assertEqual(tree.topLevelItem(0).child(0).text(0), "审查意见通知书")
        self.assertEqual(tree.topLevelItem(0).child(1).text(0), "补正通知书")
        self.assertEqual(tree.topLevelItem(1).text(0), "其他（未分组） (1)")


if __name__ == "__main__":
    unittest.main()
