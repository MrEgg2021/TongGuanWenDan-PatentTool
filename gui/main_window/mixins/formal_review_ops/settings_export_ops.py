from __future__ import annotations

from core.user_messages import user_error_text

from .shared import (
    FormalReviewSettingsDialog,
    Path,
    QDialog,
    QFileDialog,
    QMessageBox,
    _COMMENT_AUTHOR_PREF_KEY,
    _HIGHLIGHT_COLORS_PREF_KEY,
    _RULE_OPTIONS,
    _normalize_highlight_colors,
    build_report_payload,
    datetime,
    load_wordlist_profile_store,
    save_rule_enabled,
    save_rule_params,
    save_wordlist_profile_store,
    set_active_wordlist_profile,
    set_pref,
    write_report_docx,
    write_report_xlsx,
)

__all__ = [
    "on_formal_review_export_report",
    "on_formal_review_wordlist_profile_changed",
    "on_formal_review_open_settings",
]


def _resolve_plain_text_export_paths(output_dir: Path) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"形式审查报告_{stamp}"
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    idx = 0
    while True:
        suffix = "" if idx == 0 else f"_{idx}"
        docx_path = root / f"{base}{suffix}.docx"
        xlsx_path = root / f"{base}{suffix}.xlsx"
        if not docx_path.exists() and not xlsx_path.exists():
            return docx_path, xlsx_path
        idx += 1


def _ensure_file_suffix(path: str, suffix: str) -> str:
    target = Path(str(path or "").strip())
    if not target.suffix:
        target = target.with_suffix(suffix)
    return str(target)


def on_formal_review_export_report(self):
    self._ensure_formal_review_state()
    document = getattr(self, "_formal_review_document", None)
    issues = list(getattr(self, "_formal_review_issues", []) or [])
    if document is None or not issues:
        QMessageBox.information(self, "形式审查", "请先完成审查后再导出报告。")
        return

    mode = str(getattr(self, "_formal_review_input_mode", "word") or "word")
    source = str(getattr(self, "_formal_review_current_file", "") or "formal_review")
    source_file = source if source != "__formal_review_plain_text__" else "plain_text_input"
    rule_errors = list(getattr(self, "_formal_review_rule_errors", []) or [])
    payload = build_report_payload(
        source_file=source_file,
        document=document,
        issues=issues,
        extra={"rule_errors": rule_errors} if rule_errors else None,
    )

    if mode == "plain_text":
        output_dir = QFileDialog.getExistingDirectory(self, "选择导出目录", str(Path.cwd()))
        if not output_dir:
            return
        docx_path, xlsx_path = _resolve_plain_text_export_paths(Path(output_dir))
        docx_written = write_report_docx(str(docx_path), payload)
        xlsx_written = write_report_xlsx(str(xlsx_path), payload, include_ignored_column=True)
        QMessageBox.information(self, "形式审查", f"导出成功：\n{docx_written}\n{xlsx_written}")
        return

    default_name = Path(source).stem if source else "文档"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suggested_name = f"{default_name}_形式审查报告_{stamp}.xlsx"
    output_xlsx, _ = QFileDialog.getSaveFileName(self, "导出 Excel 报告", suggested_name, "Excel (*.xlsx)")
    if not output_xlsx:
        return
    xlsx_path = write_report_xlsx(_ensure_file_suffix(output_xlsx, ".xlsx"), payload, include_ignored_column=False)
    QMessageBox.information(self, "形式审查", f"导出成功：\n{xlsx_path}")


def on_formal_review_wordlist_profile_changed(self, name: str) -> None:
    target = str(name or "").strip()
    if not target:
        return
    try:
        set_active_wordlist_profile(target)
    except Exception as exc:
        QMessageBox.warning(self, "形式审查", user_error_text(f"切换词库方案失败：\n{exc}"))
        self._refresh_wordlist_profile_combo()
        return
    self._set_status_text(f"形式审查：已切换词库方案：{target}（下次开始审查生效）")


def on_formal_review_open_settings(self):
    self._ensure_formal_review_state()
    active_profile, profiles = load_wordlist_profile_store()
    dialog = FormalReviewSettingsDialog(
        self,
        wordlist_profiles=dict(profiles or {}),
        active_wordlist_profile=str(active_profile or "默认"),
        rule_params=dict(getattr(self, "_formal_review_rule_params", {}) or {}),
        comment_author=str(getattr(self, "_formal_review_comment_author", "") or ""),
        highlight_colors=dict(getattr(self, "_formal_review_highlight_colors", {}) or {}),
        rule_enabled=dict(getattr(self, "_formal_review_rule_enabled", {}) or {}),
        rule_options=_RULE_OPTIONS,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    payload = dialog.get_settings_payload()
    save_wordlist_profile_store(
        str(payload.get("active_wordlist_profile") or active_profile or "默认"),
        dict(payload.get("wordlist_profiles") or {}),
    )
    self._refresh_wordlist_profile_combo()
    self._formal_review_comment_author = str(payload.get("comment_author") or "").strip()
    set_pref(_COMMENT_AUTHOR_PREF_KEY, self._formal_review_comment_author)
    colors = _normalize_highlight_colors(dict(payload.get("highlight_colors") or {}))
    self._formal_review_highlight_colors = colors
    set_pref(_HIGHLIGHT_COLORS_PREF_KEY, colors)
    self._formal_review_rule_enabled = save_rule_enabled(dict(payload.get("rule_enabled") or {}))
    self._formal_review_rule_params = save_rule_params(dict(payload.get("rule_params") or {}))
    self._refresh_highlights()
    self._sync_issue_detail_panel(self._get_issue_by_id(str(getattr(self, "_formal_review_selected_issue_id", "") or "")))
    self._update_marker_apply_enabled()
