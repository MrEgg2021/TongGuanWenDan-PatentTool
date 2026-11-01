from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFrame, QLabel, QListWidget, QPushButton, QTableWidget

    from gui.main_window.mixins.official_docs_ops import settings_ops, state_ops, type_list_ops
    from gui.main_window.mixins.official_docs_ops.shared import (
        TYPE_NODE_KIND_GROUP,
        TYPE_NODE_KIND_GROUP_MEMBER,
        TYPE_NODE_KIND_UNGROUPED_ROOT,
        TYPE_NODE_KIND_UNGROUPED_TYPE,
        get_type_display_name,
    )
    from gui.main_window.mixins.official_docs_ops.state_ops import _serialize_type_cfg

    _PYSIDE6_AVAILABLE = True
except Exception:
    QApplication = None  # type: ignore[assignment]
    QCheckBox = object  # type: ignore[assignment]
    QComboBox = object  # type: ignore[assignment]
    QFrame = object  # type: ignore[assignment]
    QLabel = object  # type: ignore[assignment]
    QListWidget = object  # type: ignore[assignment]
    QPushButton = object  # type: ignore[assignment]
    QTableWidget = object  # type: ignore[assignment]
    state_ops = None  # type: ignore[assignment]
    type_list_ops = None  # type: ignore[assignment]
    TYPE_NODE_KIND_GROUP = "group"
    TYPE_NODE_KIND_GROUP_MEMBER = "group_member"
    TYPE_NODE_KIND_UNGROUPED_ROOT = "ungrouped_root"
    TYPE_NODE_KIND_UNGROUPED_TYPE = "ungrouped_type"
    get_type_display_name = None  # type: ignore[assignment]
    _serialize_type_cfg = None  # type: ignore[assignment]
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:
    class _NamingScopeHost:
        RECEIPT_TYPE_KEY = "10071|电子提交收据"

        _current_type_selection_context = type_list_ops._current_type_selection_context
        _official_docs_cards_widget = type_list_ops._official_docs_cards_widget
        _set_cards_to_widget = type_list_ops._set_cards_to_widget
        _list_widget_to_cards = type_list_ops._list_widget_to_cards
        _set_alias_notice_item = type_list_ops._set_alias_notice_item
        _alias_notice_name_from_row = type_list_ops._alias_notice_name_from_row
        _resolve_type_group_member_keys = type_list_ops._resolve_type_group_member_keys
        _current_type_alias_notice_options = type_list_ops._current_type_alias_notice_options
        _set_official_docs_naming_scope = type_list_ops._set_official_docs_naming_scope
        _set_filename_fields_card_editable = type_list_ops._set_filename_fields_card_editable
        _card_to_item = type_list_ops._card_to_item
        _pdf_parse_field_widgets = type_list_ops._pdf_parse_field_widgets
        _set_pdf_parse_field_checks_enabled = type_list_ops._set_pdf_parse_field_checks_enabled
        _refresh_official_docs_type_action_buttons = type_list_ops._refresh_official_docs_type_action_buttons
        _load_type_cards_to_ui = type_list_ops._load_type_cards_to_ui
        _sync_current_type_cards_from_ui = type_list_ops._sync_current_type_cards_from_ui
        _refresh_official_docs_naming_mode_labels = settings_ops._refresh_official_docs_naming_mode_labels
        _build_type_tree_payload = type_list_ops._build_type_tree_payload
        _normalize_naming_groups_payload = state_ops._normalize_naming_groups_payload
        _serialize_naming_group = state_ops._serialize_naming_group

        def __init__(self) -> None:
            group_alias_notice = str(get_type_display_name("exam_opinion"))
            self._official_docs_working_settings = {
                "type_configs": {
                    "exam_opinion": {
                        "naming_mode": "default",
                        "filename_fields": ["通知书名称", "申请号"],
                        "alias_rules": [
                            {
                                "notice_name": group_alias_notice,
                                "short_name": "审查",
                                "enabled": True,
                            }
                        ],
                    },
                    "certificate": {
                        "naming_mode": "custom",
                        "filename_fields": ["证书名称", "申请号"],
                        "alias_rules": [
                            {
                                "notice_name": "certificate",
                                "short_name": "证书",
                                "enabled": True,
                            }
                        ],
                    }
                },
                "naming_groups": [
                    {
                        "id": "group-a",
                        "name": "审查通知类",
                        "member_type_keys": ["exam_opinion", "rectification"],
                        "group_config": {
                            "naming_mode": "custom",
                            "filename_fields": ["通知书名称", "申请号"],
                            "alias_rules": [
                                {
                                    "notice_name": group_alias_notice,
                                    "short_name": "分组审查",
                                    "enabled": True,
                                }
                            ],
                        },
                    }
                ],
                "type_group_membership": {
                    "exam_opinion": "group-a",
                    "rectification": "group-a",
                },
            }
            self._official_docs_current_type = "exam_opinion"
            self._official_docs_type_members_by_primary = {
                "exam_opinion": ["exam_opinion", "rectification"],
                "rectification": ["rectification"],
                "certificate": ["certificate"],
            }
            self._official_docs_type_selection_context = {
                "node_kind": TYPE_NODE_KIND_UNGROUPED_ROOT,
                "group_id": "",
                "type_key": "",
                "member_keys": [],
                "display_name": "",
            }
            self._official_docs_signals_blocked = False
            self._official_docs_alias_loading = False
            self._checked_targets = {
                "group_ids": [],
                "type_contexts": [],
                "group_member_contexts": [],
                "ungrouped_type_contexts": [],
                "checked_group_count": 0,
                "checked_type_count": 0,
            }

            self.official_docs_naming_mode_combo = QComboBox()
            self.official_docs_naming_mode_combo.addItem("默认", "default")
            self.official_docs_naming_mode_combo.addItem("自定义", "custom")
            self.official_docs_filename_fields_card = QFrame()
            self.official_docs_alias_card = QFrame()
            self.official_docs_filename_fields_list = QListWidget()
            self.official_docs_alias_title_label = QLabel()
            self.official_docs_alias_table = QTableWidget(0, 3)
            self.official_docs_add_alias_button = QPushButton()
            self.official_docs_remove_alias_button = QPushButton()
            self.official_docs_naming_scope_label = QLabel()
            self.official_docs_naming_scope_hint_label = QLabel()
            self.official_docs_filename_preview_label = QLabel()
            self.official_docs_chk_exam_pdf_parse = QCheckBox()
            self.official_docs_pdf_parse_fields_wrap = QFrame()
            self.official_docs_pdf_parse_field_checks = {}
            self.official_docs_create_group_button = QPushButton()
            self.official_docs_rename_group_button = QPushButton()
            self.official_docs_delete_group_button = QPushButton()
            self.official_docs_add_group_member_button = QPushButton()
            self.official_docs_join_group_button = QPushButton()
            self.official_docs_move_group_button = QPushButton()
            self.official_docs_remove_group_button = QPushButton()

        def _init_official_docs_state(self) -> None:
            return None

        def _get_official_docs_settings_snapshot(self, sync_current_type: bool = False) -> dict[str, object]:
            return self._official_docs_working_settings

        def _serialize_type_cfg(self, cfg):
            return _serialize_type_cfg(self, cfg)

        def _collect_available_type_entries(self) -> list[dict[str, object]]:
            return [
                {"key": "exam_opinion", "display_name": "审查意见通知书", "processable": True, "disabled_reason": "", "is_new": False},
                {"key": "rectification", "display_name": "补正通知书", "processable": True, "disabled_reason": "", "is_new": False},
                {"key": "certificate", "display_name": "证书类", "processable": True, "disabled_reason": "", "is_new": False},
            ]

        def _collect_checked_type_tree_targets(self) -> dict[str, object]:
            return dict(self._checked_targets)

        def _refresh_official_docs_settings_preview_line(self) -> None:
            return None
else:
    class _NamingScopeHost:
        pass


@unittest.skipUnless(_PYSIDE6_AVAILABLE, "PySide6 not installed")
class OfficialDocsNamingScopeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.host = _NamingScopeHost()

    def test_group_focus_loads_group_editor_state(self) -> None:
        self.host._official_docs_type_selection_context = {
            "node_kind": TYPE_NODE_KIND_GROUP,
            "group_id": "group-a",
            "type_key": "exam_opinion",
            "member_keys": ["exam_opinion", "rectification"],
            "display_name": "审查通知类",
        }

        self.host._load_type_cards_to_ui("exam_opinion")
        self._app.processEvents()

        self.assertIn("当前编辑：分组“审查通知类”", self.host.official_docs_naming_scope_label.text())
        self.assertEqual(self.host.official_docs_alias_title_label.text(), "通知书简称规则")
        self.assertTrue(self.host.official_docs_alias_card.isHidden())
        self.assertTrue(self.host.official_docs_naming_mode_combo.isEnabled())
        self.assertEqual(self.host.official_docs_filename_fields_list.count(), 2)
        self.assertEqual(self.host.official_docs_alias_table.rowCount(), 0)
        self.assertFalse(self.host.official_docs_naming_scope_hint_label.isVisible())

    def test_mixed_receipt_group_focus_shows_field_system_hint(self) -> None:
        self.host._official_docs_working_settings["naming_groups"][0]["member_type_keys"] = [
            "exam_opinion",
            self.host.RECEIPT_TYPE_KEY,
        ]
        self.host._official_docs_working_settings["type_group_membership"] = {
            "exam_opinion": "group-a",
            self.host.RECEIPT_TYPE_KEY: "group-a",
        }
        self.host._official_docs_type_selection_context = {
            "node_kind": TYPE_NODE_KIND_GROUP,
            "group_id": "group-a",
            "type_key": "exam_opinion",
            "member_keys": ["exam_opinion", self.host.RECEIPT_TYPE_KEY],
            "display_name": "审查通知类",
        }

        self.host._load_type_cards_to_ui("exam_opinion")
        self._app.processEvents()

        self.assertTrue(self.host.official_docs_naming_scope_hint_label.isVisible())
        self.assertIn("不同字段体系", self.host.official_docs_naming_scope_hint_label.text())

    def test_receipt_group_focus_keeps_receipt_default_fields_when_mixed(self) -> None:
        self.host._official_docs_working_settings["naming_groups"][0] = {
            "id": "receipt",
            "name": "收据",
            "member_type_keys": [self.host.RECEIPT_TYPE_KEY, "exam_opinion"],
            "group_config": {
                "naming_mode": "default",
                "filename_fields": ["收据", "收据_缴费人", "收据_申请号", "收据_缴费项目首项"],
                "alias_rules": [],
            },
        }
        self.host._official_docs_working_settings["type_group_membership"] = {
            self.host.RECEIPT_TYPE_KEY: "receipt",
            "exam_opinion": "receipt",
        }
        self.host._official_docs_type_selection_context = {
            "node_kind": TYPE_NODE_KIND_GROUP,
            "group_id": "receipt",
            "type_key": "exam_opinion",
            "member_keys": ["exam_opinion", self.host.RECEIPT_TYPE_KEY],
            "display_name": "收据",
        }

        self.host._load_type_cards_to_ui("exam_opinion")
        self._app.processEvents()

        fields = [
            self.host.official_docs_filename_fields_list.item(row).text()
            for row in range(self.host.official_docs_filename_fields_list.count())
        ]
        field_text = "\n".join(fields)
        self.assertEqual(self.host._official_docs_current_type, self.host.RECEIPT_TYPE_KEY)
        self.assertIn("收据_缴费项目首项", field_text)
        self.assertNotIn("发明名称", field_text)
        self.assertIn("收据_缴费项目汇总", self.host.official_docs_naming_mode_combo.itemText(0))
        self.assertNotIn("发明名称", self.host.official_docs_naming_mode_combo.itemText(0))

    def test_group_member_focus_loads_type_bound_alias_rules(self) -> None:
        self.host._official_docs_type_selection_context = {
            "node_kind": TYPE_NODE_KIND_GROUP_MEMBER,
            "group_id": "group-a",
            "type_key": "exam_opinion",
            "member_keys": ["exam_opinion", "rectification"],
            "display_name": "审查意见通知书",
        }

        self.host._load_type_cards_to_ui("exam_opinion")
        self._app.processEvents()

        self.assertIn("当前编辑：类型“审查意见通知书”", self.host.official_docs_naming_scope_label.text())
        self.assertEqual(self.host.official_docs_alias_title_label.text(), "通知书简称规则")
        self.assertFalse(self.host.official_docs_alias_card.isHidden())
        self.assertFalse(self.host.official_docs_naming_mode_combo.isEnabled())
        self.assertTrue(self.host.official_docs_alias_table.isEnabled())
        self.assertEqual(self.host.official_docs_filename_fields_list.count(), 2)
        self.assertEqual(self.host.official_docs_alias_table.rowCount(), 1)
        self.assertEqual(self.host.official_docs_alias_table.item(0, 2).text(), "审查")

    def test_ungrouped_type_focus_loads_direct_edit_state(self) -> None:
        self.host._official_docs_type_selection_context = {
            "node_kind": TYPE_NODE_KIND_UNGROUPED_TYPE,
            "group_id": "",
            "type_key": "certificate",
            "member_keys": ["certificate"],
            "display_name": "证书类",
        }

        self.host._load_type_cards_to_ui("certificate")
        self._app.processEvents()

        self.assertEqual(self.host.official_docs_naming_scope_label.text(), "当前编辑：未分组类型“证书类”")
        self.assertEqual(self.host.official_docs_alias_title_label.text(), "通知书简称规则")
        self.assertFalse(self.host.official_docs_alias_card.isHidden())
        self.assertTrue(self.host.official_docs_naming_mode_combo.isEnabled())
        self.assertGreaterEqual(self.host.official_docs_filename_fields_list.count(), 1)
        self.assertEqual(self.host.official_docs_alias_table.rowCount(), 1)

    def test_ungrouped_root_focus_shows_empty_editor_state(self) -> None:
        self.host._official_docs_type_selection_context = {
            "node_kind": TYPE_NODE_KIND_UNGROUPED_ROOT,
            "group_id": "",
            "type_key": "",
            "member_keys": [],
            "display_name": "",
        }

        self.host._load_type_cards_to_ui("")
        self._app.processEvents()

        self.assertEqual(self.host.official_docs_alias_title_label.text(), "通知书简称规则")
        self.assertTrue(self.host.official_docs_alias_card.isHidden())
        self.assertFalse(self.host.official_docs_naming_mode_combo.isEnabled())
        self.assertEqual(self.host.official_docs_naming_scope_label.text(), "当前编辑：请先选择左侧对象")
        self.assertEqual(self.host.official_docs_filename_fields_list.count(), 0)
        self.assertEqual(self.host.official_docs_alias_table.rowCount(), 0)

    def test_group_member_sync_writes_alias_rules_only_to_selected_type(self) -> None:
        self.host._official_docs_type_selection_context = {
            "node_kind": TYPE_NODE_KIND_GROUP_MEMBER,
            "group_id": "group-a",
            "type_key": "exam_opinion",
            "member_keys": ["exam_opinion", "rectification"],
            "display_name": "审查意见通知书",
        }

        self.host._load_type_cards_to_ui("exam_opinion")
        self._app.processEvents()
        self.host.official_docs_alias_table.item(0, 2).setText("新简称")

        self.host._sync_current_type_cards_from_ui()

        self.assertEqual(
            self.host._official_docs_working_settings["type_configs"]["exam_opinion"]["alias_rules"][0]["short_name"],
            "新简称",
        )
        self.assertEqual(
            self.host._official_docs_working_settings["naming_groups"][0]["group_config"]["alias_rules"][0]["short_name"],
            "分组审查",
        )


if __name__ == "__main__":
    unittest.main()
