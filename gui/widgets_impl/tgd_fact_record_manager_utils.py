from __future__ import annotations

import hashlib
import re


def _validate_china_id(s: str) -> bool:
    # Basic length and char check
    s = s.strip().upper()
    if not s:
        return True  # Don't flag empty
    if len(s) != 18:
        return False
    if not re.match(r"^\d{17}[\dX]$", s):
        return False
    return True


def _validate_social_credit_code(s: str) -> bool:
    s = s.strip().upper()
    if not s:
        return True  # Don't flag empty
    if len(s) != 18:
        return False
    # 18 chars, no I, O, S, V, Z
    if not re.match(r"^[0-9A-HJ-NP-RTUWXY]{2}\d{6}[0-9A-HJ-NP-RTUWXY]{10}$", s):
        return False
    return True


def _norm_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _make_record_hash(*parts) -> str:
    raw = "\x1f".join(_norm_text(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
