from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFrame,
        QLabel,
        QListWidget,
        QPushButton,
        QStyle,
        QStyleOptionViewItem,
        QTableWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    from gui.main_window.mixins.official_docs_mixin import OfficialDocsMixin
    from gui.ui_layout_impl.official_docs_page_parts.settings_panel import OfficialDocsNamingTypeTree

    _PYSIDE6_AVAILABLE = True
except Exception:
    QPoint = object  # type: ignore[assignment]
    Qt = object  # type: ignore[assignment]
    QTest = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    QCheckBox = object  # type: ignore[assignment]
    QComboBox = object  # type: ignore[assignment]
    QFrame = object  # type: ignore[assignment]
    QLabel = object  # type: ignore[assignment]
    QListWidget = object  # type: ignore[assignment]
    QPushButton = object  # type: ignore[assignment]
    QStyle = object  # type: ignore[assignment]
    QStyleOptionViewItem = object  # type: ignore[assignment]
    QTableWidget = object  # type: ignore[assignment]
    QTreeWidgetItem = object  # type: ignore[assignment]
    QVBoxLayout = object  # type: ignore[assignment]
    QWidget = object  # type: ignore[assignment]
    OfficialDocsMixin = object  # type: ignore[assignment]
    OfficialDocsNamingTypeTree = object  # type: ignore[assignment]
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:
    class _TypeTreeHost(QWidget, OfficialDocsMixin):
        def __init__(self) -> None:
            super().__init__()
            self._official_docs_working_settings = {
                "summary_root_dir": "",
                "archive_root_dir": "",
                "write_summary": True,
                "write_archive": False,
                "confirm_each": False,
                "enable_exam_pdf_parse": False,
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
                                    "notice_name": "审查意见通知书",
                                    "short_name": "审查",
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
                "type_configs": {
                    "exam_opinion": {
                        "naming_mode": "default",
                        "filename_fields": ["通知书名称", "申请号"],
                        "alias_rules": [
                            {
                                "notice_name": "审查意见通知书",
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
                                "notice_name": "证书",
                                "short_name": "证书",
                                "enabled": True,
                            }
                        ],
                    }
                },
            }
            self._official_docs_saved_settings = dict(self._official_docs_working_settings)
            self._official_docs_current_type = "exam_opinion"
            self._official_docs_type_search_text = ""
            self._official_docs_type_tree_rebuilding = False
            self._official_docs_type_tree_checked_state = {}
            self._official_docs_type_selection_context = {
                "node_kind": "ungrouped_root",
                "group_id": "",
                "type_key": "",
                "member_keys": [],
                "display_name": "",
            }
            self._official_docs_type_members_by_primary = {}
            self._official_docs_signals_blocked = False
            self._official_docs_alias_loading = False
            self._official_docs_dirty = False
            self._official_docs_selected_leaf_id = ""
            self._official_docs_leaves = {}

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
            self.official_docs_settings_error_label = QLabel()
            self.official_docs_settings_type_tree = OfficialDocsNamingTypeTree()
            self.official_docs_settings_type_tree.setHeaderHidden(True)
            self.official_docs_settings_type_tree.currentItemChanged.connect(self.on_official_docs_type_selection_changed)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.official_docs_settings_type_tree)

        def _init_official_docs_state(self) -> None:
            return None

        def _get_official_docs_settings_snapshot(self, sync_current_type: bool = False) -> dict[str, object]:
            return self._official_docs_working_settings

        def _collect_available_type_entries(self) -> list[dict[str, object]]:
            return [
                {"key": "exam_opinion", "display_name": "审查意见通知书", "processable": True, "disabled_reason": "", "is_new": False},
                {"key": "rectification", "display_name": "补正通知书", "processable": True, "disabled_reason": "", "is_new": False},
                {"key": "certificate", "display_name": "证书", "processable": True, "disabled_reason": "", "is_new": False},
            ]

        def _refresh_official_docs_detail(self) -> None:
            return None

        def _update_official_docs_settings_dirty_ui(self) -> None:
            return None
else:
    class _TypeTreeHost:
        pass


@unittest.skipUnless(_PYSIDE6_AVAILABLE, "PySide6 not installed")
class OfficialDocsTypeTreeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.host = _TypeTreeHost()
        self.host.show()

    def _refresh_tree(self) -> None:
        self.host._refresh_official_docs_type_list()
        self.host._load_type_cards_to_ui(self.host._official_docs_current_type)
        self._app.processEvents()

    def _item_text_click_pos(self, item: QTreeWidgetItem) -> QPoint:
        tree = self.host.official_docs_settings_type_tree
        rect = tree.visualItemRect(item)
        option = QStyleOptionViewItem()
        option.initFrom(tree)
        option.rect = rect
        right_edge = rect.x() + 12
        indicator_rect = tree.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, option, tree)
        if indicator_rect.isValid():
            right_edge = max(right_edge, indicator_rect.right() + 12)
        disclosure_element = getattr(QStyle, "SE_TreeViewDisclosureItem", None)
        if disclosure_element is not None:
            disclosure_rect = tree.style().subElementRect(disclosure_element, option, tree)
            if disclosure_rect.isValid():
                right_edge = max(right_edge, disclosure_rect.right() + 12)
        return QPoint(min(right_edge, rect.right() - 8), rect.center().y())

    def _item_checkbox_click_pos(self, item: QTreeWidgetItem) -> QPoint:
        tree = self.host.official_docs_settings_type_tree
        rect = tree.visualItemRect(item)
        option = QStyleOptionViewItem()
        option.initFrom(tree)
        option.rect = rect
        option.features |= QStyleOptionViewItem.HasCheckIndicator
        indicator_rect = tree.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, option, tree)
        return indicator_rect.center()

    def _item_branch_click_pos(self, item: QTreeWidgetItem) -> QPoint | None:
        tree = self.host.official_docs_settings_type_tree
        disclosure_rect = tree._branch_click_rect(item)
        if not disclosure_rect.isValid():
            return None
        return disclosure_rect.center()

    def test_group_nodes_show_member_count_and_ungrouped_root_shows_total_count(self) -> None:
        self._refresh_tree()

        tree = self.host.official_docs_settings_type_tree
        top_labels = [tree.topLevelItem(index).text(0) for index in range(tree.topLevelItemCount())]
        self.assertIn("审查通知类 (2)", top_labels)
        self.assertIn("其他（未分组） (1)", top_labels)
        self.assertEqual(self.host._current_type_selection_context()["display_name"], "审查意见通知书")

    def test_group_roots_collapse_by_default_and_expand_while_searching(self) -> None:
        self._refresh_tree()

        tree = self.host.official_docs_settings_type_tree
        self.assertFalse(tree.topLevelItem(0).isExpanded())
        self.assertFalse(tree.topLevelItem(1).isExpanded())

        self.host._official_docs_type_search_text = "审查"
        self._refresh_tree()
        self.assertTrue(tree.topLevelItem(0).isExpanded())

    def test_refresh_prefers_current_type_leaf_over_root_empty_state(self) -> None:
        self._refresh_tree()

        context = self.host._current_type_selection_context()
        self.assertEqual(context["node_kind"], "group_member")
        self.assertEqual(context["type_key"], "exam_opinion")
        self.assertEqual(context["display_name"], "审查意见通知书")
        self.assertIn("当前编辑：类型“审查意见通知书”", self.host.official_docs_naming_scope_label.text())

    def test_clicking_ungrouped_leaf_text_switches_right_editor_state(self) -> None:
        self._refresh_tree()

        tree = self.host.official_docs_settings_type_tree
        tree.topLevelItem(1).setExpanded(True)
        ungrouped_leaf = tree.topLevelItem(1).child(0)
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier, self._item_text_click_pos(ungrouped_leaf))
        self._app.processEvents()

        context = self.host._current_type_selection_context()
        self.assertEqual(context["node_kind"], "ungrouped_type")
        self.assertEqual(context["type_key"], "certificate")
        self.assertEqual(self.host.official_docs_naming_scope_label.text(), "当前编辑：未分组类型“证书”")
        self.assertEqual(self.host.official_docs_alias_title_label.text(), "通知书简称规则")
        self.assertNotIn("请选择左侧的分组或类型", self.host.official_docs_filename_preview_label.text())
        self.assertEqual(self.host.official_docs_alias_table.rowCount(), 1)

    def test_clicking_leaf_checkbox_also_switches_current_editor_state(self) -> None:
        self._refresh_tree()

        tree = self.host.official_docs_settings_type_tree
        tree.topLevelItem(1).setExpanded(True)
        ungrouped_leaf = tree.topLevelItem(1).child(0)
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier, self._item_text_click_pos(ungrouped_leaf))
        self._app.processEvents()

        tree.topLevelItem(0).setExpanded(True)
        grouped_leaf = tree.topLevelItem(0).child(0)
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier, self._item_checkbox_click_pos(grouped_leaf))
        self._app.processEvents()

        context = self.host._current_type_selection_context()
        self.assertEqual(context["node_kind"], "group_member")
        self.assertEqual(context["type_key"], "exam_opinion")
        self.assertIn("当前编辑：类型“审查意见通知书”", self.host.official_docs_naming_scope_label.text())
        self.assertEqual(self.host.official_docs_alias_title_label.text(), "通知书简称规则")
        self.assertFalse(self.host.official_docs_alias_card.isHidden())
        self.assertNotIn("请选择左侧的分组或类型", self.host.official_docs_filename_preview_label.text())
        self.assertEqual(grouped_leaf.checkState(0), Qt.Checked)

    def test_clicking_group_text_switches_focus_to_group_and_enables_group_actions(self) -> None:
        self._refresh_tree()

        tree = self.host.official_docs_settings_type_tree
        group_item = tree.topLevelItem(0)
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier, self._item_text_click_pos(group_item))
        self._app.processEvents()

        context = self.host._current_type_selection_context()
        self.assertEqual(context["node_kind"], "group")
        self.assertEqual(context["group_id"], "group-a")
        self.assertEqual(context["display_name"], "审查通知类")
        self.assertEqual(self.host.official_docs_naming_scope_label.text(), "当前编辑：分组“审查通知类”")
        self.assertEqual(self.host.official_docs_alias_title_label.text(), "通知书简称规则")
        self.assertTrue(self.host.official_docs_alias_card.isHidden())
        self.assertTrue(self.host.official_docs_rename_group_button.isEnabled())
        self.assertTrue(self.host.official_docs_delete_group_button.isEnabled())

    def test_clicking_group_disclosure_does_not_replace_current_editor_target(self) -> None:
        self._refresh_tree()

        tree = self.host.official_docs_settings_type_tree
        tree.topLevelItem(1).setExpanded(True)
        ungrouped_leaf = tree.topLevelItem(1).child(0)
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier, self._item_text_click_pos(ungrouped_leaf))
        self._app.processEvents()

        branch_pos = self._item_branch_click_pos(tree.topLevelItem(0))
        if branch_pos is None:
            self.skipTest("tree disclosure rect unavailable on this platform")
        QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier, branch_pos)
        self._app.processEvents()

        context = self.host._current_type_selection_context()
        self.assertEqual(context["node_kind"], "ungrouped_type")
        self.assertEqual(context["type_key"], "certificate")
        self.assertEqual(self.host.official_docs_naming_scope_label.text(), "当前编辑：未分组类型“证书”")


if __name__ == "__main__":
    unittest.main()
