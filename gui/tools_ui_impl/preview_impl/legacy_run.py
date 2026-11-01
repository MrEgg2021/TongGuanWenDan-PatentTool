from __future__ import annotations

import os
import webbrowser

from PySide6.QtCore import QObject, QThread, Qt, Signal

from gui.dialog_utils import show_blocking_alert_modal

from .legacy import build_legacy_preview_base_url, ping_legacy_preview_service, prompt_legacy_preview_port
from .worker import LegacyPreviewWorker


class _LegacyPreviewBridge(QObject):
    status = Signal(str)
    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)


def preview_single_case_legacy(window, zip_path: str) -> None:
    if not zip_path or not os.path.isfile(zip_path):
        show_blocking_alert_modal(window, "错误", "未找到可预览的案卷 ZIP 文件。", primary_text="关闭", secondary_text="关闭")
        return
    if getattr(window, "_preview_in_progress", False):
        show_blocking_alert_modal(window, "提示", "正在生成 PDF 预览，请稍候……", primary_text="关闭", secondary_text="关闭")
        return

    base_url = build_legacy_preview_base_url()
    if not ping_legacy_preview_service(base_url):
        choice = show_blocking_alert_modal(
            window,
            "轻量预览服务未启动",
            "未检测到官方轻量预览服务。请确认预览插件已启动；如果实际端口不是 8080，可修改端口后重试。",
            primary_text="修改端口",
            secondary_text="取消",
        )
        if choice != "primary":
            return
        port = prompt_legacy_preview_port(window)
        if port is None:
            return
        base_url = build_legacy_preview_base_url(port)

    window._preview_last_zip_path = str(zip_path)
    window._preview_in_progress = True
    window._overlay_preview_zip_only = True
    window._preview_overlay_kind = "legacy"
    window._progress_scope = "preview"
    if hasattr(window, "_reset_cancel_state"):
        window._reset_cancel_state()
    if hasattr(window, "_show_processing_overlay"):
        window._show_processing_overlay("正在生成轻量 PDF 预览……", os.path.basename(zip_path))
    if hasattr(window, "preview_start_button"):
        window.preview_start_button.setEnabled(False)

    parent = window if isinstance(window, QObject) else None
    thread = QThread(parent)
    worker = LegacyPreviewWorker(zip_path, base_url)
    bridge = _LegacyPreviewBridge(parent)
    worker.moveToThread(thread)

    def on_status(text: str) -> None:
        if hasattr(window, "update_progress"):
            window.update_progress(3, text, "")

    def on_progress(completed: int, total: int, name: str) -> None:
        percent = int(round(100 * completed / max(total, 1)))
        if hasattr(window, "update_progress"):
            window.update_progress(percent, "正在生成轻量 PDF 预览……", name)

    def on_completed(result) -> None:
        callback = getattr(window, "on_preview_legacy_completed", None)
        if callable(callback):
            callback(result, zip_path)
        try:
            webbrowser.open(str(result.preview_url))
        except webbrowser.Error as exc:
            show_blocking_alert_modal(window, "打开失败", f"预览已生成，但无法打开浏览器：{exc}", primary_text="关闭", secondary_text="关闭")

    def on_failed(message: str) -> None:
        if message != "轻量预览已取消。":
            show_blocking_alert_modal(window, "轻量预览失败", message, primary_text="关闭", secondary_text="关闭")

    def clear_refs() -> None:
        window._preview_in_progress = False
        window._overlay_preview_zip_only = False
        window._preview_overlay_kind = ""
        if getattr(window, "_progress_scope", None) == "preview":
            window._progress_scope = None
        if hasattr(window, "update_progress"):
            window.update_progress(0, "", "")
        if hasattr(window, "_hide_processing_overlay"):
            window._hide_processing_overlay()
        if hasattr(window, "preview_start_button"):
            window.preview_start_button.setEnabled(True)
        window._legacy_preview_worker = None
        window._legacy_preview_bridge = None
        window._legacy_preview_thread = None

    bridge.status.connect(on_status)
    bridge.progress.connect(on_progress)
    bridge.completed.connect(on_completed)
    bridge.failed.connect(on_failed)
    worker.status.connect(bridge.status, Qt.QueuedConnection)
    worker.progress.connect(bridge.progress, Qt.QueuedConnection)
    worker.completed.connect(bridge.completed, Qt.QueuedConnection)
    worker.failed.connect(bridge.failed, Qt.QueuedConnection)
    worker.finished.connect(thread.quit)
    thread.started.connect(worker.run)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(bridge.deleteLater)
    thread.finished.connect(clear_refs)
    thread.finished.connect(thread.deleteLater)
    window._legacy_preview_worker = worker
    window._legacy_preview_bridge = bridge
    window._legacy_preview_thread = thread
    thread.start()


__all__ = ["preview_single_case_legacy"]
