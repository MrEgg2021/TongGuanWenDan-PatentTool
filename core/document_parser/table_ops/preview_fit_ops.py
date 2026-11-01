from __future__ import annotations

import json
import os

from core.logging_utils import logger


def _resolve_preview_fit_report_path(owner, raw_path: str | None) -> str | None:
    if not raw_path:
        return None
    try:
        report_path = str(raw_path).strip()
    except Exception:
        return None
    if not report_path:
        return None
    if os.path.isabs(report_path):
        return report_path
    return os.path.abspath(report_path)


def _load_preview_fit_report(owner) -> dict:
    cfg = getattr(owner, 'config', {}) or {}
    table_cfg = (cfg.get('table_capture') or {}) if isinstance(cfg, dict) else {}
    preview_cfg = (table_cfg.get('preview_fit') or {}) if isinstance(table_cfg, dict) else {}
    report_path = _resolve_preview_fit_report_path(owner, preview_cfg.get('calibration_report'))
    if not report_path or not os.path.isfile(report_path):
        return {}
    try:
        with open(report_path, 'r', encoding='utf-8') as fh:
            payload = json.load(fh)
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        logger.warning('[TABLE_PREVIEW_FIT_REPORT] load_failed path=%s error_type=%s error=%s', report_path, type(exc).__name__, str(exc))
        return {}


def load_preview_fit_settings(owner) -> dict[str, object]:
    cfg = getattr(owner, 'config', {}) or {}
    table_cfg = (cfg.get('table_capture') or {}) if isinstance(cfg, dict) else {}
    preview_cfg = (table_cfg.get('preview_fit') or {}) if isinstance(table_cfg, dict) else {}
    configured_enabled = bool(preview_cfg.get('enabled'))

    safe_max_he_mm = preview_cfg.get('safe_max_he_mm')
    max_excess_mm = preview_cfg.get('max_excess_mm')
    report = _load_preview_fit_report(owner)

    if safe_max_he_mm in (None, ''):
        safe_max_he_mm = report.get('safe_max_he_mm')
    if max_excess_mm in (None, ''):
        max_excess_mm = report.get('max_excess_mm')
    if max_excess_mm in (None, ''):
        max_excess_mm = report.get('recommended_max_excess_mm')
    if max_excess_mm in (None, ''):
        suggested = report.get('suggested') if isinstance(report, dict) else None
        if isinstance(suggested, dict):
            max_excess_mm = suggested.get('max_excess_mm')

    try:
        safe_max_value = float(safe_max_he_mm) if safe_max_he_mm not in (None, '') else None
    except (TypeError, ValueError):
        safe_max_value = None
    try:
        max_excess_value = float(max_excess_mm) if max_excess_mm not in (None, '') else None
    except (TypeError, ValueError):
        max_excess_value = None

    enabled = bool(configured_enabled and safe_max_value and max_excess_value and safe_max_value > 0 and max_excess_value >= 0)
    return {
        'configured_enabled': bool(configured_enabled),
        'enabled': bool(enabled),
        'safe_max_he_mm': safe_max_value,
        'max_excess_mm': max_excess_value,
        'report_loaded': bool(report),
    }


def fragment_can_bypass_split(owner, height_mm: float, *, hard_limit_mm: float) -> bool:
    try:
        height_value = float(height_mm)
        limit_value = float(hard_limit_mm)
    except (TypeError, ValueError):
        return False
    if height_value <= limit_value + 1e-6:
        return True

    settings = load_preview_fit_settings(owner)
    if not bool(settings.get('enabled')):
        return False

    safe_max = settings.get('safe_max_he_mm')
    max_excess = settings.get('max_excess_mm')
    if safe_max is None or max_excess is None:
        return False
    try:
        return float(height_value) <= float(safe_max) + float(max_excess) + 1e-6
    except Exception:
        return False


def apply_preview_fit_if_enabled(owner, width_mm: float, height_mm: float, *, section: str, filename: str | None = None) -> tuple[float, float, bool]:
    try:
        width_value = float(width_mm)
        height_value = float(height_mm)
    except (TypeError, ValueError):
        return width_mm, height_mm, False

    settings = load_preview_fit_settings(owner)
    if not bool(settings.get('enabled')):
        return width_value, height_value, False

    safe_max = settings.get('safe_max_he_mm')
    max_excess = settings.get('max_excess_mm')
    if safe_max is None or max_excess is None:
        return width_value, height_value, False

    try:
        safe_max_value = float(safe_max)
        max_excess_value = float(max_excess)
    except (TypeError, ValueError):
        return width_value, height_value, False

    if height_value <= safe_max_value + 1e-6:
        return width_value, height_value, False
    if height_value > safe_max_value + max_excess_value + 1e-6:
        return width_value, height_value, False
    if height_value <= 0:
        return width_value, height_value, False

    scale = safe_max_value / height_value
    scaled_width = round(width_value * scale, 2)
    scaled_height = round(safe_max_value, 2)
    logger.info(
        '[TABLE_PREVIEW_FIT] section=%s file=%s before_w_mm=%.2f before_h_mm=%.2f after_w_mm=%.2f after_h_mm=%.2f safe_max_he_mm=%.2f max_excess_mm=%.2f',
        str(section),
        str(filename),
        float(width_value),
        float(height_value),
        float(scaled_width),
        float(scaled_height),
        float(safe_max_value),
        float(max_excess_value),
    )
    return float(scaled_width), float(scaled_height), True


__all__ = ['apply_preview_fit_if_enabled', 'fragment_can_bypass_split', 'load_preview_fit_settings']
