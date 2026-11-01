from __future__ import annotations
import unittest
from unittest.mock import patch
from core.office_process_safety import OfficeProcessClassification
from core.word_startup_health import WordStartupHealthResult
from gui import run_dispatch

class _DummyLineEdit:

    def __init__(self, text: str='') -> None:
        self._text = str(text)

    def text(self) -> str:
        return str(self._text)

class _DummyButton:

    def __init__(self) -> None:
        self.enabled_values: list[bool] = []

    def setEnabled(self, enabled: bool) -> None:
        self.enabled_values.append(bool(enabled))

class _DummySingleWindow:

    def __init__(self) -> None:
        self._processing_mode = 'single'
        self.path_edit = _DummyLineEdit('demo.docx')
        self.btn_run = _DummyButton()
        self.clipboard_cleared = False
        self.progress_events: list[tuple[int, str, str]] = []
        self.overlay_events: list[tuple[str, str]] = []
        self.overlay_hidden = 0
        self._cancel_requested = True

    def findChild(self, *_args, **_kwargs):
        return None

    def update_progress(self, percent: int, primary: str, detail: str) -> None:
        self.progress_events.append((int(percent), str(primary), str(detail)))

    def _show_processing_overlay(self, primary: str, detail: str) -> None:
        self.overlay_events.append((str(primary), str(detail)))

    def _hide_processing_overlay(self) -> None:
        self.overlay_hidden += 1

    def _clear_system_clipboard_safely(self) -> None:
        self.clipboard_cleared = True

    def _reset_cancel_state(self) -> None:
        self._cancel_requested = False

    def get_enabled_sections(self):
        return {'request_form': True}


def _ok_health(*, killed_before_check: bool=False) -> WordStartupHealthResult:
    return WordStartupHealthResult(ok=True, pid=2345, binding_progid='Word.Application.16', error=None, killed_before_check=killed_before_check)

def _failed_health(*, killed_before_check: bool=False, reason_code: str='word_exit_failed', user_message: str='Word startup health check failed.') -> WordStartupHealthResult:
    return WordStartupHealthResult(ok=False, pid=None, binding_progid=None, error=user_message, killed_before_check=killed_before_check, reason_code=reason_code, user_message=user_message, technical_detail=user_message)

class ConversionProcessGateTests(unittest.TestCase):

    def test_run_button_uses_unified_office_process_guard_after_session_starts(self) -> None:
        window = _DummySingleWindow()
        with patch('gui.run_dispatch.ask_continue_cancel', return_value=True), patch('gui.run_dispatch.begin_conversion_session', return_value=True), patch('gui.run_dispatch.set_conversion_ui_enabled'), patch('gui.run_dispatch.ensure_office_processes_ready', return_value=False) as guard_mock, patch('gui.run_dispatch._start_word_health_check') as health_start_mock, patch('gui.run_dispatch.run_single_conversion') as single_mock, patch('gui.run_dispatch.release_conversion_session') as release_mock:
            run_dispatch.handle_run_clicked(window)
        guard_mock.assert_called_once_with(window, context='conversion_start')
        health_start_mock.assert_not_called()
        single_mock.assert_not_called()
        release_mock.assert_called_once_with(window)

    def test_run_button_starts_background_health_check_without_sync_health_call(self) -> None:
        window = _DummySingleWindow()
        with patch('gui.run_dispatch.ask_continue_cancel', return_value=True), patch('gui.run_dispatch.begin_conversion_session', return_value=True), patch('gui.run_dispatch.set_conversion_ui_enabled'), patch('gui.run_dispatch.ensure_office_processes_ready', return_value=True), patch('gui.run_dispatch._start_word_health_check', return_value=True) as health_start_mock, patch('gui.run_dispatch.check_word_startup_health', create=True) as sync_health_mock, patch('gui.run_dispatch.run_single_conversion') as single_mock, patch('gui.run_dispatch.release_conversion_session') as release_mock:
            run_dispatch.handle_run_clicked(window)
        health_start_mock.assert_called_once_with(window, killed_before_check=False, retry_attempted=False)
        sync_health_mock.assert_not_called()
        single_mock.assert_not_called()
        release_mock.assert_not_called()
        self.assertTrue(any(('Word' in event[1] for event in window.progress_events)))

    def test_run_button_blocks_when_word_startup_health_fails_after_kill(self) -> None:
        window = _DummySingleWindow()
        failed = _failed_health(killed_before_check=True, reason_code='word_exit_failed', user_message='Office/WPS abnormal state.')

        def _guard_sets_killed(_window, *, context: str) -> bool:
            self.assertEqual('conversion_start', context)
            _window._office_process_guard_killed = True
            return True

        def _finish_health(_window, *, killed_before_check: bool, retry_attempted: bool=False) -> bool:
            self.assertTrue(killed_before_check)
            self.assertFalse(retry_attempted)
            run_dispatch._on_word_health_finished(_window, failed, retry_attempted=retry_attempted)
            return True
        with patch('gui.run_dispatch.ask_continue_cancel', return_value=True), patch('gui.run_dispatch.begin_conversion_session', return_value=True), patch('gui.run_dispatch.set_conversion_ui_enabled'), patch('gui.run_dispatch.ensure_office_processes_ready', side_effect=_guard_sets_killed), patch('gui.run_dispatch._start_word_health_check', side_effect=_finish_health) as health_start_mock, patch('gui.run_dispatch.show_blocking_alert_modal') as alert_mock, patch('gui.run_dispatch.run_single_conversion') as single_mock, patch('gui.run_dispatch.release_conversion_session') as release_mock:
            run_dispatch.handle_run_clicked(window)
        health_start_mock.assert_called_once()
        alert_mock.assert_called_once()
        self.assertIn('Office/WPS abnormal state.', str(alert_mock.call_args.args[2]))
        single_mock.assert_not_called()
        release_mock.assert_called_once_with(window)

    def test_run_button_retries_health_after_unified_office_gate(self) -> None:
        window = _DummySingleWindow()
        results = [_failed_health(killed_before_check=False, reason_code='word_pid_missing_unclaimed', user_message='Word PID missing.'), _ok_health(killed_before_check=False)]

        def _finish_next_health(_window, *, killed_before_check: bool, retry_attempted: bool=False) -> bool:
            result = results.pop(0)
            run_dispatch._on_word_health_finished(_window, result, retry_attempted=retry_attempted)
            return True
        with patch('gui.run_dispatch.ask_continue_cancel', return_value=True), patch('gui.run_dispatch.begin_conversion_session', return_value=True), patch('gui.run_dispatch.set_conversion_ui_enabled'), patch('gui.run_dispatch.ensure_office_processes_ready', return_value=True) as guard_mock, patch('gui.run_dispatch._start_word_health_check', side_effect=_finish_next_health) as health_start_mock, patch('gui.run_dispatch.logger') as logger_mock, patch('gui.run_dispatch.os.path.isfile', return_value=True), patch('gui.run_dispatch.run_single_conversion') as single_mock, patch('gui.run_dispatch.release_conversion_session') as release_mock:
            run_dispatch.handle_run_clicked(window)
        self.assertEqual(2, health_start_mock.call_count)
        self.assertEqual(False, health_start_mock.call_args_list[0].kwargs['retry_attempted'])
        self.assertEqual(True, health_start_mock.call_args_list[1].kwargs['retry_attempted'])
        self.assertEqual(2, guard_mock.call_count)
        self.assertEqual('conversion_start', guard_mock.call_args_list[0].kwargs['context'])
        self.assertEqual('word_health_failure', guard_mock.call_args_list[1].kwargs['context'])
        warning_messages = [str(call.args[0]) for call in logger_mock.warning.call_args_list]
        info_messages = [str(call.args[0]) for call in logger_mock.info.call_args_list]
        self.assertTrue(any(('[WORD_HEALTH] first_failed' in msg for msg in warning_messages)))
        self.assertTrue(any(('[WORD_HEALTH] recovered_after_office_gate' in msg for msg in info_messages)))
        self.assertTrue(window.clipboard_cleared)
        single_mock.assert_called_once_with(window, 'demo.docx')
        release_mock.assert_called_once_with(window)

    def test_run_button_logs_process_classification_and_health_success(self) -> None:
        window = _DummySingleWindow()

        def _finish_health(_window, *, killed_before_check: bool, retry_attempted: bool=False) -> bool:
            run_dispatch._on_word_health_finished(_window, _ok_health(killed_before_check=killed_before_check), retry_attempted=retry_attempted)
            return True
        with patch('gui.run_dispatch.ask_continue_cancel', return_value=True), patch('gui.run_dispatch.begin_conversion_session', return_value=True), patch('gui.run_dispatch.set_conversion_ui_enabled'), patch('gui.run_dispatch.ensure_office_processes_ready', return_value=True), patch('gui.run_dispatch.classify_office_processes', return_value=OfficeProcessClassification()), patch('gui.run_dispatch._start_word_health_check', side_effect=_finish_health), patch('gui.run_dispatch.logger') as logger_mock, patch('gui.run_dispatch.os.path.isfile', return_value=True), patch('gui.run_dispatch.run_single_conversion') as single_mock, patch('gui.run_dispatch.release_conversion_session'):
            run_dispatch.handle_run_clicked(window)
        info_messages = [str(call.args[0]) for call in logger_mock.info.call_args_list]
        self.assertTrue(any(('[OFFICE_PROCESS_CLASSIFICATION]' in msg for msg in info_messages)))
        self.assertTrue(any(('[WORD_HEALTH] ok' in msg for msg in info_messages)))
        single_mock.assert_called_once_with(window, 'demo.docx')

    def test_non_office_conversion_failure_does_not_cleanup_hidden_processes(self) -> None:
        window = _DummySingleWindow()

        def _finish_health(_window, *, killed_before_check: bool, retry_attempted: bool=False) -> bool:
            run_dispatch._on_word_health_finished(_window, _ok_health(killed_before_check=killed_before_check), retry_attempted=retry_attempted)
            return True
        with patch('gui.run_dispatch.ask_continue_cancel', return_value=True), patch('gui.run_dispatch.begin_conversion_session', return_value=True), patch('gui.run_dispatch.set_conversion_ui_enabled'), patch('gui.run_dispatch.ensure_office_processes_ready', return_value=True), patch('gui.run_dispatch.classify_office_processes', return_value=OfficeProcessClassification()), patch('gui.run_dispatch._start_word_health_check', side_effect=_finish_health), patch('gui.run_dispatch.os.path.isfile', return_value=True), patch('gui.run_dispatch.run_single_conversion', side_effect=RuntimeError('parse failed')), patch('gui.run_dispatch.release_conversion_session') as release_mock:
            with self.assertRaises(RuntimeError):
                run_dispatch.handle_run_clicked(window)
        release_mock.assert_called_once_with(window)
if __name__ == '__main__':
    unittest.main()
