from __future__ import annotations

import os

from PySide6.QtCore import QObject, QThread, Qt, Signal

from core.conversion import ConversionCancelled
from core.logging_utils import logger
from core.office_process_safety import classify_office_processes
from gui.conversion_session import (
    begin_conversion_session,
    release_conversion_session,
    set_conversion_ui_enabled,
)
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal
from gui.office_process_guard import ensure_office_processes_ready
from gui.single_run import run_single_conversion
from gui.word_health_worker import WordHealthWorker


_HEALTH_RETRY_REASON_CODES = {
    "word_start_failed",
    "com_bind_failed",
    "com_bound_to_wps",
    "unexpected_word_pid",
    "word_pid_missing_unclaimed",
    "word_quit_failed",
    "word_exit_failed",
}


class _WordHealthBridge(QObject):
    progress = Signal(int, str, str)
    finished = Signal(object)


def handle_run_clicked(window) -> None:
    """处理转换按钮点击，支持单文件和批量模式。"""


    if not ask_continue_cancel(
        window,
        "提示",
        "本工具在转换前会检测当前是否有正在运行的 Word/WPS 进程，并会清空当前系统剪切板内容。"
        "\n\n程序在运行过程中，会频繁调用系统剪切板，在此期间请不要操作电脑。"
        "\n\n请确认您已保存并关闭所有 Word/WPS 文档，并已知晓上述剪切板说明。"
        "\n\n是否继续？",
        icon=None,
    ):
        return

    if not begin_conversion_session(window):
        return

    session_handed_to_worker = False
    try:
        set_conversion_ui_enabled(window, False)
        try:
            window._office_process_guard_killed = False
        except Exception:
            pass
        _log_office_process_classification()
        if not _ensure_office_processes_closed(window):
            return

        killed_before_check = _get_guard_killed_flag(window)
        _show_word_health_progress(window)
        session_handed_to_worker = True
        if not _start_word_health_check(window, killed_before_check=killed_before_check, retry_attempted=False):
            session_handed_to_worker = False
            show_blocking_alert_modal(
                window,
                "Word 启动检查失败",
                "无法开始 Word 环境检查，请重试；如仍失败，请重启程序后重试。",
                primary_text="关闭",
                secondary_text="关闭",
            )
            return
        return
    except ConversionCancelled:
        _mark_conversion_cancelled(window)
        return
    finally:
        if not session_handed_to_worker:
            release_conversion_session(window)


def _start_word_health_check(window, *, killed_before_check: bool, retry_attempted: bool = False) -> bool:
    try:
        parent = window if isinstance(window, QObject) else None
        thread = QThread(parent)
        worker = WordHealthWorker(killed_before_check=bool(killed_before_check))
        worker.moveToThread(thread)
        bridge = _WordHealthBridge(parent)

        def _on_progress(percent: int, primary: str, detail: str) -> None:
            try:
                window.update_progress(int(percent), str(primary), str(detail))
            except Exception:
                pass

        def _on_finished(result) -> None:
            _on_word_health_finished(window, result, retry_attempted=bool(retry_attempted))

        def _clear_refs() -> None:
            try:
                if getattr(window, "_word_health_worker", None) is worker:
                    window._word_health_worker = None
                if getattr(window, "_word_health_worker_bridge", None) is bridge:
                    window._word_health_worker_bridge = None
                if getattr(window, "_word_health_worker_thread", None) is thread:
                    window._word_health_worker_thread = None
            except Exception:
                pass

        bridge.progress.connect(_on_progress)
        bridge.finished.connect(_on_finished)
        worker.progress.connect(bridge.progress, Qt.QueuedConnection)
        worker.finished.connect(bridge.finished, Qt.QueuedConnection)
        worker.finished.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(bridge.deleteLater)
        thread.finished.connect(_clear_refs)
        thread.finished.connect(thread.deleteLater)
        window._word_health_worker = worker
        window._word_health_worker_bridge = bridge
        window._word_health_worker_thread = thread
        thread.start()
        return True
    except Exception as exc:
        try:
            logger.warning("[WORD_HEALTH] worker_start_failed detail=%r", exc)
        except Exception:
            pass
        return False


def _on_word_health_finished(window, health, *, retry_attempted: bool = False) -> None:
    if not bool(getattr(health, "ok", False)):
        if (not retry_attempted) and _should_retry_after_hidden_cleanup(health):
            _log_word_health_result("[WORD_HEALTH] first_failed", health, level="warning")
            if ensure_office_processes_ready(window, context="word_health_failure"):
                killed_before_check = _get_guard_killed_flag(window)
                _show_word_health_progress(window)
                if _start_word_health_check(
                    window,
                    killed_before_check=killed_before_check,
                    retry_attempted=True,
                ):
                    return
                try:
                    logger.warning("[WORD_HEALTH] retry_worker_start_failed")
                except Exception:
                    pass
        _log_word_health_result("[WORD_HEALTH] failed", health, level="warning")
        msg = str(
            getattr(health, "user_message", None)
            or getattr(health, "error", None)
            or "Word 启动检查未通过，请关闭 Word/WPS 后重试。"
        )
        show_blocking_alert_modal(
            window,
            "Word 启动检查失败",
            msg,
            primary_text="关闭",
            secondary_text="关闭",
        )
        release_conversion_session(window)
        return

    if bool(retry_attempted):
        _log_word_health_result("[WORD_HEALTH] recovered_after_office_gate", health)
    else:
        _log_word_health_result("[WORD_HEALTH] ok", health)

    try:
        _continue_conversion_after_word_health(window)
    except ConversionCancelled:
        _mark_conversion_cancelled(window)
    finally:
        release_conversion_session(window)


def _continue_conversion_after_word_health(window) -> None:
    window._clear_system_clipboard_safely()

    try:
        if hasattr(window, "_reset_cancel_state"):
            window._reset_cancel_state()
        else:
            window._cancel_requested = False
    except Exception:
        pass

    if window._processing_mode == "single":
        input_path = window.path_edit.text().strip()
        if not input_path:
            show_blocking_alert_modal(window, "提示", "请先选择一个 DOC/DOCX 文件。", primary_text="关闭", secondary_text="关闭")
            return
        if not os.path.isfile(input_path):
            show_blocking_alert_modal(window, "错误", "指定的 DOC/DOCX 文件不存在。", primary_text="关闭", secondary_text="关闭")
            return
        if not input_path.lower().endswith((".doc", ".docx")):
            show_blocking_alert_modal(window, "错误", "当前仅支持 DOC/DOCX 格式文件。", primary_text="关闭", secondary_text="关闭")
            return

        try:
            enabled_sections = window.get_enabled_sections()
        except Exception:
            enabled_sections = {"request_form": True}
        if not enabled_sections.get("request_form", True):
            try:
                window._show_request_form_skip_tip("single")
            except Exception:
                pass

        run_single_conversion(window, input_path)
        return

    try:
        enabled_sections = window.get_enabled_sections()
    except Exception:
        enabled_sections = {"request_form": True}
    if not enabled_sections.get("request_form", True):
        try:
            window._show_request_form_skip_tip("batch")
        except Exception:
            pass
    window.run_batch_conversion()


def _ensure_office_processes_closed(window) -> bool:
    return ensure_office_processes_ready(window, context="conversion_start")


def _get_guard_killed_flag(window) -> bool:
    try:
        return bool(getattr(window, "_office_process_guard_killed", False))
    except Exception:
        return False


def _show_word_health_progress(window) -> None:
    primary = "正在后台检查 Word 环境"
    detail = "正在启动并验证 Microsoft Word，请稍候..."
    try:
        window._progress_scope = "word_health"
    except Exception:
        pass
    try:
        window.update_progress(0, primary, detail)
    except Exception:
        pass
    try:
        window._show_processing_overlay(primary, detail)
    except Exception:
        pass


def _mark_conversion_cancelled(window) -> None:
    try:
        lbl_status = getattr(window, "status_label", None)
        if lbl_status is not None:
            lbl_status.setText("状态：已取消")
    except Exception:
        pass


def _should_retry_after_hidden_cleanup(health) -> bool:
    try:
        if bool(getattr(health, "killed_before_check", False)):
            return False
    except Exception:
        return False
    try:
        reason_code = str(getattr(health, "reason_code", "") or "")
    except Exception:
        reason_code = ""
    return reason_code in _HEALTH_RETRY_REASON_CODES


def _process_labels(items) -> list[str]:
    labels: list[str] = []
    for item in list(items or []):
        try:
            labels.append(f"{item.name}:{item.pid}:visible={item.visible}:owned={item.owned}")
        except Exception:
            labels.append(repr(item))
    return labels


def _log_office_process_classification() -> None:
    try:
        classified = classify_office_processes()
        logger.info(
            "[OFFICE_PROCESS_CLASSIFICATION] visible=%d %r hidden=%d %r owned=%d %r ignored=%d %r",
            len(classified.visible_document_sessions),
            _process_labels(classified.visible_document_sessions),
            len(classified.hidden_background_document_hosts),
            _process_labels(classified.hidden_background_document_hosts),
            len(classified.owned_residuals),
            _process_labels(classified.owned_residuals),
            len(classified.ignored_background_services),
            _process_labels(classified.ignored_background_services),
        )
    except Exception as exc:
        try:
            logger.warning("[OFFICE_PROCESS_CLASSIFICATION] failed detail=%r", exc)
        except Exception:
            pass


def _log_word_health_result(prefix: str, health, *, level: str = "info") -> None:
    try:
        log_func = logger.warning if level == "warning" else logger.info
        log_func(
            f"{prefix} ok=%r reason=%r pid=%r progid=%r user=%r detail=%r",
            getattr(health, "ok", None),
            getattr(health, "reason_code", ""),
            getattr(health, "pid", None),
            getattr(health, "binding_progid", None),
            getattr(health, "user_message", ""),
            getattr(health, "technical_detail", ""),
        )
    except Exception:
        pass
