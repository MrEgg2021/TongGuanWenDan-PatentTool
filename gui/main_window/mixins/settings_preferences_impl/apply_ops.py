from core.app_preferences import (
    get_auto_open_pdf_preview_single,
    get_id_validation_cn_enabled,
    get_id_validation_uscc_enabled,
    get_optimize_equation_centering_default,
    get_optimize_table_image_centering_default,
    get_request_form_skip_tip_enabled,
    set_auto_open_pdf_preview_single,
)
from PySide6.QtCore import QSignalBlocker

from gui.main_window.mixins.settings_env_impl.ops import init_settings_env_section

from .snapshot_ops import settings_collect_snapshot_from_ui


def apply_persisted_preferences(window) -> None:
    window._opt_center_enabled = bool(get_optimize_equation_centering_default())
    window._opt_table_img_center_enabled = bool(get_optimize_table_image_centering_default())
    req_tip = get_request_form_skip_tip_enabled()
    window._req_form_skip_tip_enabled = True if req_tip is None else req_tip
    window._id_validation_cn_enabled = bool(get_id_validation_cn_enabled())
    window._id_validation_uscc_enabled = bool(get_id_validation_uscc_enabled())
    auto_preview = get_auto_open_pdf_preview_single()
    if auto_preview is not None:
        with QSignalBlocker(window.chk_auto_open_preview):
            window.chk_auto_open_preview.setChecked(auto_preview)
    window.chk_auto_open_preview.toggled.connect(window._on_auto_preview_toggled)
    refresh_settings_page_from_state(window)


def on_auto_preview_toggled(window, checked: bool) -> None:
    set_auto_open_pdf_preview_single(checked)


def refresh_settings_page_from_state(window) -> None:
    for widget, checked in (
        (window.settings_opt_center, window._opt_center_enabled),
        (window.settings_table_img_center, window._opt_table_img_center_enabled),
        (window.settings_req_form_skip_tip, window._req_form_skip_tip_enabled),
        (window.settings_id_validation_cn, window._id_validation_cn_enabled),
        (window.settings_id_validation_uscc, window._id_validation_uscc_enabled),
    ):
        with QSignalBlocker(widget):
            widget.setChecked(checked)

    mode = window.get_description_paragraph_split_mode()
    window.settings_desc_split_mode.setCurrentIndex(window.settings_desc_split_mode.findData(mode))
    with QSignalBlocker(window.settings_scale_ratio):
        window.settings_scale_ratio.setValue(window._img_scale_ratio_override)
    init_settings_env_section(window)
    window._settings_saved_snapshot = settings_collect_snapshot_from_ui(window)


def get_optimize_equation_centering_enabled(window) -> bool:
    return window._opt_center_enabled
