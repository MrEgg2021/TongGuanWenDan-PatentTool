from __future__ import annotations

import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from core.cnipa_preview.models import RendererState, RendererStateInfo
from gui.tools_ui_impl.preview_impl import service_status
from gui.tools_ui_impl.preview_impl import worker as workers


class PreviewServiceStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def manager(self, state=RendererState.RUNNING, error=""):
        return Mock(
            state_info=lambda: RendererStateInfo(state, runtime_id="C:/CNIPAClient"),
            configuration_error=lambda: error,
        )

    def test_status_distinguishes_recorded_directory_from_ready_process(self):
        cold, detail = service_status.full_preview_status(self.manager(RendererState.STOPPED))
        warm, _ = service_status.full_preview_status(self.manager())
        self.assertIn("未启动", cold)
        self.assertIn("C:/CNIPAClient", detail)
        self.assertIn("已就绪", warm)
        loading, _ = service_status.full_preview_status(self.manager(RendererState.STOPPED), warming=True)
        self.assertIn("检测中", loading)
        failed, detail = service_status.full_preview_status(self.manager(error="组件缺失"))
        self.assertIn("不可用", failed)
        self.assertEqual(detail, "组件缺失")

    def test_startup_prewarm_is_independent_of_preview_mode_and_started_once(self):
        window = QWidget()
        window.preview_full_connection_label = QLabel(window)
        window.settings_env_preview_status = QLabel(window)
        with (
            patch.object(service_status, "get_default_runtime_manager", return_value=self.manager()),
            patch.object(service_status, "prewarm_full_preview") as prewarm,
            patch.object(service_status.PreviewServiceMonitor, "refresh_legacy"),
        ):
            service_status.start_preview_services(window)
            service_status.start_preview_services(window)
            prewarm.assert_called_once_with(window)
            self.assertIn("已就绪", window.preview_full_connection_label.text())
            self.assertIn("已就绪", window.settings_env_preview_status.text())
            window._preview_service_monitor.stop()
        window.deleteLater()

    def test_legacy_probe_runs_off_ui_thread_and_updates_both_pages(self):
        window = QWidget()
        window.preview_legacy_connection_label = QLabel(window)
        window.settings_env_legacy_preview_status = QLabel(window)
        monitor = service_status.PreviewServiceMonitor(window)
        ui_thread = threading.get_ident()
        observed = []

        def ping(url):
            observed.append((threading.get_ident(), url))
            return False

        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        with (
            patch.object(service_status, "read_legacy_preview_port", return_value=8080),
            patch.object(service_status, "ping_legacy_preview_service", side_effect=ping),
        ):
            monitor.refresh_legacy()
            monitor.probe.finished.connect(loop.quit)
            timer.start(3000)
            loop.exec()
        monitor.stop()
        self.assertEqual(len(observed), 1)
        self.assertNotEqual(observed[0][0], ui_thread)
        self.assertIn("未连接", window.preview_legacy_connection_label.text())
        self.assertIn("8080", window.settings_env_legacy_preview_status.text())
        window.deleteLater()

    def test_warmup_cancellation_reaches_manager(self):
        worker = workers.RuntimeWarmupWorker()
        worker.request_cancel()
        manager = Mock(is_running=lambda: False)
        with patch.object(workers, "get_default_runtime_manager", return_value=manager):
            worker.run()
        self.assertTrue(manager.prewarm.call_args.kwargs["cancelled"]())

    def test_monitor_stop_cancels_and_joins_warmup(self):
        window = QWidget()
        window._preview_warmup_worker = Mock()
        window._preview_warmup_thread = Mock()
        monitor = service_status.PreviewServiceMonitor(window)
        monitor.stop()
        window._preview_warmup_worker.request_cancel.assert_called_once()
        window._preview_warmup_thread.quit.assert_called_once()
        window._preview_warmup_thread.wait.assert_called_once()
        window.deleteLater()

    def test_missing_client_failure_is_emitted_without_ready(self):
        worker = workers.RuntimeWarmupWorker()
        manager = Mock(is_running=lambda: False)
        manager.prewarm.side_effect = RuntimeError("未检测到客户端")
        events = SimpleNamespace(failed=[], ready=[])
        worker.failed.connect(events.failed.append)
        worker.ready.connect(lambda: events.ready.append(True))
        with patch.object(workers, "get_default_runtime_manager", return_value=manager):
            worker.run()
        self.assertEqual(events.failed, ["未检测到客户端"])
        self.assertFalse(events.ready)


if __name__ == "__main__":
    unittest.main()
