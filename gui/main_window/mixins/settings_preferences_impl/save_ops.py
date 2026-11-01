from core.logging_utils import logger
from core.user_prefs import load_prefs, save_prefs
from gui.dialog_utils import show_blocking_alert_modal

from .snapshot_ops import settings_collect_snapshot_from_ui


def on_other_settings_save(window) -> bool:
    settings = settings_collect_snapshot_from_ui(window)
    try:
        save_prefs({**load_prefs(), **settings})
    except OSError:
        logger.exception("保存设置失败")
        show_blocking_alert_modal(
            window, "保存失败", "设置未保存。请检查用户数据目录的写入权限和磁盘空间后重试。",
            primary_text="关闭", secondary_text="关闭",
        )
        return False

    window._opt_center_enabled = settings["optimize_equation_centering"]
    window._opt_table_img_center_enabled = settings["optimize_table_image_centering"]
    window._req_form_skip_tip_enabled = settings["request_form_skip_tip_enabled"]
    window._id_validation_cn_enabled = settings["id_validation_cn_enabled"]
    window._id_validation_uscc_enabled = settings["id_validation_uscc_enabled"]
    window._img_scale_ratio_override = settings["equation_display_scale_ratio"]
    window._settings_saved_snapshot = settings
    show_blocking_alert_modal(
        window, "保存成功", "设置已保存。",
        primary_text="关闭", secondary_text="关闭", body_variant="settings_saved",
    )
    return True
