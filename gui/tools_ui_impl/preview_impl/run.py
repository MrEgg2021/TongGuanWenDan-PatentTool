from __future__ import annotations

import os

from PySide6.QtCore import QObject, QThread, Qt, Signal

from core.cnipa_preview.runtime import get_default_runtime_manager
from core.app_preferences import get_pdf_preview_mode
from gui.dialog_utils import show_blocking_alert_modal

from .worker import PreviewManifestWorker, PreviewRenderWorker, RuntimeWarmupWorker


class _PreviewRenderBridge(QObject):
    status = Signal(str)
    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)


class _PreviewWarmupBridge(QObject):
    status = Signal(str)
    ready = Signal()
    failed = Signal(str)


def _set_preview_busy(window, busy: bool) -> None:
    window._preview_in_progress = bool(busy)
    for name in ("preview_document_list", "preview_case_list_body", "preview_clear_button", "preview_zip_drop_zone", "preview_legacy_mode_button", "preview_full_mode_button", "preview_export_button"):
        widget = getattr(window, name, None)
        if widget is not None:
            widget.setEnabled(not busy)
    if hasattr(window, "preview_start_button"):
        window.preview_start_button.setEnabled(not busy)


def _set_warmup_summary(window, text: str) -> None:
    label = getattr(window, "preview_action_summary_label", None)
    if label is not None:
        label.setText(str(text))


def prewarm_full_preview(window) -> None:
    """Start the managed renderer without blocking full-preview page interaction."""

    if getattr(window, "_preview_warmup_thread", None) is not None:
        return
    if get_default_runtime_manager().is_running():
        return
    try:
        parent = window if isinstance(window, QObject) else None
        thread = QThread(parent)
        worker = RuntimeWarmupWorker()
        bridge = _PreviewWarmupBridge(parent)
        worker.moveToThread(thread)

        def on_status(text: str) -> None:
            if get_pdf_preview_mode() == "full" and not getattr(window, "_preview_documents", ()) and not getattr(window, "_preview_in_progress", False):
                _set_warmup_summary(window, text)

        def on_failed(message: str) -> None:
            on_status(f"全量预览官方渲染器未能后台启动：{message}")

        def clear_refs() -> None:
            if getattr(window, "_preview_warmup_worker", None) is worker:
                window._preview_warmup_worker = None
            if getattr(window, "_preview_warmup_bridge", None) is bridge:
                window._preview_warmup_bridge = None
            if getattr(window, "_preview_warmup_thread", None) is thread:
                window._preview_warmup_thread = None

        bridge.status.connect(on_status)
        bridge.failed.connect(on_failed)
        worker.status.connect(bridge.status, Qt.QueuedConnection)
        worker.ready.connect(bridge.ready, Qt.QueuedConnection)
        worker.failed.connect(bridge.failed, Qt.QueuedConnection)
        worker.finished.connect(thread.quit, Qt.DirectConnection)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(bridge.deleteLater)
        thread.finished.connect(clear_refs)
        thread.finished.connect(thread.deleteLater)
        window._preview_warmup_worker = worker
        window._preview_warmup_bridge = bridge
        window._preview_warmup_thread = thread
        thread.start()
    except Exception as exc:
        _set_warmup_summary(window, f"无法启动全量预览后台预热：{exc}")


def _finish_preview_render(window) -> None:
    try:
        window.update_progress(0, "", "")
    except Exception:
        pass
    try:
        window._hide_processing_overlay()
    except Exception:
        pass
    window._overlay_preview_zip_only = False
    window._preview_overlay_kind = ""
    _set_preview_busy(window, False)
    callback = getattr(window, "_apply_preview_export_state", None)
    if callable(callback):
        label = getattr(window, "preview_action_summary_label", None)
        message = label.text() if label is not None else ""
        callback()
        if label is not None and message:
            label.setText(message)
    if getattr(window, "_progress_scope", None) == "preview":
        window._progress_scope = None
    if hasattr(window, "preview_start_button"):
        window.preview_start_button.setEnabled(True)


def preview_single_case(window, zip_path: str, *, documents=None, selected_document_ids=None) -> None:
    if not zip_path or not os.path.isfile(zip_path):
        show_blocking_alert_modal(window, "错误", "未找到可预览的案卷 ZIP 文件。", primary_text="关闭", secondary_text="关闭")
        return
    if getattr(window, "_preview_in_progress", False):
        show_blocking_alert_modal(window, "提示", "正在生成 PDF 预览，请稍候...", primary_text="关闭", secondary_text="关闭")
        return

    window._preview_last_zip_path = str(zip_path)
    window._overlay_preview_zip_only = True
    window._preview_overlay_kind = "full"
    window._progress_scope = "preview"
    if hasattr(window, "_reset_cancel_state"):
        window._reset_cancel_state()
    else:
        window._cancel_requested = False
    if hasattr(window, "_show_processing_overlay"):
        window._show_processing_overlay("正在准备全量预览官方渲染器...", os.path.basename(zip_path))
    _set_preview_busy(window, True)

    try:
        parent = window if isinstance(window, QObject) else None
        thread = QThread(parent)
        worker = PreviewRenderWorker(
            zip_path,
            documents=tuple(documents) if documents is not None else None,
            selected_document_ids=tuple(selected_document_ids) if selected_document_ids is not None else None,
        )
        bridge = _PreviewRenderBridge(parent)
        worker.moveToThread(thread)

        def on_status(text: str) -> None:
            try:
                window.update_progress(3, str(text), "")
            except Exception:
                pass

        def on_progress(completed: int, total: int, name: str) -> None:
            if total <= 0:
                return
            percent = 15 + int(round(80 * completed / total))
            detail = f"正在渲染 {name}" if name else "正在整理预览 PDF..."
            try:
                window.update_progress(percent, "正在生成官方 PDF 预览...", detail)
            except Exception:
                pass

        def on_completed(result) -> None:
            if bool(getattr(result, "cancelled", False)):
                try:
                    window.update_progress(0, "已取消", "")
                except Exception:
                    pass
                return
            callback = getattr(window, "on_preview_render_completed", None)
            if callable(callback):
                try:
                    callback(result, zip_path)
                except (OSError, RuntimeError, ValueError) as exc:
                    on_failed(str(exc))

        def on_failed(message: str) -> None:
            show_blocking_alert_modal(
                window,
                "预览失败",
                f"全量预览官方渲染器未能完成预览：{message}",
                primary_text="关闭",
                secondary_text="关闭",
            )

        def clear_refs() -> None:
            if getattr(window, "_preview_render_worker", None) is worker:
                window._preview_render_worker = None
            if getattr(window, "_preview_render_bridge", None) is bridge:
                window._preview_render_bridge = None
            if getattr(window, "_preview_render_thread", None) is thread:
                window._preview_render_thread = None
            _finish_preview_render(window)

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
        window._preview_render_worker = worker
        window._preview_render_bridge = bridge
        window._preview_render_thread = thread
        thread.start()
    except Exception as exc:
        _finish_preview_render(window)
        show_blocking_alert_modal(window, "预览失败", f"无法启动后台预览任务：{exc}", primary_text="关闭", secondary_text="关闭")


def inspect_preview_case(window, zip_path: str) -> None:
    """Parse list.xml first, without launching the managed PDF renderer."""
    if not zip_path or not os.path.isfile(zip_path):
        show_blocking_alert_modal(window, "错误", "未找到可解析的案卷 ZIP 文件。", primary_text="关闭", secondary_text="关闭")
        return
    if getattr(window, "_preview_in_progress", False):
        show_blocking_alert_modal(window, "提示", "正在处理当前案卷，请稍候...", primary_text="关闭", secondary_text="关闭")
        return

    window._preview_last_zip_path = str(zip_path)
    window._overlay_preview_zip_only = True
    window._preview_overlay_kind = "manifest"
    window._progress_scope = "preview"
    if hasattr(window, "_reset_cancel_state"):
        window._reset_cancel_state()
    if hasattr(window, "_show_processing_overlay"):
        window._show_processing_overlay("正在解析案卷文件清单...", os.path.basename(zip_path))
    _set_preview_busy(window, True)

    try:
        parent = window if isinstance(window, QObject) else None
        thread = QThread(parent)
        worker = PreviewManifestWorker(zip_path)
        bridge = _PreviewRenderBridge(parent)
        worker.moveToThread(thread)

        def on_completed(result) -> None:
            callback = getattr(window, "on_preview_manifest_completed", None)
            if callable(callback):
                callback(result, zip_path)

        def on_failed(message: str) -> None:
            show_blocking_alert_modal(
                window,
                "解析失败",
                f"无法识别案卷文件：{message}",
                primary_text="关闭",
                secondary_text="关闭",
            )

        def clear_refs() -> None:
            if getattr(window, "_preview_manifest_worker", None) is worker:
                window._preview_manifest_worker = None
            if getattr(window, "_preview_manifest_bridge", None) is bridge:
                window._preview_manifest_bridge = None
            if getattr(window, "_preview_manifest_thread", None) is thread:
                window._preview_manifest_thread = None
            _finish_preview_render(window)

        bridge.completed.connect(on_completed)
        bridge.failed.connect(on_failed)
        worker.completed.connect(bridge.completed, Qt.QueuedConnection)
        worker.failed.connect(bridge.failed, Qt.QueuedConnection)
        worker.finished.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(bridge.deleteLater)
        thread.finished.connect(clear_refs)
        thread.finished.connect(thread.deleteLater)
        window._preview_manifest_worker = worker
        window._preview_manifest_bridge = bridge
        window._preview_manifest_thread = thread
        thread.start()
    except Exception as exc:
        _finish_preview_render(window)
        show_blocking_alert_modal(window, "解析失败", f"无法启动后台解析任务：{exc}", primary_text="关闭", secondary_text="关闭")


__all__ = ["inspect_preview_case", "preview_single_case", "prewarm_full_preview"]
