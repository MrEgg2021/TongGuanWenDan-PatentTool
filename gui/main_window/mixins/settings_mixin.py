from gui.main_window.mixins.settings_env_registry import (
    probe_word_env_from_registry,
)
from gui.main_window.mixins.settings_env_impl.ops import (
    auto_env_check_and_alert_if_needed,
    build_hijack_help_text,
    on_env_banner_retry,
    on_settings_env_refresh,
    on_settings_env_wps_help,
    run_env_check,
)
from gui.main_window.mixins.settings_preferences_impl.apply_ops import (
    apply_persisted_preferences,
    get_optimize_equation_centering_enabled,
    on_auto_preview_toggled,
    refresh_settings_page_from_state,
)
from gui.main_window.mixins.settings_preferences_impl.save_ops import on_other_settings_save
from gui.main_window.mixins.settings_preferences_impl.snapshot_ops import confirm_leave_settings_if_dirty


class SettingsMixin:
    def _probe_word_env_from_registry(self) -> dict:
        probed = probe_word_env_from_registry()
        hijacked = bool(probed.get("hijacked", False))
        fallback_possible = bool(probed.get("fallback_possible", False))
        server = str(probed.get("localserver32", "") or "")

        hint = str(probed.get("wps_hint", "") or "")
        try:
            if not hint.strip():
                if hijacked:
                    if fallback_possible:
                        base = (
                            "检测到 WPS 接管了 Word 连接，但本机仍有可用的 Microsoft Word。\n\n"
                            "转换时会尝试连接 Microsoft Word；"
                            "如果仍失败，再按下方建议检查 WPS 接管设置。\n\n"
                            + self._build_hijack_help_text(hijacked=True, detail="")
                        )
                    else:
                        base = self._build_hijack_help_text(hijacked=True, detail="")
                    if server.strip():
                        hint = f"当前 Word.Application 指向：\n{server}\n\n" + base
                    else:
                        hint = base
                else:
                    hint = self._build_hijack_help_text(hijacked=False, detail="")
        except Exception:
            hint = ""

        return {
            "word_ok": bool(probed.get("word_ok", False)),
            "hijacked": hijacked,
            "word_version": probed.get("word_version"),
            "word_error": str(probed.get("word_error", "") or ""),
            "wps_hint": str(hint or ""),
            "fallback_possible": bool(fallback_possible),
            "block_reason": str(probed.get("block_reason", "") or ""),
            "default_com_path_exists": bool(probed.get("default_com_path_exists", False)),
        }

    def _build_hijack_help_text(self, *, hijacked: bool, detail: str = "") -> str:
        return build_hijack_help_text(hijacked=hijacked, detail=detail)

    def _run_env_check(self, *, update_ui: bool = True) -> dict:
        return run_env_check(self, update_ui=update_ui)

    def _on_settings_env_refresh(self) -> None:
        on_settings_env_refresh(self)

    def _on_env_banner_retry(self) -> None:
        on_env_banner_retry(self)

    def _on_settings_env_wps_help(self) -> None:
        on_settings_env_wps_help(self)

    def _on_settings_legacy_preview_port(self) -> None:
        from gui.tools_ui_impl.preview_impl.legacy import prompt_legacy_preview_port

        prompt_legacy_preview_port(self)
        self._run_env_check(update_ui=True)

    def _on_settings_full_preview_runtime(self) -> None:
        from gui.tools_ui_impl.preview_impl.runtime_setup import configure_installed_client

        if configure_installed_client(self):
            from gui.tools_ui_impl.preview_impl.run import prewarm_full_preview

            prewarm_full_preview(self)
        self._run_env_check(update_ui=True)

    def _auto_env_check_and_alert_if_needed(self) -> None:
        """自动环境检测：用于启动时/打开其他设置时。

        - 正常：不提示
        - 异常：弹窗提醒（不包含预览服务）
        """

        auto_env_check_and_alert_if_needed(self)

    def _apply_persisted_preferences(self) -> None:
        apply_persisted_preferences(self)

    def _on_auto_preview_toggled(self, checked: bool) -> None:
        on_auto_preview_toggled(self, checked)

    def _refresh_settings_page_from_state(self) -> None:
        refresh_settings_page_from_state(self)

    def get_optimize_equation_centering_enabled(self) -> bool:
        return bool(get_optimize_equation_centering_enabled(self))

    def _confirm_leave_settings_if_dirty(self) -> bool:
        return bool(confirm_leave_settings_if_dirty(self))

    def _on_other_settings_save(self) -> bool:
        return on_other_settings_save(self)
