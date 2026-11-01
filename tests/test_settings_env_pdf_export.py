from __future__ import annotations

import unittest
from unittest.mock import patch

from core.word_startup_health import WordStartupHealthResult, check_word_pdf_export_health
from gui.main_window.mixins.settings_env_impl.ops_impl import actions_ops, env_check_ops


class _DummyStatus:
    def __init__(self) -> None:
        self.value = ""
        self.tooltip = ""

    def setText(self, value):
        self.value = str(value)

    def text(self):
        return self.value

    def setToolTip(self, value):
        self.tooltip = str(value)


class _DummyButton:
    def __init__(self) -> None:
        self.enabled = True

    def setEnabled(self, value):
        self.enabled = bool(value)


class _DummyWindow:
    def __init__(self) -> None:
        self.settings_env_pdf_export_status = _DummyStatus()
        self.settings_env_refresh_button = _DummyButton()


def _base_result() -> dict:
    return {
        "word_ok": True,
        "hijacked": False,
        "word_too_low": False,
        "word_version": 16.0,
        "runtime_ok": True,
    }


class SettingsEnvPdfExportTests(unittest.TestCase):
    def test_cached_pdf_status_is_restored_without_starting_word(self) -> None:
        window = _DummyWindow()
        with patch.object(
            env_check_ops,
            "get_env_check_cache",
            return_value={
                "pdf_export_status": "不可用（请修复或重装完整 Microsoft Office）",
                "pdf_export_ok": False,
                "pdf_export_error": "feature unavailable",
            },
        ):
            env_check_ops.init_settings_env_section(window)

        self.assertFalse(window._env_pdf_export_ok)
        self.assertEqual("feature unavailable", window._env_pdf_export_error)
        self.assertIn("不可用", window.settings_env_pdf_export_status.text())

    def test_result_updates_status_cache_and_banner(self) -> None:
        window = _DummyWindow()
        with (
            patch.object(env_check_ops, "get_env_check_cache", return_value={"word_status": "Word 16+"}),
            patch.object(env_check_ops, "set_env_check_cache") as cache_write,
            patch.object(env_check_ops, "update_env_banner_from_result") as banner,
        ):
            env_check_ops.update_pdf_export_check_result(
                window,
                pdf_export_ok=False,
                pdf_export_error="此功能尚未安装",
                status_text="不可用（请修复或重装完整 Microsoft Office）",
                base_result=_base_result(),
            )

        self.assertFalse(window._env_pdf_export_ok)
        self.assertIn("不可用", window.settings_env_pdf_export_status.text())
        self.assertFalse(cache_write.call_args.args[0]["pdf_export_ok"])
        self.assertFalse(banner.call_args.kwargs["pdf_export_ok"])

    def test_process_guard_cancel_blocks_probe_worker(self) -> None:
        window = _DummyWindow()
        with (
            patch.object(actions_ops, "ensure_office_processes_ready", return_value=False) as guard,
            patch.object(actions_ops, "WordHealthWorker") as worker_type,
            patch.object(actions_ops, "update_pdf_export_check_result") as update,
        ):
            actions_ops._start_pdf_export_check(window, _base_result())

        guard.assert_called_once_with(window, context="settings_pdf_export_check")
        worker_type.assert_not_called()
        self.assertIsNone(update.call_args.kwargs["pdf_export_ok"])
        self.assertIn("检测受阻", update.call_args.kwargs["status_text"])

    def test_process_guard_success_continues_probe_with_kill_context(self) -> None:
        window = _DummyWindow()

        def _guard_sets_killed(target, *, context):
            self.assertEqual("settings_pdf_export_check", context)
            target._office_process_guard_killed = True
            return True

        with (
            patch.object(actions_ops, "ensure_office_processes_ready", side_effect=_guard_sets_killed),
            patch.object(actions_ops, "QThread") as thread_type,
            patch.object(actions_ops, "WordHealthWorker") as worker_type,
            patch.object(actions_ops, "update_env_banner_checking"),
        ):
            thread_type.return_value.isRunning.return_value = False
            actions_ops._start_pdf_export_check(window, _base_result())

        self.assertIs(worker_type.call_args.kwargs["health_check"], check_word_pdf_export_health)
        self.assertTrue(worker_type.call_args.kwargs["killed_before_check"])
        thread_type.return_value.start.assert_called_once()
        self.assertFalse(window.settings_env_refresh_button.enabled)

    def test_manual_refresh_starts_probe_but_auto_check_does_not(self) -> None:
        window = _DummyWindow()
        base = _base_result()
        with (
            patch.object(actions_ops, "run_env_check", return_value=base),
            patch.object(actions_ops, "_start_pdf_export_check") as start_probe,
        ):
            actions_ops.on_settings_env_refresh(window)
            start_probe.assert_called_once_with(window, base)
            start_probe.reset_mock()
            actions_ops.auto_env_check_and_alert_if_needed(window)
            start_probe.assert_not_called()

    def test_pdf_probe_failure_is_not_word_startup_failure(self) -> None:
        result = WordStartupHealthResult(
            ok=True,
            pid=42,
            binding_progid="Word.Application.16",
            error=None,
            killed_before_check=False,
            pdf_export_ok=False,
            pdf_export_error="feature unavailable",
        )
        self.assertTrue(result.ok)
        self.assertFalse(result.pdf_export_ok)


if __name__ == "__main__":
    unittest.main()
