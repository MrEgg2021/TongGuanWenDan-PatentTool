from __future__ import annotations

from core.user_messages import user_error_text

from gui.windowing import ui_pump as ui_pump_api

from .shared import (
    EditableSegment,
    FormalReviewDocument,
    Path,
    ProjectionBundle,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
    _COMMENT_AUTHOR_PREF_KEY,
    _COMMENT_COPY_PATH_PREF_KEY,
    _MARKER_NOTE_PREF_KEY,
    _SUPPORTED_WORD_SUFFIXES,
    _TOOL_COMMENT_PREFIX,
    _normalized_word_suffix,
    check_com_find_ready,
    connect_active_word,
    datetime,
    detect_unsaved_source,
    enabled_rule_id_set,
    get_document_snapshot,
    get_word_hwnd,
    inspect_doc_clean_state,
    load_wordlist_profile_store,
    load_wordlists,
    logger,
    normalize_word_window,
    open_or_attach_document,
    parse_marker_note_payload,
    parse_plain_text_sections,
    run_formal_review,
    set_pref,
    show_blocking_alert_modal,
    shutil,
    sync_comments_inplace,
)

__all__ = [
    "_determine_input_mode_from_radios",
    "_fit_formal_review_overlay_card_width",
    "_show_formal_review_overlay",
    "_update_formal_review_overlay",
    "_hide_formal_review_overlay",
    "_emit_formal_review_overlay_progress",
    "on_formal_review_choose_file",
    "_reset_companion_selection_after_gate_block",
    "_create_timestamp_working_copy",
    "_set_auto_comment_sync_digest",
    "_publish_auto_comment_sync_summary",
    "_auto_sync_comments_to_copy",
    "_run_companion_review_cycle",
    "_apply_document_snapshot",
    "_prepare_marker_basis_rule_inputs",
    "_run_review_on_current_document",
    "_connect_or_attach_companion",
    "_clean_gate_bool_label",
    "_clean_gate_count_label",
    "_ensure_com_find_ready_or_prompt",
    "_ensure_companion_doc_clean_or_prompt",
    "on_formal_review_connect_word",
    "on_formal_review_parse",
    "on_formal_review_marker_note_changed",
    "on_formal_review_start_check",
]

_MARKER_BASIS_RULE_IDS = ("claim.ref.marker_basis.missing", "claim.ref.term_basis.missing")
_MARKER_BASIS_RULE_LABELS = {
    "claim.ref.marker_basis.missing": "附图标记引用基础缺失",
    "claim.ref.term_basis.missing": "所述后术语未对应标号说明",
}


def _hide_processing_overlay_cancel_button(self) -> None:
    overlay = getattr(self, "_processing_overlay", None)
    if overlay is None:
        return
    try:
        cancel_button = overlay.findChild(QPushButton, "processingCancelButton")
    except Exception:
        cancel_button = None
    if cancel_button is None:
        return
    try:
        cancel_button.setVisible(False)
        cancel_button.setEnabled(False)
    except Exception:
        pass


def _resolve_formal_review_warning_text(status_text: str) -> str:
    text = str(status_text or "").strip()
    lowered = text.lower()

    if any(keyword in text for keyword in ("写入", "同步", "修订")) or any(
        keyword in lowered for keyword in ("write", "sync", "apply")
    ):
        return "⚠ 正在写入修订：请勿操作键鼠、切换窗口或关闭 Word，避免写入中断。"

    if any(keyword in text for keyword in ("审查", "审核", "规则")) or any(
        keyword in lowered for keyword in ("review", "check")
    ):
        return "⚠ 形式审查进行中：请勿手动编辑 Word 正文或切换窗口，避免定位偏差。"

    if any(keyword in text for keyword in ("准备", "连接", "停靠", "打开", "文档", "快照", "校验")) or any(
        keyword in lowered for keyword in ("prepare", "connect", "attach", "dock", "snapshot")
    ):
        return "⚠ 形式审查准备中：请勿关闭 Word 或切换到其他文档。"

    return "⚠ 形式审查处理中，请稍候。"


def _apply_formal_review_overlay_warning(self, status_text: str) -> None:
    overlay = getattr(self, "_processing_overlay", None)
    if overlay is None:
        return
    try:
        warn_label = overlay.findChild(QLabel, "processingWarnLabel")
    except Exception:
        warn_label = None
    if warn_label is None:
        return
    try:
        warn_label.setText(_resolve_formal_review_warning_text(status_text))
    except Exception:
        pass


def _fit_formal_review_overlay_card_width(self) -> None:
    if not bool(getattr(self, "_formal_review_overlay_active", False)):
        return
    overlay = getattr(self, "_processing_overlay", None)
    if overlay is None:
        return
    try:
        card = overlay.findChild(QWidget, "ModalCard")
    except Exception:
        card = None
    if card is None:
        return

    def _widget_width(widget) -> int:
        if widget is None:
            return 0
        try:
            return max(0, int(widget.width() or 0))
        except Exception:
            return 0

    left_panel = getattr(self, "formal_review_left_panel", None)
    page = getattr(self, "_formal_review_page", None) or getattr(self, "formal_review_page", None)
    owner = None
    try:
        owner = overlay.parentWidget()
    except Exception:
        owner = None

    base_width = _widget_width(left_panel)
    if base_width <= 0:
        base_width = _widget_width(page)
    if base_width <= 0:
        base_width = _widget_width(owner)
    if base_width <= 0:
        return

    target = max(220, min(900, int(base_width - 24)))
    owner_width = _widget_width(owner)
    if owner_width <= 0:
        owner_width = _widget_width(page)
    if owner_width > 0:
        viewport_cap = max(180, int(owner_width - 24))
        target = min(target, viewport_cap)
        target = max(180, target)
    try:
        card.setMinimumWidth(target)
        card.setMaximumWidth(target)
        card.updateGeometry()
    except Exception:
        pass


def _show_formal_review_overlay(self, status_text: str, file_text: str = "") -> bool:
    if not hasattr(self, "_show_processing_overlay"):
        return False
    try:
        self._show_processing_overlay(str(status_text or ""), str(file_text or ""))
        self._formal_review_overlay_active = True
        self._hide_processing_overlay_cancel_button()
        self._apply_formal_review_overlay_warning(str(status_text or ""))
        self._fit_formal_review_overlay_card_width()
        ui_pump_api.pump(allow_user_input=False)
        return True
    except Exception:
        return False


def _update_formal_review_overlay(self, percent: int, status_text: str = "", detail_text: str = "") -> None:
    if not hasattr(self, "_update_processing_overlay"):
        return
    try:
        self._update_processing_overlay(int(percent), str(status_text or ""), str(detail_text or ""))
        self._apply_formal_review_overlay_warning(str(status_text or ""))
        self._fit_formal_review_overlay_card_width()
        ui_pump_api.pump(allow_user_input=False)
    except Exception:
        pass


def _hide_formal_review_overlay(self, overlay_visible: bool) -> None:
    self._formal_review_overlay_active = False
    if not overlay_visible or (not hasattr(self, "_hide_processing_overlay")):
        return
    try:
        self._hide_processing_overlay()
    except Exception:
        pass


def _emit_formal_review_overlay_progress(self, percent: int, status_text: str) -> None:
    callback = getattr(self, "_formal_review_overlay_progress_callback", None)
    if not callable(callback):
        return
    try:
        callback(int(percent), str(status_text or ""))
    except Exception:
        pass


def _determine_input_mode_from_radios(self) -> str:
    word_radio = getattr(self, "formal_review_mode_word_radio", None)
    plain_radio = getattr(self, "formal_review_mode_plain_radio", None)
    word_checked = bool(word_radio is not None and word_radio.isChecked())
    plain_checked = bool(plain_radio is not None and plain_radio.isChecked())

    if word_checked and not plain_checked:
        return "word"
    if plain_checked and not word_checked:
        return "plain_text"

    sender = self.sender()
    if sender is word_radio and word_checked:
        return "word"
    if sender is plain_radio and plain_checked:
        return "plain_text"

    current = str(getattr(self, "_formal_review_input_mode", "word") or "word")
    if current not in {"word", "plain_text"}:
        current = "word"

    if word_radio is not None and plain_radio is not None:
        word_radio.blockSignals(True)
        plain_radio.blockSignals(True)
        word_radio.setChecked(current == "word")
        plain_radio.setChecked(current == "plain_text")
        word_radio.blockSignals(False)
        plain_radio.blockSignals(False)
    return current

def on_formal_review_choose_file(self):
    self._ensure_formal_review_state()
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") != "word":
        word_radio = getattr(self, "formal_review_mode_word_radio", None)
        plain_radio = getattr(self, "formal_review_mode_plain_radio", None)
        if word_radio is not None:
            word_radio.blockSignals(True)
            word_radio.setChecked(True)
            word_radio.blockSignals(False)
        if plain_radio is not None:
            plain_radio.blockSignals(True)
            plain_radio.setChecked(False)
            plain_radio.blockSignals(False)
        self._formal_review_input_mode = "word"
        self._apply_input_mode_to_ui()

    file_path, _ = QFileDialog.getOpenFileName(self, "选择 Word 文件", "", "Word 文件 (*.docx *.doc)")
    if not file_path:
        return

    next_source = str(Path(file_path).resolve())
    suffix = _normalized_word_suffix(next_source)
    if suffix not in _SUPPORTED_WORD_SUFFIXES:
        QMessageBox.warning(self, "形式审查", user_error_text(f"不支持的 Word 扩展名：{suffix or '（无后缀）'}"))
        return

    if detect_unsaved_source(next_source):
        QMessageBox.warning(self, "形式审查", "检测到源文件在 Word 中有未保存修改，请先保存后再导入。")
        return

    try:
        working_copy = self._create_timestamp_working_copy(next_source)
    except Exception as exc:
        show_blocking_alert_modal(self, "形式审查", f"创建伴侣副本失败：\n{exc}")
        return

    self._formal_review_source_file = next_source
    self._formal_review_current_file = working_copy
    self._formal_review_comment_copy_path = working_copy
    self._formal_review_is_working_copy = True
    set_pref(_COMMENT_COPY_PATH_PREF_KEY, working_copy)
    self._formal_review_com_block_prompted = False
    self._formal_review_com_block_last_reason = ""

    file_edit = getattr(self, "formal_review_file_edit", None)
    if file_edit is not None:
        file_edit.setText(working_copy)

    session = getattr(self, "_formal_review_companion_session", None)
    if session is not None:
        session_path = str(getattr(session, "document_path", "") or "")
        if session_path and str(Path(session_path).resolve()) != working_copy:
            self._close_companion_session()

    store = getattr(self, "_formal_review_suppression_store", None)
    if store is not None:
        store.switch_file(working_copy)

    self._formal_review_document = None
    self._formal_review_projections = None
    self._build_section_segments([])
    self._reset_issue_views(clear_ignore=True)
    self._set_needs_parse(False)
    self._apply_input_mode_to_ui()
    overlay_title = "正在打开形式审查工作副本，请不要编辑 Word 文档，请稍等。"
    overlay_file = Path(working_copy).name
    overlay_visible = self._show_formal_review_overlay(overlay_title, overlay_file)
    self._update_formal_review_overlay(8, overlay_title, overlay_file)
    try:
        self._update_formal_review_overlay(28, "正在连接工作副本文档，请稍等。", overlay_file)
        if not self._connect_or_attach_companion():
            return
        self._update_formal_review_overlay(60, "正在整理审查窗口布局，请稍等。", overlay_file)
        self._formal_review_companion_docked_once = False
        self._dock_companion_windows_once()
        self._update_formal_review_overlay(82, "正在检查旧批注、修订和保存状态，请稍等。", overlay_file)
        if not self._ensure_companion_doc_clean_or_prompt(trigger="choose_file", allow_retry=False):
            self._reset_companion_selection_after_gate_block()
            return
        self._update_formal_review_overlay(100, "形式审查工作副本已准备完成。", overlay_file)
    finally:
        self._hide_formal_review_overlay(overlay_visible)
    self._set_status_text("形式审查：工作副本已就绪，请点击“开始审查”。")
    self._apply_input_mode_to_ui()

def _reset_companion_selection_after_gate_block(self) -> None:
    self._close_companion_session()
    self._formal_review_current_file = ""
    self._formal_review_source_file = ""
    self._formal_review_comment_copy_path = ""
    self._formal_review_is_working_copy = False
    self._formal_review_document = None
    self._formal_review_projections = None
    self._formal_review_com_block_prompted = False
    self._formal_review_com_block_last_reason = ""
    self._build_section_segments([])
    self._reset_issue_views(clear_ignore=True)
    self._set_needs_parse(False)
    set_pref(_COMMENT_COPY_PATH_PREF_KEY, "")
    file_edit = getattr(self, "formal_review_file_edit", None)
    if file_edit is not None:
        file_edit.clear()
    store = getattr(self, "_formal_review_suppression_store", None)
    if store is not None:
        store.switch_file("")
    self._update_companion_status_labels()
    self._apply_input_mode_to_ui()

def _create_timestamp_working_copy(self, source_path: str) -> str:
    source = Path(str(source_path or "")).resolve()
    suffix = _normalized_word_suffix(str(source))
    if suffix not in _SUPPORTED_WORD_SUFFIXES:
        raise ValueError(f"unsupported_word_suffix:{suffix or 'none'}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parent = source.parent
    stem = source.stem
    ext = source.suffix
    candidate = parent / f"{stem}_形式审查副本_{stamp}{ext}"
    idx = 1
    while candidate.exists():
        candidate = parent / f"{stem}_形式审查副本_{stamp}_{idx}{ext}"
        idx += 1
    parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(candidate))
    return str(candidate.resolve())

def _set_auto_comment_sync_digest(self, text: str) -> None:
    label = getattr(self, "formal_review_sync_digest_label", None)
    if label is None:
        return
    digest_text = str(text or "").strip()
    label.setText(digest_text or "\u6700\u8fd1\u540c\u6b65\uff1a\u6682\u65e0")

def _publish_auto_comment_sync_summary(self, result, output_path: str, trigger: str) -> None:
    written = int(getattr(result, "written", 0) or 0)
    skipped = int(getattr(result, "skipped", 0) or 0)
    cleared = int(getattr(result, "cleared_tool_comments", 0) or 0)
    cleared_highlights = int(getattr(result, "cleared_tool_highlights", 0) or 0)
    failed = int(getattr(result, "failed_issue_count", 0) or 0)
    failed_reason_codes = [str(row) for row in list(getattr(result, "failed_reason_codes", []) or []) if str(row)]
    reason_sample = ", ".join(failed_reason_codes[:3])
    file_name = Path(str(output_path or "")).name or str(output_path or "")
    trigger_label = {
        "choose_file": "\u9009\u62e9\u6587\u4ef6",
        "refresh": "\u5237\u65b0",
        "connect_word": "\u8fde\u63a5",
        "ignore": "\u5ffd\u7565",
        "start_check": "\u5f00\u59cb\u5ba1\u67e5",
    }.get(str(trigger or "").strip(), "\u672c\u6b21")
    status_text = (
        f"\u5f62\u5f0f\u5ba1\u67e5\uff1a\u6279\u6ce8\u5df2\u540c\u6b65\uff08\u5199\u5165 {written}\uff0c"
        f"\u8df3\u8fc7 {skipped}\uff0c\u6e05\u65e7 {cleared}\uff0c\u6e05\u9ad8\u4eae {cleared_highlights}\uff09\u3002"
    )
    if failed > 0:
        if written > 0:
            status_text = (
                f"\u5f62\u5f0f\u5ba1\u67e5\uff1a\u6279\u6ce8\u90e8\u5206\u5199\u5165\uff08\u5199\u5165 {written}\uff0c"
                f"\u5b9a\u4f4d\u5931\u8d25 {failed}\uff09\uff0c\u5931\u8d25\u9879\u5df2\u8df3\u8fc7\u3002"
            )
        else:
            status_text = (
                f"\u5f62\u5f0f\u5ba1\u67e5\uff1a\u672c\u6b21\u6279\u6ce8\u540c\u6b65\u5df2\u4e2d\u6b62\uff08\u5b9a\u4f4d\u5931\u8d25 {failed}\uff09\uff0c"
                f"\u4e3a\u907f\u514d\u9519\u4f4d\u672c\u8f6e\u672a\u5199\u5165\u3002"
            )
        if reason_sample:
            status_text = f"{status_text}\u539f\u56e0\u6837\u672c\uff1a{reason_sample}\u3002"
    self._formal_review_last_sync_summary = {
        "trigger": str(trigger or ""),
        "written": int(written),
        "skipped": int(skipped),
        "failed": int(failed),
        "cleared": int(cleared),
        "cleared_highlights": int(cleared_highlights),
        "file_name": str(file_name or ""),
    }
    self._set_status_text(status_text)
    self._set_auto_comment_sync_digest(
        f"\u6700\u8fd1\u540c\u6b65\uff1a{trigger_label}\uff5c\u5199\u5165 {written}\uff5c\u8df3\u8fc7 {skipped}\uff5c"
        f"\u5931\u8d25 {failed}\uff5c\u6e05\u65e7 {cleared}\uff5c\u6e05\u9ad8\u4eae {cleared_highlights}\uff5c"
        f"\u539f\u56e0 {reason_sample or '-'}\uff5c\u526f\u672c {file_name}"
    )


def _show_formal_review_cycle_summary_dialog(self, *, trigger: str, auto_sync_comments: bool) -> None:
    if str(trigger or "") != "start_check":
        return
    issues = list(getattr(self, "_formal_review_issues", []) or [])
    total = len(issues)
    ignored = sum(1 for row in issues if bool(getattr(row, "ignored", False)))
    effective = max(0, total - ignored)
    severity_counts = {"high": 0, "medium": 0, "low": 0, "warning": 0, "error": 0}
    for row in issues:
        severity = str(getattr(row, "severity", "") or "").strip().lower()
        if severity in {"fatal", "error"}:
            severity_counts["error"] += 1
        elif severity == "high":
            severity_counts["high"] += 1
        elif severity == "medium":
            severity_counts["medium"] += 1
        elif severity == "warning":
            severity_counts["warning"] += 1
        else:
            severity_counts["low"] += 1

    lines = [
        "本轮审查已完成。",
        f"问题总数：{total}",
        f"有效问题：{effective}",
        f"已忽略：{ignored}",
        (
            "严重度分布："
            f"高 {severity_counts['high']} / "
            f"中 {severity_counts['medium']} / "
            f"低 {severity_counts['low']} / "
            f"警告 {severity_counts['warning']} / "
            f"错误 {severity_counts['error']}"
        ),
    ]
    sync_summary = getattr(self, "_formal_review_last_sync_summary", None)
    if bool(auto_sync_comments) and isinstance(sync_summary, dict):
        if str(sync_summary.get("trigger", "")) == str(trigger or ""):
            lines.append(
                "同步结果："
                f"写入 {int(sync_summary.get('written', 0) or 0)} / "
                f"跳过 {int(sync_summary.get('skipped', 0) or 0)} / "
                f"失败 {int(sync_summary.get('failed', 0) or 0)}"
            )
    skipped_rule_labels = [
        str(row)
        for row in list(getattr(self, "_formal_review_skipped_rule_labels", []) or [])
        if str(row).strip()
    ]
    if skipped_rule_labels:
        reason = str(getattr(self, "_formal_review_skipped_rule_reason", "") or "标号说明为空/无有效映射")
        lines.append(f"本轮已跳过：{'、'.join(skipped_rule_labels)}（原因：{reason}）。")
    QMessageBox.information(self, "审查结果摘要", "\n".join(lines))

def _auto_sync_comments_to_copy(self, *, trigger: str, notify_failure: bool = True) -> bool:
    session = getattr(self, "_formal_review_companion_session", None)
    if session is None:
        return False
    if not self._ensure_com_find_ready_or_prompt(context=f"comment_sync:{str(trigger or '')}"):
        return False

    issues = list(getattr(self, "_formal_review_issues", []) or [])
    if self._ignore_enabled():
        # Only sync non-ignored issues to Word.
        issues = [row for row in issues if not bool(getattr(row, "ignored", False))]

    author = str(getattr(self, "_formal_review_comment_author", "") or "").strip()
    set_pref(_COMMENT_AUTHOR_PREF_KEY, author)
    try:
        result = sync_comments_inplace(
            session.doc,
            list(issues or []),
            author_name=author,
            tool_prefix=_TOOL_COMMENT_PREFIX,
            projections=getattr(self, "_formal_review_projections", None),
            color_map=dict(getattr(self, "_formal_review_highlight_colors", {}) or {}),
            apply_highlights=False,
            clear_tool_highlights=True,
            allow_loose_fallback=True,
            allow_legacy_fallback=False,
            require_com_ready=True,
            allow_partial_on_preflight_failure=True,
            preserve_failed_existing_comments=True,
        )
    except Exception as exc:
        logger.exception("[formal_review][comment_sync] gui_call_failed: %s", exc)
        if bool(notify_failure):
            show_blocking_alert_modal(self, "形式审查", f"批注同步失败：\n{exc}")
        else:
            self._set_status_text(f"\u5f62\u5f0f\u5ba1\u67e5\uff1a\u6279\u6ce8\u540c\u6b65\u5931\u8d25\uff08{exc}\uff09")
        return False

    written = int(getattr(result, "written", 0) or 0)
    failed = int(getattr(result, "failed_issue_count", 0) or 0)
    if failed > 0:
        failed_ids = list(getattr(result, "failed_issue_ids", []) or [])
        reason_codes = list(getattr(result, "failed_reason_codes", []) or [])
        strict_failed = int(getattr(result, "strict_failed", 0) or 0)
        loose_rescued = int(getattr(result, "loose_rescued", 0) or 0)
        sample = ", ".join([str(x) for x in failed_ids[:6]])
        reason_sample = ", ".join(reason_codes[:4])
        logger.info(
            "[formal_review][comment_sync] stopped: failed=%s strict_failed=%s loose_rescued=%s sample_ids=%s reason_sample=%s",
            int(failed),
            int(strict_failed),
            int(loose_rescued),
            str(sample),
            str(reason_sample),
        )
        if bool(notify_failure):
            if written > 0:
                msg = (
                    f"批注同步已部分完成：已写入 {written} 条，仍有 {failed} 条问题无法安全定位，"
                    "已跳过失败项，请逐项核对未添加批注的问题。"
                )
            else:
                msg = (
                    f"批注同步已中止：仍有 {failed} 条问题无法安全定位，本轮未写入。请重新连接 Word 后重试。"
                )
            QMessageBox.warning(
                self,
                "形式审查",
                user_error_text(msg),
            )

    try:
        current_file = str(getattr(self, "_formal_review_current_file", "") or getattr(session, "document_path", "") or "")
        resolved_output = str(Path(str(current_file)).resolve())
    except Exception:
        resolved_output = str(getattr(self, "_formal_review_current_file", "") or "")

    self._publish_auto_comment_sync_summary(result, resolved_output, trigger)

    # After a successful commit, refresh projections to avoid click-locate drift.
    cleared = int(getattr(result, "cleared_tool_comments", 0) or 0)
    cleared_highlights = int(getattr(result, "cleared_tool_highlights", 0) or 0)
    if failed <= 0 and (written > 0 or cleared > 0 or cleared_highlights > 0):
        try:
            document, anchors, editable_segments, projections = get_document_snapshot(session)
        except Exception as exc:
            self._set_status_text(f"\u5f62\u5f0f\u5ba1\u67e5\uff1a\u91cd\u65b0\u6355\u83b7Word\u5feb\u7167\u5931\u8d25\uff08{exc}\uff09")
        else:
            self._apply_document_snapshot(
                document=document,
                anchors=list(anchors or []),
                editable_segments=list(editable_segments or []),
                projections=projections,
            )
    return True

def _run_companion_review_cycle(self, *, trigger: str, auto_sync_comments: bool, redock: bool) -> bool:
    if bool(getattr(self, "_formal_review_busy", False)):
        QMessageBox.information(self, "形式审查", "当前任务正在执行，请稍后重试。")
        return False

    emit_overlay_progress = getattr(self, "_emit_formal_review_overlay_progress", None)
    if not callable(emit_overlay_progress):
        def emit_overlay_progress(*_args, **_kwargs):
            return None

    emit_overlay_progress(20, "正在连接 Word 文档，请稍等。")
    if not self._connect_or_attach_companion():
        return False

    if redock:
        self._formal_review_companion_docked_once = False
    emit_overlay_progress(35, "正在停靠窗口布局，请稍等。")
    self._dock_companion_windows_once()

    session = getattr(self, "_formal_review_companion_session", None)
    emit_overlay_progress(48, "正在检查 Word 文档是否可修改，请稍等。")
    if not self._ensure_com_find_ready_or_prompt(context=f"review_cycle:{str(trigger or '')}"):
        return False
    emit_overlay_progress(60, "正在执行文档清洁检查，请稍等。")
    if not self._ensure_companion_doc_clean_or_prompt(trigger=str(trigger or "")):
        return False
    emit_overlay_progress(72, "正在读取文档快照，请稍等。")
    try:
        document, anchors, editable_segments, projections = get_document_snapshot(session)
    except Exception as exc:
        show_blocking_alert_modal(self, "形式审查", f"读取 Word 文档失败：\n{exc}")
        return False

    self._reset_issue_views(clear_ignore=False)
    self._apply_document_snapshot(
        document=document,
        anchors=list(anchors or []),
        editable_segments=list(editable_segments or []),
        projections=projections,
    )
    emit_overlay_progress(84, "正在执行规则审查，请稍等。")
    reviewed = self._run_review_on_current_document()
    if not reviewed:
        return False
    self._apply_input_mode_to_ui()

    synced = False
    if auto_sync_comments:
        emit_overlay_progress(92, "正在写入并同步标记，请稍等。")
        synced = self._auto_sync_comments_to_copy(trigger=trigger)
    if not auto_sync_comments and not synced:
        self._set_status_text("形式审查：伴侣模式审查完成。")
    emit_overlay_progress(100, "审核完成。")
    self._show_formal_review_cycle_summary_dialog(
        trigger=str(trigger or ""),
        auto_sync_comments=bool(auto_sync_comments),
    )
    return True

def _apply_document_snapshot(
    self,
    *,
    document: FormalReviewDocument,
    anchors: list,
    editable_segments: list[EditableSegment],
    projections: ProjectionBundle | None = None,
) -> None:
    mode = str(getattr(self, "_formal_review_input_mode", "word") or "word")
    self._formal_review_document = document
    self._formal_review_projections = projections
    self._build_section_segments(list(anchors or []))
    if mode == "plain_text":
        self._set_edit_segments(list(editable_segments or []))
        self._populate_document_views()
    else:
        rows = list(editable_segments or [])
        self._formal_review_edit_segments = rows
        self._formal_review_edit_segment_map = {str(item.segment_id): item for item in rows}
        self._formal_review_segment_edits = {str(item.segment_id): str(item.original_display_text or "") for item in rows}
    self._set_needs_parse(False)

def _prepare_marker_basis_rule_inputs(self, enabled_rule_ids: set[str], marker_text: str) -> tuple[set[str], dict[str, str], list[str], str]:
    rule_ids = set(enabled_rule_ids or set())
    enabled_marker_basis_rules = [rule_id for rule_id in _MARKER_BASIS_RULE_IDS if rule_id in rule_ids]
    if not enabled_marker_basis_rules:
        return rule_ids, {}, [], ""

    def _skip(reason: str) -> tuple[set[str], dict[str, str], list[str], str]:
        filtered_rule_ids = set(rule_ids)
        for rule_id in enabled_marker_basis_rules:
            filtered_rule_ids.discard(rule_id)
        labels = [_MARKER_BASIS_RULE_LABELS.get(rule_id, rule_id) for rule_id in enabled_marker_basis_rules]
        logger.info(
            "[formal_review][marker_basis_skip] reason=%s skipped_rules=%s",
            str(reason or ""),
            enabled_marker_basis_rules,
        )
        return filtered_rule_ids, {}, labels, str(reason or "")

    marker_note = str(marker_text or "").strip()
    if not marker_note:
        return _skip("标号说明为空")

    try:
        payload = parse_marker_note_payload(marker_note)
    except Exception as exc:
        logger.warning("[formal_review][marker_basis_skip] marker_note_parse_failed: %s", exc)
        return _skip("标号说明解析失败")

    errors = [str(item) for item in list(getattr(payload, "errors", []) or []) if str(item).strip()]
    if errors:
        logger.info("[formal_review][marker_basis_skip] marker_note_errors=%s", errors[:5])
        return _skip("标号说明存在冲突")

    marker_to_name = {
        str(marker).strip(): str(name).strip()
        for marker, name in dict(getattr(payload, "marker_to_name", {}) or {}).items()
        if str(marker).strip() and str(name).strip()
    }
    if not marker_to_name:
        warnings = [str(item) for item in list(getattr(payload, "warnings", []) or []) if str(item).strip()]
        if warnings:
            logger.info("[formal_review][marker_basis_skip] marker_note_warnings=%s", warnings[:5])
        return _skip("标号说明无有效映射")

    return rule_ids, marker_to_name, [], ""

def _run_review_on_current_document(self) -> bool:
    mode = str(getattr(self, "_formal_review_input_mode", "word") or "word")
    self._formal_review_skipped_rule_labels = []
    self._formal_review_skipped_rule_reason = ""
    document = getattr(self, "_formal_review_document", None)
    if document is None or bool(getattr(self, "_formal_review_needs_parse", False)):
        QMessageBox.information(self, "形式审查", "请先连接并解析文档。")
        return False
    marker_edit = getattr(self, "formal_review_marker_edit", None)
    marker_note = str(marker_edit.toPlainText() or "").strip() if marker_edit is not None else ""
    if marker_edit is not None:
        set_pref(_MARKER_NOTE_PREF_KEY, marker_edit.toPlainText())
        if mode == "plain_text":
            self._render_claims_tree()
    active_wordlist_profile, _wordlist_profiles = load_wordlist_profile_store()
    wordlists = load_wordlists()
    enabled_rule_ids = enabled_rule_id_set(dict(getattr(self, "_formal_review_rule_enabled", {}) or {}))
    enabled_rule_ids, marker_note_map, skipped_rule_labels, skipped_rule_reason = self._prepare_marker_basis_rule_inputs(
        enabled_rule_ids,
        marker_note,
    )
    self._formal_review_skipped_rule_labels = list(skipped_rule_labels or [])
    self._formal_review_skipped_rule_reason = str(skipped_rule_reason or "")
    document = getattr(self, "_formal_review_document", None) if mode == "word" else self._build_document_from_current_views()
    if document is None:
        QMessageBox.information(self, "形式审查", "当前文档不可用，请先点击开始审查后重试。")
        return False
    self._formal_review_document = document
    if mode == "plain_text":
        self._formal_review_fill_claims_table()
        self._render_claims_tree()
    result = run_formal_review(
        document,
        wordlists=wordlists,
        ignored_issue_ids=set(),
        abstract_threshold=300,
        enabled_rule_ids=enabled_rule_ids,
        rule_params=dict(getattr(self, "_formal_review_rule_params", {}) or {}),
        marker_note_map=marker_note_map,
    )
    issues = list(result.get("issues", []) or [])
    rule_errors = list(result.get("rule_errors", []) or [])
    self._formal_review_rule_errors = rule_errors
    self._rebuild_issue_ids(issues)
    self._apply_ignore_state(issues)
    self._formal_review_issues = issues
    self._render_issue_views()
    status_text = f"形式审查：已完成审查，共 {len(issues)} 条问题。"
    if rule_errors:
        logger.warning(
            "[formal_review][rule_error_summary] count=%s errors=%s",
            len(rule_errors),
            rule_errors[:5],
        )
        status_text += f" 另有 {len(rule_errors)} 个规则执行异常，其他规则已继续。"
    if skipped_rule_labels:
        status_text += f" 本轮因{skipped_rule_reason or '标号说明为空/无有效映射'}，已跳过：{'、'.join(skipped_rule_labels)}。"
    wordlist_issue_count = sum(1 for issue in issues if str(getattr(issue, "rule_id", "") or "").startswith("wordlist."))
    if wordlist_issue_count:
        status_text += f" 词库命中 {wordlist_issue_count} 条，来自当前方案「{active_wordlist_profile}」，可在 设置 > 词库管理 调整。"
    self._set_status_text(status_text)
    return True

def _connect_or_attach_companion(self) -> bool:
    expected_path = str(getattr(self, "_formal_review_current_file", "") or "").strip()
    if expected_path == "__formal_review_plain_text__":
        expected_path = ""
    try:
        session = open_or_attach_document(expected_path) if expected_path else connect_active_word()
    except Exception as exc:
        show_blocking_alert_modal(self, "形式审查", f"连接 Word 失败：\n{exc}")
        return False

    current_session = getattr(self, "_formal_review_companion_session", None)
    if current_session is not None:
        current_path = str(getattr(current_session, "document_path", "") or "")
        next_path = str(getattr(session, "document_path", "") or "")
        if current_session is not session and current_path and next_path and current_path != next_path:
            self._close_companion_session()

    session_changed = current_session is not session
    self._formal_review_companion_session = session
    if session_changed:
        self._formal_review_com_block_prompted = False
        self._formal_review_com_block_last_reason = ""
    try:
        normalize_word_window(session)
    except Exception:
        pass
    try:
        session.word_hwnd = int(get_word_hwnd(session) or 0) or None
    except Exception:
        pass

    file_key = self._companion_file_key() or "__word_active__"
    current_path = str(getattr(session, "document_path", "") or file_key)
    self._formal_review_current_file = current_path
    source_path = str(getattr(self, "_formal_review_source_file", "") or "").strip()
    if not source_path:
        self._formal_review_source_file = current_path
        self._formal_review_comment_copy_path = ""
        set_pref(_COMMENT_COPY_PATH_PREF_KEY, "")
        self._formal_review_is_working_copy = False
    else:
        try:
            self._formal_review_is_working_copy = str(Path(source_path).resolve()) != str(Path(current_path).resolve())
        except Exception:
            self._formal_review_is_working_copy = source_path != current_path

    store = getattr(self, "_formal_review_suppression_store", None)
    if store is not None:
        store.switch_file(file_key)
    file_edit = getattr(self, "formal_review_file_edit", None)
    if file_edit is not None:
        text = str(getattr(session, "document_path", "") or getattr(session, "document_name", "") or "")
        file_edit.setText(text)
    self._update_companion_status_labels()
    self._apply_input_mode_to_ui()
    return True

def _clean_gate_bool_label(value: bool | None, *, true_label: str, false_label: str) -> str:
    if value is None:
        return "未知"
    return true_label if value else false_label

def _clean_gate_count_label(value: int | None) -> str:
    if value is None:
        return "未知"
    try:
        return str(int(value))
    except Exception:
        return "未知"

def _ensure_com_find_ready_or_prompt(self, *, context: str) -> bool:
    session = getattr(self, "_formal_review_companion_session", None)
    doc = getattr(session, "doc", None) if session is not None else None
    if doc is None:
        self._set_status_text("形式审查：Word 文档不可用，无法继续。")
        return False

    ready = check_com_find_ready(doc)
    if bool(getattr(ready, "ok", False)):
        return True

    reason_code = str(getattr(ready, "reason_code", "") or "com_find_unavailable")
    detail = str(getattr(ready, "detail", "") or "")
    prompted = bool(getattr(self, "_formal_review_com_block_prompted", False))

    if not prompted:
        self._formal_review_com_block_prompted = True
        self._formal_review_com_block_last_reason = reason_code
        QMessageBox.warning(
            self,
            "形式审查",
            "无法可靠定位 Word 中的文字，已停止本次修改或定位操作。\n\n"
            "请确认目标文档仍在 Word 中打开，重新连接后再试；如仍失败，请查看程序日志排查。",
        )
    else:
        self._formal_review_com_block_last_reason = reason_code
        self._set_status_text("形式审查：无法可靠定位 Word 中的文字，请重新连接文档。")

    logger.warning(
        "[formal_review][resolver] com_blocked context=%s reason_code=%s detail=%s prompted=%s",
        str(context or ""),
        reason_code,
        detail,
        bool(prompted),
    )
    return False

def _ensure_companion_doc_clean_or_prompt(self, *, trigger: str, allow_retry: bool = True) -> bool:
    session = getattr(self, "_formal_review_companion_session", None)
    doc = getattr(session, "doc", None) if session is not None else None
    if doc is None:
        QMessageBox.warning(self, "形式审查", "Word 文档不可用，无法开始审查。")
        return False

    max_attempts = 5 if bool(allow_retry) else 1
    for attempt in range(0, max_attempts):
        state = inspect_doc_clean_state(doc)
        if bool(getattr(state, "is_clean", False)):
            return True

        saved_text = self._clean_gate_bool_label(getattr(state, "saved", None), true_label="是", false_label="否")
        track_text = self._clean_gate_bool_label(getattr(state, "track_revisions", None), true_label="开", false_label="关")
        revisions_text = self._clean_gate_count_label(getattr(state, "revisions_count", None))
        comments_text = self._clean_gate_count_label(getattr(state, "comments_count", None))
        details = [
            f"已保存：{saved_text}",
            f"修订模式：{track_text}",
            f"未接受修订：{revisions_text}",
            f"批注数量：{comments_text}",
        ]
        errors = list(getattr(state, "errors", []) or [])
        if errors:
            details.append("")
            details.append("读取状态异常：")
            details.extend([f"- {row}" for row in errors[:6]])
            if len(errors) > 6:
                details.append(f"- ... 另有 {len(errors) - 6} 条未显示")

        tip = (
            "为避免重复叠加导致定位漂移/崩溃与误差累积，本工具在伴侣模式仅支持“一次性审查”。\n"
            "请先在 Word 中完成清理并保存：\n"
            "1) 删除全部批注；\n"
            "2) 接受所有修订并关闭修订模式；\n"
            "3) 点击保存；\n"
            "然后再回到本工具点击“开始审查”。"
        )

        title = "重新检测" if attempt > 0 else "文档状态检查"
        message = "重新开始审查前检测到 Word 文档未清理，已阻断本次操作。\n\n" + "\n".join(details) + "\n\n" + tip
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Warning)
        box.setText("请先清理批注和修订后再重审")
        box.setInformativeText(message)
        retry_button = None
        if bool(allow_retry):
            retry_button = box.addButton("我已清理并保存，重新检测", QMessageBox.AcceptRole)
        cancel_button = box.addButton("取消" if bool(allow_retry) else "确定", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()
        if retry_button is not None and box.clickedButton() is retry_button:
            continue

        self._set_status_text("形式审查：已阻断：请先删除全部批注、接受所有修订并关闭修订模式、保存后再开始审查。")
        logger.info("[formal_review][clean_gate] blocked: trigger=%s attempt=%s", str(trigger or ""), int(attempt))
        return False

    QMessageBox.warning(
        self,
        "形式审查",
        "多次重新检测仍未通过文档状态检查。\n请确认已：删除全部批注、接受所有修订并关闭修订模式、保存后再重试。",
    )
    self._set_status_text("形式审查：已阻断：文档状态检查未通过。")
    logger.info(
        "[formal_review][clean_gate] blocked: trigger=%s attempts_exceeded=%s",
        str(trigger or ""),
        int(max_attempts),
    )
    return False

def on_formal_review_connect_word(self):
    self._ensure_formal_review_state()
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") != "word":
        QMessageBox.information(self, "形式审查", "请先切换到 Word 文件模式。")
        return
    self._run_companion_review_cycle(trigger="connect_word", auto_sync_comments=True, redock=True)

def on_formal_review_parse(self):
    self._ensure_formal_review_state()
    mode = str(getattr(self, "_formal_review_input_mode", "word") or "word")
    if mode == "word":
        self.on_formal_review_connect_word()
        return
    claims_text = str(getattr(self, "formal_review_claims_input_text").toPlainText() or "")
    description_text = str(getattr(self, "formal_review_description_text").toPlainText() or "")
    abstract_text = str(getattr(self, "formal_review_abstract_text").toPlainText() or "")
    drawings_text = str(getattr(self, "formal_review_drawings_text").toPlainText() or "")
    if not any([claims_text.strip(), description_text.strip(), abstract_text.strip(), drawings_text.strip()]):
        QMessageBox.information(self, "形式审查", "纯文本模式下请输入至少一个分区内容后再解析。")
        return
    plain_key = "__formal_review_plain_text__"
    self._formal_review_current_file = plain_key
    self._formal_review_source_file = ""
    self._formal_review_comment_copy_path = ""
    self._formal_review_is_working_copy = False
    store = getattr(self, "_formal_review_suppression_store", None)
    if store is not None:
        store.switch_file(plain_key)
    document, anchors, editable_segments = parse_plain_text_sections(claims_text, description_text, abstract_text, drawings_text)
    self._reset_issue_views(clear_ignore=False)
    self._apply_document_snapshot(
        document=document,
        anchors=list(anchors or []),
        editable_segments=list(editable_segments or []),
        projections=None,
    )
    self._apply_input_mode_to_ui()
    claims = list(getattr(document, "claims", []) or [])
    self._set_status_text(f"形式审查：纯文本解析完成，共 {len(claims)} 条权利要求。")

def on_formal_review_marker_note_changed(self):
    marker_edit = getattr(self, "formal_review_marker_edit", None)
    if marker_edit is not None:
        set_pref(_MARKER_NOTE_PREF_KEY, marker_edit.toPlainText())
    if (
        getattr(self, "_formal_review_document", None) is not None
        and str(getattr(self, "_formal_review_input_mode", "word") or "word") == "plain_text"
    ):
        self._render_claims_tree()
        self._refresh_highlights()

def on_formal_review_start_check(self):
    self._ensure_formal_review_state()
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word":
        current_file = str(getattr(self, "_formal_review_current_file", "") or "")
        overlay_file = Path(current_file).name if current_file else ""
        overlay_title = "正在执行形式审查并同步批注，请不要编辑 Word 文档，请稍等。"
        overlay_visible = self._show_formal_review_overlay(overlay_title, overlay_file)
        self._update_formal_review_overlay(8, overlay_title, overlay_file)
        self._formal_review_overlay_progress_callback = (
            lambda pct, text: self._update_formal_review_overlay(int(pct), str(text or ""), overlay_file)
        )
        try:
            self._run_companion_review_cycle(trigger="start_check", auto_sync_comments=True, redock=False)
        finally:
            self._formal_review_overlay_progress_callback = None
            self._hide_formal_review_overlay(overlay_visible)
        return
    self._run_review_on_current_document()


