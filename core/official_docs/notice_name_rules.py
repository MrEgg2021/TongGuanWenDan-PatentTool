from __future__ import annotations

from .models import NoticeMeta


DESIGN_FORCE_NTH_NAME_BY_CODE: dict[str, str] = {
    "230301": "第N次补正通知书",
    "230302": "第N次审查意见通知书",
}


def is_design_patent_label(patent_type_label: str) -> bool:
    text = str(patent_type_label or "").strip()
    if not text:
        return False
    return "外观" in text


def normalize_notice_name(
    *,
    notice_code: str,
    notice_name: str,
    patent_type_label: str = "",
    force_by_code: bool = False,
) -> str:
    code = str(notice_code or "").strip()
    raw_name = str(notice_name or "").strip()
    mapped = str(DESIGN_FORCE_NTH_NAME_BY_CODE.get(code, "") or "").strip()
    if not mapped:
        return raw_name
    if bool(force_by_code):
        return mapped
    if is_design_patent_label(patent_type_label):
        return mapped
    return raw_name


def normalize_notice_name_for_meta(meta: NoticeMeta) -> str:
    return normalize_notice_name(
        notice_code=str(meta.notice_code or "").strip(),
        notice_name=str(meta.notice_name or "").strip(),
        patent_type_label=str(meta.patent_type or "").strip(),
        force_by_code=False,
    )


def normalize_notice_name_for_key(type_key: str, *, force_by_code: bool = True) -> str:
    key = str(type_key or "").strip()
    if "|" not in key:
        return key
    code_part, name_part = key.split("|", 1)
    return normalize_notice_name(
        notice_code=str(code_part or "").strip(),
        notice_name=str(name_part or "").strip(),
        patent_type_label="",
        force_by_code=bool(force_by_code),
    )


__all__ = [
    "DESIGN_FORCE_NTH_NAME_BY_CODE",
    "is_design_patent_label",
    "normalize_notice_name",
    "normalize_notice_name_for_key",
    "normalize_notice_name_for_meta",
]
