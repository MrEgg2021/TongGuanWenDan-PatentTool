from __future__ import annotations

import hashlib
import re
from typing import Any, Optional, Tuple

from core.regions_cn import CITIES_BY_PROVINCE, PROVINCES

from .constants import _REGION_CODES_6, _USCC_RE


def _normalize_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        try:
            if v.is_integer():
                return str(int(v))
        except Exception:
            pass
        try:
            return format(v, "f").rstrip("0").rstrip(".")
        except Exception:
            return str(v).strip()
    try:
        return str(v).strip()
    except Exception:
        return ""


def _is_uscc(value: str) -> bool:
    s = _normalize_text(value).upper()
    return bool(s and _USCC_RE.match(s))


def _mask_id_number(id_number: str) -> str:
    s = _normalize_text(id_number)
    if not s:
        return ""
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:6]}{'*' * (len(s) - 10)}{s[-4:]}"


def _mask_phone(phone: str) -> str:
    s = _normalize_text(phone)
    if not s:
        return ""
    if len(s) < 7:
        return "*" * len(s)
    return f"{s[:3]}{'*' * (len(s) - 7)}{s[-4:]}"


def _mask_email(email: str) -> str:
    s = _normalize_text(email)
    if not s:
        return ""
    if "@" not in s:
        if len(s) <= 2:
            return "*" * len(s)
        return f"{s[:1]}{'*' * (len(s) - 1)}"
    name, domain = s.split("@", 1)
    if not name:
        return f"*@{domain}"
    if len(name) == 1:
        return f"{name}@{domain}"
    return f"{name[:1]}{'*' * (len(name) - 1)}@{domain}"


def _mask_address_detail(text: str) -> str:
    s = _normalize_text(text)
    if not s:
        return ""
    if len(s) <= 6:
        return "*" * len(s)
    return f"{s[:6]}{'*' * (len(s) - 6)}"


def _normalize_applicant_id_type_code(value: Any) -> str:
    s = _normalize_text(value)
    if not s:
        return ""
    up = s.upper()
    if up.startswith("F") or ("统一社会信用" in s) or ("社会信用" in s):
        return "F"
    if up.startswith("I") or ("身份证" in s) or ("居民" in s):
        return "I"
    if up.startswith("O") or ("其他" in s):
        return "0"
    return s


def _applicant_type_text_from_code(value: Any) -> str:
    s = _normalize_text(value)
    if not s:
        return ""
    if s == "3":
        return "工矿企业"
    if s == "1":
        return "个人"
    if s == "2":
        return "事业单位/科研机构"
    return s


def _applicant_id_type_text_from_code(value: Any) -> str:
    s = _normalize_text(value)
    if not s:
        return ""
    up = s.upper()
    if up.startswith("F"):
        return "统一社会信用代码"
    if up.startswith("I"):
        return "居民身份证"
    if up.startswith("O") or s == "0":
        return "其他"
    return s


def _infer_applicant_id_type_from_id_no(id_no: str) -> str:
    s = _normalize_text(id_no)
    if not s:
        return ""
    if _is_uscc(s):
        return "F"
    return "I"


def _extract_zip_and_remove(full_text: str) -> Tuple[str, str]:
    s = _normalize_text(full_text)
    if not s:
        return "", ""
    candidates = re.findall(r"\d{6}", s)
    zip_code = ""
    for cand in reversed(candidates):
        if cand not in _REGION_CODES_6:
            zip_code = cand
            break
    if not zip_code:
        return "", s
    cleaned = re.sub(re.escape(zip_code), " ", s, count=1)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,，。；;\t\n\r")
    return zip_code, cleaned


def _coalesce_non_empty_str(new_val: Any, old_val: Any) -> str:
    nv = _normalize_text(new_val)
    if nv:
        return nv
    return _normalize_text(old_val)


def _coalesce_non_empty_int(new_val: Optional[int], old_val: Any) -> Optional[int]:
    if new_val is None:
        try:
            return int(old_val) if old_val is not None else None
        except Exception:
            return None
    return int(new_val)


def _province_name_from_code(code: str) -> str:
    c = _normalize_text(code)
    if not c:
        return ""
    for p in PROVINCES:
        try:
            if str(p.get("code") or "") == c:
                return str(p.get("name") or "")
        except Exception:
            continue
    return ""


def _city_name_from_code(code: str) -> str:
    c = _normalize_text(code)
    if not c:
        return ""
    for items in CITIES_BY_PROVINCE.values():
        for it in items:
            try:
                if str(it.get("code") or "") == c:
                    return str(it.get("name") or "")
            except Exception:
                continue
    return ""


def _format_merged_address(*, province_code: str, city_code: str, detail: str, zip_code: str, masked: bool) -> str:
    prov = _province_name_from_code(province_code) or _normalize_text(province_code)
    city = _city_name_from_code(city_code) or _normalize_text(city_code)
    det = _mask_address_detail(detail) if masked else _normalize_text(detail)
    z = _normalize_text(zip_code)
    parts = [p for p in [prov, city, det, z] if p]
    return " ".join(parts).strip()


def _make_record_hash(*parts: Any) -> str:
    raw = "\x1f".join(_normalize_text(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mask_text(value: str) -> str:
    s = _normalize_text(value)
    if not s:
        return ""
    if _is_uscc(s):
        return s.upper()
    return _mask_id_number(s)


def mask_phone_text(value: str) -> str:
    return _mask_phone(value)
