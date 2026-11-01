from __future__ import annotations

from core.user_messages import user_error_text

from .shared import (
    Any,
    CONFIG_TAB_INDEXES,
    NAMING_ALIAS_SPLITTER_DEFAULT,
    NAMING_ALIAS_SPLITTER_KEY,
    OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION,
    OFFICIAL_DOC_BASE_TYPES,
    OFFICIAL_DOC_SETTINGS_VERSION,
    PDF_PARSE_FIELD_FLAGS_DEFAULT,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QSignalBlocker,
    QTableWidget,
    QTableWidgetItem,
    QTimer,
    QTreeWidgetItem,
    Qt,
    TYPE_NODE_KIND_UNGROUPED_ROOT,
    TYPE_NODE_KIND_GROUP,
    _group_config_notice_type_hint,
    _normalize_naming_alias_splitter_sizes,
    _default_kind_cards,
    copy,
    get_type_display_name,
    get_type_tokens,
    normalize_filename_separator,
    normalize_notice_type,
    normalize_type_naming_config,
    os,
    set_official_doc_settings,
    show_official_docs_archive_consent_dialog,
    show_official_docs_pdf_parse_enable_notice_dialog,
    validate_filename_separator,
)


def _update_official_docs_settings_dirty_ui(self) -> None:
    self._init_official_docs_state()
    dirty = bool(getattr(self, "_official_docs_dirty", False))
    save_btn = getattr(self, "official_docs_settings_save_button", None)
    if save_btn is not None:
        save_btn.setEnabled(dirty)
    error_label = getattr(self, "official_docs_settings_error_label", None)
    if error_label is not None and not dirty and not str(error_label.text() or "").strip():
        self._set_official_docs_settings_message("")

def _set_official_docs_settings_message(self, text: str) -> None:
    label = getattr(self, "official_docs_settings_error_label", None)
    if label is None:
        return
    message = str(text or "").strip()
    label.setText(message)
    label.setVisible(bool(message))

def _current_default_naming_notice_type(self) -> str:
    current_type = normalize_notice_type(getattr(self, "_official_docs_current_type", "exam_opinion") or "exam_opinion")
    try:
        context = self._current_type_selection_context()
    except Exception:
        context = {}
    if str(context.get("node_kind", "") or "") != TYPE_NODE_KIND_GROUP:
        return current_type or "exam_opinion"

    settings = getattr(self, "_official_docs_working_settings", {})
    group_id = str(context.get("group_id", "") or "").strip()
    member_keys: list[str] = []
    if isinstance(settings, dict):
        for raw_group in list(settings.get("naming_groups", []) or []):
            if not isinstance(raw_group, dict) or str(raw_group.get("id", "") or "").strip() != group_id:
                continue
            member_keys = [
                normalize_notice_type(str(item or "").strip())
                for item in list(raw_group.get("member_type_keys", []) or [])
                if normalize_notice_type(str(item or "").strip())
            ]
            break
    if not member_keys:
        member_keys = [
            normalize_notice_type(str(item or "").strip())
            for item in list(context.get("member_keys", []) or [])
            if normalize_notice_type(str(item or "").strip())
        ]
    return _group_config_notice_type_hint(group_id, member_keys, current_type or "exam_opinion")

def _refresh_official_docs_naming_mode_labels(self) -> None:
    mode_combo = getattr(self, "official_docs_naming_mode_combo", None)
    if mode_combo is None:
        return
    separator_edit = getattr(self, "official_docs_filename_separator_edit", None)
    if separator_edit is not None:
        raw_separator = str(separator_edit.text())
    else:
        settings = getattr(self, "_official_docs_working_settings", {})
        raw_separator = str(settings.get("filename_separator", "+") if isinstance(settings, dict) else "+")
    separator = normalize_filename_separator(raw_separator)
    default_text = f"默认（{separator.join(_default_kind_cards(_current_default_naming_notice_type(self)))}）"
    for index in range(mode_combo.count()):
        if str(mode_combo.itemData(index) or "").strip() == "default":
            with QSignalBlocker(mode_combo):
                mode_combo.setItemText(index, default_text)
            return

def _collect_official_docs_naming_splitter_sizes(self) -> list[int] | None:
    splitter = getattr(self, "official_docs_naming_splitter", None)
    if splitter is None:
        return None
    return _normalize_naming_alias_splitter_sizes(splitter.sizes())

def _apply_official_docs_naming_splitter_sizes(self, sizes: Any | None = None) -> None:
    splitter = getattr(self, "official_docs_naming_splitter", None)
    if splitter is None:
        return
    target_sizes = _normalize_naming_alias_splitter_sizes(sizes)
    if target_sizes is None:
        settings = getattr(self, "_official_docs_working_settings", {})
        if isinstance(settings, dict):
            target_sizes = _normalize_naming_alias_splitter_sizes(settings.get(NAMING_ALIAS_SPLITTER_KEY))
    if target_sizes is None:
        target_sizes = list(NAMING_ALIAS_SPLITTER_DEFAULT)

    self._official_docs_naming_splitter_syncing = True
    try:
        splitter.setSizes(target_sizes)
    except Exception:
        pass
    finally:
        self._official_docs_naming_splitter_syncing = False

def _persist_official_docs_naming_splitter_sizes(self) -> None:
    self._init_official_docs_state()
    sizes = _normalize_naming_alias_splitter_sizes(getattr(self, "_official_docs_naming_splitter_sizes_pending", None))
    if sizes is None:
        sizes = self._collect_official_docs_naming_splitter_sizes()
    if sizes is None:
        return

    saved = getattr(self, "_official_docs_saved_settings", None)
    working = getattr(self, "_official_docs_working_settings", None)
    if isinstance(saved, dict):
        saved[NAMING_ALIAS_SPLITTER_KEY] = list(sizes)
    if isinstance(working, dict):
        working[NAMING_ALIAS_SPLITTER_KEY] = list(sizes)

    try:
        persisted = copy.deepcopy(saved) if isinstance(saved, dict) else {}
        if not isinstance(persisted, dict):
            persisted = {}
        persisted["version"] = OFFICIAL_DOC_SETTINGS_VERSION
        persisted[NAMING_ALIAS_SPLITTER_KEY] = list(sizes)
        set_official_doc_settings(persisted)
    except Exception:
        pass
    self._official_docs_naming_splitter_sizes_pending = None

def on_official_docs_naming_splitter_moved(self, _pos: int, _index: int) -> None:
    self._init_official_docs_state()
    if bool(getattr(self, "_official_docs_naming_splitter_syncing", False)):
        return
    sizes = self._collect_official_docs_naming_splitter_sizes()
    if sizes is None:
        return
    self._official_docs_naming_splitter_sizes_pending = sizes
    timer = getattr(self, "_official_docs_naming_splitter_save_timer", None)
    if isinstance(timer, QTimer):
        timer.start(250)
    else:
        self._persist_official_docs_naming_splitter_sizes()

def _apply_official_docs_settings_to_ui(self) -> None:
    self._init_official_docs_state()
    settings = self._get_official_docs_settings_snapshot(sync_current_type=False)

    self._official_docs_signals_blocked = True
    try:
        checkbox_mapping = [
            ("official_docs_chk_summary", "write_summary"),
            ("official_docs_chk_archive", "write_archive"),
            ("official_docs_chk_confirm", "confirm_each"),
            ("official_docs_chk_exam_pdf_parse", "enable_exam_pdf_parse"),
        ]
        for widget_name, key in checkbox_mapping:
            widget = getattr(self, widget_name, None)
            if widget is not None:
                with QSignalBlocker(widget):
                    widget.setChecked(bool(settings.get(key, False)))

        mode_combo = getattr(self, "official_docs_no_list_multi_pdf_mode_combo", None)
        if mode_combo is not None:
            target_mode = str(settings.get("no_list_multi_pdf_mode", "split_each_pdf") or "split_each_pdf").strip().lower()
            if target_mode != "merge_all":
                target_mode = "split_each_pdf"
            with QSignalBlocker(mode_combo):
                index = int(mode_combo.findData(target_mode))
                mode_combo.setCurrentIndex(index if index >= 0 else 0)

        pdf_field_flags = settings.get("pdf_parse_field_flags", {})
        if not isinstance(pdf_field_flags, dict):
            pdf_field_flags = {}
        for field_key, widget in self._pdf_parse_field_widgets().items():
            with QSignalBlocker(widget):
                widget.setChecked(bool(pdf_field_flags.get(field_key, False)))

        summary_edit = getattr(self, "official_docs_summary_root_edit", None)
        if summary_edit is not None:
            with QSignalBlocker(summary_edit):
                summary_edit.setText(str(settings.get("summary_root_dir", "") or ""))

        archive_edit = getattr(self, "official_docs_archive_root_edit", None)
        if archive_edit is not None:
            with QSignalBlocker(archive_edit):
                archive_edit.setText(str(settings.get("archive_root_dir", "") or ""))

        separator_edit = getattr(self, "official_docs_filename_separator_edit", None)
        if separator_edit is not None:
            with QSignalBlocker(separator_edit):
                separator_edit.setText(str(settings.get("filename_separator", "+") or "+"))

        type_search_edit = getattr(self, "official_docs_settings_type_search_edit", None)
        if type_search_edit is not None:
            with QSignalBlocker(type_search_edit):
                type_search_edit.setText(str(getattr(self, "_official_docs_type_search_text", "") or ""))

        self._refresh_official_docs_naming_mode_labels()
        current_type = normalize_notice_type(getattr(self, "_official_docs_current_type", "exam_opinion"))
        target_type = self._refresh_official_docs_type_list(current_type)
        self._load_type_cards_to_ui(target_type)
        self._apply_official_docs_naming_splitter_sizes(settings.get(NAMING_ALIAS_SPLITTER_KEY))
        parse_enabled = bool(settings.get("enable_exam_pdf_parse", False))
        self._set_pdf_parse_field_checks_enabled(parse_enabled)
    finally:
        self._official_docs_signals_blocked = False

    self._refresh_official_docs_settings_preview_line()
    self._update_official_docs_settings_dirty_ui()

def _refresh_official_docs_page_from_state(self) -> None:
    self._init_official_docs_state()
    self._apply_official_docs_settings_to_ui()
    self._render_official_docs_tree()
    self._refresh_official_docs_detail()

def _confirm_leave_official_docs_if_dirty(self) -> bool:
    self._init_official_docs_state()
    if not bool(getattr(self, "_official_docs_dirty", False)):
        return True

    box = QMessageBox(self)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("官文设置未保存")
    box.setText("官文处理设置已修改但尚未保存。是否先保存？")
    btn_save = box.addButton("保存", QMessageBox.AcceptRole)
    btn_discard = box.addButton("不保存", QMessageBox.DestructiveRole)
    box.addButton("取消", QMessageBox.RejectRole)
    box.setDefaultButton(btn_save)
    box.exec()

    clicked = box.clickedButton()
    if clicked is btn_save:
        return bool(self.on_official_docs_save_settings())
    if clicked is btn_discard:
        self._official_docs_working_settings = copy.deepcopy(self._official_docs_saved_settings)
        self._official_docs_dirty = False
        self._apply_official_docs_settings_to_ui()
        self._refresh_official_docs_detail()
        return True
    return False

def on_official_docs_tab_changed(self, index: int) -> None:
    self._init_official_docs_state()
    if bool(getattr(self, "_official_docs_tab_switching", False)):
        return
    prev_index = int(getattr(self, "_official_docs_last_tab_index", 0) or 0)
    target_index = int(index)
    leaving_config_area = prev_index in CONFIG_TAB_INDEXES and target_index not in CONFIG_TAB_INDEXES
    if leaving_config_area and bool(getattr(self, "_official_docs_dirty", False)):
        ok = self._confirm_leave_official_docs_if_dirty()
        if not ok:
            tabs = getattr(self, "official_docs_tabs", None)
            if tabs is not None:
                self._official_docs_tab_switching = True
                try:
                    tabs.setCurrentIndex(prev_index if prev_index in CONFIG_TAB_INDEXES else 1)
                finally:
                    self._official_docs_tab_switching = False
            return
    self._official_docs_last_tab_index = target_index
    self._refresh_official_docs_detail()

def _ensure_archive_consent(self) -> bool:
    self._init_official_docs_state()
    settings = self._get_official_docs_settings_snapshot(sync_current_type=True)
    accepted_version = int(settings.get("archive_consent_accepted_version", 0) or 0)
    target_version = int(
        settings.get("archive_consent_doc_version", OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION)
        or OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION
    )
    if accepted_version >= target_version:
        return True

    ok = bool(show_official_docs_archive_consent_dialog(self, doc_version=target_version))
    if not ok:
        return False

    self._official_docs_working_settings["archive_consent_doc_version"] = target_version
    self._official_docs_working_settings["archive_consent_accepted_version"] = target_version
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    self._update_official_docs_settings_dirty_ui()
    return True

def on_official_docs_archive_checkbox_toggled(self, checked: bool) -> None:
    self._init_official_docs_state()
    if bool(getattr(self, "_official_docs_signals_blocked", False)):
        return
    if bool(checked):
        if not self._ensure_archive_consent():
            checkbox = getattr(self, "official_docs_chk_archive", None)
            if checkbox is not None:
                with QSignalBlocker(checkbox):
                    checkbox.setChecked(False)
            return
    self.on_official_docs_settings_changed()

def _persist_pdf_parse_notice_preference(self, suppressed: bool) -> None:
    self._init_official_docs_state()
    value = bool(suppressed)
    if isinstance(getattr(self, "_official_docs_working_settings", None), dict):
        self._official_docs_working_settings["pdf_parse_enable_notice_suppressed"] = value
    if isinstance(getattr(self, "_official_docs_saved_settings", None), dict):
        self._official_docs_saved_settings["pdf_parse_enable_notice_suppressed"] = value
    try:
        persisted = copy.deepcopy(getattr(self, "_official_docs_saved_settings", {}) or {})
        if not isinstance(persisted, dict):
            persisted = {}
        persisted["pdf_parse_enable_notice_suppressed"] = value
        set_official_doc_settings(persisted)
    except Exception:
        pass

def on_official_docs_settings_changed(self, *_args: Any) -> None:
    self._init_official_docs_state()
    if bool(getattr(self, "_official_docs_signals_blocked", False)):
        return
    self._set_official_docs_settings_message("")
    self._sync_current_type_cards_from_ui()

    settings = self._official_docs_working_settings
    prev_parse_enabled = bool(settings.get("enable_exam_pdf_parse", False))
    parse_checkbox = getattr(self, "official_docs_chk_exam_pdf_parse", None)
    next_parse_enabled = bool(parse_checkbox and parse_checkbox.isChecked())
    parse_notice_suppressed = bool(settings.get("pdf_parse_enable_notice_suppressed", False))
    if next_parse_enabled and (not prev_parse_enabled) and (not parse_notice_suppressed):
        enable_confirmed, suppress_future = show_official_docs_pdf_parse_enable_notice_dialog(self)
        if bool(suppress_future):
            _persist_pdf_parse_notice_preference(self, True)
            settings["pdf_parse_enable_notice_suppressed"] = True
        if not bool(enable_confirmed):
            if parse_checkbox is not None:
                with QSignalBlocker(parse_checkbox):
                    parse_checkbox.setChecked(False)
            next_parse_enabled = False

    settings["write_summary"] = bool(getattr(self, "official_docs_chk_summary", None) and self.official_docs_chk_summary.isChecked())
    settings["write_archive"] = bool(getattr(self, "official_docs_chk_archive", None) and self.official_docs_chk_archive.isChecked())
    settings["confirm_each"] = bool(getattr(self, "official_docs_chk_confirm", None) and self.official_docs_chk_confirm.isChecked())
    mode_combo = getattr(self, "official_docs_no_list_multi_pdf_mode_combo", None)
    settings["no_list_multi_pdf_mode"] = str(mode_combo.currentData() if mode_combo is not None else "split_each_pdf").strip() or "split_each_pdf"
    settings["enable_exam_pdf_parse"] = bool(next_parse_enabled)
    parse_enabled = bool(settings.get("enable_exam_pdf_parse", False))
    self._set_pdf_parse_field_checks_enabled(parse_enabled)
    pdf_flags = dict(PDF_PARSE_FIELD_FLAGS_DEFAULT)
    for field_key, widget in self._pdf_parse_field_widgets().items():
        pdf_flags[field_key] = bool(widget.isChecked())
    settings["pdf_parse_field_flags"] = pdf_flags

    summary_edit = getattr(self, "official_docs_summary_root_edit", None)
    archive_edit = getattr(self, "official_docs_archive_root_edit", None)
    separator_edit = getattr(self, "official_docs_filename_separator_edit", None)
    settings["summary_root_dir"] = str(summary_edit.text() if summary_edit is not None else "").strip()
    settings["archive_root_dir"] = str(archive_edit.text() if archive_edit is not None else "").strip()
    settings["filename_separator"] = str(separator_edit.text() if separator_edit is not None else "+")

    mode_combo = getattr(self, "official_docs_naming_mode_combo", None)
    mode_text = str(mode_combo.currentData() if mode_combo is not None else "default").strip().lower()
    self._set_filename_fields_card_editable(mode_text == "custom")

    self._refresh_official_docs_naming_mode_labels()
    self._official_docs_dirty = bool(settings != self._official_docs_saved_settings)
    self._update_official_docs_settings_dirty_ui()
    self._refresh_official_docs_settings_preview_line()
    self._refresh_official_docs_detail()

def on_official_docs_type_selection_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
    self._init_official_docs_state()
    if bool(getattr(self, "_official_docs_signals_blocked", False)) or bool(getattr(self, "_official_docs_type_tree_rebuilding", False)):
        return
    tree = getattr(self, "official_docs_settings_type_tree", None)
    if bool(getattr(tree, "_suppress_focus_selection_change", False)):
        return

    self._sync_current_type_cards_from_ui()
    context = self._type_tree_context_from_item(current)
    self._set_type_selection_context(
        node_kind=str(context.get("node_kind", "") or TYPE_NODE_KIND_UNGROUPED_ROOT),
        group_id=str(context.get("group_id", "") or ""),
        type_key=str(context.get("type_key", "") or ""),
        member_keys=list(context.get("member_keys", []) or []),
        display_name=str(context.get("display_name", "") or ""),
    )
    kind = normalize_notice_type(str(context.get("type_key", "") or getattr(self, "_official_docs_current_type", "exam_opinion")))
    self._load_type_cards_to_ui(kind)
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    self._update_official_docs_settings_dirty_ui()
    self._refresh_official_docs_detail()

def on_official_docs_type_search_changed(self, text: str) -> None:
    self._init_official_docs_state()
    if bool(getattr(self, "_official_docs_signals_blocked", False)):
        return
    self._official_docs_type_search_text = str(text or "").strip()
    self._sync_current_type_cards_from_ui()
    target = self._refresh_official_docs_type_list(getattr(self, "_official_docs_current_type", ""))
    self._load_type_cards_to_ui(target)
    self._official_docs_dirty = bool(self._official_docs_working_settings != self._official_docs_saved_settings)
    self._update_official_docs_settings_dirty_ui()
    self._refresh_official_docs_detail()

def _append_card_to_target(self, token: str) -> None:
    widget = self._official_docs_cards_widget()
    if widget is None:
        return
    text = str(token or "").strip()
    if not text:
        return
    widget.addItem(self._card_to_item(text))
    row = widget.count() - 1
    if row >= 0:
        widget.setCurrentRow(row)

def on_official_docs_insert_field_card(self) -> None:
    self._init_official_docs_state()
    kind = normalize_notice_type(getattr(self, "_official_docs_current_type", "exam_opinion"))
    options = get_type_tokens(kind)
    if not options:
        return
    token, ok = QInputDialog.getItem(
        self,
        "插入字段",
        f"选择要加入“{get_type_display_name(kind)}”文件名构成的字段：",
        options,
        0,
        False,
    )
    if not ok:
        return
    token_text = str(token or "").strip()
    if not token_text:
        return
    self._append_card_to_target(token_text)
    self.on_official_docs_settings_changed()

def on_official_docs_move_field_up(self) -> None:
    widget = self._official_docs_cards_widget()
    if widget is None:
        return
    row = int(widget.currentRow())
    if row <= 0:
        return
    item = widget.takeItem(row)
    if item is None:
        return
    widget.insertItem(row - 1, item)
    widget.setCurrentRow(row - 1)
    self.on_official_docs_settings_changed()

def on_official_docs_move_field_down(self) -> None:
    widget = self._official_docs_cards_widget()
    if widget is None:
        return
    row = int(widget.currentRow())
    if row < 0 or row >= widget.count() - 1:
        return
    item = widget.takeItem(row)
    if item is None:
        return
    widget.insertItem(row + 1, item)
    widget.setCurrentRow(row + 1)
    self.on_official_docs_settings_changed()

def on_official_docs_remove_selected_field(self) -> None:
    widget = self._official_docs_cards_widget()
    if widget is None:
        return
    row = int(widget.currentRow())
    if row < 0:
        return
    widget.takeItem(row)
    self.on_official_docs_settings_changed()

def on_official_docs_clear_fields(self) -> None:
    widget = self._official_docs_cards_widget()
    if widget is None:
        return
    widget.clear()
    self.on_official_docs_settings_changed()

def on_official_docs_alias_table_changed(self, _item: QTableWidgetItem | None = None) -> None:
    if bool(getattr(self, "_official_docs_alias_loading", False)):
        return
    self.on_official_docs_settings_changed()

def on_official_docs_add_alias_rule(self) -> None:
    table = getattr(self, "official_docs_alias_table", None)
    if not isinstance(table, QTableWidget):
        return
    row_idx = table.rowCount()
    table.insertRow(row_idx)

    enabled_item = QTableWidgetItem("")
    enabled_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
    enabled_item.setCheckState(Qt.Unchecked)
    table.setItem(row_idx, 0, enabled_item)
    options = self._current_type_alias_notice_options(getattr(self, "_official_docs_current_type", ""))
    default_notice_name = options[0] if options else ""
    self._set_alias_notice_item(
        table,
        row_idx,
        notice_name=default_notice_name,
        options=options,
    )
    table.setItem(row_idx, 2, QTableWidgetItem(""))
    table.setCurrentCell(row_idx, 2)
    self.on_official_docs_settings_changed()

def on_official_docs_remove_alias_rule(self) -> None:
    table = getattr(self, "official_docs_alias_table", None)
    if not isinstance(table, QTableWidget):
        return
    row = int(table.currentRow())
    if row < 0:
        return
    table.removeRow(row)
    self.on_official_docs_settings_changed()

def _validate_official_docs_settings(self, settings: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    write_summary = bool(settings.get("write_summary", False))
    write_archive = bool(settings.get("write_archive", False))
    summary_root = str(settings.get("summary_root_dir", "") or "").strip()
    archive_root = str(settings.get("archive_root_dir", "") or "").strip()

    if (not write_summary) and (not write_archive):
        errors.append("至少启用一种输出模式（单次汇总或长期归档）。")
    if write_summary and not summary_root:
        errors.append("已启用“输出单次汇总”时，汇总根目录不能为空。")
    if write_archive and not archive_root:
        errors.append("已启用“输出长期归档”时，归档根目录不能为空。")
    separator_error = validate_filename_separator(settings.get("filename_separator", "+"))
    if separator_error:
        errors.append(separator_error)

    type_configs = settings.get("type_configs", {})
    if not isinstance(type_configs, dict):
        type_configs = {}
    type_keys = [normalize_notice_type(str(key or "").strip()) for key in type_configs.keys()]
    type_keys = [key for key in type_keys if key]
    if not type_keys:
        type_keys = [normalize_notice_type(item) for item in OFFICIAL_DOC_BASE_TYPES]
    for kind in type_keys:
        cfg = normalize_type_naming_config(type_configs.get(kind), kind)
        if str(cfg.naming_mode) == "custom":
            fields = [str(token or "").strip() for token in (cfg.filename_fields or []) if str(token or "").strip()]
            if not fields:
                errors.append(f"{get_type_display_name(kind)}已选择“自定义命名”，但文件名构成为空。")

    raw_groups = settings.get("naming_groups", [])
    raw_membership = settings.get("type_group_membership", {})
    name_seen: set[str] = set()
    member_owner: dict[str, str] = {}
    for raw_group in raw_groups if isinstance(raw_groups, list) else []:
        if not isinstance(raw_group, dict):
            continue
        group_id = str(raw_group.get("id", "") or "").strip()
        group_name = str(raw_group.get("name", "") or "").strip()
        if not group_id or not group_name:
            errors.append("命名分组的名称和标识不能为空。")
            continue
        if group_name in name_seen:
            errors.append(f"分组名称“{group_name}”重复。")
        name_seen.add(group_name)

        member_keys = [
            normalize_notice_type(str(item or "").strip())
            for item in list(raw_group.get("member_type_keys", []) or [])
            if normalize_notice_type(str(item or "").strip())
        ]
        for member_key in member_keys:
            owner = member_owner.get(member_key, "")
            if owner and owner != group_id:
                errors.append(f"{get_type_display_name(member_key)}同时出现在多个命名分组中。")
            member_owner[member_key] = group_id

        notice_type_hint = _group_config_notice_type_hint(group_id, member_keys, "exam_opinion")
        group_cfg = normalize_type_naming_config(raw_group.get("group_config"), notice_type_hint)
        if str(group_cfg.naming_mode) == "custom":
            fields = [str(token or "").strip() for token in (group_cfg.filename_fields or []) if str(token or "").strip()]
            if not fields:
                errors.append(f"分组“{group_name}”已选择“自定义命名”，但文件名构成为空。")

    if isinstance(raw_membership, dict):
        for raw_key, raw_group_id in raw_membership.items():
            member_key = normalize_notice_type(str(raw_key or "").strip())
            group_id = str(raw_group_id or "").strip()
            if not member_key or not group_id:
                continue
            owner = member_owner.get(member_key, "")
            if owner and owner != group_id:
                errors.append(f"{get_type_display_name(member_key)}同时映射到了多个分组。")

    return errors

def on_official_docs_save_settings(self) -> bool:
    self._init_official_docs_state()
    self._sync_current_type_cards_from_ui()
    settings = self._get_official_docs_settings_snapshot(sync_current_type=False)
    errors = self._validate_official_docs_settings(settings)

    if errors:
        self._set_official_docs_settings_message(errors[0])
        QMessageBox.warning(self, "保存失败", user_error_text("\n".join(errors)))
        return False

    normalized_groups, normalized_membership = self._normalize_naming_groups_payload(
        settings.get("naming_groups", []),
        settings.get("type_group_membership", {}),
    )
    settings["naming_groups"] = normalized_groups
    settings["type_group_membership"] = normalized_membership
    settings["filename_separator"] = normalize_filename_separator(settings.get("filename_separator", "+"))

    settings["version"] = OFFICIAL_DOC_SETTINGS_VERSION
    settings["archive_consent_doc_version"] = int(
        settings.get("archive_consent_doc_version", OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION)
        or OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION
    )

    set_official_doc_settings(settings)
    self._official_docs_saved_settings = copy.deepcopy(settings)
    self._official_docs_working_settings = copy.deepcopy(settings)
    self._official_docs_dirty = False

    self._set_official_docs_settings_message("设置已保存")
    QTimer.singleShot(
        1600,
        lambda: self._set_official_docs_settings_message("") if not self._official_docs_dirty else None,
    )

    self._update_official_docs_settings_dirty_ui()
    self._refresh_official_docs_settings_preview_line()
    self._refresh_official_docs_detail()
    return True

def on_official_docs_browse_summary_root(self) -> None:
    self._init_official_docs_state()
    summary_widget = getattr(self, "official_docs_summary_root_edit", None)
    current_path = str(summary_widget.text() if summary_widget is not None else "").strip()
    start_dir = current_path if current_path and os.path.isdir(current_path) else os.getcwd()
    selected = QFileDialog.getExistingDirectory(self, "选择汇总根目录", start_dir)
    if not selected:
        return
    if summary_widget is not None:
        summary_widget.setText(selected)
    self.on_official_docs_settings_changed()

def on_official_docs_browse_archive_root(self) -> None:
    self._init_official_docs_state()
    archive_widget = getattr(self, "official_docs_archive_root_edit", None)
    current_path = str(archive_widget.text() if archive_widget is not None else "").strip()
    start_dir = current_path if current_path and os.path.isdir(current_path) else os.getcwd()
    selected = QFileDialog.getExistingDirectory(self, "选择归档根目录", start_dir)
    if not selected:
        return
    if archive_widget is not None:
        archive_widget.setText(selected)
    self.on_official_docs_settings_changed()

def _ensure_node_exists(self, key: str, *, is_bundle: bool, display_name: str, source_path: str = "") -> dict[str, Any]:
    nodes = getattr(self, "_official_docs_nodes", None)
    if not isinstance(nodes, list):
        self._official_docs_nodes = []
        nodes = self._official_docs_nodes

    for node in nodes:
        if str(node.get("key", "") or "") == key:
            return node

    new_node = {
        "key": key,
        "is_bundle": bool(is_bundle),
        "display_name": str(display_name or "").strip(),
        "source_path": str(source_path or "").strip(),
        "children": [],
    }
    nodes.append(new_node)
    return new_node

