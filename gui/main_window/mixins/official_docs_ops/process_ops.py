from __future__ import annotations

from core.user_messages import user_error_text

from PySide6.QtWidgets import QLabel, QPushButton

from gui.windowing import ui_pump as ui_pump_api

from .shared import (
    Path,
    ParsedNotice,
    PdfSource,
    ProcessSummary,
    QApplication,
    QMessageBox,
    QSignalBlocker,
    Qt,
    _leaf_display_name,
    _leaf_source_label,
    os,
    process_official_notice_archives,
    replace,
    set_official_doc_settings,
    show_blocking_alert_modal,
    show_official_docs_collision_dialog,
    show_official_docs_confirm_dialog,
    show_official_docs_done_dialog,
)


def _build_collision_resolver(self):
    self._official_docs_collision_policy_cache = None

    def _resolver(summary_path: str, archive_path: str) -> str:
        cache = getattr(self, "_official_docs_collision_policy_cache", None)
        if isinstance(cache, tuple) and len(cache) == 2:
            policy, apply_all = cache
            if bool(apply_all):
                return str(policy)

        policy, apply_all = show_official_docs_collision_dialog(
            self,
            summary_path=summary_path,
            archive_path=archive_path,
        )
        if bool(apply_all):
            self._official_docs_collision_policy_cache = (policy, apply_all)
        return policy

    return _resolver

def _find_leaf_id_by_zip_path(self, zip_path: str) -> str:
    target = str(zip_path or "").strip().lower()
    if not target:
        return ""
    leaves = getattr(self, "_official_docs_leaves", {})
    for leaf_id, leaf in (leaves or {}).items():
        if not isinstance(leaf, dict):
            continue
        if str(leaf.get("zip_path", "") or "").strip().lower() == target:
            return str(leaf_id)
    return ""

def _build_confirm_callback(self):
    def _open_from_parsed(parsed: ParsedNotice, source: PdfSource) -> bool:
        leaf_id = self._find_leaf_id_by_zip_path(parsed.source_zip_path)
        if leaf_id:
            return self._open_pdf_source_for_leaf(leaf_id, source)
        out_path = self._extract_pdf_to_temp(zip_path=parsed.source_zip_path, source=source)
        if not out_path:
            return False
        try:
            os.startfile(out_path)
            return True
        except Exception:
            return False

    def _confirm(parsed: ParsedNotice, summary_preview: str, archive_preview: str) -> str:
        return show_official_docs_confirm_dialog(
            self,
            parsed=parsed,
            summary_path_preview=summary_preview,
            archive_path_preview=archive_preview,
            on_open_pdf=lambda source: _open_from_parsed(parsed, source),
        )

    return _confirm

def _collect_done_dirs(self, summary: ProcessSummary) -> list[str]:
    def _normalize_dir_text(path_text: str) -> str:
        text = str(path_text or "").strip()
        if not text:
            return ""
        # Keep directory display/readability stable across Windows separators.
        return text.replace("\\", "/")

    out: list[str] = []
    run_dir = _normalize_dir_text(summary.summary_run_dir)
    if run_dir:
        out.append(run_dir)

    seen: set[str] = set(path.lower() for path in out)
    for item in summary.items or []:
        if str(item.status) != "success":
            continue
        archive_pdf = str(item.archive_pdf_path or "").strip()
        if not archive_pdf:
            continue
        archive_dir = _normalize_dir_text(str(Path(archive_pdf).parent))
        key = archive_dir.lower()
        if not archive_dir or key in seen:
            continue
        seen.add(key)
        out.append(archive_dir)
    return out


def _cache_official_docs_process_results(self, summary: ProcessSummary) -> None:
    self._init_official_docs_state()
    leaves = getattr(self, "_official_docs_leaves", {}) or {}
    if not isinstance(leaves, dict):
        return
    ordered_leaf_ids = [str(leaf_id or "").strip() for leaf_id in list(getattr(self, "_official_docs_last_process_leaf_ids", []) or []) if str(leaf_id or "").strip()]
    for index, result in enumerate(summary.items or []):
        leaf_id = ordered_leaf_ids[index] if index < len(ordered_leaf_ids) else ""
        if not leaf_id:
            leaf_id = self._find_leaf_id_by_zip_path(str(result.source_zip_path or ""))
        if not leaf_id:
            continue
        leaf = leaves.get(leaf_id)
        if not isinstance(leaf, dict):
            continue
        leaf["last_result"] = {
            "status": str(result.status or ""),
            "reason": str(result.reason or ""),
            "output_pdf_name": str(result.output_pdf_name or ""),
            "summary_pdf_path": str(result.summary_pdf_path or ""),
            "archive_pdf_path": str(result.archive_pdf_path or ""),
        }

def on_official_docs_start_processing(self) -> None:
    self._init_official_docs_state()
    checked_ids = list(self._iter_checked_leaf_ids())
    if not checked_ids:
        QMessageBox.information(self, "提示", "请先勾选要处理的通知书。")
        return

    if self._official_docs_dirty:
        ok = self._confirm_leave_official_docs_if_dirty()
        if not ok:
            return

    options = self._build_official_docs_options(use_saved=True)
    setting_errors = self._validate_official_docs_settings(self._official_docs_saved_settings)
    if setting_errors:
        QMessageBox.warning(self, "无法开始处理", user_error_text("\n".join(setting_errors)))
        return
    if bool(options.write_archive):
        if not self._ensure_archive_consent():
            checkbox = getattr(self, "official_docs_chk_archive", None)
            if checkbox is not None:
                with QSignalBlocker(checkbox):
                    checkbox.setChecked(False)
            self._official_docs_working_settings["write_archive"] = False
            self._official_docs_saved_settings["write_archive"] = False
            set_official_doc_settings(self._official_docs_saved_settings)
            return

    leaves = getattr(self, "_official_docs_leaves", {}) or {}
    zip_paths: list[str] = []
    ordered_leaf_ids: list[str] = []
    source_labels_by_zip: dict[str, str] = {}
    for leaf_id in checked_ids:
        leaf = leaves.get(leaf_id)
        if not isinstance(leaf, dict):
            continue
        zip_path = str(leaf.get("zip_path", "") or "").strip()
        if not zip_path:
            continue
        zip_paths.append(zip_path)
        ordered_leaf_ids.append(leaf_id)
        source_label = _leaf_source_label(leaf)
        if source_label:
            source_labels_by_zip[zip_path] = source_label

    if not zip_paths:
        QMessageBox.warning(self, "无法开始处理", "当前选择条目没有可用 ZIP 文件。")
        return

    self._official_docs_last_process_leaf_ids = list(ordered_leaf_ids)
    options = replace(options, source_label_by_zip_path=dict(source_labels_by_zip))
    collision_resolver = self._build_collision_resolver()
    confirm_cb = self._build_confirm_callback() if bool(options.confirm_each) else None

    start_button = getattr(self, "official_docs_start_button", None)
    if start_button is not None:
        start_button.setEnabled(False)

    self._progress_scope = "official_docs"
    try:
        self._reset_cancel_state()
    except Exception:
        try:
            self._cancel_requested = False
        except Exception:
            pass

    overlay_status = "正在处理官文..."
    overlay_file = "准备开始..."
    if bool(options.enable_exam_pdf_parse):
        overlay_status = "正在处理官文（已启用PDF解析）..."
    try:
        self._show_processing_overlay(overlay_status, overlay_file)
    except Exception:
        pass

    overlay = getattr(self, "_processing_overlay", None)
    if overlay is not None:
        try:
            cancel_button = overlay.findChild(QPushButton, "processingCancelButton")
            if cancel_button is not None:
                cancel_button.setEnabled(False)
                cancel_button.setVisible(False)
        except Exception:
            pass
        if bool(options.enable_exam_pdf_parse):
            try:
                warn_label = overlay.findChild(QLabel, "processingWarnLabel")
                if warn_label is not None:
                    warn_label.setText("已启用PDF解析，处理耗时较久且可能存在误差，请在处理完成后自行检查核对。")
            except Exception:
                pass

    def _progress_cb(current: int, total_count: int, message: str) -> None:
        percent = 0
        try:
            if int(total_count) > 0:
                percent = int(max(0, min(100, (int(current) * 100) / int(total_count))))
        except Exception:
            percent = 0
        primary = f"正在处理官文 ({int(current)}/{int(total_count)})" if int(total_count) > 0 else "正在处理官文..."
        detail = str(message or "").strip() or "处理中..."
        try:
            self._update_processing_overlay(percent, primary, detail)
            ui_pump_api.pump(allow_user_input=False)
        except Exception:
            pass

    summary = None
    process_error = None
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        try:
            summary = process_official_notice_archives(
                zip_paths,
                options,
                collision_resolver=collision_resolver,
                confirm_cb=confirm_cb,
                progress_cb=_progress_cb,
            )
        except Exception as exc:
            process_error = exc
        finally:
            try:
                self._hide_processing_overlay()
            except Exception:
                pass
    finally:
        QApplication.restoreOverrideCursor()
        if start_button is not None:
            try:
                start_button.setEnabled(True)
            except Exception:
                pass
        if getattr(self, "_progress_scope", None) == "official_docs":
            self._progress_scope = None

    if process_error is not None:
        show_blocking_alert_modal(self, "官文处理失败", f"官文处理过程中发生错误：\n{process_error}")
        return
    if summary is None:
        return

    result_rows: list[dict[str, str]] = []
    for index, result in enumerate(summary.items or []):
        leaf_id = ordered_leaf_ids[index] if index < len(ordered_leaf_ids) else ""
        leaf = leaves.get(leaf_id) if isinstance(leaves, dict) else None
        name = _leaf_display_name(leaf) if isinstance(leaf, dict) else ""
        if not name:
            name = os.path.basename(str(result.source_zip_path or "").strip()) or str(result.source_zip_path or "")
        result_rows.append(
            {
                "display_name": name,
                "status": str(result.status or ""),
                "source_zip_path": str(result.source_zip_path or ""),
                "summary_pdf_path": str(result.summary_pdf_path or ""),
                "archive_pdf_path": str(result.archive_pdf_path or ""),
                "output_pdf_name": str(result.output_pdf_name or ""),
            }
        )

    open_dirs = self._collect_done_dirs(summary)
    self._cache_official_docs_process_results(summary)

    show_official_docs_done_dialog(
        self,
        total=summary.total,
        success=summary.success,
        skipped=summary.skipped,
        failed=summary.failed,
        items=result_rows,
        open_dirs=open_dirs,
        excel_path=summary.excel_path,
        run_dir=summary.summary_run_dir,
    )

    self.on_official_docs_clear_items()

