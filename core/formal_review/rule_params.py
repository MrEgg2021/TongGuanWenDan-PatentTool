from __future__ import annotations

from typing import Any

from core.user_prefs import get_pref, set_pref

RULE_PARAMS_PREF_KEY = "formal_review.rule_params.v1"

_DEFAULT_CLAIM1_WORD_LIMIT = 500
_DEFAULT_CLAIM1_MARKER_LIMIT = 20
_MAX_LIMIT_VALUE = 100000

_BUILTIN_REFER_WORDS = [
    "所述",
    "所述的",
    "所述各",
    "上述",
    "上述的",
    "上述各",
    "前述",
    "前述的",
    "前述各",
    "该",
    "该些",
    "该各",
    "以上",
    "以上的",
    "以上各",
    "所说",
    "所说的",
    "所说各",
]


def _normalize_limit(value: Any, *, fallback: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return int(fallback)
    if parsed <= 0:
        return int(fallback)
    return int(min(parsed, _MAX_LIMIT_VALUE))


def _normalize_refer_words_extra(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_rows = value.splitlines()
    elif isinstance(value, (list, tuple, set)):
        raw_rows = [str(item or "") for item in value]
    else:
        raw_rows = []
    rows: list[str] = []
    seen: set[str] = set()
    for row in raw_rows:
        item = str(row or "").strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append(item)
    return rows


def default_rule_params() -> dict[str, object]:
    return {
        "claim1_word_limit": int(_DEFAULT_CLAIM1_WORD_LIMIT),
        "claim1_marker_limit": int(_DEFAULT_CLAIM1_MARKER_LIMIT),
        "refer_words_extra": [],
    }


def normalize_rule_params(payload: Any) -> dict[str, object]:
    defaults = default_rule_params()
    source = dict(payload or {}) if isinstance(payload, dict) else {}
    return {
        "claim1_word_limit": _normalize_limit(
            source.get("claim1_word_limit"),
            fallback=int(defaults["claim1_word_limit"]),
        ),
        "claim1_marker_limit": _normalize_limit(
            source.get("claim1_marker_limit"),
            fallback=int(defaults["claim1_marker_limit"]),
        ),
        "refer_words_extra": _normalize_refer_words_extra(source.get("refer_words_extra")),
    }


def load_rule_params() -> dict[str, object]:
    raw = get_pref(RULE_PARAMS_PREF_KEY, None)
    normalized = normalize_rule_params(raw)
    if raw != normalized:
        set_pref(RULE_PARAMS_PREF_KEY, normalized)
    return normalized


def save_rule_params(payload: dict[str, object]) -> dict[str, object]:
    normalized = normalize_rule_params(payload)
    set_pref(RULE_PARAMS_PREF_KEY, normalized)
    return normalized


def merged_refer_words(rule_params: dict[str, object] | None = None) -> list[str]:
    params = normalize_rule_params(rule_params if rule_params is not None else load_rule_params())
    merged: list[str] = []
    seen: set[str] = set()
    for item in list(_BUILTIN_REFER_WORDS) + list(params.get("refer_words_extra") or []):
        word = str(item or "").strip()
        if not word:
            continue
        key = word.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(word)
    return merged


__all__ = [
    "RULE_PARAMS_PREF_KEY",
    "default_rule_params",
    "load_rule_params",
    "merged_refer_words",
    "normalize_rule_params",
    "save_rule_params",
]
