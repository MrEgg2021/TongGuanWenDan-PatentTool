from __future__ import annotations

from PySide6.QtCore import QObject, QThread, QTimer, Slot
from PySide6.QtWidgets import QApplication

from core.cnipa_preview.models import RendererState
from core.cnipa_preview.runtime import get_default_runtime_manager
from core.user_messages import user_error_text

from .legacy import build_legacy_preview_base_url, ping_legacy_preview_service, read_legacy_preview_port
from .run import prewarm_full_preview


def full_preview_status(manager, *, warming=False) -> tuple[str, str]:
    info = manager.state_info()
    error = manager.configuration_error()
    if error:
        return "不可用，请检查设置", user_error_text(error)
    if info.state == RendererState.RUNNING:
        text = "已就绪，可复用"
    elif info.state == RendererState.STARTING:
        text = "组件加载中…"
    elif warming:
        text = "客户端检测中…"
    else:
        text = {
            RendererState.STOPPED: "未启动（预览时加载）",
            RendererState.STOPPING: "正在停止",
            RendererState.FAILED: "加载失败，请重新检测",
        }[info.state]
    path = info.runtime_id
    if not path and not warming:
        text = "未检测到客户端"
    detail = f"{text}\n客户端目录（只读）：{path}" if path else text
    return text, detail


class _LegacyProbe(QThread):
    def __init__(self, parent, port):
        super().__init__(parent)
        self.port = port
        self.connected = False

    def run(self):
        self.connected = ping_legacy_preview_service(build_legacy_preview_base_url(self.port))


class PreviewServiceMonitor(QObject):
    """Update both pages without performing service I/O on the UI thread."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.probe = None
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh_full)
        self.legacy_timer = QTimer(self)
        self.legacy_timer.setInterval(5000)
        self.legacy_timer.timeout.connect(self.refresh_legacy)

    def start(self):
        self.refresh_legacy()
        prewarm_full_preview(self.window)
        self.refresh_full()
        self.timer.start()
        self.legacy_timer.start()

    @Slot()
    def refresh_full(self):
        text, detail = full_preview_status(
            get_default_runtime_manager(),
            warming=getattr(self.window, "_preview_warmup_thread", None) is not None,
        )
        self._display("preview_full_connection_label", f"全量预览：{text}", detail)
        self._display("settings_env_preview_status", f"官方渲染组件：{text}", detail)

    def _display(self, name, text, detail):
        label = getattr(self.window, name, None)
        if label is not None:
            label.setText(text)
            label.setToolTip(detail)

    @Slot()
    def refresh_legacy(self):
        if self.probe is not None:
            return
        self.probe = _LegacyProbe(self, read_legacy_preview_port())
        self.probe.finished.connect(self._legacy_finished)
        self.probe.start()

    @Slot()
    def _legacy_finished(self):
        probe = self.probe
        text = "已连接" if probe.connected else "未连接"
        detail = f"{text}（127.0.0.1:{probe.port}）"
        self._display("preview_legacy_connection_label", f"轻量预览：{text}", detail)
        self._display("settings_env_legacy_preview_status", detail, detail)
        self.probe = None
        probe.deleteLater()

    @Slot()
    def stop(self):
        self.timer.stop()
        self.legacy_timer.stop()
        if self.probe is not None:
            self.probe.wait()
        worker = getattr(self.window, "_preview_warmup_worker", None)
        thread = getattr(self.window, "_preview_warmup_thread", None)
        if worker is not None:
            worker.request_cancel()
        if thread is not None:
            thread.quit()
            thread.wait()


def start_preview_services(window):
    if getattr(window, "_preview_service_monitor", None) is not None:
        return
    monitor = PreviewServiceMonitor(window)
    window._preview_service_monitor = monitor
    QApplication.instance().aboutToQuit.connect(monitor.stop)
    monitor.start()
