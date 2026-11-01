from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from PySide6.QtCore import QEventLoop, QTimer

from core.cnipa_preview.installed_client import CLIENT_MISSING
from gui.main_window.mixins.preview_mixin import PreviewMixin
from gui.tools_ui_impl.preview_impl import legacy, main
from gui.tools_ui_impl.preview_impl.runtime_setup import ClientDetectionWorker, RuntimeSetupDialog
from gui.ui_layout_impl.settings_page import build_settings_page


class _PreviewModeWindow(PreviewMixin):
    def __init__(self) -> None:
        self.preview_legacy_mode_button = QPushButton()
        self.preview_legacy_mode_button.setCheckable(True)
        self.applied = 0

    def _apply_preview_mode_ui(self) -> None:
        self.applied += 1


class _AnyCallbackWindow:
    def __getattr__(self, _name: str):
        return lambda *_args, **_kwargs: None


class _Response:
    def __init__(self, *, text: str = "", content: bytes = b"") -> None:
        self.text = text
        self.content = content
        self.cookies = {}
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


class PreviewDualModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_dispatches_legacy_without_touching_managed_runtime(self) -> None:
        with (
            patch.object(main, "get_pdf_preview_mode", return_value="legacy"),
            patch.object(main, "preview_single_case_legacy") as legacy_preview,
            patch.object(main, "get_default_runtime_manager") as active_runtime,
            patch.object(main, "preview_single_case_full") as full_preview,
        ):
            main.preview_single_case(object(), "case.zip")

        legacy_preview.assert_called_once()
        active_runtime.assert_not_called()
        full_preview.assert_not_called()

    def test_full_dispatch_blocks_when_setup_is_cancelled(self) -> None:
        with (
            patch.object(main, "get_default_runtime_manager", return_value=Mock(configured_path=lambda: None, configuration_error=lambda: "")),
            patch.object(main, "configure_installed_client", return_value=False) as configure,
            patch.object(main, "preview_single_case_full") as full_preview,
        ):
            main.preview_single_case(object(), "case.zip", mode="full")

        configure.assert_called_once()
        full_preview.assert_not_called()

    def test_full_dispatch_uses_remembered_client_without_discovery(self) -> None:
        active = Mock(configured_path=lambda: "D:/CNIPAClient", configuration_error=lambda: "")
        with (
            patch.object(main, "get_default_runtime_manager", return_value=active),
            patch.object(main, "configure_installed_client") as configure,
            patch.object(main, "preview_single_case_full") as full_preview,
        ):
            main.preview_single_case(object(), "case.zip", mode="full")

        configure.assert_not_called()
        full_preview.assert_called_once()

    def test_cancelled_first_full_mode_selection_restores_legacy_without_saving_full(self) -> None:
        window = _PreviewModeWindow()
        with (
            patch("gui.main_window.mixins.preview_mixin.get_default_runtime_manager", return_value=Mock(configured_path=lambda: None)),
            patch("gui.main_window.mixins.preview_mixin.configure_installed_client", return_value=False),
            patch("gui.main_window.mixins.preview_mixin.set_pdf_preview_mode") as set_mode,
        ):
            window.on_preview_mode_changed("full")

        set_mode.assert_called_once_with("legacy")
        self.assertTrue(window.preview_legacy_mode_button.isChecked())
        self.assertEqual(1, window.applied)

    def test_legacy_protocol_fetches_only_four_fixed_documents(self) -> None:
        pdf = fitz.open()
        pdf.new_page()
        pdf_bytes = pdf.tobytes()
        pdf.close()
        session = Mock()
        session.proxies = {}
        session.cookies = Mock()
        session.get.side_effect = lambda url, **_kwargs: _Response(content=pdf_bytes if url.endswith(".pdf") else b"")
        response = _Response(text="http://127.0.0.1:8080/view/token-1")
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "case.zip"
            zip_path.write_bytes(b"zip")
            with (
                patch.object(legacy, "build_preview_zip_without_case_root", return_value=str(zip_path)),
                patch.object(legacy.requests, "post", return_value=response),
                patch.object(legacy.requests, "Session", return_value=session),
            ):
                result = legacy.render_legacy_preview(str(zip_path), "http://127.0.0.1:8080")

        self.assertEqual(("100001", "100002", "100003", "100004"), tuple(result.render_result.pdf_by_document_id))
        requested_pdf_urls = [
            call.args[0]
            for call in session.get.call_args_list
            if call.args[0].startswith("http://127.0.0.1:8080/view-pdf/token-1/")
        ]
        self.assertEqual(4, len(requested_pdf_urls))

    def test_detection_worker_remembers_only_verified_client(self) -> None:
        worker = ClientDetectionWorker()
        completed: list[object] = []
        worker.completed.connect(completed.append)
        manager = Mock()
        manager.configure.return_value = SimpleNamespace(root="D:/CNIPAClient")
        with patch("gui.tools_ui_impl.preview_impl.runtime_setup.get_default_runtime_manager", return_value=manager):
            worker.run()
        manager.configure.assert_called_once_with(None, detect=True)
        self.assertEqual(["D:/CNIPAClient"], completed)

    def test_setup_exposes_detection_and_directory_only_and_does_not_rescan_saved_path(self) -> None:
        manager = Mock(configured_path=lambda: "D:/CNIPAClient", configuration_error=lambda: "")
        with patch("gui.tools_ui_impl.preview_impl.runtime_setup.get_default_runtime_manager", return_value=manager):
            dialog = RuntimeSetupDialog()
            self.app.processEvents()
            self.assertEqual("重新检测", dialog.detect_button.text())
            self.assertEqual("选择客户端目录…", dialog.browse_button.text())
            self.assertFalse(any("ZIP" in b.text() or "导入" in b.text() for b in dialog.findChildren(QPushButton)))
            manager.configure.assert_not_called()
            dialog.close()

    def test_initial_detection_runs_in_worker_and_missing_client_keeps_manual_choice(self) -> None:
        manager = Mock(configured_path=lambda: None, configuration_error=lambda: "")
        manager.configure.side_effect = RuntimeError(CLIENT_MISSING)
        with patch("gui.tools_ui_impl.preview_impl.runtime_setup.get_default_runtime_manager", return_value=manager):
            dialog = RuntimeSetupDialog(automatic=True)
            dialog.show()
            loop = QEventLoop()
            QTimer.singleShot(300, loop.quit)
            loop.exec()
            self.assertIsNone(dialog._thread)
            manager.configure.assert_called_once_with(None, detect=True)
            self.assertIn("没有检测到已安装", dialog.status_label.text())
            self.assertTrue(dialog.browse_button.isEnabled())
            self.assertFalse(dialog._success)
            dialog.close()

    def test_settings_page_exposes_independent_preview_status_and_actions(self) -> None:
        window = _AnyCallbackWindow()
        page = build_settings_page(window)

        self.assertIsNotNone(page.findChild(QLabel, "settingsEnvLegacyPreviewStatus"))
        self.assertIsNotNone(page.findChild(QLabel, "settingsEnvPreviewStatus"))
        self.assertIsNotNone(window.settings_legacy_preview_port_button)
        self.assertIsNotNone(window.settings_full_preview_runtime_button)


if __name__ == "__main__":
    unittest.main()
