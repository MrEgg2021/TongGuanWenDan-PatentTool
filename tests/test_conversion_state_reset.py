from __future__ import annotations
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from gui.conversion_session import release_single_run_session
from gui.run_dispatch import handle_run_clicked
from gui.single_run import run_single_conversion

class _DummyPathEdit:

    def text(self) -> str:
        return ''

class _DummyButton:

    def __init__(self, *, raise_on_enable: bool=False) -> None:
        self.enabled_values: list[bool] = []
        self._raise_on_enable = raise_on_enable

    def setEnabled(self, enabled: bool) -> None:
        self.enabled_values.append(bool(enabled))
        if self._raise_on_enable:
            raise RuntimeError('button boom')

class _DummyWindow:

    def __init__(self) -> None:
        self._is_processing_conversion = False
        self._single_run_in_progress = False
        self._progress_scope = None
        self._cancel_requested = False
        self._processing_mode = 'single'
        self.path_edit = _DummyPathEdit()
        self.btn_run = _DummyButton()
        self.overlay_hidden = 0

    def findChild(self, *_args, **_kwargs):
        return None

    def _hide_processing_overlay(self) -> None:
        self.overlay_hidden += 1

    def _show_processing_overlay(self, *_args, **_kwargs) -> None:
        return None

    def _set_current_file_label(self, *_args, **_kwargs) -> None:
        return None

    def update_progress(self, *_args, **_kwargs) -> None:
        return None

    def _clear_system_clipboard_safely(self) -> None:
        return None

    def run_batch_conversion(self) -> None:
        return None

    def _check_required_headers_single(self, *_args, **_kwargs) -> bool:
        return False

class ConversionStateResetTests(unittest.TestCase):

    def test_dispatch_cancel_before_session_does_not_leak_busy_flag(self) -> None:
        window = _DummyWindow()
        with patch('gui.run_dispatch.ask_continue_cancel', return_value=False):
            handle_run_clicked(window)
        self.assertFalse(window._is_processing_conversion)

    def test_dispatch_precheck_abort_releases_outer_busy_flag(self) -> None:
        window = _DummyWindow()
        with patch('gui.run_dispatch.ask_continue_cancel', return_value=True), patch('gui.run_dispatch._ensure_office_processes_closed', return_value=False):
            handle_run_clicked(window)
        self.assertFalse(window._is_processing_conversion)
        self.assertIsNone(window._progress_scope)
        self.assertFalse(window._cancel_requested)

    def test_release_single_run_session_clears_flag_before_ui_restore(self) -> None:
        window = SimpleNamespace(_single_run_in_progress=True, _progress_scope='single', _cancel_requested=True, btn_run=_DummyButton(raise_on_enable=True), _hide_processing_overlay=lambda: None)
        release_single_run_session(window)
        self.assertFalse(window._single_run_in_progress)
        self.assertIsNone(window._progress_scope)
        self.assertFalse(window._cancel_requested)

    def test_single_run_header_precheck_failure_releases_busy_flag(self) -> None:
        window = _DummyWindow()
        with patch('gui.single_run.get_effective_image_overrides', return_value={}):
            run_single_conversion(window, 'demo.docx')
        self.assertFalse(window._single_run_in_progress)
        self.assertIsNone(window._progress_scope)
        self.assertFalse(window._cancel_requested)
        self.assertGreaterEqual(window.overlay_hidden, 1)
if __name__ == '__main__':
    unittest.main()
