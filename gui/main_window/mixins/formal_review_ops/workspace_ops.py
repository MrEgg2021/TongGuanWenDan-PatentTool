from __future__ import annotations

from core.app_preferences import get_formal_review_auto_maximize

from .shared import (
    DockLayout,
    QTimer,
    QWidget,
    Qt,
    _COMMENT_COPY_PATH_PREF_KEY,
    _MARKER_NOTE_PREF_KEY,
    dock_app_and_word,
    get_word_hwnd,
    logger,
    set_pref,
)

__all__ = [
    "_apply_formal_review_entry_window_state",
    "_dock_companion_windows_once",
    "_set_splitter_order",
    "_apply_plain_workspace_layout",
    "_apply_companion_workspace_layout",
    "_attach_plain_center_panel",
    "_detach_plain_center_panel",
    "_apply_input_mode_to_ui",
    "_ignore_enabled",
    "_is_word_mode_editable",
    "_apply_claim_editor_readonly_state",
    "_update_marker_apply_enabled",
    "_reset_formal_review_runtime_state",
    "on_formal_review_mode_changed",
]

def _apply_formal_review_entry_window_state(self) -> None:
    def _apply() -> None:
        auto_maximize = False
        try:
            auto_maximize = bool(get_formal_review_auto_maximize(default=False))
        except Exception:
            auto_maximize = False
        if auto_maximize:
            try:
                self.showMaximized()
            except Exception:
                pass

    _apply()
    try:
        QTimer.singleShot(0, _apply)
    except Exception:
        pass

def _dock_companion_windows_once(self) -> None:
    if bool(getattr(self, "_formal_review_companion_docked_once", False)):
        return
    session = getattr(self, "_formal_review_companion_session", None)
    if session is None:
        return
    try:
        word_hwnd = int(get_word_hwnd(session) or 0)
    except Exception:
        word_hwnd = 0
    if not word_hwnd:
        self._set_status_text("形式审查：未找到 Word 窗口，已跳过自动停靠。")
        return
    try:
        app_hwnd = int(self.winId())
    except Exception:
        app_hwnd = 0
    if not app_hwnd:
        return

    result = dock_app_and_word(app_hwnd, word_hwnd, DockLayout(left_ratio=0.30, primary_monitor_only=True))
    if bool(getattr(result, "ok", False)):
        self._formal_review_companion_docked_once = True
        self._set_status_text("形式审查：应用窗口与 Word 窗口已自动停靠。")
    else:
        logger.warning(
            "[formal_review][docking] failed app_hwnd=%s word_hwnd=%s message=%s app_rect=%s word_rect=%s",
            int(app_hwnd or 0),
            int(word_hwnd or 0),
            str(getattr(result, "message", "") or ""),
            getattr(result, "app_rect", None),
            getattr(result, "word_rect", None),
        )
        self._set_status_text(f"形式审查：自动停靠失败（{getattr(result, 'message', '未知原因')}）。")

def _set_splitter_order(splitter, widgets: list[QWidget]) -> None:
    if splitter is None:
        return
    try:
        count = int(splitter.count())
    except Exception:
        count = 0
    for _ in range(max(0, count)):
        try:
            widget = splitter.widget(0)
        except Exception:
            widget = None
        if widget is None:
            break
        widget.setParent(None)
    for widget in list(widgets or []):
        if widget is None:
            continue
        splitter.addWidget(widget)

def _apply_plain_workspace_layout(self) -> None:
    splitter = getattr(self, "formal_review_workspace_splitter", None)
    left_panel = getattr(self, "formal_review_left_panel", None)
    center_panel = getattr(self, "formal_review_center_panel", None)
    right_panel = getattr(self, "formal_review_right_panel", None)
    detail_section = getattr(self, "formal_review_detail_section", None)
    marker_section = getattr(self, "formal_review_marker_section", None)
    if splitter is None:
        return
    splitter.setOrientation(Qt.Horizontal)
    self._set_splitter_order(splitter, [left_panel, center_panel, right_panel])
    right_splitter = getattr(self, "formal_review_right_splitter", None)
    if right_splitter is not None:
        self._set_splitter_order(right_splitter, [marker_section, detail_section])
        try:
            right_splitter.setSizes([220, 280])
        except Exception:
            pass
    self.formal_review_center_panel_attached = True
    restore_sizes = list(getattr(self, "_formal_review_plain_splitter_sizes", [260, 520, 300]) or [260, 520, 300])
    if len(restore_sizes) >= 3:
        splitter.setSizes(restore_sizes[:3])

def _apply_companion_workspace_layout(self) -> None:
    splitter = getattr(self, "formal_review_workspace_splitter", None)
    left_panel = getattr(self, "formal_review_left_panel", None)
    right_panel = getattr(self, "formal_review_right_panel", None)
    marker_section = getattr(self, "formal_review_marker_section", None)
    if splitter is None:
        return
    sizes = list(splitter.sizes() or [])
    if len(sizes) >= 3:
        self._formal_review_plain_splitter_sizes = list(sizes[:3])
    splitter.setOrientation(Qt.Vertical)
    right_splitter = getattr(self, "formal_review_right_splitter", None)
    if right_splitter is not None:
        self._set_splitter_order(right_splitter, [marker_section])
        try:
            right_splitter.setSizes([1000])
        except Exception:
            pass
    self._set_splitter_order(splitter, [right_panel, left_panel])
    self.formal_review_center_panel_attached = False
    splitter.setSizes([260, 620])

def _attach_plain_center_panel(self) -> None:
    self._apply_plain_workspace_layout()

def _detach_plain_center_panel(self) -> None:
    self._apply_companion_workspace_layout()

def _apply_input_mode_to_ui(self) -> None:
    is_plain = str(getattr(self, "_formal_review_input_mode", "word") or "word") == "plain_text"
    is_word = not is_plain
    busy = bool(getattr(self, "_formal_review_busy", False))
    has_document = getattr(self, "_formal_review_document", None) is not None
    has_session = getattr(self, "_formal_review_companion_session", None) is not None

    section_editable = bool(is_plain or self._is_word_mode_editable())
    ignore_enabled = bool(is_plain)

    choose_button = getattr(self, "formal_review_choose_button", None)
    if choose_button is not None:
        choose_button.setVisible(is_word)
        choose_button.setEnabled(is_word and (not busy))

    parse_button = getattr(self, "formal_review_parse_button", None)
    if parse_button is not None:
        parse_button.setVisible(is_plain)
        parse_button.setEnabled((not busy) and is_plain)

    start_button = getattr(self, "formal_review_start_button", None)
    if start_button is not None:
        start_button.setVisible(True)
        start_button.setEnabled((is_word and has_session and (not busy)) or (is_plain and has_document and (not busy)))

    results_tree = getattr(self, "formal_review_results_tree", None)
    if results_tree is not None:
        try:
            results_tree.setColumnHidden(3, not ignore_enabled)
        except Exception:
            pass

    issue_ignore_toggle = getattr(self, "formal_review_issue_ignore_toggle", None)
    if issue_ignore_toggle is not None:
        issue_ignore_toggle.setVisible(ignore_enabled)

    for table_name in (
        "formal_review_claims_rule_table",
        "formal_review_claims_forbidden_table",
        "formal_review_claims_sensitive_table",
        "formal_review_description_rule_table",
        "formal_review_description_forbidden_table",
        "formal_review_description_sensitive_table",
        "formal_review_abstract_rule_table",
        "formal_review_summary_table",
    ):
        table = getattr(self, table_name, None)
        if table is None:
            continue
        try:
            table.setColumnHidden(3, not ignore_enabled)
        except Exception:
            pass

    file_edit = getattr(self, "formal_review_file_edit", None)
    if file_edit is not None:
        file_edit.setVisible(is_word)
        if is_plain:
            file_edit.setPlaceholderText("纯文本模式：无需连接 Word。")
            file_edit.clear()
        else:
            file_edit.setPlaceholderText("伴侣模式：请选择文件后点击“开始审查”。")

    word_state = getattr(self, "formal_review_word_state_label", None)
    dirty_state = getattr(self, "formal_review_dirty_state_label", None)
    if word_state is not None:
        word_state.setVisible(is_word)
    if dirty_state is not None:
        dirty_state.setVisible(is_word)

    for name in ("formal_review_description_text", "formal_review_abstract_text", "formal_review_drawings_text", "formal_review_claims_input_text"):
        editor = getattr(self, name, None)
        if editor is not None:
            editor.setReadOnly(not section_editable if name != "formal_review_claims_input_text" else (not is_plain))

    claims_input_label = getattr(self, "formal_review_claims_input_label", None)
    claims_input_text = getattr(self, "formal_review_claims_input_text", None)
    if claims_input_label is not None:
        claims_input_label.setVisible(is_plain)
    if claims_input_text is not None:
        claims_input_text.setVisible(is_plain)

    if is_plain:
        self._attach_plain_center_panel()
    else:
        self._detach_plain_center_panel()

    self._apply_claim_editor_readonly_state()
    self._update_companion_status_labels()
    self._update_marker_apply_enabled()
    self._refresh_results_tree_layout()

def _ignore_enabled(self) -> bool:
    return str(getattr(self, "_formal_review_input_mode", "word") or "word") == "plain_text"

def _is_word_mode_editable(self) -> bool:
    return False

def _apply_claim_editor_readonly_state(self) -> None:
    editable = bool(
        str(getattr(self, "_formal_review_input_mode", "word") or "word") == "plain_text"
        or self._is_word_mode_editable()
    )
    for editor in list((getattr(self, "_formal_review_claim_content_views", {}) or {}).values()):
        if editor is not None:
            editor.setReadOnly(not editable)

def _update_marker_apply_enabled(self) -> None:
    button = getattr(self, "formal_review_apply_marker_button", None)
    if button is None:
        return
    is_word = str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word"
    busy = bool(getattr(self, "_formal_review_busy", False))
    has_session = getattr(self, "_formal_review_companion_session", None) is not None
    has_document = getattr(self, "_formal_review_document", None) is not None
    button.setVisible(is_word)
    button.setEnabled(is_word and has_session and has_document and (not busy))
    button.setToolTip("根据标号说明直接生成并应用修订" if is_word else "")


def _reset_formal_review_runtime_state(self, *, full_reset: bool = True) -> None:
    marker_edit = getattr(self, "formal_review_marker_edit", None)
    if marker_edit is not None:
        marker_edit.blockSignals(True)
        try:
            marker_edit.clear()
        finally:
            marker_edit.blockSignals(False)
    set_pref(_MARKER_NOTE_PREF_KEY, "")

    file_edit = getattr(self, "formal_review_file_edit", None)
    if file_edit is not None:
        try:
            file_edit.clear()
        except Exception:
            pass

    set_pref(_COMMENT_COPY_PATH_PREF_KEY, "")
    self._formal_review_current_file = ""
    self._formal_review_source_file = ""
    self._formal_review_comment_copy_path = ""
    self._formal_review_is_working_copy = False
    self._formal_review_document = None
    self._formal_review_projections = None
    self._formal_review_rule_errors = []
    self._formal_review_skipped_rule_labels = []
    self._formal_review_skipped_rule_reason = ""
    self._formal_review_selected_issue_id = ""
    self._formal_review_selected_claim_num = None
    self._formal_review_results_tree_width_mode_applied = ""
    self._formal_review_results_tree_width_save_pending = False

    if bool(full_reset) and str(getattr(self, "_formal_review_input_mode", "word") or "word") != "word":
        self._close_companion_session()

    store = getattr(self, "_formal_review_suppression_store", None)
    if store is not None and bool(full_reset):
        store.clear_all()

    self._build_section_segments([])
    self._clear_document_views()
    self._reset_issue_views(clear_ignore=True)
    self._set_needs_parse(False)


def on_formal_review_mode_changed(self, _checked: bool = False) -> None:
    previous_mode = str(getattr(self, "_formal_review_input_mode", "word") or "word")
    self._ensure_formal_review_state()
    mode = self._determine_input_mode_from_radios()
    if mode == previous_mode:
        return

    self._formal_review_input_mode = mode
    self._reset_formal_review_runtime_state(full_reset=True)
    self._apply_input_mode_to_ui()
    self._set_status_text(f"形式审查：已切换到{'纯文本模式' if mode == 'plain_text' else 'Word 伴侣模式'}。")

