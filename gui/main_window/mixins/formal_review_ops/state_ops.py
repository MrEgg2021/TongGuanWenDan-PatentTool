from __future__ import annotations

from core.user_messages import user_error_text

from .shared import (
    EditableSegment,
    ProjectionBundle,
    SuppressionStore,
    _COMMENT_AUTHOR_PREF_KEY,
    _COMMENT_COPY_PATH_PREF_KEY,
    _HIGHLIGHT_COLORS_PREF_KEY,
    _MARKER_NOTE_PREF_KEY,
    _normalize_highlight_colors,
    close_session,
    get_dirty_state,
    get_pref,
    load_rule_enabled,
    load_rule_params,
    load_wordlist_profile_store,
    logger,
    set_pref,
)

__all__ = [
    "_set_status_text",
    "_companion_file_key",
    "_close_companion_session",
    "_update_companion_status_labels",
    "_refresh_wordlist_profile_combo",
    "_ensure_formal_review_state",
    "_set_formal_review_busy",
]

def _set_status_text(self, text: str) -> None:
    try:
        if any(word in text for word in ("失败", "错误", "异常")):
            text = user_error_text(text)
        self._set_status_hint(str(text or ""))
    except Exception:
        pass

def _companion_file_key(self) -> str:
    session = getattr(self, "_formal_review_companion_session", None)
    if session is None:
        return ""
    path = str(getattr(session, "document_path", "") or "").strip()
    if path:
        return path
    return str(getattr(session, "document_name", "") or "").strip()

def _close_companion_session(self) -> None:
    session = getattr(self, "_formal_review_companion_session", None)
    if session is None:
        return
    try:
        close_session(session)
    except Exception:
        pass
    self._formal_review_companion_session = None
    self._formal_review_companion_docked_once = False
    self._formal_review_com_block_prompted = False
    self._formal_review_com_block_last_reason = ""

def _update_companion_status_labels(self) -> None:
    word_state = getattr(self, "formal_review_word_state_label", None)
    dirty_state = getattr(self, "formal_review_dirty_state_label", None)
    session = getattr(self, "_formal_review_companion_session", None)
    connected = session is not None
    if word_state is not None:
        if connected:
            name = str(getattr(session, "document_name", "") or "当前文档")
            word_state.setText(f"Word状态：已连接（{name}）")
        else:
            word_state.setText("Word状态：未连接")
    if dirty_state is not None:
        if not connected:
            dirty_state.setText("文档变更：未知")
            return
        try:
            dirty = bool(get_dirty_state(session))
        except Exception:
            dirty = False
        dirty_state.setText("文档变更：是" if dirty else "文档变更：否")

def _refresh_wordlist_profile_combo(self) -> None:
    combo = getattr(self, "formal_review_wordlist_profile_combo", None)
    if combo is None:
        return
    try:
        active, profiles = load_wordlist_profile_store()
    except Exception as exc:
        logger.exception("[formal_review][wordlist_profiles] load_failed: %s", exc)
        return
    names = list((profiles or {}).keys())
    if not names:
        names = ["默认"]
    combo.blockSignals(True)
    try:
        combo.clear()
        combo.addItems(names)
        idx = combo.findText(str(active or ""))
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)
    finally:
        combo.blockSignals(False)

def _ensure_formal_review_state(self) -> None:
    if not hasattr(self, "_formal_review_suppression_store"):
        self._formal_review_suppression_store = SuppressionStore()
    if not hasattr(self, "_formal_review_current_file"):
        self._formal_review_current_file = ""
    if not hasattr(self, "_formal_review_source_file"):
        self._formal_review_source_file = ""
    if not hasattr(self, "_formal_review_comment_copy_path"):
        self._formal_review_comment_copy_path = str(get_pref(_COMMENT_COPY_PATH_PREF_KEY, "") or "").strip()
    if not hasattr(self, "_formal_review_is_working_copy"):
        self._formal_review_is_working_copy = False
    if not hasattr(self, "_formal_review_document"):
        self._formal_review_document = None
    if not hasattr(self, "_formal_review_projections"):
        self._formal_review_projections: ProjectionBundle | None = None
    if not hasattr(self, "_formal_review_companion_session"):
        self._formal_review_companion_session = None
    if not hasattr(self, "_formal_review_companion_docked_once"):
        self._formal_review_companion_docked_once = False
    if not hasattr(self, "_formal_review_com_block_prompted"):
        self._formal_review_com_block_prompted = False
    if not hasattr(self, "_formal_review_com_block_last_reason"):
        self._formal_review_com_block_last_reason = ""
    if not hasattr(self, "_formal_review_overlay_progress_callback"):
        self._formal_review_overlay_progress_callback = None
    if not hasattr(self, "_formal_review_overlay_active"):
        self._formal_review_overlay_active = False
    if not hasattr(self, "_formal_review_last_sync_summary"):
        self._formal_review_last_sync_summary = None
    if not hasattr(self, "_formal_review_companion_submode"):
        self._formal_review_companion_submode = "review"
    if not hasattr(self, "_formal_review_edit_segments"):
        self._formal_review_edit_segments: list[EditableSegment] = []
    if not hasattr(self, "_formal_review_edit_segment_map"):
        self._formal_review_edit_segment_map: dict[str, EditableSegment] = {}
    if not hasattr(self, "_formal_review_segment_edits"):
        self._formal_review_segment_edits: dict[str, str] = {}
    if not hasattr(self, "_formal_review_writeback_report"):
        self._formal_review_writeback_report = {}
    if not hasattr(self, "_formal_review_issues"):
        self._formal_review_issues = []
    if not hasattr(self, "_formal_review_rule_errors"):
        self._formal_review_rule_errors = []
    if not hasattr(self, "_formal_review_skipped_rule_labels"):
        self._formal_review_skipped_rule_labels = []
    if not hasattr(self, "_formal_review_skipped_rule_reason"):
        self._formal_review_skipped_rule_reason = ""
    if not hasattr(self, "_formal_review_issue_map"):
        self._formal_review_issue_map = {}
    if not hasattr(self, "_formal_review_issue_fingerprints"):
        self._formal_review_issue_fingerprints: dict[str, str] = {}
    if not hasattr(self, "_formal_review_ignore_resync_seq"):
        self._formal_review_ignore_resync_seq = 0
    if not hasattr(self, "_formal_review_selected_issue_id"):
        self._formal_review_selected_issue_id = ""
    if not hasattr(self, "_formal_review_selected_claim_num"):
        self._formal_review_selected_claim_num = None
    if not hasattr(self, "_formal_review_section_segments"):
        self._formal_review_section_segments = {"claims": {}, "description": [], "abstract": [], "drawings": []}
    if not hasattr(self, "_formal_review_plain_splitter_sizes"):
        self._formal_review_plain_splitter_sizes = [250, 500, 250]
    if not hasattr(self, "_formal_review_claim_content_views"):
        self._formal_review_claim_content_views = {}
    if not hasattr(self, "_formal_review_claim_marker_labels"):
        self._formal_review_claim_marker_labels = {}
    if not hasattr(self, "_formal_review_claim_marker_rows"):
        self._formal_review_claim_marker_rows = {}
    if not hasattr(self, "_formal_review_busy"):
        self._formal_review_busy = False
    if not hasattr(self, "_formal_review_worker_thread"):
        self._formal_review_worker_thread = None
    if not hasattr(self, "_formal_review_worker"):
        self._formal_review_worker = None
    if not hasattr(self, "_formal_review_worker_bridge"):
        self._formal_review_worker_bridge = None
    if not hasattr(self, "_formal_review_syncing_ui"):
        self._formal_review_syncing_ui = False
    if not hasattr(self, "_formal_review_input_mode"):
        self._formal_review_input_mode = "word"
    if not hasattr(self, "_formal_review_needs_parse"):
        self._formal_review_needs_parse = False
    if not hasattr(self, "_formal_review_comment_author"):
        self._formal_review_comment_author = str(get_pref(_COMMENT_AUTHOR_PREF_KEY, "") or "").strip()
    if not hasattr(self, "_formal_review_highlight_colors"):
        self._formal_review_highlight_colors = _normalize_highlight_colors(get_pref(_HIGHLIGHT_COLORS_PREF_KEY, {}))
    if not hasattr(self, "_formal_review_rule_enabled"):
        self._formal_review_rule_enabled = load_rule_enabled()
    if not hasattr(self, "_formal_review_rule_params"):
        self._formal_review_rule_params = load_rule_params()
    if not hasattr(self, "_formal_review_signals_bound"):
        self._formal_review_signals_bound = False
    if not hasattr(self, "_formal_review_claim_layout_refresh_pending"):
        self._formal_review_claim_layout_refresh_pending = False
    if not hasattr(self, "_formal_review_results_layout_refresh_pending"):
        self._formal_review_results_layout_refresh_pending = False
    if not hasattr(self, "_formal_review_results_tree_width_mode_applied"):
        self._formal_review_results_tree_width_mode_applied = ""
    if not hasattr(self, "_formal_review_results_tree_restoring_widths"):
        self._formal_review_results_tree_restoring_widths = False
    if not hasattr(self, "_formal_review_results_tree_width_save_pending"):
        self._formal_review_results_tree_width_save_pending = False
    if not hasattr(self, "_formal_review_results_tree_column_widths_by_mode"):
        self._formal_review_results_tree_column_widths_by_mode = self._load_results_tree_column_widths_pref()
    if not hasattr(self, "_formal_review_marker_note_initialized"):
        self._formal_review_marker_note_initialized = False

    marker_edit = getattr(self, "formal_review_marker_edit", None)
    if (not bool(getattr(self, "_formal_review_marker_note_initialized", False))) and marker_edit is not None:
        marker_edit.blockSignals(True)
        try:
            marker_edit.clear()
        finally:
            marker_edit.blockSignals(False)
        set_pref(_MARKER_NOTE_PREF_KEY, "")
        self._formal_review_marker_note_initialized = True

    if not self._formal_review_signals_bound:
        try:
            getattr(self, "formal_review_issue_ignore_toggle").stateChanged.connect(self.on_formal_review_issue_toggle_changed)
        except Exception:
            pass
        try:
            getattr(self, "formal_review_results_tree").itemChanged.connect(self.on_formal_review_summary_tree_item_changed)
        except Exception:
            pass
        try:
            results_tree = getattr(self, "formal_review_results_tree", None)
            if results_tree is not None:
                results_tree.itemExpanded.connect(lambda *_: self._schedule_results_tree_layout_refresh())
                results_tree.itemCollapsed.connect(lambda *_: self._schedule_results_tree_layout_refresh())
                header = results_tree.header()
                if header is not None:
                    header.sectionResized.connect(self._on_results_tree_section_resized)
        except Exception:
            pass
        try:
            marker_edit = getattr(self, "formal_review_marker_edit", None)
            if marker_edit is not None:
                marker_edit.textChanged.connect(self.on_formal_review_marker_note_changed)
        except Exception:
            pass
        try:
            description_text = getattr(self, "formal_review_description_text", None)
            if description_text is not None:
                description_text.textChanged.connect(lambda: self._on_formal_review_section_text_edited("description"))
        except Exception:
            pass
        try:
            abstract_text = getattr(self, "formal_review_abstract_text", None)
            if abstract_text is not None:
                abstract_text.textChanged.connect(self._update_abstract_count_label)
                abstract_text.textChanged.connect(lambda: self._on_formal_review_section_text_edited("abstract"))
        except Exception:
            pass
        try:
            drawings_text = getattr(self, "formal_review_drawings_text", None)
            if drawings_text is not None:
                drawings_text.textChanged.connect(lambda: self._on_formal_review_section_text_edited("drawings"))
        except Exception:
            pass
        try:
            claims_tree = getattr(self, "formal_review_claims_tree", None)
            if claims_tree is not None:
                claims_tree.itemExpanded.connect(self._schedule_claims_dynamic_layout)
                claims_tree.itemCollapsed.connect(self._schedule_claims_dynamic_layout)
        except Exception:
            pass
        try:
            workspace_splitter = getattr(self, "formal_review_workspace_splitter", None)
            if workspace_splitter is not None:
                workspace_splitter.splitterMoved.connect(self._on_formal_review_workspace_splitter_moved)
        except Exception:
            pass
        self._formal_review_signals_bound = True

    self._refresh_wordlist_profile_combo()
    self._apply_input_mode_to_ui()
    self._update_companion_status_labels()
    self._update_abstract_count_label()
    try:
        if hasattr(self, "_schedule_results_tree_layout_refresh"):
            self._schedule_results_tree_layout_refresh()
        if hasattr(self, "_schedule_claims_dynamic_layout"):
            self._schedule_claims_dynamic_layout()
    except Exception:
        pass

def _set_formal_review_busy(self, busy: bool, action: str = "") -> None:
    controls = (
        getattr(self, "formal_review_choose_button", None),
        getattr(self, "formal_review_connect_word_button", None),
        getattr(self, "formal_review_parse_button", None),
        getattr(self, "formal_review_start_button", None),
        getattr(self, "formal_review_export_report_button", None),
        getattr(self, "formal_review_apply_marker_button", None),
        getattr(self, "formal_review_settings_button", None),
        getattr(self, "formal_review_wordlist_profile_combo", None),
        getattr(self, "formal_review_mode_word_radio", None),
        getattr(self, "formal_review_mode_plain_radio", None),
        getattr(self, "formal_review_companion_review_radio", None),
        getattr(self, "formal_review_companion_apply_radio", None),
    )
    for control in controls:
        if control is not None:
            control.setEnabled(not busy)

    if busy and action:
        self._set_status_text(f"形式审查：{action}")
    elif not busy:
        self._set_status_text("形式审查：就绪")

    self._update_companion_status_labels()
    self._update_marker_apply_enabled()

