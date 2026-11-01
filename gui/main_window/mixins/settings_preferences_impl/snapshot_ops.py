from gui.dialog_utils import show_blocking_alert_modal


def settings_collect_snapshot_from_ui(window) -> dict:
    return {
        "optimize_equation_centering": window.settings_opt_center.isChecked(),
        "optimize_table_image_centering": window.settings_table_img_center.isChecked(),
        "request_form_skip_tip_enabled": window.settings_req_form_skip_tip.isChecked(),
        "id_validation_cn_enabled": window.settings_id_validation_cn.isChecked(),
        "id_validation_uscc_enabled": window.settings_id_validation_uscc.isChecked(),
        "desc_para_split_mode": window.settings_desc_split_mode.currentData(),
        "equation_display_scale_ratio": round(window.settings_scale_ratio.value(), 4),
    }


def settings_is_visible(window) -> bool:
    return window._settings_page.isVisible()


def settings_has_unsaved_changes(window) -> bool:
    return settings_is_visible(window) and (
        settings_collect_snapshot_from_ui(window) != window._settings_saved_snapshot
    )


def confirm_leave_settings_if_dirty(window) -> bool:
    if not settings_has_unsaved_changes(window):
        return True

    choice = show_blocking_alert_modal(
        window, "?????", "???????????",
        primary_text="??", secondary_text="???", close_result="cancel",
    )
    if choice == "primary":
        from .save_ops import on_other_settings_save

        return on_other_settings_save(window)
    if choice == "secondary":
        from .apply_ops import refresh_settings_page_from_state

        refresh_settings_page_from_state(window)
        return True
    return False
