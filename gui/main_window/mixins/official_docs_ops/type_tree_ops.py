from __future__ import annotations

from .shared import (
    Any,
    OFFICIAL_DOC_UNGROUPED_ROOT_LABEL,
    QSignalBlocker,
    QTreeWidgetItem,
    Qt,
    TYPE_DISABLED_REASON_ROLE,
    TYPE_DISPLAY_NAME_ROLE,
    TYPE_GROUP_ID_ROLE,
    TYPE_IS_NEW_ROLE,
    TYPE_KEY_ROLE,
    TYPE_MEMBER_KEYS_ROLE,
    TYPE_NODE_KIND_GROUP,
    TYPE_NODE_KIND_GROUP_MEMBER,
    TYPE_NODE_KIND_ROLE,
    TYPE_NODE_KIND_UNGROUPED_ROOT,
    TYPE_NODE_KIND_UNGROUPED_TYPE,
    TYPE_PROCESSABLE_ROLE,
    _build_type_display_groups,
    _group_config_notice_type_hint,
    _match_type_search,
    get_type_display_name,
    normalize_notice_type,
)


def _current_type_selection_context(self) -> dict[str, Any]:
    raw = getattr(self, "_official_docs_type_selection_context", None)
    if isinstance(raw, dict):
        type_key = normalize_notice_type(str(raw.get("type_key", "") or "").strip())
        member_keys = [
            normalize_notice_type(str(item or "").strip())
            for item in list(raw.get("member_keys", []) or [])
            if normalize_notice_type(str(item or "").strip())
        ]
        return {
            "node_kind": str(raw.get("node_kind", TYPE_NODE_KIND_UNGROUPED_TYPE) or TYPE_NODE_KIND_UNGROUPED_TYPE),
            "group_id": str(raw.get("group_id", "") or "").strip(),
            "type_key": type_key,
            "member_keys": member_keys or ([type_key] if type_key else []),
            "display_name": str(raw.get("display_name", "") or "").strip(),
        }
    fallback_type = normalize_notice_type(str(getattr(self, "_official_docs_current_type", "exam_opinion") or "exam_opinion"))
    return {
        "node_kind": TYPE_NODE_KIND_UNGROUPED_TYPE,
        "group_id": "",
        "type_key": fallback_type,
        "member_keys": [fallback_type] if fallback_type else [],
        "display_name": get_type_display_name(fallback_type),
    }


def _set_type_selection_context(
    self,
    *,
    node_kind: str,
    type_key: str = "",
    group_id: str = "",
    member_keys: list[str] | None = None,
    display_name: str = "",
) -> dict[str, Any]:
    normalized_type_key = normalize_notice_type(type_key)
    normalized_members = [
        normalize_notice_type(str(item or "").strip())
        for item in list(member_keys or [])
        if normalize_notice_type(str(item or "").strip())
    ]
    if normalized_type_key and normalized_type_key not in normalized_members:
        normalized_members = [normalized_type_key, *normalized_members]
    context = {
        "node_kind": str(node_kind or TYPE_NODE_KIND_UNGROUPED_TYPE),
        "group_id": str(group_id or "").strip(),
        "type_key": normalized_type_key,
        "member_keys": normalized_members,
        "display_name": str(display_name or "").strip(),
    }
    self._official_docs_type_selection_context = context
    if normalized_type_key:
        self._official_docs_current_type = normalized_type_key
    return context



def _build_type_tree_payload(self, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    current_settings = settings if isinstance(settings, dict) else self._get_official_docs_settings_snapshot(sync_current_type=False)
    normalized_groups, normalized_membership = self._normalize_naming_groups_payload(
        current_settings.get("naming_groups", []),
        current_settings.get("type_group_membership", {}),
    )
    group_map = {
        str(group.get("id", "") or "").strip(): dict(group)
        for group in normalized_groups
        if isinstance(group, dict) and str(group.get("id", "") or "").strip()
    }
    entries = _build_type_display_groups(self._collect_available_type_entries())
    entries_by_group: dict[str, list[dict[str, Any]]] = {group_id: [] for group_id in group_map.keys()}
    ungrouped_entries: list[dict[str, Any]] = []
    members_by_primary: dict[str, list[str]] = {}

    for raw_entry in entries:
        entry = dict(raw_entry or {})
        primary_key = normalize_notice_type(str(entry.get("primary_key", "") or "").strip())
        member_keys = [
            normalize_notice_type(str(raw_key or "").strip())
            for raw_key in list(entry.get("member_keys", []) or [])
            if normalize_notice_type(str(raw_key or "").strip())
        ]
        if not primary_key:
            primary_key = member_keys[0] if member_keys else ""
        if not primary_key:
            continue
        if not member_keys:
            member_keys = [primary_key]
        members_by_primary[primary_key] = member_keys

        assigned_group_ids = {
            str(normalized_membership.get(member_key, "") or "").strip()
            for member_key in member_keys
            if str(normalized_membership.get(member_key, "") or "").strip()
        }
        assigned_group_id = ""
        if len(assigned_group_ids) == 1:
            candidate = next(iter(assigned_group_ids))
            if candidate in group_map:
                assigned_group_id = candidate

        entry["primary_key"] = primary_key
        entry["member_keys"] = member_keys
        entry["assigned_group_id"] = assigned_group_id
        if assigned_group_id:
            entries_by_group.setdefault(assigned_group_id, []).append(entry)
        else:
            ungrouped_entries.append(entry)

    return {
        "naming_groups": normalized_groups,
        "group_map": group_map,
        "type_group_membership": normalized_membership,
        "entries_by_group": entries_by_group,
        "ungrouped_entries": ungrouped_entries,
        "members_by_primary": members_by_primary,
    }


def _type_tree_item_label(entry: dict[str, Any]) -> str:
    key = normalize_notice_type(str(entry.get("primary_key", "") or "").strip())
    display_name = str(entry.get("display_name", "") or "").strip() or get_type_display_name(key)
    labels: list[str] = []
    if bool(entry.get("is_new", False)):
        labels.append("新类型")
    if not bool(entry.get("processable", True)):
        labels.append("不可处理")
    suffix = f"（{'/'.join(labels)}）" if labels else ""
    return f"{display_name}{suffix}"


def _group_tree_item_label(group_name: str, member_count: int) -> str:
    return f"{str(group_name or '').strip()} ({max(0, int(member_count))})"


def _type_tree_context_from_item(item: QTreeWidgetItem | None) -> dict[str, Any]:
    if item is None:
        return {
            "node_kind": TYPE_NODE_KIND_UNGROUPED_ROOT,
            "group_id": "",
            "type_key": "",
            "member_keys": [],
            "display_name": "",
        }
    return {
        "node_kind": str(item.data(0, TYPE_NODE_KIND_ROLE) or TYPE_NODE_KIND_UNGROUPED_ROOT),
        "group_id": str(item.data(0, TYPE_GROUP_ID_ROLE) or "").strip(),
        "type_key": normalize_notice_type(str(item.data(0, TYPE_KEY_ROLE) or "").strip()),
        "member_keys": [
            normalize_notice_type(str(item_key or "").strip())
            for item_key in list(item.data(0, TYPE_MEMBER_KEYS_ROLE) or [])
            if normalize_notice_type(str(item_key or "").strip())
        ],
        "display_name": str(item.data(0, TYPE_DISPLAY_NAME_ROLE) or item.text(0) or "").strip(),
    }


def _merge_checked_type_tree_targets(checked_contexts: list[dict[str, Any]]) -> dict[str, Any]:
    group_contexts: list[dict[str, Any]] = []
    group_ids: list[str] = []
    type_contexts: list[dict[str, Any]] = []
    group_member_contexts: list[dict[str, Any]] = []
    ungrouped_type_contexts: list[dict[str, Any]] = []
    seen_group_ids: set[str] = set()
    seen_type_keys: set[str] = set()
    seen_group_member_keys: set[str] = set()
    seen_ungrouped_keys: set[str] = set()

    def _append_type_context(target: list[dict[str, Any]], context: dict[str, Any], seen: set[str]) -> None:
        type_key = normalize_notice_type(str(context.get("type_key", "") or "").strip())
        if not type_key or type_key in seen:
            return
        seen.add(type_key)
        payload = {
            "node_kind": str(context.get("node_kind", "") or ""),
            "group_id": str(context.get("group_id", "") or "").strip(),
            "type_key": type_key,
            "member_keys": [
                normalize_notice_type(str(item or "").strip())
                for item in list(context.get("member_keys", []) or [])
                if normalize_notice_type(str(item or "").strip())
            ]
            or [type_key],
            "display_name": str(context.get("display_name", "") or "").strip(),
        }
        target.append(payload)
        if type_key not in seen_type_keys:
            seen_type_keys.add(type_key)
            type_contexts.append(dict(payload))

    for raw_context in list(checked_contexts or []):
        if not isinstance(raw_context, dict):
            continue
        node_kind = str(raw_context.get("node_kind", "") or "").strip()
        if node_kind == TYPE_NODE_KIND_GROUP:
            group_id = str(raw_context.get("group_id", "") or "").strip()
            if group_id and group_id not in seen_group_ids:
                seen_group_ids.add(group_id)
                group_ids.append(group_id)
                group_contexts.append(
                    {
                        "node_kind": TYPE_NODE_KIND_GROUP,
                        "group_id": group_id,
                        "type_key": normalize_notice_type(str(raw_context.get("type_key", "") or "").strip()),
                        "display_name": str(raw_context.get("display_name", "") or "").strip(),
                        "member_contexts": [dict(item) for item in list(raw_context.get("member_contexts", []) or []) if isinstance(item, dict)],
                    }
                )
            for member_context in list(raw_context.get("member_contexts", []) or []):
                if not isinstance(member_context, dict):
                    continue
                _append_type_context(group_member_contexts, member_context, seen_group_member_keys)
        elif node_kind == TYPE_NODE_KIND_UNGROUPED_ROOT:
            for member_context in list(raw_context.get("member_contexts", []) or []):
                if not isinstance(member_context, dict):
                    continue
                _append_type_context(ungrouped_type_contexts, member_context, seen_ungrouped_keys)
        elif node_kind == TYPE_NODE_KIND_GROUP_MEMBER:
            _append_type_context(group_member_contexts, raw_context, seen_group_member_keys)
        elif node_kind == TYPE_NODE_KIND_UNGROUPED_TYPE:
            _append_type_context(ungrouped_type_contexts, raw_context, seen_ungrouped_keys)

    return {
        "group_ids": group_ids,
        "group_contexts": group_contexts,
        "type_contexts": type_contexts,
        "group_member_contexts": group_member_contexts,
        "ungrouped_type_contexts": ungrouped_type_contexts,
        "checked_group_count": len(group_ids),
        "checked_type_count": len(type_contexts),
    }


def _build_type_action_button_states(
    *,
    focus_node_kind: str,
    has_ungrouped_entries: bool,
    checked_targets: dict[str, Any],
) -> dict[str, bool]:
    checked_group_count = len(list(checked_targets.get("group_ids", []) or []))
    checked_type_count = len(list(checked_targets.get("type_contexts", []) or []))
    checked_ungrouped_count = len(list(checked_targets.get("ungrouped_type_contexts", []) or []))
    checked_group_member_count = len(list(checked_targets.get("group_member_contexts", []) or []))
    has_explicit_checked_targets = any(
        count > 0
        for count in (
            checked_group_count,
            checked_type_count,
            checked_ungrouped_count,
            checked_group_member_count,
        )
    )
    focus_is_group = focus_node_kind == TYPE_NODE_KIND_GROUP
    focus_is_ungrouped_type = focus_node_kind == TYPE_NODE_KIND_UNGROUPED_TYPE
    focus_is_group_member = focus_node_kind == TYPE_NODE_KIND_GROUP_MEMBER
    return {
        "official_docs_create_group_button": True,
        "official_docs_rename_group_button": focus_is_group,
        "official_docs_delete_group_button": checked_group_count > 0 or (focus_is_group and not has_explicit_checked_targets),
        "official_docs_add_group_member_button": focus_is_group and has_ungrouped_entries,
        "official_docs_join_group_button": checked_ungrouped_count > 0 or (focus_is_ungrouped_type and not has_explicit_checked_targets),
        "official_docs_move_group_button": checked_type_count > 0 or ((focus_is_ungrouped_type or focus_is_group_member) and not has_explicit_checked_targets),
        "official_docs_remove_group_button": checked_group_member_count > 0 or (focus_is_group_member and not has_explicit_checked_targets),
    }


def _remember_checked_type_tree_state_from_tree(self) -> dict[str, Any]:
    tree = getattr(self, "official_docs_settings_type_tree", None)
    state = {
        "group_ids": [],
        "type_keys": [],
        "ungrouped_root_checked": False,
    }
    if tree is None:
        self._official_docs_type_tree_checked_state = state
        return state

    group_ids: set[str] = set()
    type_keys: set[str] = set()
    for index in range(int(tree.topLevelItemCount())):
        root_item = tree.topLevelItem(index)
        if root_item is None:
            continue
        node_kind = str(root_item.data(0, TYPE_NODE_KIND_ROLE) or "").strip()
        if node_kind == TYPE_NODE_KIND_GROUP and root_item.checkState(0) == Qt.Checked:
            group_id = str(root_item.data(0, TYPE_GROUP_ID_ROLE) or "").strip()
            if group_id:
                group_ids.add(group_id)
        elif node_kind == TYPE_NODE_KIND_UNGROUPED_ROOT and root_item.checkState(0) == Qt.Checked:
            state["ungrouped_root_checked"] = True
        for child_index in range(int(root_item.childCount())):
            child_item = root_item.child(child_index)
            if child_item is None or child_item.checkState(0) != Qt.Checked:
                continue
            type_key = normalize_notice_type(str(child_item.data(0, TYPE_KEY_ROLE) or "").strip())
            if type_key:
                type_keys.add(type_key)

    state["group_ids"] = sorted(group_ids)
    state["type_keys"] = sorted(type_keys)
    self._official_docs_type_tree_checked_state = state
    return state


def _checked_type_tree_state(self) -> dict[str, Any]:
    raw = getattr(self, "_official_docs_type_tree_checked_state", None)
    if not isinstance(raw, dict):
        return {
            "group_ids": [],
            "type_keys": [],
            "ungrouped_root_checked": False,
        }
    return {
        "group_ids": [
            str(item or "").strip()
            for item in list(raw.get("group_ids", []) or [])
            if str(item or "").strip()
        ],
        "type_keys": [
            normalize_notice_type(str(item or "").strip())
            for item in list(raw.get("type_keys", []) or [])
            if normalize_notice_type(str(item or "").strip())
        ],
        "ungrouped_root_checked": bool(raw.get("ungrouped_root_checked", False)),
    }


def _collect_checked_type_tree_targets(self) -> dict[str, Any]:
    tree = getattr(self, "official_docs_settings_type_tree", None)
    if tree is None:
        return _merge_checked_type_tree_targets([])

    checked_contexts: list[dict[str, Any]] = []
    for index in range(int(tree.topLevelItemCount())):
        root_item = tree.topLevelItem(index)
        if root_item is None:
            continue
        root_context = _type_tree_context_from_item(root_item)
        node_kind = str(root_context.get("node_kind", "") or "").strip()
        member_contexts = [
            _type_tree_context_from_item(root_item.child(child_index))
            for child_index in range(int(root_item.childCount()))
            if root_item.child(child_index) is not None
        ]
        if node_kind == TYPE_NODE_KIND_GROUP and root_item.checkState(0) == Qt.Checked:
            checked_contexts.append({**root_context, "member_contexts": member_contexts})
            continue
        if node_kind == TYPE_NODE_KIND_UNGROUPED_ROOT and root_item.checkState(0) == Qt.Checked:
            checked_contexts.append({**root_context, "member_contexts": member_contexts})
            continue
        for child_index in range(int(root_item.childCount())):
            child_item = root_item.child(child_index)
            if child_item is None or child_item.checkState(0) != Qt.Checked:
                continue
            checked_contexts.append(_type_tree_context_from_item(child_item))
    return _merge_checked_type_tree_targets(checked_contexts)


def _clear_checked_type_tree_targets(self) -> None:
    tree = getattr(self, "official_docs_settings_type_tree", None)
    self._official_docs_type_tree_checked_state = {
        "group_ids": [],
        "type_keys": [],
        "ungrouped_root_checked": False,
    }
    if tree is None:
        self._refresh_official_docs_type_action_buttons()
        return

    with QSignalBlocker(tree):
        for index in range(int(tree.topLevelItemCount())):
            root_item = tree.topLevelItem(index)
            if root_item is None:
                continue
            root_item.setCheckState(0, Qt.Unchecked)
            for child_index in range(int(root_item.childCount())):
                child_item = root_item.child(child_index)
                if child_item is not None:
                    child_item.setCheckState(0, Qt.Unchecked)
    self._refresh_official_docs_type_action_buttons()




def _refresh_official_docs_type_action_buttons(self) -> None:
    context = self._current_type_selection_context()
    node_kind = str(context.get("node_kind", "") or "")
    settings = getattr(self, "_official_docs_working_settings", None)
    payload = self._build_type_tree_payload(settings if isinstance(settings, dict) else None)
    has_ungrouped_entries = bool(payload.get("ungrouped_entries"))
    checked_targets = self._collect_checked_type_tree_targets()
    button_states = _build_type_action_button_states(
        focus_node_kind=node_kind,
        has_ungrouped_entries=has_ungrouped_entries,
        checked_targets=checked_targets,
    )
    for attr_name, enabled in button_states.items():
        widget = getattr(self, attr_name, None)
        if widget is None:
            continue
        try:
            widget.setEnabled(bool(enabled))
        except Exception:
            continue



def _refresh_official_docs_type_list(self, preferred_key: str = "") -> str:
    type_tree = getattr(self, "official_docs_settings_type_tree", None)
    if type_tree is None:
        return normalize_notice_type(preferred_key or getattr(self, "_official_docs_current_type", "exam_opinion"))

    payload = self._build_type_tree_payload()
    checked_state = _checked_type_tree_state(self)
    checked_group_ids = set(checked_state.get("group_ids", []) or [])
    checked_type_keys = set(checked_state.get("type_keys", []) or [])
    ungrouped_root_checked = bool(checked_state.get("ungrouped_root_checked", False))
    keyword = str(getattr(self, "_official_docs_type_search_text", "") or "").strip().lower()
    preferred_context = self._current_type_selection_context()
    preferred_type_key = normalize_notice_type(
        preferred_key or preferred_context.get("type_key", "") or getattr(self, "_official_docs_current_type", "")
    )

    self._official_docs_type_members_by_primary = dict(payload.get("members_by_primary", {}))
    self._official_docs_type_tree_rebuilding = True
    selected_item: QTreeWidgetItem | None = None
    preferred_leaf_item: QTreeWidgetItem | None = None
    preferred_group_item: QTreeWidgetItem | None = None
    preferred_ungrouped_root_item: QTreeWidgetItem | None = None
    fallback_item: QTreeWidgetItem | None = None

    try:
        with QSignalBlocker(type_tree):
            type_tree.clear()

            for raw_group in list(payload.get("naming_groups", []) or []):
                if not isinstance(raw_group, dict):
                    continue
                group_id = str(raw_group.get("id", "") or "").strip()
                group_name = str(raw_group.get("name", "") or "").strip()
                if not group_id or not group_name:
                    continue
                group_member_keys = [
                    normalize_notice_type(str(item or "").strip())
                    for item in list(raw_group.get("member_type_keys", []) or [])
                    if normalize_notice_type(str(item or "").strip())
                ]
                group_notice_type = _group_config_notice_type_hint(
                    group_id,
                    group_member_keys,
                    preferred_type_key or "exam_opinion",
                )

                all_children = list((payload.get("entries_by_group", {}) or {}).get(group_id, []) or [])
                group_matches = bool(keyword) and keyword in group_name.lower()
                visible_children = all_children if group_matches else [
                    entry for entry in all_children if _match_type_search(entry, keyword)
                ]
                if keyword and not group_matches and not visible_children:
                    continue

                group_item = QTreeWidgetItem([_group_tree_item_label(group_name, len(all_children))])
                group_item.setData(0, TYPE_NODE_KIND_ROLE, TYPE_NODE_KIND_GROUP)
                group_item.setData(0, TYPE_GROUP_ID_ROLE, group_id)
                group_item.setData(0, TYPE_DISPLAY_NAME_ROLE, group_name)
                group_item.setData(
                    0,
                    TYPE_KEY_ROLE,
                    group_notice_type,
                )
                group_item.setData(
                    0,
                    TYPE_MEMBER_KEYS_ROLE,
                    group_member_keys,
                )
                group_item.setFlags(group_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                group_item.setCheckState(0, Qt.Unchecked)
                type_tree.addTopLevelItem(group_item)
                group_item.setExpanded(bool(keyword))
                if fallback_item is None:
                    fallback_item = group_item
                if preferred_context.get("node_kind") == TYPE_NODE_KIND_GROUP and preferred_context.get("group_id") == group_id:
                    preferred_group_item = group_item

                for entry in visible_children:
                    child_item = QTreeWidgetItem([_type_tree_item_label(entry)])
                    child_item.setData(0, TYPE_NODE_KIND_ROLE, TYPE_NODE_KIND_GROUP_MEMBER)
                    child_item.setData(0, TYPE_GROUP_ID_ROLE, group_id)
                    child_item.setData(
                        0,
                        TYPE_DISPLAY_NAME_ROLE,
                        str(entry.get("display_name", "") or "").strip() or get_type_display_name(str(entry.get("primary_key", "") or "")),
                    )
                    child_item.setData(0, TYPE_KEY_ROLE, normalize_notice_type(str(entry.get("primary_key", "") or "")))
                    # 兼容旧的“显示组同步配置”源代码契约：item.setData(TYPE_MEMBER_KEYS_ROLE, member_keys)
                    child_item.setData(0, TYPE_MEMBER_KEYS_ROLE, list(entry.get("member_keys", []) or []))
                    child_item.setData(0, TYPE_PROCESSABLE_ROLE, bool(entry.get("processable", True)))
                    child_item.setData(0, TYPE_IS_NEW_ROLE, bool(entry.get("is_new", False)))
                    child_item.setData(0, TYPE_DISABLED_REASON_ROLE, str(entry.get("disabled_reason", "") or "").strip())
                    if not bool(entry.get("processable", True)):
                        child_item.setFlags(child_item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled & ~Qt.ItemIsUserCheckable)
                    else:
                        child_item.setFlags(child_item.flags() | Qt.ItemIsUserCheckable)
                        child_item.setCheckState(
                            0,
                            Qt.Checked if normalize_notice_type(str(entry.get("primary_key", "") or "")) in checked_type_keys else Qt.Unchecked,
                        )
                    group_item.addChild(child_item)
                    if (
                        preferred_context.get("node_kind") == TYPE_NODE_KIND_GROUP_MEMBER
                        and preferred_context.get("group_id") == group_id
                        and normalize_notice_type(str(entry.get("primary_key", "") or "")) == preferred_type_key
                    ):
                        selected_item = child_item
                    elif (
                        preferred_leaf_item is None
                        and preferred_type_key
                        and normalize_notice_type(str(entry.get("primary_key", "") or "")) == preferred_type_key
                    ):
                        preferred_leaf_item = child_item
                    if fallback_item is None and bool(entry.get("processable", True)):
                        fallback_item = child_item
                if group_id in checked_group_ids:
                    group_item.setCheckState(0, Qt.Checked)

            all_ungrouped_children = list(payload.get("ungrouped_entries", []) or [])
            ungrouped_children = [entry for entry in all_ungrouped_children if _match_type_search(entry, keyword)]
            if ungrouped_children or not keyword:
                ungrouped_root = QTreeWidgetItem([_group_tree_item_label(OFFICIAL_DOC_UNGROUPED_ROOT_LABEL, len(all_ungrouped_children))])
                ungrouped_root.setData(0, TYPE_NODE_KIND_ROLE, TYPE_NODE_KIND_UNGROUPED_ROOT)
                ungrouped_root.setData(0, TYPE_GROUP_ID_ROLE, "")
                ungrouped_root.setData(0, TYPE_DISPLAY_NAME_ROLE, OFFICIAL_DOC_UNGROUPED_ROOT_LABEL)
                ungrouped_root.setFlags(ungrouped_root.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                ungrouped_root.setCheckState(0, Qt.Unchecked)
                type_tree.addTopLevelItem(ungrouped_root)
                ungrouped_root.setExpanded(bool(keyword))
                if fallback_item is None:
                    fallback_item = ungrouped_root
                if preferred_context.get("node_kind") == TYPE_NODE_KIND_UNGROUPED_ROOT:
                    preferred_ungrouped_root_item = ungrouped_root

                for entry in ungrouped_children:
                    child_item = QTreeWidgetItem([_type_tree_item_label(entry)])
                    child_item.setData(0, TYPE_NODE_KIND_ROLE, TYPE_NODE_KIND_UNGROUPED_TYPE)
                    child_item.setData(0, TYPE_GROUP_ID_ROLE, "")
                    child_item.setData(
                        0,
                        TYPE_DISPLAY_NAME_ROLE,
                        str(entry.get("display_name", "") or "").strip() or get_type_display_name(str(entry.get("primary_key", "") or "")),
                    )
                    child_item.setData(0, TYPE_KEY_ROLE, normalize_notice_type(str(entry.get("primary_key", "") or "")))
                    # 兼容旧的“显示组同步配置”源代码契约：item.setData(TYPE_MEMBER_KEYS_ROLE, member_keys)
                    child_item.setData(0, TYPE_MEMBER_KEYS_ROLE, list(entry.get("member_keys", []) or []))
                    child_item.setData(0, TYPE_PROCESSABLE_ROLE, bool(entry.get("processable", True)))
                    child_item.setData(0, TYPE_IS_NEW_ROLE, bool(entry.get("is_new", False)))
                    child_item.setData(0, TYPE_DISABLED_REASON_ROLE, str(entry.get("disabled_reason", "") or "").strip())
                    if not bool(entry.get("processable", True)):
                        child_item.setFlags(child_item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled & ~Qt.ItemIsUserCheckable)
                    else:
                        child_item.setFlags(child_item.flags() | Qt.ItemIsUserCheckable)
                        child_item.setCheckState(
                            0,
                            Qt.Checked if normalize_notice_type(str(entry.get("primary_key", "") or "")) in checked_type_keys else Qt.Unchecked,
                        )
                    ungrouped_root.addChild(child_item)
                    if (
                        preferred_context.get("node_kind") == TYPE_NODE_KIND_UNGROUPED_TYPE
                        and normalize_notice_type(str(entry.get("primary_key", "") or "")) == preferred_type_key
                    ):
                        selected_item = child_item
                    elif (
                        preferred_leaf_item is None
                        and preferred_type_key
                        and normalize_notice_type(str(entry.get("primary_key", "") or "")) == preferred_type_key
                    ):
                        preferred_leaf_item = child_item
                    if fallback_item is None and bool(entry.get("processable", True)):
                        fallback_item = child_item
                if ungrouped_root_checked:
                    ungrouped_root.setCheckState(0, Qt.Checked)

            if selected_item is None:
                if preferred_leaf_item is not None:
                    selected_item = preferred_leaf_item
                elif preferred_context.get("node_kind") == TYPE_NODE_KIND_GROUP and preferred_group_item is not None:
                    selected_item = preferred_group_item
                elif preferred_context.get("node_kind") == TYPE_NODE_KIND_UNGROUPED_ROOT and preferred_ungrouped_root_item is not None:
                    selected_item = preferred_ungrouped_root_item
                else:
                    selected_item = fallback_item
            if selected_item is not None:
                type_tree.setCurrentItem(selected_item)
                selected_context = _type_tree_context_from_item(selected_item)
                self._set_type_selection_context(
                    node_kind=str(selected_context.get("node_kind", "") or TYPE_NODE_KIND_UNGROUPED_ROOT),
                    group_id=str(selected_context.get("group_id", "") or ""),
                    type_key=str(selected_context.get("type_key", "") or ""),
                    member_keys=list(selected_context.get("member_keys", []) or []),
                    display_name=str(selected_context.get("display_name", "") or ""),
                )
            if not keyword:
                for index in range(type_tree.topLevelItemCount()):
                    type_tree.topLevelItem(index).setExpanded(False)
            _remember_checked_type_tree_state_from_tree(self)
    finally:
        self._official_docs_type_tree_rebuilding = False

    self._refresh_official_docs_type_action_buttons()
    return normalize_notice_type(str(getattr(self, "_official_docs_current_type", "exam_opinion") or "exam_opinion"))
