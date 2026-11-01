from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QComboBox, QHBoxLayout, QPushButton, QTableWidgetItem, QWidget

from core.response_correction import (
    CorrectionItem,
    CorrectionPackageRequest,
    NoticeMeta,
    ResponsePackageRequest,
    SlotInput,
    build_correction_package,
    build_response_package,
    infer_response_correction_notice_kind,
    normalize_application_no,
    parse_notice_source,
)
from core.logging_utils import logger
from core.word_engine import WordComHijackedError
from core.word_startup_health import WordStartupHealthResult, check_word_startup_health
from gui.app_impl.file_ops import reveal_path_in_explorer, show_drop_ignored_message
from gui.app_impl.response_correction_imports import (
    StagedImportItem,
    collect_response_correction_files,
    role_label_for_code,
    role_options_for_flow,
    should_attempt_notice_parse,
    should_silently_ignore_material,
    source_kind_for_path,
    suggest_role_for_path,
    unsupported_material_reason,
)
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal
from gui.office_process_guard import ensure_office_processes_ready
from gui.widgets_impl.combo_wheel_blocker import ComboWheelBlocker

try:
    import pythoncom
except Exception:  # pragma: no cover - pywin32 is present in supported Windows runtime.
    pythoncom = None


SUPPORTED_DOCUMENT_SLOTS: tuple[tuple[str, str], ...] = (
    ("100001", "权利要求书"),
    ("100002", "说明书"),
    ("100003", "说明书附图"),
    ("100004", "说明书摘要"),
)
_SLOT_LABEL_BY_CODE = dict(SUPPORTED_DOCUMENT_SLOTS)
_SUBMISSION_SCENE_BY_FLOW = {
    "response": "notice_response",
    "correction": "notice_correction",
    "active_response": "active_response",
    "active_correction": "active_correction",
}
_CORRECTION_TABLE_ATTR_BY_FLOW = {
    "correction": "correction_items_table",
    "active_correction": "active_correction_items_table",
}
_WORD_HEALTH_RETRY_REASON_CODES = {
    "word_start_failed",
    "com_bind_failed",
    "com_bound_to_wps",
    "unexpected_word_pid",
    "word_pid_missing_unclaimed",
    "word_quit_failed",
    "word_exit_failed",
}


def _text(widget) -> str:
    try:
        return str(widget.text() or "").strip()
    except Exception:
        return ""


def _set_text(widget, value: str) -> None:
    try:
        widget.setText(str(value or ""))
    except Exception:
        pass


def _should_retry_response_word_health(health: WordStartupHealthResult, *, retry_attempted: bool) -> bool:
    if bool(retry_attempted):
        return False
    try:
        if bool(getattr(health, "killed_before_check", False)):
            return False
    except Exception:
        return False
    try:
        reason_code = str(getattr(health, "reason_code", "") or "")
    except Exception:
        reason_code = ""
    return reason_code in _WORD_HEALTH_RETRY_REASON_CODES


def _emit_response_word_health_progress(progress_callback, stage: str, payload: dict) -> None:
    if not callable(progress_callback):
        return
    stage_text = str(stage or "")
    detail = stage_text
    try:
        pid = payload.get("pid") if isinstance(payload, dict) else None
        if pid is not None:
            detail = f"{stage_text} | PID={pid}"
    except Exception:
        detail = stage_text
    try:
        progress_callback(3, "正在后台检查 Word 环境", detail)
    except Exception:
        pass


def _wrap_task_with_word_health(task_callable, *, killed_before_check: bool):
    def _task(progress_callback=None):
        health = check_word_startup_health(
            killed_before_check=bool(killed_before_check),
            progress_callback=lambda stage, payload: _emit_response_word_health_progress(
                progress_callback,
                stage,
                payload,
            ),
        )
        if not bool(getattr(health, "ok", False)):
            raise _ResponseCorrectionWordHealthError(health)
        return task_callable(progress_callback=progress_callback)

    return _task


class _ResponseCorrectionWorker(QObject):
    finished = Signal(object)
    failed = Signal(object, str)
    progress = Signal(int, str, str)

    def __init__(self, task_callable):
        super().__init__()
        self._task_callable = task_callable

    @Slot()
    def run(self) -> None:
        initialized = False
        try:
            if pythoncom is not None:
                pythoncom.CoInitialize()
                initialized = True
            result = self._task_callable(progress_callback=self.progress.emit)
        except Exception as exc:
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            self.failed.emit(exc, detail or str(exc))
            return
        finally:
            if initialized and pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
        self.finished.emit(result)


class _ResponseCorrectionWordHealthError(RuntimeError):
    def __init__(self, health: WordStartupHealthResult) -> None:
        self.health = health
        message = str(
            getattr(health, "user_message", None)
            or getattr(health, "error", None)
            or "Word 启动检查未通过，请关闭 Word/WPS 后重试。"
        )
        super().__init__(message)


class _ResponseCorrectionBridge(QObject):
    success = Signal(object)
    failed = Signal(object, str)
    progress = Signal(int, str, str)


@dataclass(frozen=True)
class _StagedImportSnapshot:
    items: tuple[StagedImportItem, ...]
    current_slots: dict[str, dict[str, str]]
    current_opinion_material: dict[str, str] | None


@dataclass(frozen=True)
class _StagedImportProcessResult:
    ok: bool
    updated_items: tuple[StagedImportItem, ...]
    next_slots: dict[str, dict[str, str]]
    next_opinion_material: dict[str, str] | None
    status_message: str = ""
    alert_title: str = ""
    alert_message: str = ""


class ResponseCorrectionMixin:
    def _expected_notice_kind_for_flow(self, flow: str) -> str:
        return {
            "response": "exam_opinion",
            "correction": "rectification",
        }.get(flow, "")

    def _flow_requires_notice(self, flow: str) -> bool:
        return flow in {"response", "correction"}


    def _submission_scene_for_flow(self, flow: str) -> str:
        return _SUBMISSION_SCENE_BY_FLOW.get(flow, "notice_response")

    def _correction_items_table_for_flow(self, flow: str):
        return getattr(self, _CORRECTION_TABLE_ATTR_BY_FLOW.get(flow, "correction_items_table"), None)

    def _flow_attr(self, flow: str, name: str) -> str:
        return f"{flow}_{name}"

    def _flow_widget(self, flow: str, name: str):
        return getattr(self, self._flow_attr(flow, name), None)

    def _slot_state_for_flow(self, flow: str) -> dict[str, dict[str, str]]:
        attr = f"_{flow}_document_slots"
        state = getattr(self, attr, None)
        if not isinstance(state, dict):
            state = {}
            setattr(self, attr, state)
        return state

    def _staged_import_items_for_flow(self, flow: str) -> list[StagedImportItem]:
        attr = f"_{flow}_staged_import_items"
        items = getattr(self, attr, None)
        if not isinstance(items, list):
            items = []
            setattr(self, attr, items)
        return items

    def _set_staged_import_items_for_flow(self, flow: str, items: list[StagedImportItem]) -> None:
        setattr(self, f"_{flow}_staged_import_items", list(items))

    def _confirmed_opinion_material_for_flow(self, flow: str) -> dict[str, str] | None:
        data = getattr(self, f"_{flow}_opinion_material", None)
        return data if isinstance(data, dict) else None

    def _confirmed_opinion_input_for_flow(self, flow: str) -> SlotInput | None:
        data = self._confirmed_opinion_material_for_flow(flow)
        if not data:
            return None
        path = str(data.get("path", "") or "").strip()
        if not path:
            return None
        return SlotInput(path=path, preconverted=False)

    def _combo_wheel_blocker_for_flow(self, flow: str) -> ComboWheelBlocker:
        attr = f"_{flow}_combo_wheel_blocker"
        blocker = getattr(self, attr, None)
        if isinstance(blocker, ComboWheelBlocker):
            return blocker
        parent = self if isinstance(self, QObject) else None
        blocker = ComboWheelBlocker(parent)
        setattr(self, attr, blocker)
        return blocker

    def _protect_combo_wheel_for_flow(self, flow: str, *, combo: QComboBox | None = None, table=None) -> None:
        blocker = self._combo_wheel_blocker_for_flow(flow)
        if table is not None:
            attr = f"_{flow}_combo_wheel_registered_tables"
            seen_tables = getattr(self, attr, None)
            if not isinstance(seen_tables, set):
                seen_tables = set()
                setattr(self, attr, seen_tables)
            table_key = id(table)
            if table_key not in seen_tables:
                blocker.register_strict_scroll_area(table)
                seen_tables.add(table_key)
        if combo is not None:
            blocker.register_combo(combo)

    def _set_notice_section_expanded(self, flow: str, expanded: bool) -> None:
        notice_section_body = self._flow_widget(flow, "notice_section_body")
        notice_section_toggle = self._flow_widget(flow, "notice_section_toggle")
        if notice_section_body is not None:
            try:
                notice_section_body.setVisible(bool(expanded))
            except Exception:
                pass
        if notice_section_toggle is not None:
            try:
                notice_section_toggle.blockSignals(True)
                notice_section_toggle.setChecked(bool(expanded))
                notice_section_toggle.setText(f"通知书与字段 {'▼' if expanded else '▶'}")
                notice_section_toggle.blockSignals(False)
            except Exception:
                pass

    def on_toggle_notice_section(self, flow: str, checked: bool) -> None:
        self._set_notice_section_expanded(str(flow or "").strip(), bool(checked))

    def _clear_notice_for_flow(self, flow: str, *, status_message: str = "") -> None:
        _set_text(self._flow_widget(flow, "notice_edit"), "")
        _set_text(self._flow_widget(flow, "application_no_edit"), "")
        _set_text(self._flow_widget(flow, "title_edit"), "")
        _set_text(self._flow_widget(flow, "applicant_edit"), "")
        _set_text(self._flow_widget(flow, "notice_name_edit"), "")
        _set_text(self._flow_widget(flow, "issue_date_edit"), "")
        _set_text(self._flow_widget(flow, "doc_serial_edit"), "")
        combo = self._flow_widget(flow, "patent_type_combo")
        if combo is not None:
            try:
                combo.setCurrentIndex(0)
            except Exception:
                pass
        setattr(self, f"_{flow}_notice_meta", NoticeMeta())
        status = self._flow_widget(flow, "status_label")
        if status is not None:
            try:
                status.setText(str(status_message or "").strip() or "等待开始")
            except Exception:
                pass

    def _set_flow_status_message(self, flow: str, message: str) -> None:
        status = self._flow_widget(flow, "status_label")
        if status is None:
            return
        try:
            status.setText(str(message or "").strip() or "等待开始")
        except Exception:
            pass

    def _flow_has_notice_fields(self, flow: str) -> bool:
        meta = getattr(self, f"_{flow}_notice_meta", None)
        if isinstance(meta, NoticeMeta) and any(
            (
                str(meta.application_no or "").strip(),
                str(meta.notice_name or "").strip(),
                str(meta.invention_title or "").strip(),
                str(meta.applicant or "").strip(),
            )
        ):
            return True
        return any(
            (
                _text(self._flow_widget(flow, "application_no_edit")),
                _text(self._flow_widget(flow, "notice_name_edit")),
                _text(self._flow_widget(flow, "title_edit")),
                _text(self._flow_widget(flow, "applicant_edit")),
            )
        )

    def _notice_status_text(self, parsed, notice_kind: str) -> str:
        source = str(getattr(parsed, "meta_source", "") or "unknown").strip() or "unknown"
        if notice_kind == "unknown":
            message = f"已解析通知书元数据（来源：{source}），但通知书类型未能自动识别。"
        else:
            message = f"已解析通知书元数据（来源：{source}）。"
        meta = getattr(parsed, "meta", NoticeMeta())
        if not str(getattr(meta, "issue_date", "") or "").strip():
            return f"{message[:-1]}，但未识别出发文日，请补录后再生成。"
        if not str(getattr(meta, "doc_serial", "") or "").strip():
            return f"{message[:-1]}，但未识别出发文序号，请补录发文序号。"
        return message

    def _validate_notice_kind_for_flow(
        self,
        flow: str,
        notice: NoticeMeta,
        *,
        clear_on_mismatch: bool,
        show_alert: bool = True,
    ) -> bool:
        expected_notice_kind = self._expected_notice_kind_for_flow(flow)
        if not expected_notice_kind:
            return True
        notice_kind = infer_response_correction_notice_kind(notice)
        if notice_kind == "unknown":
            return True
        if notice_kind == expected_notice_kind:
            return True
        message = self._notice_kind_mismatch_message(flow)
        if show_alert:
            show_blocking_alert_modal(self, "类型不匹配", message, primary_text="知道了", secondary_text="知道了")
        if clear_on_mismatch:
            self._clear_notice_for_flow(flow, status_message=message)
        return False

    def _notice_kind_mismatch_message(self, flow: str) -> str:
        if flow == "response":
            return "当前页面仅接受审查意见通知书，请确认文件类型是否正确。"
        if flow == "correction":
            return "当前页面仅接受补正通知书，请确认文件类型是否正确。"
        return "当前通知书类型与所选流程不匹配。"

    def _flow_prefills_notice_basics_only(self, flow: str) -> bool:
        return flow in {"active_response", "active_correction"}

    def _active_notice_prefill_status_text(self, parsed) -> str:
        meta = getattr(parsed, "meta", NoticeMeta())
        missing: list[str] = []
        if not str(getattr(meta, "application_no", "") or "").strip():
            missing.append("申请号")
        if not str(getattr(meta, "invention_title", "") or "").strip():
            missing.append("发明名称")
        if not str(getattr(meta, "applicant", "") or "").strip():
            missing.append("申请人")
        if missing:
            return f"已识别通知书，但部分基础字段缺失，请补充：{'、'.join(missing)}。"
        return "已自动解析通知书并回填基础信息。"

    def _apply_parsed_notice_prefill_to_active_flow(
        self,
        flow: str,
        parsed,
        *,
        source_path: str,
        status_text: str | None = None,
    ) -> None:
        meta = getattr(parsed, "meta", NoticeMeta())
        setattr(self, f"_{flow}_notice_meta", meta)
        _set_text(self._flow_widget(flow, "notice_edit"), source_path)
        if str(meta.application_no or "").strip():
            _set_text(self._flow_widget(flow, "application_no_edit"), meta.application_no)
        if str(meta.invention_title or "").strip():
            _set_text(self._flow_widget(flow, "title_edit"), meta.invention_title)
        if str(meta.applicant or "").strip():
            _set_text(self._flow_widget(flow, "applicant_edit"), meta.applicant)
        if str(meta.patent_type or "").strip():
            self._set_patent_type_combo(flow, meta.patent_type)
        self._set_flow_status_message(flow, status_text or self._active_notice_prefill_status_text(parsed))

    def _apply_parsed_notice_to_flow(self, flow: str, parsed, *, source_path: str, status_text: str | None = None) -> None:
        meta = getattr(parsed, "meta", NoticeMeta())
        if self._flow_prefills_notice_basics_only(flow):
            self._apply_parsed_notice_prefill_to_active_flow(
                flow,
                parsed,
                source_path=source_path,
                status_text=status_text,
            )
            return
        setattr(self, f"_{flow}_notice_meta", meta)
        _set_text(self._flow_widget(flow, "notice_edit"), source_path)
        _set_text(self._flow_widget(flow, "application_no_edit"), meta.application_no)
        _set_text(self._flow_widget(flow, "title_edit"), meta.invention_title)
        _set_text(self._flow_widget(flow, "applicant_edit"), meta.applicant)
        _set_text(self._flow_widget(flow, "notice_name_edit"), meta.notice_name)
        _set_text(self._flow_widget(flow, "issue_date_edit"), meta.issue_date)
        _set_text(self._flow_widget(flow, "doc_serial_edit"), meta.doc_serial)
        if meta.patent_type:
            self._set_patent_type_combo(flow, meta.patent_type)
        self._set_flow_status_message(
            flow,
            status_text or self._notice_status_text(parsed, infer_response_correction_notice_kind(meta)),
        )
        self._set_notice_section_expanded(flow, True)

    def _looks_like_notice_parse_result(self, parsed) -> bool:
        meta = getattr(parsed, "meta", NoticeMeta())
        notice_name = str(getattr(meta, "notice_name", "") or "").strip()
        notice_code = str(getattr(meta, "notice_code", "") or "").strip()
        if notice_name and ("通知书" in notice_name or "notice" in notice_name.lower()):
            return True
        if infer_response_correction_notice_kind(meta) != "unknown":
            return True
        return bool(notice_code)

    def _try_auto_import_notice_for_flow(self, flow: str, source_path: str) -> bool:
        if not should_attempt_notice_parse(source_path, flow):
            return False
        parsed = parse_notice_source(source_path, mode_hint=flow)
        if not self._looks_like_notice_parse_result(parsed):
            return False
        existing_notice_present = self._flow_has_notice_fields(flow)
        path_name = Path(str(source_path or "")).name
        if getattr(parsed, "errors", ()):
            detail = "；".join(str(item) for item in (parsed.errors or ()) if str(item or "").strip())
            suffix = "，已保留当前通知书。" if existing_notice_present else "。"
            self._set_flow_status_message(flow, f"自动解析的通知书失败：{path_name}；{detail}{suffix}")
            return True
        notice_kind = infer_response_correction_notice_kind(parsed.meta)
        expected_notice_kind = self._expected_notice_kind_for_flow(flow)
        if expected_notice_kind and notice_kind not in {"unknown", expected_notice_kind}:
            suffix = "，已保留当前通知书。" if existing_notice_present else "。"
            self._set_flow_status_message(
                flow,
                f"自动解析的通知书已跳过：{path_name}；{self._notice_kind_mismatch_message(flow)}{suffix}",
            )
            return True
        status_text = self._notice_status_text(parsed, notice_kind)
        if self._flow_prefills_notice_basics_only(flow):
            status_text = self._active_notice_prefill_status_text(parsed)
        self._apply_parsed_notice_to_flow(
            flow,
            parsed,
            source_path=source_path,
            status_text=f"自动解析的通知书：{path_name}；{status_text}",
        )
        return True

    def _browse_response_correction_file(self, attr: str, title: str, file_filter: str) -> str:
        try:
            current = _text(getattr(self, attr, None))
            base = str(Path(current).parent) if current else os.getcwd()
            path, _ = QFileDialog.getOpenFileName(self, title, base, file_filter)
            if path:
                _set_text(getattr(self, attr, None), path)
                return str(path)
            return ""
        except Exception as exc:
            show_blocking_alert_modal(self, "打开失败", f"选择文件时发生错误：{exc}", primary_text="知道了", secondary_text="知道了")
            return ""

    def _browse_output_dir_for_flow(self, flow: str) -> None:
        try:
            current = _text(self._flow_widget(flow, "output_dir_edit")) or os.getcwd()
            path = QFileDialog.getExistingDirectory(self, "选择输出目录", current)
            if path:
                _set_text(self._flow_widget(flow, "output_dir_edit"), path)
        except Exception as exc:
            show_blocking_alert_modal(self, "打开失败", f"选择输出目录时发生错误：{exc}", primary_text="知道了", secondary_text="知道了")

    def _browse_import_files_for_flow(self, flow: str) -> None:
        try:
            paths, _ = QFileDialog.getOpenFileNames(self, "选择导入文件", os.getcwd(), "支持的文件 (*.doc *.docx *.pdf *.zip)")
        except Exception as exc:
            show_blocking_alert_modal(self, "打开失败", f"选择导入文件时发生错误：{exc}", primary_text="知道了", secondary_text="知道了")
            return
        if paths:
            self._ingest_import_paths_for_flow(flow, paths)

    def _browse_import_folder_for_flow(self, flow: str) -> None:
        try:
            folder = QFileDialog.getExistingDirectory(self, "选择导入文件夹", os.getcwd())
        except Exception as exc:
            show_blocking_alert_modal(self, "打开失败", f"选择导入文件夹时发生错误：{exc}", primary_text="知道了", secondary_text="知道了")
            return
        if folder:
            self._ingest_import_paths_for_flow(flow, [folder])

    def _normalize_import_key(self, path: str) -> str:
        text = str(path or "").strip()
        if not text:
            return ""
        try:
            return os.path.normcase(str(Path(text).resolve()))
        except Exception:
            return os.path.normcase(os.path.normpath(text))

    def _ingest_import_paths_for_flow(self, flow: str, paths) -> None:
        valid_paths, ignored = collect_response_correction_files(paths, include_directories=True)
        existing = self._staged_import_items_for_flow(flow)
        seen = {self._normalize_import_key(item.source_path) for item in existing}
        items = list(existing)
        for path in valid_paths:
            key = self._normalize_import_key(path)
            if not key or key in seen:
                continue
            if self._try_auto_import_notice_for_flow(flow, str(path)):
                seen.add(key)
                continue
            if should_silently_ignore_material(path, flow):
                seen.add(key)
                continue
            reason = unsupported_material_reason(path, flow)
            if reason:
                ignored.append(reason)
                seen.add(key)
                continue
            suggested_role = suggest_role_for_path(path, flow)
            items.append(
                StagedImportItem(
                    source_path=str(path),
                    source_kind=source_kind_for_path(path),
                    suggested_role=suggested_role,
                    selected_role=suggested_role,
                )
            )
            seen.add(key)
        self._set_staged_import_items_for_flow(flow, items)
        self._refresh_staged_files_table(flow)
        show_drop_ignored_message(self, "部分文件未导入", ignored)

    def _clear_staged_files_for_flow(self, flow: str) -> None:
        self._set_staged_import_items_for_flow(flow, [])
        self._refresh_materials_table(flow)

    def _role_combo_for_flow(self, flow: str, selected_role: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem("暂不关联", "")
        for label, code in role_options_for_flow(flow):
            combo.addItem(label, code)
        target = str(selected_role or "").strip()
        for index in range(combo.count()):
            if str(combo.itemData(index) or "") == target:
                combo.setCurrentIndex(index)
                break
        return combo

    def _update_staged_item_role(self, flow: str, row: int, role: str) -> None:
        items = list(self._staged_import_items_for_flow(flow))
        if row < 0 or row >= len(items):
            return
        selected_role = str(role or "").strip()
        item = items[row]
        next_status = item.status
        next_confirmed_time = item.confirmed_time
        next_confirmed_payload_path = item.confirmed_payload_path
        next_result_message = item.result_message
        next_error_message = item.error_message
        if selected_role != str(item.confirmed_role or "").strip():
            next_status = "待上传"
            next_confirmed_time = ""
            next_confirmed_payload_path = ""
            next_result_message = ""
            next_error_message = ""
        items[row] = replace(
            item,
            selected_role=selected_role,
            status=next_status,
            confirmed_time=next_confirmed_time,
            confirmed_payload_path=next_confirmed_payload_path,
            result_message=next_result_message,
            error_message=next_error_message,
        )
        self._set_staged_import_items_for_flow(flow, items)
        self._refresh_materials_table(flow)

    def _remove_material_item_for_flow(self, flow: str, row: int) -> None:
        items = list(self._staged_import_items_for_flow(flow))
        if row < 0 or row >= len(items):
            return
        items.pop(row)
        self._set_staged_import_items_for_flow(flow, items)
        self._refresh_materials_table(flow)
        self._set_flow_status_message(flow, "材料列表已更新；如需同步到实际打包内容，请再次点击“上传/更新已关联材料”。")

    def _material_result_text(self, item: StagedImportItem) -> str:
        if str(item.error_message or "").strip():
            return str(item.error_message or "").strip()
        if str(item.result_message or "").strip():
            return str(item.result_message or "").strip()
        if str(item.confirmed_payload_path or "").strip():
            return Path(str(item.confirmed_payload_path or "")).name
        if not str(item.selected_role or "").strip():
            return "未选择关联类型"
        return ""

    def _wrap_material_cell_widget(self, widget, *, center: bool = False) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if center:
            layout.addStretch(1)
            layout.addWidget(widget, 0, Qt.AlignCenter)
            layout.addStretch(1)
        else:
            layout.addWidget(widget, 0, Qt.AlignVCenter | Qt.AlignLeft)
            layout.addStretch(1)
        return container

    def _refresh_materials_table(self, flow: str) -> None:
        table = self._flow_widget(flow, "materials_table")
        if table is None:
            return
        self._protect_combo_wheel_for_flow(flow, table=table)
        items = list(self._staged_import_items_for_flow(flow))
        table.setRowCount(0)
        row_height = 58
        control_height = 40
        try:
            table.verticalHeader().setDefaultSectionSize(row_height)
        except Exception:
            pass
        for row, item in enumerate(items):
            table.insertRow(row)
            name_item = QTableWidgetItem(Path(item.source_path).name)
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            table.setItem(row, 0, name_item)
            clear_btn = QPushButton("清除")
            clear_btn.setProperty("class", "Ghost")
            clear_btn.setMinimumHeight(control_height)
            clear_btn.setFixedHeight(control_height)
            clear_btn.clicked.connect(lambda _checked=False, item_flow=flow, item_row=row: self._remove_material_item_for_flow(item_flow, item_row))
            table.setCellWidget(row, 1, self._wrap_material_cell_widget(clear_btn, center=True))
            suggested_item = QTableWidgetItem(role_label_for_code(item.suggested_role))
            suggested_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            table.setItem(row, 2, suggested_item)
            role_combo = self._role_combo_for_flow(flow, item.selected_role)
            role_combo.setMinimumHeight(control_height)
            role_combo.setFixedHeight(control_height)
            role_combo.currentIndexChanged.connect(
                lambda _index, combo=role_combo, item_flow=flow, item_row=row: self._update_staged_item_role(
                    item_flow,
                    item_row,
                    str(combo.currentData() or ""),
                )
            )
            self._protect_combo_wheel_for_flow(flow, combo=role_combo)
            table.setCellWidget(row, 3, self._wrap_material_cell_widget(role_combo))
            status_item = QTableWidgetItem(str(item.status or ""))
            status_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            table.setItem(row, 4, status_item)
            confirmed_time_item = QTableWidgetItem(str(item.confirmed_time or ""))
            confirmed_time_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            table.setItem(row, 5, confirmed_time_item)
            result_item = QTableWidgetItem(self._material_result_text(item))
            result_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            table.setItem(row, 6, result_item)

    def _refresh_staged_files_table(self, flow: str) -> None:
        self._refresh_materials_table(flow)

    def _allowed_suffixes_for_role(self, role: str) -> set[str]:
        if role == "opinion_body":
            return {".doc", ".docx"}
        if role in _SLOT_LABEL_BY_CODE:
            return {".doc", ".docx", ".zip"}
        return set()


    def _capture_staged_import_snapshot(self, flow: str) -> _StagedImportSnapshot:
        return _StagedImportSnapshot(
            items=tuple(self._staged_import_items_for_flow(flow)),
            current_slots=dict(self._slot_state_for_flow(flow)),
            current_opinion_material=self._confirmed_opinion_material_for_flow(flow),
        )


    def _process_staged_import_snapshot(
        self,
        flow: str,
        snapshot: _StagedImportSnapshot,
        *,
        progress_callback=None,
    ) -> _StagedImportProcessResult:
        items = list(snapshot.items)
        selected = [(index, item) for index, item in enumerate(items) if str(item.selected_role or "").strip()]
        if callable(progress_callback):
            progress_callback(5, "正在更新已关联材料", "步骤 1/5：校验当前材料映射")
        role_counts: dict[str, int] = {}
        indexed_errors: dict[int, str] = {}
        for index, item in selected:
            role = str(item.selected_role or "").strip()
            role_counts[role] = role_counts.get(role, 0) + 1
            if role_counts[role] > 1:
                indexed_errors[index] = f"{role_label_for_code(role)} 只能关联一个文件。"
                continue
            suffix = Path(item.source_path).suffix.lower()
            if suffix not in self._allowed_suffixes_for_role(role):
                indexed_errors[index] = f"{Path(item.source_path).name} 不能关联到 {role_label_for_code(role)}。"

        if indexed_errors:
            updated: list[StagedImportItem] = []
            for index, item in enumerate(items):
                message = indexed_errors.get(index, "")
                if message:
                    updated.append(
                        replace(
                            item,
                            status="校验失败",
                            confirmed_time="",
                            confirmed_payload_path="",
                            result_message="",
                            error_message=message,
                        )
                    )
                else:
                    updated.append(item)
            return _StagedImportProcessResult(
                ok=False,
                updated_items=tuple(updated),
                next_slots=dict(snapshot.current_slots),
                next_opinion_material=snapshot.current_opinion_material,
                status_message="材料关联校验失败",
                alert_title="关联校验失败",
                alert_message="\n".join(indexed_errors.values()),
            )

        confirmed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        next_slots: dict[str, dict[str, str]] = {}
        next_opinion_material: dict[str, str] | None = None
        updated_items: list[StagedImportItem] = list(items)
        current_index = -1
        try:
            for current_index, item in enumerate(items):
                role = str(item.selected_role or "").strip()
                if not role:
                    updated_items[current_index] = replace(
                        item,
                        status="待上传",
                        confirmed_role="",
                        confirmed_time="",
                        confirmed_payload_path="",
                        result_message="",
                        error_message="",
                    )
                    continue
                source_path = str(item.source_path or "").strip()
                if callable(progress_callback):
                    progress_callback(
                        15 + int(55 * (current_index + 1) / max(1, len(items))),
                        "正在更新已关联材料",
                        f"步骤 2/5：逐行处理材料（{Path(source_path).name}）",
                    )
                final_path = source_path
                if role == "opinion_body":
                    next_opinion_material = {
                        "path": source_path,
                        "source_name": Path(source_path).name,
                        "source_kind": source_kind_for_path(source_path),
                        "created_at": confirmed_time,
                        "display_name": role_label_for_code(role),
                        "final_path": source_path,
                        "result": "已上传",
                    }
                else:
                    next_slots[role] = {
                        "slot_code": role,
                        "display_name": role_label_for_code(role),
                        "path": source_path,
                        "preconverted": "1" if Path(source_path).suffix.lower() == ".zip" else "0",
                        "source_kind": source_kind_for_path(source_path),
                        "created_at": confirmed_time,
                    }
                updated_items[current_index] = replace(
                    item,
                    status="已上传",
                    confirmed_role=role,
                    confirmed_time=confirmed_time,
                    confirmed_payload_path=final_path,
                    result_message=Path(str(final_path or "")).name,
                    error_message="",
                )
        except Exception as exc:
            message = str(exc)
            rollback_items = list(snapshot.items)
            if 0 <= current_index < len(updated_items):
                failed_item = items[current_index]
                rollback_items[current_index] = replace(
                    failed_item,
                    status="处理失败",
                    confirmed_time="",
                    confirmed_payload_path="",
                    result_message="",
                    error_message=message,
                )
            return _StagedImportProcessResult(
                ok=False,
                updated_items=tuple(rollback_items),
                next_slots=dict(snapshot.current_slots),
                next_opinion_material=snapshot.current_opinion_material,
                status_message="材料处理失败",
                alert_title="处理失败",
                alert_message=message,
            )

        if callable(progress_callback):
            progress_callback(88, "正在更新已关联材料", "步骤 3/5：写回确认状态")
            progress_callback(96, "正在更新已关联材料", "步骤 4/5：刷新补正内容文件下拉")
            progress_callback(100, "正在更新已关联材料", "步骤 5/5：完成")
        return _StagedImportProcessResult(
            ok=True,
            updated_items=tuple(updated_items),
            next_slots=next_slots,
            next_opinion_material=next_opinion_material,
            status_message="已同步当前材料关联状态。",
        )

    def _apply_staged_import_process_result(self, flow: str, result: _StagedImportProcessResult) -> None:
        if result.ok:
            setattr(self, f"_{flow}_document_slots", dict(result.next_slots))
            setattr(self, f"_{flow}_opinion_material", result.next_opinion_material)
        self._set_staged_import_items_for_flow(flow, list(result.updated_items))
        self._refresh_materials_table(flow)
        if flow in {"correction", "active_correction"}:
            self._refresh_correction_item_file_combos(flow)
        if str(result.status_message or "").strip():
            self._set_flow_status_message(flow, result.status_message)

    def _confirm_staged_imports_for_flow(self, flow: str, *, progress_callback=None, show_alert: bool = True) -> bool:
        result = self._process_staged_import_snapshot(
            flow,
            self._capture_staged_import_snapshot(flow),
            progress_callback=progress_callback,
        )
        self._apply_staged_import_process_result(flow, result)
        if show_alert and str(result.alert_message or "").strip():
            show_blocking_alert_modal(
                self,
                str(result.alert_title or "处理失败"),
                str(result.alert_message or "").strip(),
                primary_text="知道了",
                secondary_text="知道了",
            )
        return bool(result.ok)


    def _correction_file_name_options(self) -> list[str]:
        return [label for _code, label in SUPPORTED_DOCUMENT_SLOTS]

    def _make_correction_file_combo(self, selected: str = "") -> QComboBox:
        combo = QComboBox()
        for label in self._correction_file_name_options():
            combo.addItem(label)
        if selected:
            index = combo.findText(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo

    def _refresh_correction_item_file_combos(self, flow: str = "correction") -> None:
        table = self._correction_items_table_for_flow(flow)
        if table is None:
            return
        self._protect_combo_wheel_for_flow(flow, table=table)
        for row in range(table.rowCount()):
            current = ""
            widget = table.cellWidget(row, 0)
            if isinstance(widget, QComboBox):
                current = str(widget.currentText() or "").strip()
            elif table.item(row, 0) is not None:
                current = str(table.item(row, 0).text() or "").strip()
            combo = self._make_correction_file_combo(current)
            self._protect_combo_wheel_for_flow(flow, combo=combo)
            table.setCellWidget(row, 0, combo)

    def on_correction_add_item(self) -> None:
        table = self._correction_items_table_for_flow("correction")
        if table is None:
            return
        row = table.rowCount()
        table.insertRow(row)
        combo = self._make_correction_file_combo()
        self._protect_combo_wheel_for_flow("correction", combo=combo, table=table)
        table.setCellWidget(row, 0, combo)
        for col in range(1, 4):
            table.setItem(row, col, QTableWidgetItem(""))

    def on_active_correction_add_item(self) -> None:
        table = self._correction_items_table_for_flow("active_correction")
        if table is None:
            return
        row = table.rowCount()
        table.insertRow(row)
        combo = self._make_correction_file_combo()
        self._protect_combo_wheel_for_flow("active_correction", combo=combo, table=table)
        table.setCellWidget(row, 0, combo)
        for col in range(1, 4):
            table.setItem(row, col, QTableWidgetItem(""))

    def on_correction_remove_item(self) -> None:
        table = self._correction_items_table_for_flow("correction")
        if table is None:
            return
        for row in sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True):
            table.removeRow(row)

    def on_active_correction_remove_item(self) -> None:
        table = self._correction_items_table_for_flow("active_correction")
        if table is None:
            return
        for row in sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True):
            table.removeRow(row)

    def on_response_browse_notice(self) -> None:
        path = self._browse_response_correction_file("response_notice_edit", "选择通知书 ZIP/PDF", "通知书文件 (*.zip *.pdf)")
        if path:
            self._parse_notice_for_flow("response")

    def on_correction_browse_notice(self) -> None:
        path = self._browse_response_correction_file("correction_notice_edit", "选择通知书 ZIP/PDF", "通知书文件 (*.zip *.pdf)")
        if path:
            self._parse_notice_for_flow("correction")

    def on_response_browse_import_files(self) -> None:
        self._browse_import_files_for_flow("response")

    def on_correction_browse_import_files(self) -> None:
        self._browse_import_files_for_flow("correction")

    def on_active_response_browse_import_files(self) -> None:
        self._browse_import_files_for_flow("active_response")

    def on_active_correction_browse_import_files(self) -> None:
        self._browse_import_files_for_flow("active_correction")

    def on_response_browse_import_folder(self) -> None:
        self._browse_import_folder_for_flow("response")

    def on_correction_browse_import_folder(self) -> None:
        self._browse_import_folder_for_flow("correction")

    def on_active_response_browse_import_folder(self) -> None:
        self._browse_import_folder_for_flow("active_response")

    def on_active_correction_browse_import_folder(self) -> None:
        self._browse_import_folder_for_flow("active_correction")

    def on_response_import_paths_dropped(self, paths) -> None:
        self._ingest_import_paths_for_flow("response", paths)

    def on_correction_import_paths_dropped(self, paths) -> None:
        self._ingest_import_paths_for_flow("correction", paths)

    def on_active_response_import_paths_dropped(self, paths) -> None:
        self._ingest_import_paths_for_flow("active_response", paths)

    def on_active_correction_import_paths_dropped(self, paths) -> None:
        self._ingest_import_paths_for_flow("active_correction", paths)

    def on_response_clear_staged_files(self) -> None:
        self._clear_staged_files_for_flow("response")

    def on_correction_clear_staged_files(self) -> None:
        self._clear_staged_files_for_flow("correction")

    def on_active_response_clear_staged_files(self) -> None:
        self._clear_staged_files_for_flow("active_response")

    def on_active_correction_clear_staged_files(self) -> None:
        self._clear_staged_files_for_flow("active_correction")

    def _snapshot_has_material_work(self, snapshot: _StagedImportSnapshot) -> bool:
        if snapshot.items:
            return True
        if snapshot.current_slots:
            return True
        if snapshot.current_opinion_material:
            return True
        return False

    def _start_import_confirmation_for_flow(self, flow: str) -> None:
        snapshot = self._capture_staged_import_snapshot(flow)
        if not self._snapshot_has_material_work(snapshot):
            self._confirm_staged_imports_for_flow(flow, show_alert=False)
            return
        self._start_response_correction_worker(
            lambda progress_callback=None, item_flow=flow, item_snapshot=snapshot: self._process_staged_import_snapshot(
                item_flow,
                item_snapshot,
                progress_callback=progress_callback,
            ),
            flow=flow,
            package_label="材料关联更新",
            busy_message="正在更新已关联材料...",
            overlay_detail="请稍候，系统正在校验材料映射并同步正式关联状态。",
            failure_title="材料更新失败",
            success_handler=lambda result, item_flow=flow: self._handle_import_confirmation_success(item_flow, result),
            office_preflight=False,
        )

    def on_response_confirm_imports(self) -> None:
        self._start_import_confirmation_for_flow("response")

    def on_correction_confirm_imports(self) -> None:
        self._start_import_confirmation_for_flow("correction")

    def on_active_response_confirm_imports(self) -> None:
        self._start_import_confirmation_for_flow("active_response")

    def on_active_correction_confirm_imports(self) -> None:
        self._start_import_confirmation_for_flow("active_correction")

    def on_response_browse_output_dir(self) -> None:
        self._browse_output_dir_for_flow("response")

    def on_correction_browse_output_dir(self) -> None:
        self._browse_output_dir_for_flow("correction")

    def on_active_response_browse_output_dir(self) -> None:
        self._browse_output_dir_for_flow("active_response")

    def on_active_correction_browse_output_dir(self) -> None:
        self._browse_output_dir_for_flow("active_correction")

    def _set_patent_type_combo(self, flow: str, patent_type: str) -> None:
        combo = self._flow_widget(flow, "patent_type_combo")
        if combo is None:
            return
        for index in range(combo.count()):
            if str(combo.itemData(index) or "") == str(patent_type or ""):
                combo.setCurrentIndex(index)
                return

    def _current_patent_type(self, flow: str) -> str:
        combo = self._flow_widget(flow, "patent_type_combo")
        try:
            return str(combo.currentData() or "invention")
        except Exception:
            return "invention"

    def _parse_notice_for_flow(self, flow: str) -> None:
        path = _text(self._flow_widget(flow, "notice_edit"))
        parsed = parse_notice_source(path, mode_hint=flow)
        if parsed.errors:
            show_blocking_alert_modal(self, "解析失败", "\n".join(parsed.errors), primary_text="知道了", secondary_text="知道了")
        meta = parsed.meta
        if not self._validate_notice_kind_for_flow(flow, meta, clear_on_mismatch=True):
            return
        self._apply_parsed_notice_to_flow(
            flow,
            parsed,
            source_path=path,
            status_text=self._notice_status_text(parsed, infer_response_correction_notice_kind(meta)),
        )

    def _collect_notice_for_flow(self, flow: str) -> NoticeMeta:
        meta = getattr(self, f"_{flow}_notice_meta", None)
        if not isinstance(meta, NoticeMeta):
            meta = NoticeMeta()
        application_no_widget = self._flow_widget(flow, "application_no_edit")
        application_no = normalize_application_no(_text(application_no_widget))
        _set_text(application_no_widget, application_no)
        return replace(
            meta,
            application_no=application_no,
            invention_title=_text(self._flow_widget(flow, "title_edit")),
            applicant=_text(self._flow_widget(flow, "applicant_edit")),
            notice_name=_text(self._flow_widget(flow, "notice_name_edit")),
            issue_date=_text(self._flow_widget(flow, "issue_date_edit")),
            doc_serial=_text(self._flow_widget(flow, "doc_serial_edit")),
            patent_type=self._current_patent_type(flow),
        )

    def _collect_slots_for_flow(self, flow: str) -> dict[str, SlotInput]:
        slots: dict[str, SlotInput] = {}
        for code, item in self._slot_state_for_flow(flow).items():
            path = str(item.get("path", "") or "").strip()
            if path:
                slots[code] = SlotInput(path=path, preconverted=str(item.get("preconverted", "") or "").strip() == "1")
        return slots

    def _collect_correction_items(self, flow: str = "correction") -> tuple[CorrectionItem, ...]:
        table = self._correction_items_table_for_flow(flow)
        if table is None:
            return tuple()
        items: list[CorrectionItem] = []
        for row in range(table.rowCount()):
            widget = table.cellWidget(row, 0)
            if isinstance(widget, QComboBox):
                file_name = str(widget.currentText() or "").strip()
            else:
                cell = table.item(row, 0)
                file_name = str(cell.text() if cell is not None else "").strip()
            values = [file_name]
            for col in range(1, 4):
                cell = table.item(row, col)
                values.append(str(cell.text() if cell is not None else "").strip())
            if any(values):
                items.append(CorrectionItem(file_name=values[0], location=values[1], before=values[2], after=values[3]))
        return tuple(items)

    def _set_response_correction_busy(self, busy: bool, flow: str = "", message: str = "") -> None:
        try:
            self._response_correction_busy = bool(busy)
        except Exception:
            pass
        for item_flow in ("response", "correction", "active_response", "active_correction"):
            for widget_name in ("start_btn", "confirm_imports_btn"):
                target_btn = self._flow_widget(item_flow, widget_name)
                if target_btn is None:
                    continue
                try:
                    target_btn.setEnabled(not bool(busy))
                except Exception:
                    pass
        status = self._flow_widget(flow, "status_label") if flow else None
        if status is not None:
            try:
                if busy:
                    status.setText(message or "正在生成，请稍候…")
                elif message:
                    status.setText(message)
            except Exception:
                pass

    def _handle_import_confirmation_success(self, flow: str, result: _StagedImportProcessResult) -> None:
        self._apply_staged_import_process_result(flow, result)
        if not result.ok and str(result.alert_message or "").strip():
            show_blocking_alert_modal(
                self,
                str(result.alert_title or "材料更新失败"),
                str(result.alert_message or "").strip(),
                primary_text="知道了",
                secondary_text="知道了",
            )

    def _handle_response_correction_success(self, flow: str, package_label: str, result) -> None:
        path = str(getattr(result, "outer_zip_path", "") or "")
        choice = show_blocking_alert_modal(
            self,
            "生成完成",
            f"{package_label}已生成：\n{path}",
            primary_text="知道了",
            secondary_text="打开文件所在目录",
        )
        if choice == "secondary" and path:
            if not reveal_path_in_explorer(path):
                parent_dir = str(Path(path).parent)
                reveal_path_in_explorer(parent_dir)

    def _start_response_correction_worker(
        self,
        task_callable,
        *,
        flow: str,
        package_label: str,
        busy_message: str | None = None,
        overlay_detail: str | None = None,
        failure_title: str = "生成失败",
        success_handler=None,
        office_preflight: bool = True,
        health_retry_attempted: bool = False,
        office_gate_checked: bool = False,
    ) -> bool:
        if bool(getattr(self, "_response_correction_busy", False)):
            show_blocking_alert_modal(self, "仍在处理中", "上一次生成尚未结束，请稍候。", primary_text="知道了", secondary_text="知道了")
            return False
        worker_task_callable = task_callable
        if office_preflight:
            if not bool(office_gate_checked):
                try:
                    self._office_process_guard_killed = False
                except Exception:
                    pass
                try:
                    logger.info(
                        "[RESPONSE_CORRECTION_OFFICE_PREFLIGHT] start flow=%r package=%r",
                        flow,
                        package_label,
                    )
                except Exception:
                    pass
                if not ensure_office_processes_ready(self, context="response_correction_start"):
                    try:
                        logger.warning(
                            "[RESPONSE_CORRECTION_OFFICE_PREFLIGHT] blocked flow=%r package=%r",
                            flow,
                            package_label,
                        )
                    except Exception:
                        pass
                    return False
                try:
                    logger.info(
                        "[RESPONSE_CORRECTION_OFFICE_PREFLIGHT] ok flow=%r package=%r",
                        flow,
                        package_label,
                    )
                except Exception:
                    pass
            try:
                killed_before_check = bool(getattr(self, "_office_process_guard_killed", False))
            except Exception:
                killed_before_check = False
            worker_task_callable = _wrap_task_with_word_health(task_callable, killed_before_check=killed_before_check)
        busy_text = str(busy_message or f"正在生成{package_label}...").strip()
        detail_text = str(overlay_detail or "请稍候，系统正在整理文书并打包。").strip()
        self._set_response_correction_busy(True, flow, busy_text)
        try:
            self._progress_scope = "response_correction"
        except Exception:
            pass
        try:
            self.update_progress(0, busy_text, detail_text)
        except Exception:
            pass
        try:
            self._show_processing_overlay(busy_text, detail_text)
        except Exception:
            pass

        thread = QThread(self)
        worker = _ResponseCorrectionWorker(worker_task_callable)
        worker.moveToThread(thread)
        bridge = _ResponseCorrectionBridge(self)
        done = {"value": False}

        def _finish(message: str = "") -> None:
            if done["value"]:
                return
            done["value"] = True
            try:
                self._hide_processing_overlay()
            except Exception:
                pass
            if getattr(self, "_progress_scope", None) == "response_correction":
                try:
                    self._progress_scope = None
                except Exception:
                    pass
            self._set_response_correction_busy(False, flow, message)

        def _clear_refs() -> None:
            try:
                if getattr(self, "_response_correction_worker", None) is worker:
                    self._response_correction_worker = None
                if getattr(self, "_response_correction_worker_bridge", None) is bridge:
                    self._response_correction_worker_bridge = None
                if getattr(self, "_response_correction_worker_thread", None) is thread:
                    self._response_correction_worker_thread = None
            except Exception:
                pass

        def _on_progress(percent: int, primary: str, detail: str) -> None:
            try:
                self.update_progress(percent, primary, detail)
            except Exception:
                pass
            if str(detail or "").strip():
                self._set_flow_status_message(flow, str(detail or "").strip())

        def _on_success(result) -> None:
            path = str(getattr(result, "outer_zip_path", "") or "")
            _finish(str(getattr(result, "status_message", "") or "").strip() or f"处理完成：{path or package_label}")
            handler = success_handler
            if callable(handler):
                handler(result)
                return
            self._handle_response_correction_success(flow, package_label, result)

        def _on_failed(exc_obj, message: str) -> None:
            _finish(str(failure_title or "处理失败"))
            if isinstance(exc_obj, _ResponseCorrectionWordHealthError):
                health = exc_obj.health
                try:
                    logger.warning(
                        "[RESPONSE_CORRECTION_WORD_HEALTH] failed flow=%r package=%r retry=%r reason=%r pid=%r detail=%r",
                        flow,
                        package_label,
                        bool(health_retry_attempted),
                        getattr(health, "reason_code", ""),
                        getattr(health, "pid", None),
                        getattr(health, "technical_detail", ""),
                    )
                except Exception:
                    pass
                if _should_retry_response_word_health(health, retry_attempted=bool(health_retry_attempted)):
                    if ensure_office_processes_ready(self, context="word_health_failure"):
                        self._start_response_correction_worker(
                            task_callable,
                            flow=flow,
                            package_label=package_label,
                            busy_message=busy_message,
                            overlay_detail=overlay_detail,
                            failure_title=failure_title,
                            success_handler=success_handler,
                            office_preflight=office_preflight,
                            health_retry_attempted=True,
                            office_gate_checked=True,
                        )
                        return
                health_message = str(
                    getattr(health, "user_message", None)
                    or getattr(health, "error", None)
                    or message
                    or "Word 启动检查未通过，请关闭 Word/WPS 后重试。"
                )
                show_blocking_alert_modal(
                    self,
                    "Word 启动检查失败",
                    health_message,
                    primary_text="知道了",
                    secondary_text="知道了",
                )
                return
            if isinstance(exc_obj, WordComHijackedError):
                should_retry = ask_continue_cancel(
                    self,
                    "Word/WPS 占用异常",
                    str(message or ""),
                    continue_text="关闭占用进程/继续",
                    cancel_text="取消",
                    default_continue=True,
                    icon=None,
                )
                if should_retry:
                    self._start_response_correction_worker(
                        task_callable,
                        flow=flow,
                        package_label=package_label,
                        busy_message=busy_message,
                        overlay_detail=overlay_detail,
                        failure_title=failure_title,
                        success_handler=success_handler,
                        office_preflight=office_preflight,
                        health_retry_attempted=health_retry_attempted,
                    )
                return
            show_blocking_alert_modal(
                self,
                str(failure_title or "处理失败"),
                str(message or ""),
                primary_text="知道了",
                secondary_text="知道了",
            )

        bridge.success.connect(_on_success)
        bridge.failed.connect(_on_failed)
        bridge.progress.connect(_on_progress)
        worker.progress.connect(bridge.progress, Qt.QueuedConnection)
        worker.finished.connect(bridge.success, Qt.QueuedConnection)
        worker.failed.connect(bridge.failed, Qt.QueuedConnection)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(_clear_refs)
        thread.finished.connect(thread.deleteLater)
        self._response_correction_worker = worker
        self._response_correction_worker_bridge = bridge
        self._response_correction_worker_thread = thread
        thread.start()
        return True

    def _validate_notice_for_flow(self, flow: str, notice: NoticeMeta) -> bool:
        if not notice.application_no or not notice.invention_title or not notice.applicant:
            show_blocking_alert_modal(self, "信息不完整", "请至少填写申请号、发明名称和申请人。", primary_text="知道了", secondary_text="知道了")
            return False
        if self._flow_requires_notice(flow):
            if not notice.notice_name:
                show_blocking_alert_modal(self, "信息不完整", "请先导入通知书，或补充通知书名称。", primary_text="知道了", secondary_text="知道了")
                return False
            if not str(notice.issue_date or "").strip():
                show_blocking_alert_modal(self, "信息不完整", "请先补充通知书发文日后再生成。", primary_text="知道了", secondary_text="知道了")
                return False
            if not str(notice.doc_serial or "").strip():
                show_blocking_alert_modal(self, "信息不完整", "请先补充通知书发文序号后再生成。", primary_text="知道了", secondary_text="知道了")
                return False
            if not self._validate_notice_kind_for_flow(flow, notice, clear_on_mismatch=False):
                return False
        return True

    def _package_label_for_flow(self, flow: str) -> str:
        return {
            "response": "答复审查意见包",
            "correction": "答复补正包",
            "active_response": "主动答复包",
            "active_correction": "主动补正包",
        }.get(flow, "答复/补正包")

    def _start_response_flow(self, flow: str) -> None:
        output_dir = _text(self._flow_widget(flow, "output_dir_edit"))
        if not output_dir:
            show_blocking_alert_modal(self, "信息不完整", "请选择输出目录。", primary_text="知道了", secondary_text="知道了")
            return
        notice = self._collect_notice_for_flow(flow)
        if not self._validate_notice_for_flow(flow, notice):
            return
        opinion_input = self._confirmed_opinion_input_for_flow(flow)
        if not opinion_input:
            show_blocking_alert_modal(self, "材料未确认", "请先在材料导入区选择并确认“意见陈述书”。", primary_text="知道了", secondary_text="知道了")
            return
        request = ResponsePackageRequest(
            notice=notice,
            output_dir=output_dir,
            opinion_body=opinion_input,
            submission_scene=self._submission_scene_for_flow(flow),
            slots=self._collect_slots_for_flow(flow),
        )
        self._start_response_correction_worker(
            lambda progress_callback=None: build_response_package(request, progress_callback=progress_callback),
            flow=flow,
            package_label=self._package_label_for_flow(flow),
        )

    def _start_correction_flow(self, flow: str) -> None:
        output_dir = _text(self._flow_widget(flow, "output_dir_edit"))
        if not output_dir:
            show_blocking_alert_modal(self, "信息不完整", "请选择输出目录。", primary_text="知道了", secondary_text="知道了")
            return
        notice = self._collect_notice_for_flow(flow)
        if not self._validate_notice_for_flow(flow, notice):
            return
        request = CorrectionPackageRequest(
            notice=notice,
            output_dir=output_dir,
            submission_scene=self._submission_scene_for_flow(flow),
            correction_items=self._collect_correction_items(flow),
            slots=self._collect_slots_for_flow(flow),
        )
        self._start_response_correction_worker(
            lambda progress_callback=None: build_correction_package(request, progress_callback=progress_callback),
            flow=flow,
            package_label=self._package_label_for_flow(flow),
        )

    def on_response_start(self) -> None:
        self._start_response_flow("response")

    def on_active_response_start(self) -> None:
        self._start_response_flow("active_response")

    def on_correction_start(self) -> None:
        self._start_correction_flow("correction")

    def on_active_correction_start(self) -> None:
        self._start_correction_flow("active_correction")


__all__ = ["ResponseCorrectionMixin"]
