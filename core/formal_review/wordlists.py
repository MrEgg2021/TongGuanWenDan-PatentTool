from __future__ import annotations

from typing import Any

from core.user_prefs import get_pref, set_pref

WORDLIST_PREF_KEY_V2 = "formal_review.wordlists.v2"
WORDLIST_PREF_KEY_V1 = "formal_review.wordlists.v1"
WORDLIST_PROFILE_STORE_KEY_V1 = "formal_review.wordlists.profiles.v1"

SLIM_DEFAULT_PROFILE_NAME = "精简默认"
FULL_PRESET_PROFILE_NAME = "严格预设（旧版）"
_LEGACY_PROFILE_NAME = "默认"
_DEFAULT_PROFILE_NAME = SLIM_DEFAULT_PROFILE_NAME

DEFAULT_WORDLISTS_V2: dict[str, dict[str, list[str]]] = {
    "claims": {
        "forbidden": [],
        "sensitive": [],
    },
    "description": {
        "forbidden": [
            "其特征在于",
            "其特征是",
            "其特征为",
            "如权利要求",
            "根据权利要求",
            "权利要求书",
        ],
        "sensitive": [],
    },
}

FULL_PRESET_WORDLISTS_V2: dict[str, dict[str, list[str]]] = {
    "claims": {
        "forbidden": [
            "绝对",
            "必须",
            "必然",
            "唯一",
            "完全",
            "所有",
            "任何",
            "永久",
            "无限",
            "最佳",
            "最优",
            "最先进",
            "毫无",
            "不可避免",
        ],
        "sensitive": [
            "大约",
            "约",
            "左右",
            "基本",
            "基本上",
            "大致",
            "可能",
            "例如",
            "比如",
            "等等",
            "等",
            "诸如",
            "相关",
            "适当",
            "尽量",
            "优选",
        ],
    },
    "description": {
        "forbidden": [
            "权利要求",
            "极大",
            "确保",
            "绝对",
            "必须",
            "唯一",
            "完全",
        ],
        "sensitive": [
            "大约",
            "约",
            "左右",
            "基本",
            "大致",
            "可能",
            "例如",
            "比如",
            "等等",
            "相关",
            "适当",
            "优选",
        ],
    },
}


def builtin_wordlist_profiles() -> dict[str, dict[str, dict[str, list[str]]]]:
    return {
        SLIM_DEFAULT_PROFILE_NAME: normalize_wordlists(DEFAULT_WORDLISTS_V2),
        FULL_PRESET_PROFILE_NAME: normalize_wordlists(FULL_PRESET_WORDLISTS_V2),
    }


def _normalize_items(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        normalized.append(cleaned)
        seen.add(key)
    return normalized


def _normalize_bucket(payload: Any, defaults: dict[str, list[str]]) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        return {
            "forbidden": list(defaults.get("forbidden", [])),
            "sensitive": list(defaults.get("sensitive", [])),
        }
    if "forbidden" in payload:
        forbidden = _normalize_items(payload.get("forbidden"))
    else:
        forbidden = list(defaults.get("forbidden", []))
    if "sensitive" in payload:
        sensitive = _normalize_items(payload.get("sensitive"))
    else:
        sensitive = list(defaults.get("sensitive", []))
    return {"forbidden": forbidden, "sensitive": sensitive}


def normalize_wordlists(payload: Any) -> dict[str, dict[str, list[str]]]:
    if not isinstance(payload, dict):
        payload = {}

    has_v2_shape = isinstance(payload.get("claims"), dict) or isinstance(payload.get("description"), dict)
    if has_v2_shape:
        claims_bucket = _normalize_bucket(payload.get("claims"), DEFAULT_WORDLISTS_V2["claims"])
        description_bucket = _normalize_bucket(payload.get("description"), DEFAULT_WORDLISTS_V2["description"])
        return {"claims": claims_bucket, "description": description_bucket}

    legacy_forbidden = _normalize_items(payload.get("forbidden"))
    legacy_sensitive = _normalize_items(payload.get("sensitive"))

    if "forbidden" in payload:
        claims_forbidden = list(legacy_forbidden)
        desc_forbidden = list(legacy_forbidden)
    else:
        claims_forbidden = list(DEFAULT_WORDLISTS_V2["claims"]["forbidden"])
        desc_forbidden = list(DEFAULT_WORDLISTS_V2["description"]["forbidden"])

    if "sensitive" in payload:
        claims_sensitive = list(legacy_sensitive)
        desc_sensitive = list(legacy_sensitive)
    else:
        claims_sensitive = list(DEFAULT_WORDLISTS_V2["claims"]["sensitive"])
        desc_sensitive = list(DEFAULT_WORDLISTS_V2["description"]["sensitive"])

    return {
        "claims": {"forbidden": claims_forbidden, "sensitive": claims_sensitive},
        "description": {"forbidden": desc_forbidden, "sensitive": desc_sensitive},
    }


def load_wordlists() -> dict[str, dict[str, list[str]]]:
    active, profiles = load_wordlist_profile_store()
    payload = profiles.get(active)
    normalized = normalize_wordlists(payload)
    # Mirror current active profile to legacy v2 pref for backward compatibility.
    raw_v2 = get_pref(WORDLIST_PREF_KEY_V2, None)
    if raw_v2 != normalized:
        set_pref(WORDLIST_PREF_KEY_V2, normalized)
    return normalized


def save_wordlists(wordlists: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, list[str]]]:
    active, profiles = load_wordlist_profile_store()
    profiles[str(active or _DEFAULT_PROFILE_NAME)] = normalize_wordlists(wordlists)
    save_wordlist_profile_store(active, profiles)
    return normalize_wordlists(profiles.get(active))


def _legacy_wordlists_snapshot() -> dict[str, dict[str, list[str]]] | None:
    raw_v2 = get_pref(WORDLIST_PREF_KEY_V2, None)
    if isinstance(raw_v2, dict) and raw_v2:
        return normalize_wordlists(raw_v2)
    raw_v1 = get_pref(WORDLIST_PREF_KEY_V1, None)
    if isinstance(raw_v1, dict) and raw_v1:
        return normalize_wordlists(raw_v1)
    return None


def load_wordlist_profile_store() -> tuple[str, dict[str, dict[str, dict[str, list[str]]]]]:
    raw = get_pref(WORDLIST_PROFILE_STORE_KEY_V1, None)
    if not isinstance(raw, dict):
        raw = {}
    active = str(raw.get("active") or "").strip() or _DEFAULT_PROFILE_NAME
    raw_profiles = raw.get("profiles")
    if not isinstance(raw_profiles, dict):
        raw_profiles = {}

    normalized_profiles: dict[str, dict[str, dict[str, list[str]]]] = {}
    for name, payload in raw_profiles.items():
        if not isinstance(name, str):
            continue
        profile_name = name.strip()
        if not profile_name:
            continue
        normalized_profiles[profile_name] = normalize_wordlists(payload)

    if not normalized_profiles:
        legacy_snapshot = _legacy_wordlists_snapshot()
        if legacy_snapshot is not None:
            normalized_profiles[_LEGACY_PROFILE_NAME] = legacy_snapshot
            active = _LEGACY_PROFILE_NAME
        else:
            normalized_profiles = builtin_wordlist_profiles()
            active = _DEFAULT_PROFILE_NAME

    if active not in normalized_profiles:
        active = next(iter(normalized_profiles.keys()))

    normalized_store = {"active": active, "profiles": normalized_profiles}
    if raw != normalized_store:
        set_pref(WORDLIST_PROFILE_STORE_KEY_V1, normalized_store)
    # Keep legacy v2 mirror in sync for compatibility.
    active_payload = dict(normalized_profiles.get(active) or {})
    if get_pref(WORDLIST_PREF_KEY_V2, None) != active_payload:
        set_pref(WORDLIST_PREF_KEY_V2, active_payload)
    return active, normalized_profiles


def save_wordlist_profile_store(active: str, profiles: Any) -> None:
    active_name = str(active or "").strip() or _DEFAULT_PROFILE_NAME
    raw_profiles = profiles if isinstance(profiles, dict) else {}
    normalized_profiles: dict[str, dict[str, dict[str, list[str]]]] = {}
    for name, payload in raw_profiles.items():
        if not isinstance(name, str):
            continue
        profile_name = name.strip()
        if not profile_name:
            continue
        normalized_profiles[profile_name] = normalize_wordlists(payload)
    if not normalized_profiles:
        normalized_profiles = builtin_wordlist_profiles()
        active_name = _DEFAULT_PROFILE_NAME
    if active_name not in normalized_profiles:
        active_name = next(iter(normalized_profiles.keys()))
    store = {"active": active_name, "profiles": normalized_profiles}
    set_pref(WORDLIST_PROFILE_STORE_KEY_V1, store)
    # Mirror active profile to legacy v2 pref.
    set_pref(WORDLIST_PREF_KEY_V2, dict(normalized_profiles.get(active_name) or {}))


def set_active_wordlist_profile(name: str) -> None:
    active, profiles = load_wordlist_profile_store()
    target = str(name or "").strip()
    if not target:
        raise ValueError("profile_name 不能为空")
    if target not in profiles:
        raise ValueError(f"未找到词库方案：{target}")
    if target == active:
        return
    save_wordlist_profile_store(target, profiles)
