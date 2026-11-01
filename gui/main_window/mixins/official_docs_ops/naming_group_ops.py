from __future__ import annotations

import uuid

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from gui.widgets_impl.request_form.value_picker import pick_multi_values_from_list, pick_value_from_list

from .shared import (
    Any,
    QInputDialog,
    QMessageBox,
    QTreeWidgetItem,
    TYPE_NODE_KIND_GROUP,
    TYPE_NODE_KIND_GROUP_MEMBER,
    TYPE_NODE_KIND_UNGROUPED_ROOT,
    TYPE_NODE_KIND_UNGROUPED_TYPE,
    get_type_display_name,
    normalize_notice_type,
)
from .type_tree_ops import (
    _remember_checked_type_tree_state_from_tree,
    _type_tree_context_from_item,
    _type_tree_item_label,
)


def _find_naming_group(settings: dict[str, Any], group_id: str) -> dict[str, Any] | None:
    target = str(group_id or "").strip()
    if not target:
        return None
    for raw_group in list(settings.get("naming_groups", []) or []):
        if isinstance(raw_group, dict) and str(raw_group.get("id", "") or "").strip() == target:
            return raw_group
    return None

def _resolve_type_group_member_keys(self, primary_key: str) -> list[str]:
    key = normalize_notice_type(primary_key)
    if not key:
        return []

    mapped = getattr(self, "_official_docs_type_members_by_primary", {})
    if isinstance(mapped, dict):
        values = mapped.get(key)
        if isinstance(values, list):
            resolved = [normalize_notice_type(str(item or "").strip()) for item in values]
            resolved = [item for item in resolved if item]
            if resolved:
                return resolved

    selection_context = self._current_type_selection_context()
    current_key = normalize_notice_type(str(selection_context.get("type_key", "") or "").strip())
    if current_key == key:
        resolved = [
            normalize_notice_type(str(item or "").strip())
            for item in list(selection_context.get("member_keys", []) or [])
            if normalize_notice_type(str(item or "").strip())
        ]
        if resolved:
            return resolved
    return [key]


def _pick_group_name(self, *, title: str, value: str = "") -> str:
    name, ok = QInputDialog.getText(self, title, "请输入分组名称：", text=str(value or "").strip())
    if not ok:
        return ""
    return str(name or "").strip()


def _create_naming_group(self, *, group_name: str) -> str:
    settings = getattr(self, "_official_docs_working_settings", None)
    if not isinstance(settings, dict):
        return ""
    clean_name = str(group_name or "").strip()
    if not clean_name:
        return ""
    existing_names = {
        str(raw_group.get("name", "") or "").strip()
        for raw_group in list(settings.get("naming_groups", []) or [])
        if isinstance(raw_group, dict)
    }
    if clean_name in existing_names:
        QMessageBox.warning(self, "分组名称重复", f"分组“{clean_name}”已存在。")
        return ""
    group_id = f"naming-group-{uuid.uuid4().hex[:8]}"
    groups = settings.setdefault("naming_groups", [])
    if not isinstance(groups, list):
        groups = []
        settings["naming_groups"] = groups
    groups.append(
        {
            "id": group_id,
            "name": clean_name,
            "member_type_keys": [],
            "group_config": self._default_group_cfg_payload(getattr(self, "_official_docs_current_type", "exam_opinion")),
        }
    )
    return group_id


def _pick_target_group_id(
    self,
    *,
    exclude_group_id: str = "",
    allow_create: bool = True,
    prompt: str,
) -> str:
    payload = self._build_type_tree_payload(self._get_official_docs_settings_snapshot(sync_current_type=False))
    choices: list[tuple[str, str]] = []
    for raw_group in list(payload.get("naming_groups", []) or []):
        if not isinstance(raw_group, dict):
            continue
        group_id = str(raw_group.get("id", "") or "").strip()
        group_name = str(raw_group.get("name", "") or "").strip()
        if not group_id or not group_name or group_id == str(exclude_group_id or "").strip():
            continue
        choices.append((group_id, group_name))
    labels = [group_name for _, group_name in choices]
    if allow_create:
        labels.append("新建分组...")

    selected_index = pick_value_from_list(self, "选择分组", labels, prompt=prompt)
    if selected_index is None:
        return ""
    if allow_create and selected_index == len(labels) - 1:
        group_name = self._pick_group_name(title="新建分组")
        if not group_name:
            return ""
        return self._create_naming_group(group_name=group_name)
    if selected_index < 0 or selected_index >= len(choices):
        return ""
    return str(choices[selected_index][0] or "").strip()


def _assign_entry_to_group(self, *, group_id: str, entry_context: dict[str, Any]) -> bool:
    target_group_id = str(group_id or "").strip()
    if not target_group_id:
        return False
    settings = getattr(self, "_official_docs_working_settings", None)
    if not isinstance(settings, dict):
        return False
    group = _find_naming_group(settings, target_group_id)
    if group is None:
        return False

    member_keys = [
        normalize_notice_type(str(item or "").strip())
        for item in list(entry_context.get("member_keys", []) or [])
        if normalize_notice_type(str(item or "").strip())
    ]
    if not member_keys:
        type_key = normalize_notice_type(str(entry_context.get("type_key", "") or "").strip())
        if type_key:
            member_keys = [type_key]
    if not member_keys:
        return False

    membership = settings.setdefault("type_group_membership", {})
    if not isinstance(membership, dict):
        membership = {}
        settings["type_group_membership"] = membership

    for raw_group in list(settings.get("naming_groups", []) or []):
        if not isinstance(raw_group, dict):
            continue
        raw_group["member_type_keys"] = [
            normalize_notice_type(str(item or "").strip())
            for item in list(raw_group.get("member_type_keys", []) or [])
            if normalize_notice_type(str(item or "").strip()) not in member_keys
        ]

    updated_members = [
        normalize_notice_type(str(item or "").strip())
        for item in list(group.get("member_type_keys", []) or [])
        if normalize_notice_type(str(item or "").strip())
    ]
    for member_key in member_keys:
        membership[member_key] = target_group_id
        if member_key not in updated_members:
            updated_members.append(member_key)
    group["member_type_keys"] = updated_members
    return True


def on_official_docs_type_tree_context_menu(self, pos) -> None:
    tree = getattr(self, "official_docs_settings_type_tree", None)
    if tree is None:
        return
    item = tree.itemAt(pos)
    if item is None:
        return
    menu = QMenu(self)
    context = _type_tree_context_from_item(item)
    node_kind = str(context.get("node_kind", "") or "")

    if node_kind == TYPE_NODE_KIND_GROUP:
        act_add_member = QAction("添加成员...", menu)
        act_add_member.triggered.connect(self.on_official_docs_add_group_member)
        act_rename = QAction("重命名分组", menu)
        act_rename.triggered.connect(self.on_official_docs_rename_naming_group)
        act_delete = QAction("删除分组", menu)
        act_delete.triggered.connect(self.on_official_docs_delete_naming_group)
        menu.addActions([act_add_member, act_rename, act_delete])
    elif node_kind == TYPE_NODE_KIND_UNGROUPED_TYPE:
        act_join = QAction("加入分组...", menu)
        act_join.triggered.connect(self.on_official_docs_move_type_to_group)
        menu.addAction(act_join)
    elif node_kind == TYPE_NODE_KIND_GROUP_MEMBER:
        act_move = QAction("移动到分组...", menu)
        act_move.triggered.connect(self.on_official_docs_move_type_to_group)
        act_remove = QAction("移出分组", menu)
        act_remove.triggered.connect(self.on_official_docs_remove_type_from_group)
        menu.addActions([act_move, act_remove])
    else:
        return
    menu.exec(tree.viewport().mapToGlobal(pos))


def on_official_docs_type_tree_item_changed(self, item: QTreeWidgetItem | None, column: int) -> None:
    self._init_official_docs_state()
    if column != 0:
        return
    if bool(getattr(self, "_official_docs_signals_blocked", False)) or bool(getattr(self, "_official_docs_type_tree_rebuilding", False)):
        return
    if item is None:
        return
    _remember_checked_type_tree_state_from_tree(self)
    self._refresh_official_docs_type_action_buttons()


def _checked_or_focused_group_contexts(self) -> list[dict[str, Any]]:
    checked_targets = self._collect_checked_type_tree_targets()
    group_contexts = [dict(item) for item in list(checked_targets.get("group_contexts", []) or []) if isinstance(item, dict)]
    if group_contexts:
        return group_contexts

    context = self._current_type_selection_context()
    if str(context.get("node_kind", "") or "") != TYPE_NODE_KIND_GROUP:
        return []
    settings = getattr(self, "_official_docs_working_settings", None)
    if not isinstance(settings, dict):
        return []
    group = _find_naming_group(settings, str(context.get("group_id", "") or ""))
    if group is None:
        return []
    payload = self._build_type_tree_payload(settings)
    group_id = str(group.get("id", "") or "").strip()
    member_contexts: list[dict[str, Any]] = []
    for entry in list((payload.get("entries_by_group", {}) or {}).get(group_id, []) or []):
        member_contexts.append(
            {
                "node_kind": TYPE_NODE_KIND_GROUP_MEMBER,
                "group_id": group_id,
                "type_key": normalize_notice_type(str(entry.get("primary_key", "") or "").strip()),
                "member_keys": list(entry.get("member_keys", []) or []),
                "display_name": str(entry.get("display_name", "") or "").strip()
                or get_type_display_name(str(entry.get("primary_key", "") or "")),
            }
        )
    return [
        {
            "node_kind": TYPE_NODE_KIND_GROUP,
            "group_id": group_id,
            "type_key": normalize_notice_type(str(context.get("type_key", "") or "")),
            "display_name": str(group.get("name", "") or "").strip(),
            "member_contexts": member_contexts,
        }
    ]


def _checked_or_focused_type_contexts(self) -> dict[str, list[dict[str, Any]]]:
    checked_targets = self._collect_checked_type_tree_targets()
    type_contexts = [dict(item) for item in list(checked_targets.get("type_contexts", []) or []) if isinstance(item, dict)]
    group_member_contexts = [dict(item) for item in list(checked_targets.get("group_member_contexts", []) or []) if isinstance(item, dict)]
    ungrouped_type_contexts = [dict(item) for item in list(checked_targets.get("ungrouped_type_contexts", []) or []) if isinstance(item, dict)]
    if type_contexts:
        return {
            "type_contexts": type_contexts,
            "group_member_contexts": group_member_contexts,
            "ungrouped_type_contexts": ungrouped_type_contexts,
        }

    context = self._current_type_selection_context()
    node_kind = str(context.get("node_kind", "") or "")
    if node_kind == TYPE_NODE_KIND_UNGROUPED_TYPE:
        return {
            "type_contexts": [dict(context)],
            "group_member_contexts": [],
            "ungrouped_type_contexts": [dict(context)],
        }
    if node_kind == TYPE_NODE_KIND_GROUP_MEMBER:
        return {
            "type_contexts": [dict(context)],
            "group_member_contexts": [dict(context)],
            "ungrouped_type_contexts": [],
        }
    return {
        "type_contexts": [],
        "group_member_contexts": [],
        "ungrouped_type_contexts": [],
    }


def on_official_docs_create_naming_group(self) -> None:
    self._init_official_docs_state()
    group_name = self._pick_group_name(title="新建分组")
    if not group_name:
        return
    group_id = self._create_naming_group(group_name=group_name)
    if not group_id:
        return
    self._set_type_selection_context(
        node_kind=TYPE_NODE_KIND_GROUP,
        group_id=group_id,
        type_key=getattr(self, "_official_docs_current_type", "exam_opinion"),
        display_name=group_name,
    )
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    target_type = self._refresh_official_docs_type_list(getattr(self, "_official_docs_current_type", "exam_opinion"))
    self._load_type_cards_to_ui(target_type)
    self._update_official_docs_settings_dirty_ui()


def on_official_docs_rename_naming_group(self) -> None:
    self._init_official_docs_state()
    context = self._current_type_selection_context()
    if str(context.get("node_kind", "") or "") != TYPE_NODE_KIND_GROUP:
        return
    settings = getattr(self, "_official_docs_working_settings", None)
    if not isinstance(settings, dict):
        return
    group = _find_naming_group(settings, str(context.get("group_id", "") or ""))
    if group is None:
        return
    old_name = str(group.get("name", "") or "").strip()
    new_name = self._pick_group_name(title="重命名分组", value=old_name)
    if not new_name or new_name == old_name:
        return
    existing_names = {
        str(raw_group.get("name", "") or "").strip()
        for raw_group in list(settings.get("naming_groups", []) or [])
        if isinstance(raw_group, dict) and str(raw_group.get("id", "") or "").strip() != str(group.get("id", "") or "").strip()
    }
    if new_name in existing_names:
        QMessageBox.warning(self, "分组名称重复", f"分组“{new_name}”已存在。")
        return
    group["name"] = new_name
    self._set_type_selection_context(
        node_kind=TYPE_NODE_KIND_GROUP,
        group_id=str(group.get("id", "") or ""),
        type_key=str(context.get("type_key", "") or ""),
        member_keys=list(context.get("member_keys", []) or []),
        display_name=new_name,
    )
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    target_type = self._refresh_official_docs_type_list(getattr(self, "_official_docs_current_type", "exam_opinion"))
    self._load_type_cards_to_ui(target_type)
    self._update_official_docs_settings_dirty_ui()


def on_official_docs_delete_naming_group(self) -> None:
    self._init_official_docs_state()
    settings = getattr(self, "_official_docs_working_settings", None)
    if not isinstance(settings, dict):
        return
    group_contexts = self._checked_or_focused_group_contexts()
    if not group_contexts:
        return
    group_rows: list[tuple[str, str, int]] = []
    for group_context in group_contexts:
        group_id = str(group_context.get("group_id", "") or "").strip()
        if not group_id:
            continue
        group = _find_naming_group(settings, group_id)
        if group is None:
            continue
        group_rows.append(
            (
                group_id,
                str(group.get("name", "") or "").strip() or "未命名分组",
                len(list(group_context.get("member_contexts", []) or [])),
            )
        )
    if not group_rows:
        return
    detail_lines = [f"• {group_name}（{member_count} 个类型）" for _, group_name, member_count in group_rows]
    answer = QMessageBox.question(
        self,
        "删除分组",
        "确定删除以下分组吗？组内类型会回到未分组状态。\n\n" + "\n".join(detail_lines),
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if answer != QMessageBox.Yes:
        return

    group_id_set = {group_id for group_id, _, _ in group_rows}
    settings["naming_groups"] = [
        raw_group
        for raw_group in list(settings.get("naming_groups", []) or [])
        if not (isinstance(raw_group, dict) and str(raw_group.get("id", "") or "").strip() in group_id_set)
    ]
    membership = settings.setdefault("type_group_membership", {})
    if not isinstance(membership, dict):
        membership = {}
        settings["type_group_membership"] = membership
    for member_key in list(membership.keys()):
        if str(membership.get(member_key, "") or "").strip() in group_id_set:
            membership.pop(member_key, None)

    self._clear_checked_type_tree_targets()
    self._set_type_selection_context(
        node_kind=TYPE_NODE_KIND_UNGROUPED_ROOT,
        type_key=getattr(self, "_official_docs_current_type", "exam_opinion"),
    )
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    target_type = self._refresh_official_docs_type_list(getattr(self, "_official_docs_current_type", "exam_opinion"))
    self._load_type_cards_to_ui(target_type)
    self._update_official_docs_settings_dirty_ui()


def on_official_docs_add_group_member(self) -> None:
    self._init_official_docs_state()
    context = self._current_type_selection_context()
    if str(context.get("node_kind", "") or "") != TYPE_NODE_KIND_GROUP:
        return
    payload = self._build_type_tree_payload(self._get_official_docs_settings_snapshot(sync_current_type=False))
    ungrouped_entries = list(payload.get("ungrouped_entries", []) or [])
    if not ungrouped_entries:
        QMessageBox.information(self, "没有可添加的类型", "当前没有未分组类型。")
        return
    labels = [_type_tree_item_label(entry) for entry in ungrouped_entries]
    preselected_type_keys = {
        normalize_notice_type(str(raw_context.get("type_key", "") or "").strip())
        for raw_context in list(self._collect_checked_type_tree_targets().get("ungrouped_type_contexts", []) or [])
        if isinstance(raw_context, dict)
    }
    preselected_indexes = [
        index
        for index, entry in enumerate(ungrouped_entries)
        if normalize_notice_type(str(entry.get("primary_key", "") or "").strip()) in preselected_type_keys
    ]
    action, selected_indexes = pick_multi_values_from_list(
        self,
        "添加成员",
        labels,
        prompt="请选择要加入当前分组的未分组类型：",
        ok_text="加入分组",
        skip_text="取消",
        cancel_text="关闭",
        selected_indexes=preselected_indexes,
    )
    if action != "ok" or not selected_indexes:
        return
    for index in selected_indexes:
        if 0 <= int(index) < len(ungrouped_entries):
            self._assign_entry_to_group(group_id=str(context.get("group_id", "") or ""), entry_context=ungrouped_entries[index])
    self._clear_checked_type_tree_targets()
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    target_type = self._refresh_official_docs_type_list(getattr(self, "_official_docs_current_type", "exam_opinion"))
    self._load_type_cards_to_ui(target_type)
    self._update_official_docs_settings_dirty_ui()


def on_official_docs_move_type_to_group(self) -> None:
    self._init_official_docs_state()
    target_contexts = self._checked_or_focused_type_contexts()
    type_contexts = list(target_contexts.get("type_contexts", []) or [])
    if not type_contexts:
        return
    target_group_id = self._pick_target_group_id(
        exclude_group_id="",
        allow_create=True,
        prompt="请选择目标分组：",
    )
    if not target_group_id:
        return
    settings = getattr(self, "_official_docs_working_settings", None)
    target_group = _find_naming_group(settings, target_group_id) if isinstance(settings, dict) else None
    applied_count = 0
    skipped_labels: list[str] = []
    for context in type_contexts:
        source_group_id = str(context.get("group_id", "") or "").strip()
        if source_group_id and source_group_id == target_group_id:
            skipped_labels.append(str(context.get("display_name", "") or get_type_display_name(str(context.get("type_key", "") or ""))))
            continue
        if self._assign_entry_to_group(group_id=target_group_id, entry_context=context):
            applied_count += 1
    if applied_count <= 0:
        if skipped_labels:
            QMessageBox.information(self, "无需移动", "所选类型已在目标分组中。")
        return
    self._clear_checked_type_tree_targets()
    self._set_type_selection_context(
        node_kind=TYPE_NODE_KIND_GROUP,
        group_id=target_group_id,
        type_key=str((type_contexts[:1] or [{}])[0].get("type_key", "") or ""),
        member_keys=list((type_contexts[:1] or [{}])[0].get("member_keys", []) or []),
        display_name=str(target_group.get("name", "") or "") if isinstance(target_group, dict) else "",
    )
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    target_type = self._refresh_official_docs_type_list(str((type_contexts[:1] or [{}])[0].get("type_key", "") or getattr(self, "_official_docs_current_type", "exam_opinion")))
    self._load_type_cards_to_ui(target_type)
    self._update_official_docs_settings_dirty_ui()
    if skipped_labels:
        QMessageBox.information(self, "已跳过部分类型", "以下类型已在目标分组中，未重复移动：\n\n" + "\n".join(f"• {label}" for label in skipped_labels))


def on_official_docs_remove_type_from_group(self) -> None:
    self._init_official_docs_state()
    settings = getattr(self, "_official_docs_working_settings", None)
    if not isinstance(settings, dict):
        return
    target_contexts = self._checked_or_focused_type_contexts()
    group_member_contexts = list(target_contexts.get("group_member_contexts", []) or [])
    if not group_member_contexts:
        return
    membership = settings.setdefault("type_group_membership", {})
    if not isinstance(membership, dict):
        membership = {}
        settings["type_group_membership"] = membership
    first_context = dict((group_member_contexts[:1] or [{}])[0])
    for context in group_member_contexts:
        member_keys = [
            normalize_notice_type(str(item or "").strip())
            for item in list(context.get("member_keys", []) or [])
            if normalize_notice_type(str(item or "").strip())
        ]
        for member_key in member_keys:
            membership.pop(member_key, None)
        group = _find_naming_group(settings, str(context.get("group_id", "") or ""))
        if isinstance(group, dict):
            group["member_type_keys"] = [
                normalize_notice_type(str(item or "").strip())
                for item in list(group.get("member_type_keys", []) or [])
                if normalize_notice_type(str(item or "").strip()) not in member_keys
            ]
    self._clear_checked_type_tree_targets()
    if len(group_member_contexts) == 1:
        member_keys = [
            normalize_notice_type(str(item or "").strip())
            for item in list(first_context.get("member_keys", []) or [])
            if normalize_notice_type(str(item or "").strip())
        ]
        self._set_type_selection_context(
            node_kind=TYPE_NODE_KIND_UNGROUPED_TYPE,
            type_key=str(first_context.get("type_key", "") or ""),
            member_keys=member_keys,
            display_name=str(first_context.get("display_name", "") or ""),
        )
    else:
        self._set_type_selection_context(
            node_kind=TYPE_NODE_KIND_UNGROUPED_ROOT,
            type_key=getattr(self, "_official_docs_current_type", "exam_opinion"),
        )
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    target_type = self._refresh_official_docs_type_list(str(first_context.get("type_key", "") or getattr(self, "_official_docs_current_type", "exam_opinion")))
    self._load_type_cards_to_ui(target_type)
    self._update_official_docs_settings_dirty_ui()
