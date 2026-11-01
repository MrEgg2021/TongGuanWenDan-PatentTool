from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QMenu

from core.word_startup_health import check_word_pdf_export_health
from gui.dialog_utils import show_blocking_alert_modal
from gui.office_process_guard import ensure_office_processes_ready
from gui.word_health_worker import WordHealthWorker

from gui.main_window.mixins.settings_env_impl.ops_impl.banner_ops import update_env_banner_checking
from gui.main_window.mixins.settings_env_impl.ops_impl.env_check_ops import run_env_check, update_pdf_export_check_result
from gui.main_window.mixins.settings_env_impl.ops_impl.runtime_probe import maybe_alert_runtime_issues
from gui.main_window.mixins.settings_env_impl.ops_impl.word_env_ops import build_hijack_help_text, maybe_alert_env_issues


class _PdfExportCheckBridge(QObject):
    finished = Signal(object)


def _set_env_refresh_enabled(window, enabled: bool) -> None:
    button = getattr(window, "settings_env_refresh_button", None)
    if button is not None:
        button.setEnabled(bool(enabled))


def _start_pdf_export_check(window, base_result: dict) -> None:
    running_thread = getattr(window, "_settings_pdf_export_thread", None)
    if running_thread is not None and running_thread.isRunning():
        return

    if (
        not bool(base_result.get("word_ok", False))
        or bool(base_result.get("hijacked", False))
        or bool(base_result.get("word_too_low", False))
    ):
        update_pdf_export_check_result(
            window,
            pdf_export_ok=None,
            pdf_export_error="Word 基础环境检查未通过",
            status_text="检测受阻（请关闭 Word/WPS 后刷新）",
            base_result=base_result,
        )
        return

    window._office_process_guard_killed = False
    if not ensure_office_processes_ready(window, context="settings_pdf_export_check"):
        update_pdf_export_check_result(
            window,
            pdf_export_ok=None,
            pdf_export_error="Word/WPS 进程处理已取消或未完成",
            status_text="检测受阻（请关闭 Word/WPS 后刷新）",
            base_result=base_result,
        )
        return

    status = getattr(window, "settings_env_pdf_export_status", None)
    if status is not None:
        status.setText("检测中...")
        status.setToolTip("正在执行临时 PDF 导出测试...")
    update_env_banner_checking(window)
    _set_env_refresh_enabled(window, False)

    parent = window if isinstance(window, QObject) else None
    thread = QThread(parent)
    worker = WordHealthWorker(
        health_check=check_word_pdf_export_health,
        killed_before_check=bool(window._office_process_guard_killed),
    )
    worker.moveToThread(thread)
    bridge = _PdfExportCheckBridge(parent)

    def _on_finished(health) -> None:
        if not bool(getattr(health, "ok", False)) or getattr(health, "pdf_export_ok", None) is None:
            update_pdf_export_check_result(
                window,
                pdf_export_ok=None,
                pdf_export_error=str(
                    getattr(health, "user_message", None)
                    or getattr(health, "error", None)
                    or "Word PDF 导出检测未完成"
                ),
                status_text="检测受阻（请关闭 Word/WPS 后刷新）",
                base_result=base_result,
            )
        elif bool(health.pdf_export_ok):
            update_pdf_export_check_result(
                window,
                pdf_export_ok=True,
                pdf_export_error="",
                status_text="正常",
                base_result=base_result,
            )
        else:
            update_pdf_export_check_result(
                window,
                pdf_export_ok=False,
                pdf_export_error=str(getattr(health, "pdf_export_error", "") or "Word PDF 导出不可用"),
                status_text="不可用（请修复或重装完整 Microsoft Office）",
                base_result=base_result,
            )

    def _on_thread_finished() -> None:
        _set_env_refresh_enabled(window, True)
        window._settings_pdf_export_worker = None
        window._settings_pdf_export_bridge = None
        window._settings_pdf_export_thread = None

    thread.started.connect(worker.run)
    worker.finished.connect(bridge.finished.emit)
    bridge.finished.connect(_on_finished)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(_on_thread_finished)
    thread.finished.connect(thread.deleteLater)

    window._settings_pdf_export_worker = worker
    window._settings_pdf_export_bridge = bridge
    window._settings_pdf_export_thread = thread
    thread.start()


def on_env_status_clicked(window) -> None:
    btn = None
    try:
        shell = getattr(window, "_modern_shell", None)
        if shell is not None:
            btn = getattr(shell, "env_status", None)
    except Exception:
        btn = None
    if btn is None:
        return

    menu = None
    try:
        menu = QMenu(btn)
        act_retry = menu.addAction("重新检测")
        try:
            act_retry.triggered.connect(window._on_env_banner_retry)
        except Exception:
            pass
    except Exception:
        menu = None
    if menu is None:
        return

    try:
        if bool(getattr(window, "_env_last_show_help", False)):
            act_help = menu.addAction("查看处理建议")
            try:
                act_help.triggered.connect(window._on_settings_env_wps_help)
            except Exception:
                pass
    except Exception:
        pass
    try:
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
    except Exception:
        pos = None
    try:
        if pos is not None:
            menu.exec(pos)
        else:
            menu.exec()
    except Exception:
        pass


def on_settings_env_refresh(window) -> None:
    try:
        result = run_env_check(window, update_ui=True)
        if isinstance(result, dict):
            _start_pdf_export_check(window, result)
    except Exception:
        _set_env_refresh_enabled(window, True)


def on_env_banner_retry(window) -> None:
    try:
        run_env_check(window, update_ui=True)
    except Exception:
        pass


def on_settings_env_wps_help(window) -> None:
    hijacked = False
    try:
        wps_status = getattr(window, "settings_env_wps_status", None)
        hijacked = bool(wps_status and str(wps_status.text()).strip() == "被挟持")
    except Exception:
        hijacked = False

    try:
        runtime_ok = bool(getattr(window, "_env_runtime_ok", True))
    except Exception:
        runtime_ok = True

    if getattr(window, "_env_pdf_export_ok", None) is False:
        show_blocking_alert_modal(
            window,
            "Word PDF 导出不可用",
            "当前 Microsoft Office 无法导出 PDF。请修复或重新安装完整的 Microsoft Office，然后在环境检测中重新点击“刷新检测”。",
            primary_text="关闭",
            secondary_text="关闭",
        )
        return

    if (not hijacked) and (not runtime_ok):
        rhint = ""
        try:
            rhint = str(getattr(window, "_env_runtime_hint_text", "") or "")
        except Exception:
            rhint = ""
        try:
            show_blocking_alert_modal(window, "系统运行环境异常", rhint or "请升级系统并安装运行库后重试。", primary_text="关闭", secondary_text="关闭")
        except Exception:
            pass
        return

    hint = ""
    try:
        hint = str(getattr(window, "_env_wps_hint_text", "") or "")
    except Exception:
        hint = ""
    if not hint.strip():
        try:
            hint = build_hijack_help_text(hijacked=hijacked, detail="")
        except Exception:
            hint = ""

    title = "处理建议"
    if hijacked:
        title = "检测到 Word 后台端口被挟持"
    try:
        show_blocking_alert_modal(window, title, hint, primary_text="关闭", secondary_text="关闭")
    except Exception:
        pass


def auto_env_check_and_alert_if_needed(window) -> None:
    try:
        result = run_env_check(window, update_ui=True)
    except Exception:
        result = None
    if not isinstance(result, dict):
        return

    word_ok = bool(result.get("word_ok", False))
    hijacked = bool(result.get("hijacked", False))
    word_too_low = bool(result.get("word_too_low", False))
    word_error = str(result.get("word_error", "") or "")

    try:
        maybe_alert_env_issues(
            window,
            word_ok=word_ok,
            hijacked=hijacked,
            word_too_low=word_too_low,
            word_error=word_error,
        )
    except Exception:
        pass

    try:
        maybe_alert_runtime_issues(
            window,
            runtime_ok=bool(result.get("runtime_ok", True)),
            hint=str(result.get("runtime_hint", "") or ""),
        )
    except Exception:
        pass
