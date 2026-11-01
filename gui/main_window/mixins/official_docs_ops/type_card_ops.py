from __future__ import annotations

from core.official_docs import mask_app_no_for_preview

from .naming_group_ops import _find_naming_group
from .shared import (
    Any,
    FILENAME_TOKEN_ROLE,
    NamingGroupConfig,
    NoticeMeta,
    ParsedNotice,
    ProcessOptions,
    QListWidget,
    QListWidgetItem,
    QSignalBlocker,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    RECEIPT_TYPE_KEY,
    TYPE_NODE_KIND_GROUP,
    TYPE_NODE_KIND_GROUP_MEMBER,
    TYPE_NODE_KIND_UNGROUPED_ROOT,
    TYPE_NODE_KIND_UNGROUPED_TYPE,
    _canonical_notice_name_for_display,
    _default_kind_cards,
    _explicit_alias_rows_from_raw_cfg,
    _group_config_notice_type_hint,
    get_type_display_name,
    normalize_notice_type,
    normalize_type_naming_config,
    render_notice_output_preview,
)


def _has_mixed_receipt_field_system(member_keys: list[str]) -> bool:
    normalized_keys = [
        normalize_notice_type(str(item or "").strip())
        for item in list(member_keys or [])
        if normalize_notice_type(str(item or "").strip())
    ]
    has_receipt = any(key == RECEIPT_TYPE_KEY for key in normalized_keys)
    return has_receipt and any(key != RECEIPT_TYPE_KEY for key in normalized_keys)

def _set_official_docs_naming_scope(self, scope_text: str, hint_text: str = "") -> None:
    scope_label = getattr(self, "official_docs_naming_scope_label", None)
    if scope_label is not None:
        scope_label.setText(str(scope_text or "").strip())
    hint_label = getattr(self, "official_docs_naming_scope_hint_label", None)
    if hint_label is not None:
        clean_hint = str(hint_text or "").strip()
        hint_label.setText(clean_hint)
        hint_label.setVisible(bool(clean_hint))

def _official_docs_cards_widget(self) -> QListWidget | None:
    return getattr(self, "official_docs_filename_fields_list", None)

def _list_widget_to_cards(self, widget: QListWidget | None) -> list[str]:
    if widget is None:
        return []
    cards: list[str] = []
    for index in range(widget.count()):
        item = widget.item(index)
        if item is None:
            continue
        token = str(item.data(FILENAME_TOKEN_ROLE) or "").strip()
        if not token:
            token = str(item.text() or "").strip()
            if token.startswith("☰"):
                token = token[1:].strip()
        if token:
            cards.append(token)
    return cards

def _card_to_item(self, card_text: str) -> QListWidgetItem:
    token = str(card_text or "").strip()
    item = QListWidgetItem(f"☰ {token}")
    item.setData(FILENAME_TOKEN_ROLE, token)
    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
    return item

def _set_cards_to_widget(self, widget: QListWidget | None, cards: list[str]) -> None:
    if widget is None:
        return
    with QSignalBlocker(widget):
        widget.clear()
        for card in cards:
            token = str(card or "").strip()
            if not token:
                continue
            widget.addItem(self._card_to_item(token))

def _set_filename_fields_card_editable(self, editable: bool) -> None:
    fields_card = getattr(self, "official_docs_filename_fields_card", None)
    if fields_card is None:
        return
    fields_card.setEnabled(bool(editable))
    fields_card.setProperty("readonlyMode", not bool(editable))
    style = fields_card.style()
    if style is not None:
        style.unpolish(fields_card)
        style.polish(fields_card)
    fields_card.update()

def _pdf_parse_field_widgets(self) -> dict[str, Any]:
    widgets = getattr(self, "official_docs_pdf_parse_field_checks", None)
    return dict(widgets) if isinstance(widgets, dict) else {}

def _set_pdf_parse_field_checks_enabled(self, enabled: bool) -> None:
    wrap = getattr(self, "official_docs_pdf_parse_fields_wrap", None)
    if wrap is not None:
        try:
            wrap.setEnabled(bool(enabled))
        except Exception:
            pass
    for widget in self._pdf_parse_field_widgets().values():
        try:
            widget.setEnabled(bool(enabled))
        except Exception:
            continue

def _current_type_alias_notice_options(self, kind: str) -> list[str]:
    options: list[str] = []
    keys = self._resolve_type_group_member_keys(normalize_notice_type(kind))
    for type_key in keys:
        display_name = str(get_type_display_name(type_key) or "").strip()
        canonical = _canonical_notice_name_for_display(display_name)
        if canonical and canonical not in options:
            options.append(canonical)
    if not options:
        fallback = _canonical_notice_name_for_display(str(get_type_display_name(kind) or "").strip())
        if fallback:
            options.append(fallback)
    return options

def _set_alias_notice_item(self, table: QTableWidget, row: int, *, notice_name: str, options: list[str]) -> None:
    clean_options: list[str] = []
    for option in options:
        text = _canonical_notice_name_for_display(option)
        if text and text not in clean_options:
            clean_options.append(text)

    target = _canonical_notice_name_for_display(notice_name)
    if target and target not in clean_options:
        clean_options.append(target)
    if not target:
        target = clean_options[0] if clean_options else ""

    notice_item = table.item(row, 1) or QTableWidgetItem("")
    notice_item.setText(str(target or ""))
    notice_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
    notice_item.setData(Qt.UserRole, clean_options)
    table.setItem(row, 1, notice_item)

def _alias_notice_name_from_row(self, table: QTableWidget, row: int) -> str:
    notice_item = table.item(row, 1)
    return str(notice_item.text() if notice_item else "").strip()

def _sync_current_type_cards_from_ui(self) -> None:
    self._init_official_docs_state()
    context = self._current_type_selection_context()
    node_kind = str(context.get("node_kind", "") or "")
    if node_kind not in {TYPE_NODE_KIND_GROUP, TYPE_NODE_KIND_UNGROUPED_TYPE, TYPE_NODE_KIND_GROUP_MEMBER}:
        return
    kind = normalize_notice_type(
        str(context.get("type_key", "") or getattr(self, "_official_docs_current_type", "exam_opinion") or "exam_opinion")
    )
    member_keys = self._resolve_type_group_member_keys(kind)
    context_member_keys = [
        normalize_notice_type(str(item or "").strip())
        for item in list(context.get("member_keys", []) or [])
        if normalize_notice_type(str(item or "").strip())
    ]
    if context_member_keys:
        member_keys = context_member_keys
    if not member_keys and kind:
        member_keys = [kind]
    settings = getattr(self, "_official_docs_working_settings", None)
    if not isinstance(settings, dict):
        return

    type_configs = settings.setdefault("type_configs", {})
    if not isinstance(type_configs, dict):
        type_configs = {}
        settings["type_configs"] = type_configs

    mode_combo = getattr(self, "official_docs_naming_mode_combo", None)
    naming_mode = "default"
    try:
        if mode_combo is not None:
            naming_mode = str(mode_combo.currentData() or "default").strip().lower()
    except Exception:
        naming_mode = "default"
    if naming_mode not in ("default", "custom"):
        naming_mode = "default"

    cards_widget = self._official_docs_cards_widget()
    filename_fields = self._list_widget_to_cards(cards_widget)
    if not filename_fields:
        filename_fields = _default_kind_cards(kind)

    alias_table = getattr(self, "official_docs_alias_table", None)
    alias_rows: list[dict[str, Any]] = []
    if isinstance(alias_table, QTableWidget):
        for row in range(alias_table.rowCount()):
            enabled_item = alias_table.item(row, 0)
            short_item = alias_table.item(row, 2)
            notice_name = self._alias_notice_name_from_row(alias_table, row)
            short_name = str(short_item.text() if short_item else "").strip()
            if not notice_name or not short_name:
                continue
            enabled = bool(enabled_item and enabled_item.checkState() == Qt.Checked)
            alias_rows.append(
                {
                    "notice_name": notice_name,
                    "short_name": short_name,
                    "enabled": enabled,
                }
            )
    payload = {
        "naming_mode": naming_mode,
        "filename_fields": filename_fields,
        "alias_rules": alias_rows,
    }
    if node_kind == TYPE_NODE_KIND_GROUP:
        group = _find_naming_group(settings, str(context.get("group_id", "") or ""))
        if isinstance(group, dict):
            normalized = normalize_type_naming_config(payload, kind or "exam_opinion")
            group_payload = self._serialize_type_cfg(normalized)
            group_payload["alias_rules"] = []
            group["group_config"] = group_payload
        return

    target_keys = [kind] if node_kind == TYPE_NODE_KIND_GROUP_MEMBER and kind else list(member_keys)
    for member_key in target_keys:
        existing_raw_cfg = type_configs.get(member_key)
        normalized = normalize_type_naming_config(
            payload if node_kind == TYPE_NODE_KIND_UNGROUPED_TYPE else existing_raw_cfg,
            member_key,
        )
        serialized = self._serialize_type_cfg(normalized)
        if node_kind == TYPE_NODE_KIND_UNGROUPED_TYPE:
            serialized["naming_mode"] = naming_mode
            serialized["filename_fields"] = filename_fields
        serialized["alias_rules"] = list(alias_rows)
        type_configs[member_key] = serialized

def _load_type_cards_to_ui(self, kind: str) -> None:
    self._init_official_docs_state()
    selection_context = self._current_type_selection_context()
    node_kind = str(selection_context.get("node_kind", "") or TYPE_NODE_KIND_UNGROUPED_TYPE)
    display_name = str(selection_context.get("display_name", "") or "").strip()
    notice_type = normalize_notice_type(
        kind
        or str(selection_context.get("type_key", "") or "")
        or str(getattr(self, "_official_docs_current_type", "exam_opinion") or "exam_opinion")
    )
    member_keys = [
        normalize_notice_type(str(item or "").strip())
        for item in list(selection_context.get("member_keys", []) or [])
        if normalize_notice_type(str(item or "").strip())
    ]
    if notice_type and notice_type not in member_keys:
        member_keys = [notice_type, *member_keys]
    self._official_docs_current_type = notice_type or "exam_opinion"

    settings = self._get_official_docs_settings_snapshot(sync_current_type=False)
    type_configs = settings.get("type_configs", {})
    if not isinstance(type_configs, dict):
        type_configs = {}
    editable = False
    alias_visible = False
    alias_editable = False
    scope_text = "当前编辑：请先选择左侧对象"
    hint_text = ""
    alias_title_text = "通知书简称规则"
    cfg_dict: dict[str, Any] | None = None

    if node_kind == TYPE_NODE_KIND_GROUP:
        group = _find_naming_group(settings, str(selection_context.get("group_id", "") or ""))
        group_name = str(group.get("name", "") or "").strip() if isinstance(group, dict) else "未命名分组"
        group_id = str(group.get("id", "") or "").strip() if isinstance(group, dict) else ""
        group_member_keys = [
            normalize_notice_type(str(item or "").strip())
            for item in list(group.get("member_type_keys", []) if isinstance(group, dict) else [])
            if normalize_notice_type(str(item or "").strip())
        ]
        if group_member_keys:
            member_keys = list(group_member_keys)
        notice_type = _group_config_notice_type_hint(group_id, member_keys, notice_type or "exam_opinion")
        self._official_docs_current_type = notice_type or "exam_opinion"
        raw_cfg = group.get("group_config") if isinstance(group, dict) else None
        normalized_cfg = normalize_type_naming_config(raw_cfg, notice_type or "exam_opinion")
        cfg_dict = self._serialize_type_cfg(normalized_cfg)
        cfg_dict["alias_rules"] = []
        editable = True
        scope_text = f"当前编辑：分组“{group_name}”"
    elif node_kind == TYPE_NODE_KIND_UNGROUPED_TYPE:
        source_key = notice_type
        for candidate in member_keys:
            if candidate in type_configs:
                source_key = candidate
                break
        raw_type_cfg = type_configs.get(source_key)
        type_cfg = normalize_type_naming_config(raw_type_cfg, source_key or notice_type or "exam_opinion")
        cfg_dict = self._serialize_type_cfg(type_cfg)
        cfg_dict["alias_rules"] = _explicit_alias_rows_from_raw_cfg(raw_type_cfg)
        editable = True
        alias_visible = True
        alias_editable = True
        scope_text = f"当前编辑：未分组类型“{display_name or get_type_display_name(notice_type)}”"
    elif node_kind == TYPE_NODE_KIND_GROUP_MEMBER:
        group = _find_naming_group(settings, str(selection_context.get("group_id", "") or ""))
        raw_cfg = group.get("group_config") if isinstance(group, dict) else None
        normalized_cfg = normalize_type_naming_config(raw_cfg, notice_type or "exam_opinion")
        cfg_dict = self._serialize_type_cfg(normalized_cfg)
        cfg_dict["alias_rules"] = _explicit_alias_rows_from_raw_cfg(type_configs.get(notice_type))
        alias_visible = True
        alias_editable = True
        scope_text = f"当前编辑：类型“{display_name or get_type_display_name(notice_type)}”"
    else:
        scope_text = "当前编辑：请先选择左侧对象"
        hint_text = ""

    if node_kind in {TYPE_NODE_KIND_GROUP, TYPE_NODE_KIND_GROUP_MEMBER} and _has_mixed_receipt_field_system(member_keys):
        hint_text = "该分组包含不同字段体系（收据和普通通知书），字段会按各自通知书类型生效。"

    self._official_docs_signals_blocked = True
    try:
        mode_combo = getattr(self, "official_docs_naming_mode_combo", None)
        if mode_combo is not None:
            target_idx = 0
            if isinstance(cfg_dict, dict):
                for index in range(mode_combo.count()):
                    if str(mode_combo.itemData(index) or "").strip() == str(cfg_dict.get("naming_mode", "default")):
                        target_idx = index
                        break
            with QSignalBlocker(mode_combo):
                mode_combo.setCurrentIndex(target_idx)

        cards_widget = self._official_docs_cards_widget()
        self._set_cards_to_widget(cards_widget, list((cfg_dict or {}).get("filename_fields", [])))

        alias_table = getattr(self, "official_docs_alias_table", None)
        if isinstance(alias_table, QTableWidget):
            self._official_docs_alias_loading = True
            try:
                with QSignalBlocker(alias_table):
                    alias_table.setRowCount(0)
                    notice_options = self._current_type_alias_notice_options(notice_type) if isinstance(cfg_dict, dict) else []
                    for row_data in list((cfg_dict or {}).get("alias_rules", [])):
                        row_idx = alias_table.rowCount()
                        alias_table.insertRow(row_idx)

                        enabled_item = QTableWidgetItem("")
                        enabled_item.setFlags(
                            Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
                        )
                        enabled_item.setCheckState(Qt.Checked if bool(row_data.get("enabled", False)) else Qt.Unchecked)
                        alias_table.setItem(row_idx, 0, enabled_item)
                        notice_name = str(row_data.get("notice_name", "") or "").strip()
                        self._set_alias_notice_item(
                            alias_table,
                            row_idx,
                            notice_name=notice_name,
                            options=notice_options,
                        )
                        short_item = QTableWidgetItem(str(row_data.get("short_name", "") or ""))
                        alias_table.setItem(row_idx, 2, short_item)
            finally:
                self._official_docs_alias_loading = False
    finally:
        self._official_docs_signals_blocked = False

    mode_combo = getattr(self, "official_docs_naming_mode_combo", None)
    mode = str(mode_combo.currentData() if mode_combo is not None else "default")
    self._set_official_docs_naming_scope(scope_text, hint_text)
    self._refresh_official_docs_naming_mode_labels()
    alias_card = getattr(self, "official_docs_alias_card", None)
    if alias_card is not None:
        alias_card.setVisible(bool(alias_visible))
    alias_title_label = getattr(self, "official_docs_alias_title_label", None)
    if alias_title_label is not None:
        alias_title_label.setText(alias_title_text)
    if mode_combo is not None:
        mode_combo.setEnabled(bool(editable))
    self._set_filename_fields_card_editable(bool(editable) and mode == "custom")
    alias_table = getattr(self, "official_docs_alias_table", None)
    if alias_table is not None:
        alias_table.setEnabled(bool(alias_editable))
    for attr_name in ("official_docs_add_alias_button", "official_docs_remove_alias_button"):
        button = getattr(self, attr_name, None)
        if button is not None:
            button.setEnabled(bool(alias_editable))
    parse_enabled = bool(
        getattr(self, "official_docs_chk_exam_pdf_parse", None)
        and self.official_docs_chk_exam_pdf_parse.isChecked()
    )
    self._set_pdf_parse_field_checks_enabled(parse_enabled)

    self._refresh_official_docs_type_action_buttons()
    self._refresh_official_docs_settings_preview_line()

def _sample_meta_for_type(self, notice_type: str) -> NoticeMeta:
    key = normalize_notice_type(notice_type)
    if key == "exam_opinion":
        default_name = "第一次审查意见通知书"
        notice_code = "210401"
    elif key == "rectification":
        default_name = "第一次补正通知书"
        notice_code = "220301"
    elif key == RECEIPT_TYPE_KEY:
        return NoticeMeta(
            notice_code="10071",
            notice_name="电子提交收据",
            app_no="202510000001.0",
            applicant="示例缴费人",
            patent_type="发明专利",
            receipt_payer="示例缴费人",
            receipt_app_no="202510000001.0",
            receipt_patent_type="发明专利",
            receipt_fee_item="发明专利第4年年费",
            receipt_fee_item_first="发明专利第4年年费",
            receipt_fee_item_summary="发明专利第4年年费",
            receipt_amount="180.00",
        )
    elif "|" in key:
        code_part, name_part = key.split("|", 1)
        default_name = str(name_part or "").strip() or "通知书"
        notice_code = str(code_part or "").strip()
    else:
        default_name = "通知书"
        notice_code = ""

    text_for_guess = f"{key} {default_name}"
    if "外观" in text_for_guess:
        patent_group = "外观专利"
        sample_app_no = "2025313838195"
    elif "实用" in text_for_guess:
        patent_group = "实用新型专利"
        sample_app_no = "2025213838195"
    else:
        patent_group = "发明专利"
        sample_app_no = "2025113838195"

    return NoticeMeta(
        notice_name=default_name,
        app_no=sample_app_no,
        issue_date="2025-11-06",
        patent_type=patent_group,
        notice_code=notice_code,
        invention_name="一种示例发明",
        applicant="示例申请人",
    )

def _find_selected_meta_for_type(self, notice_type: str) -> NoticeMeta | None:
    selected_leaf_id = str(getattr(self, "_official_docs_selected_leaf_id", "") or "").strip()
    if not selected_leaf_id:
        return None
    leaf = (getattr(self, "_official_docs_leaves", {}) or {}).get(selected_leaf_id)
    if not isinstance(leaf, dict):
        return None
    parsed = leaf.get("parsed")
    if not isinstance(parsed, ParsedNotice):
        return None
    if self._type_key_from_parsed(parsed) != normalize_notice_type(notice_type):
        return None
    return parsed.meta

def _refresh_official_docs_settings_preview_line(self) -> None:
    self._init_official_docs_state()
    label = getattr(self, "official_docs_filename_preview_label", None)
    if label is None:
        label = getattr(self, "official_docs_settings_line_preview", None)
    if label is None:
        return

    selection_context = self._current_type_selection_context()
    node_kind = str(selection_context.get("node_kind", "") or TYPE_NODE_KIND_UNGROUPED_ROOT)
    if node_kind not in {TYPE_NODE_KIND_GROUP, TYPE_NODE_KIND_UNGROUPED_TYPE, TYPE_NODE_KIND_GROUP_MEMBER}:
        label.setText("文件名预览：请选择左侧的分组或类型")
        return

    settings = self._get_official_docs_settings_snapshot(sync_current_type=True)
    notice_type = normalize_notice_type(getattr(self, "_official_docs_current_type", "exam_opinion"))
    payload = self._build_type_tree_payload(settings)
    option_groups: dict[str, NamingGroupConfig] = {}
    for raw_group in list(payload.get("naming_groups", []) or []):
        if not isinstance(raw_group, dict):
            continue
        group_id = str(raw_group.get("id", "") or "").strip()
        group_name = str(raw_group.get("name", "") or "").strip()
        if not group_id or not group_name:
            continue
        member_type_keys = [
            normalize_notice_type(str(raw_key or "").strip())
            for raw_key in list(raw_group.get("member_type_keys", []) or [])
            if normalize_notice_type(str(raw_key or "").strip())
        ]
        group_notice_type = _group_config_notice_type_hint(group_id, member_type_keys, notice_type or "exam_opinion")
        option_groups[group_id] = NamingGroupConfig(
            id=group_id,
            name=group_name,
            member_type_keys=member_type_keys,
            group_config=normalize_type_naming_config(
                raw_group.get("group_config"),
                group_notice_type,
            ),
        )

    if node_kind == TYPE_NODE_KIND_GROUP:
        group = _find_naming_group(settings, str(selection_context.get("group_id", "") or ""))
        group_id = str(group.get("id", "") or "").strip() if isinstance(group, dict) else ""
        member_type_keys = [
            normalize_notice_type(str(raw_key or "").strip())
            for raw_key in list(group.get("member_type_keys", []) if isinstance(group, dict) else [])
            if normalize_notice_type(str(raw_key or "").strip())
        ]
        notice_type = _group_config_notice_type_hint(group_id, member_type_keys, notice_type or "exam_opinion")

    type_cfg = normalize_type_naming_config((settings.get("type_configs", {}) or {}).get(notice_type), notice_type)

    summary_root = str(settings.get("summary_root_dir", "") or "").strip()
    archive_root = str(settings.get("archive_root_dir", "") or "").strip()
    options = ProcessOptions(
        summary_root_dir=summary_root,
        archive_root_dir=archive_root,
        write_summary=bool(settings.get("write_summary", True)),
        write_archive=bool(settings.get("write_archive", False)),
        confirm_each=bool(settings.get("confirm_each", False)),
        enable_exam_pdf_parse=bool(settings.get("enable_exam_pdf_parse", False)),
        filename_separator=str(settings.get("filename_separator", "+")),
        type_naming_configs={notice_type: type_cfg},
        naming_groups=option_groups,
        type_group_membership=dict(payload.get("type_group_membership", {}) or {}),
    )

    meta = self._find_selected_meta_for_type(notice_type) or self._sample_meta_for_type(notice_type)
    preview = render_notice_output_preview(meta=meta, notice_kind=notice_type, options=options)
    output_name = str(preview.preview_pdf_name or "").strip() or "-"
    raw_app_no = str(meta.app_no or "").strip()
    if raw_app_no and output_name and output_name != "-":
        output_name = output_name.replace(raw_app_no, mask_app_no_for_preview(raw_app_no))
    label.setText(f"文件名预览：{output_name}")
