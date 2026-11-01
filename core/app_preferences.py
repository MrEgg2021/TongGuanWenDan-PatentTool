from __future__ import annotations

from typing import Any, Optional

from core.user_prefs import get_pref, pop_pref, set_pref


# Ordinary application preference keys
PDF_PREVIEW_PORT_KEY = "pdf_preview_port"
PDF_PREVIEW_MODE_KEY = "pdf_preview_mode"
CNIPA_RUNTIME_SOURCE_V1_KEY = "cnipa_runtime_source_v1"
DESC_PARA_SPLIT_MODE_KEY = "desc_para_split_mode"
OPT_CENTER_DEFAULT_KEY = "optimize_equation_centering"
OPT_TABLE_IMAGE_CENTER_DEFAULT_KEY = "optimize_table_image_centering"
AUTO_OPEN_PREVIEW_SINGLE_KEY = "auto_open_pdf_preview_single"
ENV_CHECK_CACHE_KEY = "env_check_cache"
REQ_FORM_SKIP_TIP_ENABLED_KEY = "request_form_skip_tip_enabled"
ID_VALIDATION_CN_ENABLED_KEY = "id_validation_cn_enabled"
ID_VALIDATION_USCC_ENABLED_KEY = "id_validation_uscc_enabled"
OFFICIAL_DOC_SETTINGS_KEY = "official_doc_settings"
MAIN_WINDOW_GEOMETRY_V1_KEY = "main_window_geometry_v1"
MAIN_WINDOW_STATE_V1_KEY = "main_window_state_v1"
FORMAL_REVIEW_AUTO_MAXIMIZE_KEY = "formal_review_auto_maximize"

EQUATION_DISPLAY_SCALE_RATIO_KEY = "equation_display_scale_ratio"

def _set_bool(key: str, value: Any) -> None:
    if value is None:
        pop_pref(key)
        return
    set_pref(key, bool(value))


def get_env_check_cache() -> dict:
    raw = get_pref(ENV_CHECK_CACHE_KEY, {})
    return raw if isinstance(raw, dict) else {}


def set_env_check_cache(cache: Any) -> None:
    set_pref(ENV_CHECK_CACHE_KEY, cache if isinstance(cache, dict) else {})


def get_pdf_preview_port() -> Optional[int]:
    raw = get_pref(PDF_PREVIEW_PORT_KEY, None)
    try:
        port = int(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if port <= 0 or port > 65535:
        return None
    return port


def set_pdf_preview_port(port: Any) -> None:
    try:
        p = int(port) if port is not None else None
    except (TypeError, ValueError, OverflowError):
        p = None
    if p is None or p <= 0 or p > 65535:
        pop_pref(PDF_PREVIEW_PORT_KEY)
        return
    set_pref(PDF_PREVIEW_PORT_KEY, p)


def get_pdf_preview_mode() -> str:
    raw = get_pref(PDF_PREVIEW_MODE_KEY, "legacy")
    return "full" if raw == "full" else "legacy"


def set_pdf_preview_mode(mode: Any) -> None:
    value = str(mode).strip() if mode is not None else ""
    if value not in ("legacy", "full"):
        raise ValueError("PDF preview mode must be 'legacy' or 'full'.")
    set_pref(PDF_PREVIEW_MODE_KEY, value)


def get_cnipa_runtime_source_v1() -> dict[str, str] | None:
    raw = get_pref(CNIPA_RUNTIME_SOURCE_V1_KEY, None)
    if not isinstance(raw, dict):
        return None
    source_kind = raw.get("source_kind")
    source_path = raw.get("source_path")
    if source_kind not in ("installed_client", "archive") or not isinstance(source_path, str):
        return None
    normalized_path = source_path.strip()
    if not normalized_path:
        return None
    return {"source_kind": str(source_kind), "source_path": normalized_path}


def set_cnipa_runtime_source_v1(source_kind: Any, source_path: Any) -> None:
    kind = str(source_kind).strip() if source_kind is not None else ""
    path = str(source_path).strip() if source_path is not None else ""
    if kind not in ("installed_client", "archive"):
        raise ValueError("CNIPA runtime source kind must be 'installed_client' or 'archive'.")
    if not path:
        raise ValueError("CNIPA runtime source path must not be empty.")
    set_pref(CNIPA_RUNTIME_SOURCE_V1_KEY, {"source_kind": kind, "source_path": path})


def get_desc_para_split_mode() -> Optional[str]:
    mode = get_pref(DESC_PARA_SPLIT_MODE_KEY, None)
    if mode in ("word", "period", "word_period_end"):
        return str(mode)
    return None


def get_optimize_equation_centering_default() -> Optional[bool]:
    raw = get_pref(OPT_CENTER_DEFAULT_KEY, None)
    return None if raw is None else bool(raw)


def get_optimize_table_image_centering_default() -> Optional[bool]:
    raw = get_pref(OPT_TABLE_IMAGE_CENTER_DEFAULT_KEY, None)
    return None if raw is None else bool(raw)


def get_auto_open_pdf_preview_single() -> Optional[bool]:
    raw = get_pref(AUTO_OPEN_PREVIEW_SINGLE_KEY, None)
    return None if raw is None else bool(raw)


def set_auto_open_pdf_preview_single(enabled: Any) -> None:
    _set_bool(AUTO_OPEN_PREVIEW_SINGLE_KEY, enabled)


def get_request_form_skip_tip_enabled() -> Optional[bool]:
    raw = get_pref(REQ_FORM_SKIP_TIP_ENABLED_KEY, None)
    return None if raw is None else bool(raw)


def get_id_validation_cn_enabled() -> Optional[bool]:
    raw = get_pref(ID_VALIDATION_CN_ENABLED_KEY, None)
    return None if raw is None else bool(raw)


def get_id_validation_uscc_enabled() -> Optional[bool]:
    raw = get_pref(ID_VALIDATION_USCC_ENABLED_KEY, None)
    return None if raw is None else bool(raw)


def get_equation_display_scale_ratio() -> Optional[float]:
    raw = get_pref(EQUATION_DISPLAY_SCALE_RATIO_KEY, None)
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if val <= 0:
        return None
    return max(0.4, min(1.0, val))


def get_official_doc_settings() -> dict:
    raw = get_pref(OFFICIAL_DOC_SETTINGS_KEY, {})
    return raw if isinstance(raw, dict) else {}


def set_official_doc_settings(data: Any) -> None:
    set_pref(OFFICIAL_DOC_SETTINGS_KEY, data if isinstance(data, dict) else {})


def get_main_window_geometry_v1() -> Optional[str]:
    raw = get_pref(MAIN_WINDOW_GEOMETRY_V1_KEY, None)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def set_main_window_geometry_v1(value: Any) -> None:
    text = str(value or "").strip()
    if not text:
        pop_pref(MAIN_WINDOW_GEOMETRY_V1_KEY)
        return
    set_pref(MAIN_WINDOW_GEOMETRY_V1_KEY, text)


def get_main_window_state_v1() -> dict:
    raw = get_pref(MAIN_WINDOW_STATE_V1_KEY, {})
    return raw if isinstance(raw, dict) else {}


def set_main_window_state_v1(value: Any) -> None:
    set_pref(MAIN_WINDOW_STATE_V1_KEY, value if isinstance(value, dict) else {})


def get_formal_review_auto_maximize(default: bool = False) -> bool:
    raw = get_pref(FORMAL_REVIEW_AUTO_MAXIMIZE_KEY, bool(default))
    return bool(raw) if raw is not None else bool(default)
