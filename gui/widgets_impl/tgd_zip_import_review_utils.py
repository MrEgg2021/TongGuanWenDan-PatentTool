from __future__ import annotations

from core.id_validation import validate_cn_id, validate_uscc


def _norm_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _infer_applicant_id_type_code_from_id_no(id_no: str) -> str:
    s = _norm_text(id_no)
    if not s:
        return ""
    if validate_uscc(s):
        return "F"
    if validate_cn_id(s):
        return "I"
    if s and s[0].isdigit() and len(s) in (15, 18):
        return "I"
    return "0"
