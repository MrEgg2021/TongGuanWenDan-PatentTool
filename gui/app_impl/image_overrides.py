from core.app_preferences import get_equation_display_scale_ratio
from core.config import load_config


def init_advanced_image_overrides(window) -> None:
    ratio = get_equation_display_scale_ratio()
    if ratio is None:
        ratio = float(load_config()["equation_display_scale_ratio"])
    window._img_scale_ratio_override = ratio


def get_effective_image_overrides(window) -> dict:
    return {"equation_display_scale_ratio": window._img_scale_ratio_override}
