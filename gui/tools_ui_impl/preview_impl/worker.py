from __future__ import annotations

from threading import Event
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from core.cnipa_preview.models import PreviewDocument, RendererState
from core.cnipa_preview.package import inspect_preview_package
from core.cnipa_preview.renderer import CnipaXmlRenderer
from core.cnipa_preview.runtime import get_default_runtime_manager
from core.cnipa_preview.form_renderer import FormRenderCancelled
from core.cnipa_preview.models import PreviewRenderResult

from .legacy import render_legacy_preview


class PreviewManifestWorker(QObject):
    """Reads a selected ZIP's list.xml without starting the PDF renderer."""

    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, zip_path: str) -> None:
        super().__init__()
        self._zip_path = str(zip_path)

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(inspect_preview_package(self._zip_path))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class PreviewRenderWorker(QObject):
    """Runs the managed full-preview renderer outside the Qt GUI thread."""

    status = Signal(str)
    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        zip_path: str,
        *,
        documents: tuple[PreviewDocument, ...] | None = None,
        selected_document_ids: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__()
        self._zip_path = str(zip_path)
        self._documents = tuple(documents) if documents is not None else None
        self._selected_document_ids = tuple(selected_document_ids) if selected_document_ids is not None else None
        self._cancel_requested = Event()

    def request_cancel(self) -> None:
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        try:
            manager = get_default_runtime_manager()
            state_info = getattr(manager, "state_info", lambda: None)()
            state = getattr(state_info, "state", None)
            if state is RendererState.STARTING:
                self.status.emit("全量预览官方渲染器正在后台启动，正在等待其就绪……")
            elif manager.is_running():
                self.status.emit("正在连接已启动的全量预览官方渲染器……")
            else:
                self.status.emit("正在加载客户端渲染组件，首次加载请稍候……")

            def report_startup_wait(elapsed_seconds: float) -> None:
                self.status.emit(f"正在初始化文书渲染和字体，已等待约 {int(elapsed_seconds)} 秒……")

            renderer = CnipaXmlRenderer(manager)
            source_before = Path(self._zip_path).stat()
            result = renderer.render_case(
                self._zip_path,
                documents=self._documents,
                selected_document_ids=self._selected_document_ids,
                progress=lambda completed, total, name: self.progress.emit(completed, total, name),
                cancelled=self._cancel_requested.is_set,
                startup_wait=report_startup_wait,
            )
            source_after = Path(self._zip_path).stat()
            if (source_before.st_size, source_before.st_mtime_ns) != (source_after.st_size, source_after.st_mtime_ns):
                raise RuntimeError("案卷 ZIP 在预览过程中发生变化，请重新选择案件后再生成。")
            self.completed.emit(result)
        except FormRenderCancelled:
            self.completed.emit(PreviewRenderResult(cancelled=True))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class LegacyPreviewWorker(QObject):
    status = Signal(str)
    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, zip_path: str, base_url: str) -> None:
        super().__init__()
        self._zip_path = str(zip_path)
        self._base_url = str(base_url)
        self._cancel_requested = Event()

    def request_cancel(self) -> None:
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        try:
            self.status.emit("正在调用轻量预览服务……")
            result = render_legacy_preview(
                self._zip_path,
                self._base_url,
                progress=lambda completed, total, name: self.progress.emit(completed, total, name),
                cancelled=self._cancel_requested.is_set,
            )
            self.completed.emit(result)
        except InterruptedError:
            self.failed.emit("轻量预览已取消。")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class RuntimeWarmupWorker(QObject):
    status = Signal(str)
    ready = Signal()
    failed = Signal(str)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self._cancel_requested = Event()

    def request_cancel(self):
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        try:
            manager = get_default_runtime_manager()
            if manager.is_running():
                self.status.emit("全量预览官方渲染器已就绪，本次程序内可直接生成 PDF。")
            else:
                self.status.emit("正在后台检测客户端并初始化文书渲染和字体……")

                def report_wait(elapsed_seconds: float) -> None:
                    self.status.emit(f"正在后台初始化文书渲染和字体，已等待约 {int(elapsed_seconds)} 秒……")

                manager.prewarm(startup_wait_callback=report_wait, cancelled=self._cancel_requested.is_set)
                self.status.emit("全量预览官方渲染器已就绪，本次程序内可直接生成 PDF。")
            self.ready.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


__all__ = ["LegacyPreviewWorker", "PreviewManifestWorker", "PreviewRenderWorker", "RuntimeWarmupWorker"]
