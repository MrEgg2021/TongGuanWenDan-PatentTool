from __future__ import annotations

DEFAULT_ENABLED_SECTIONS = {
    "claims": True,
    "description": True,
    "drawings": True,
    "abstract": True,
    "request_form": True,
}

_PROBE_SECTION_KEY_MAP = {
    "claims": "claims",
    "description": "description",
    "drawings": "drawings",
    "abstract": "abstract",
    "request_form": "request_meta",
}


def compute_request_form_prefill_available(header_probe: dict | None) -> bool | None:
    if not isinstance(header_probe, dict):
        return None
    if "request_meta" not in header_probe:
        return None
    return bool(header_probe.get("request_meta"))


def normalize_enabled_sections(enabled_sections: dict | None) -> dict:
    normalized = dict(DEFAULT_ENABLED_SECTIONS)
    if not isinstance(enabled_sections, dict):
        return normalized
    for key in DEFAULT_ENABLED_SECTIONS:
        normalized[key] = bool(enabled_sections.get(key))
    return normalized


def compute_effective_enabled_sections(enabled_sections: dict | None, header_probe: dict | None) -> dict:
    requested = normalize_enabled_sections(enabled_sections)
    if not isinstance(header_probe, dict):
        return dict(requested)

    effective: dict[str, bool] = {}
    for key, requested_enabled in requested.items():
        if not requested_enabled:
            effective[key] = False
            continue

        if key == "request_form":
            # 请求书是否生成只取决于用户勾选；request_meta 仅表示是否有可用预填来源。
            effective[key] = True
            continue

        probe_key = _PROBE_SECTION_KEY_MAP.get(key, key)
        if probe_key not in header_probe:
            effective[key] = bool(requested_enabled)
            continue
        effective[key] = bool(header_probe.get(probe_key))
    return effective


def needs_patent_type(enabled_sections: dict | None) -> bool:
    normalized = normalize_enabled_sections(enabled_sections)
    return bool(normalized.get("request_form")) or bool(normalized.get("description"))


__all__ = [
    "compute_request_form_prefill_available",
    "DEFAULT_ENABLED_SECTIONS",
    "compute_effective_enabled_sections",
    "needs_patent_type",
    "normalize_enabled_sections",
]
