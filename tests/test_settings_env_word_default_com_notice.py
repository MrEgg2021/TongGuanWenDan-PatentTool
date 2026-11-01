from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from core.cnipa_preview.models import RendererState, RendererStateInfo
from gui.main_window.mixins.settings_env_impl.ops_impl import env_check_ops
from gui.main_window.mixins.settings_env_impl.ops_impl import word_env_ops


class _DummyWindow:
    def __init__(self) -> None:
        self._env_wps_fallback_possible = False
        self._env_wps_hint_text = ""


class _DummyStatus:
    def __init__(self) -> None:
        self._text = ""
        self._tooltip = ""

    def setText(self, text: str) -> None:  # noqa: N802 - Qt style
        self._text = str(text)

    def text(self) -> str:
        return self._text

    def setToolTip(self, text: str) -> None:  # noqa: N802 - Qt style
        self._tooltip = str(text)


class _DummyHelpButton:
    def __init__(self) -> None:
        self.visible = False
        self.enabled = False

    def setVisible(self, value: bool) -> None:  # noqa: N802 - Qt style
        self.visible = bool(value)

    def setEnabled(self, value: bool) -> None:  # noqa: N802 - Qt style
        self.enabled = bool(value)


class SettingsEnvWordDefaultComNoticeTests(unittest.TestCase):
    def test_fallback_possible_default_com_takeover_is_weak_warning_without_modal(self) -> None:
        window = _DummyWindow()
        window._env_wps_fallback_possible = True
        window._env_wps_hint_text = "当前 Word.Application 指向：\nC:/wps.exe /Automation"

        with patch.object(word_env_ops, "show_blocking_alert_modal") as alert_mock:
            word_env_ops.maybe_alert_env_issues(
                window,
                word_ok=True,
                hijacked=True,
                word_too_low=False,
                word_error="",
            )

        alert_mock.assert_not_called()

    def test_run_env_check_marks_fallback_possible_as_auto_bypass(self) -> None:
        window = _DummyWindow()
        window.settings_env_word_status = _DummyStatus()
        window.settings_env_wps_status = _DummyStatus()
        window.settings_env_preview_status = _DummyStatus()
        window.settings_env_legacy_preview_status = _DummyStatus()
        window.settings_env_windows_status = _DummyStatus()
        window.settings_env_runtime_status = _DummyStatus()
        window.settings_env_wps_help_button = _DummyHelpButton()

        with (
            patch.object(env_check_ops, "_probe_windows_runtime_env", return_value={"runtime_ok": True}),
            patch.object(
                env_check_ops,
                "probe_word_env_from_registry",
                return_value={
                    "word_ok": True,
                    "hijacked": True,
                    "fallback_possible": True,
                    "word_version": 16.0,
                    "word_error": "",
                    "wps_hint": "可自动绕过",
                },
            ),
            patch.object(env_check_ops, "get_default_runtime_manager", return_value=Mock(
                configured_path=lambda: None, configuration_error=lambda: "",
                state_info=lambda: RendererStateInfo(RendererState.STOPPED),
            )),
            patch.object(env_check_ops, "ping_legacy_preview_service", return_value=False),
            patch.object(env_check_ops, "set_env_check_cache"),
            patch.object(env_check_ops, "update_env_banner_checking"),
            patch.object(env_check_ops, "update_env_banner_from_result"),
            patch.object(env_check_ops.QApplication, "processEvents"),
        ):
            result = env_check_ops.run_env_check(window, update_ui=True)

        self.assertTrue(result["word_ok"])
        self.assertTrue(result["hijacked"])
        self.assertEqual("Word 16+", window.settings_env_word_status.text())
        self.assertEqual("WPS兼容：可自动绕过", window.settings_env_wps_status.text())

    def test_critical_hijack_dialog_is_shown(self) -> None:
        window = _DummyWindow()
        window._env_wps_fallback_possible = False
        window._env_wps_hint_text = "hint"

        with patch.object(word_env_ops, "show_blocking_alert_modal") as alert_mock:
            word_env_ops.maybe_alert_env_issues(
                window,
                word_ok=True,
                hijacked=True,
                word_too_low=False,
                word_error="",
            )

        alert_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
