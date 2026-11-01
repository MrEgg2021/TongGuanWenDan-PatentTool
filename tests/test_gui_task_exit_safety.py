from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QWidget

from gui.main_window.mixins.progress_mixin import ProgressMixin
from gui.main_window.mixins.tray_mixin import TrayMixin


class TestWindow(TrayMixin, ProgressMixin, QWidget):
    def __init__(self):
        super().__init__()
        self._processing_overlay = None
        self._allow_close = False
        self.tray_icon = None


class GuiTaskExitSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_response_overlay_hides_cancel_but_batch_keeps_it(self):
        window = TestWindow()
        try:
            for scope, expected_hidden in (("response_correction", True), ("batch", False)):
                with self.subTest(scope=scope):
                    window._progress_scope = scope
                    window._cancel_requested = False
                    overlay = QFrame(window)
                    cancel = QPushButton("取消", overlay)
                    cancel.setObjectName("processingCancelButton")
                    cancel.show()
                    with patch("gui.main_window.mixins.progress_mixin.resolve_modal_owner", return_value=window), \
                         patch("gui.main_window.mixins.progress_mixin.build_processing_modal", return_value=overlay), \
                         patch("gui.main_window.mixins.progress_mixin.overlay_controller_api.attach"), \
                         patch("gui.main_window.mixins.progress_mixin.overlay_controller_api.set_modal_active"):
                        window._show_processing_overlay()
                    self.assertIs(window._processing_overlay, overlay)
                    self.assertEqual(cancel.isHidden(), expected_hidden)
                    cancel.click()
                    self.assertEqual(window._cancel_requested, not expected_hidden)
        finally:
            window.close()

    def test_running_qthread_blocks_tray_and_allowed_close(self):
        window = TestWindow()
        thread = QThread(window)
        thread.start()
        try:
            self.assertTrue(thread.isRunning())
            with patch("gui.main_window.mixins.tray_mixin.QMessageBox.information") as alert:
                window._tray_quit()
                self.assertFalse(window._allow_close)
                self.assertEqual(alert.call_count, 1)
                window._allow_close = True
                event = QCloseEvent()
                window.closeEvent(event)
                self.assertFalse(event.isAccepted())
                self.assertFalse(window._allow_close)
                self.assertEqual(alert.call_count, 2)
        finally:
            thread.quit()
            thread.wait(2000)
            window.close()

    def test_idle_monitor_and_completed_task_do_not_block_exit(self):
        window = TestWindow()
        warmup = QThread(window)
        window._preview_warmup_thread = warmup
        warmup.start()
        try:
            self.assertFalse(window._has_active_task())
            window._response_correction_busy = True
            self.assertTrue(window._has_active_task())
            window._response_correction_busy = False
            window._processing_overlay = QFrame(window)
            self.assertTrue(window._has_active_task())
            window._processing_overlay = None
            self.assertFalse(window._has_active_task())
        finally:
            warmup.quit()
            warmup.wait(2000)
            window.close()


if __name__ == "__main__":
    unittest.main()
