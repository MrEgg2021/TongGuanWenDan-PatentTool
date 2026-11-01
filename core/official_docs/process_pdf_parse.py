from __future__ import annotations

from typing import Callable

from .field_governance import build_notice_key
from .models import ParsedNotice, ProcessOptions


PDF_PARSE_FLAG_KEYS: tuple[str, ...] = (
    "applicant",
    "inventor",
    "agent",
    "agency_raw",
    "department",
    "center",
    "examiner",
    "panel",
    "reject_reason",
    "prior_art",
    "dossier_no",
    "authorization_pub_no",
    "authorization_pub_date",
    "certificate_no",
    "qrcode_link",
    "qrcode_image",
)


PDF_PARSE_EVIDENCE_KEYS_BY_FLAG: dict[str, tuple[str, ...]] = {
    "applicant": ("evidence_applicant",),
    "inventor": ("evidence_inventor",),
    "agent": ("evidence_agent",),
    "agency_raw": ("evidence_agency_raw",),
    "department": ("evidence_department",),
    "center": ("evidence_center",),
    "examiner": ("evidence_examiner", "evidence_examiner_phone"),
    "panel": ("evidence_panel_head", "evidence_panel_main", "evidence_panel_member"),
    "reject_reason": ("evidence_reject_reason",),
    "prior_art": ("evidence_prior_art",),
    "dossier_no": ("evidence_dossier_no",),
    "authorization_pub_no": ("evidence_authorization_pub_no",),
    "authorization_pub_date": ("evidence_authorization_pub_date",),
    "certificate_no": ("evidence_certificate_no",),
    "qrcode_link": ("evidence_qrcode_link",),
    "qrcode_image": ("evidence_qrcode_image",),
}


def normalize_pdf_parse_field_flags(options: ProcessOptions) -> dict[str, bool]:
    raw_flags = dict(options.pdf_parse_field_flags or {})
    normalized = {key: False for key in PDF_PARSE_FLAG_KEYS}
    legacy_alias = {
        "reject_clauses": "reject_reason",
        "reject_reasons": "reject_reason",
    }
    for old_key, new_key in legacy_alias.items():
        if bool(raw_flags.get(old_key, False)):
            normalized[new_key] = True
    for key in normalized.keys():
        if key in raw_flags:
            normalized[key] = bool(raw_flags.get(key, False))
    return normalized


def default_pdf_parse_status(
    *,
    parsed: ParsedNotice,
    options: ProcessOptions,
    resolve_pdf_applicable_fields_fn: Callable[..., tuple[str, ...]],
) -> str:
    if not bool(options.enable_exam_pdf_parse):
        return "未启用"
    notice_key = build_notice_key(parsed.meta)
    applicable_fields = resolve_pdf_applicable_fields_fn(notice_key=notice_key, notice_kind=parsed.notice_kind)
    if not applicable_fields:
        return "未适用"
    return "未命中"


__all__ = [
    "PDF_PARSE_EVIDENCE_KEYS_BY_FLAG",
    "PDF_PARSE_FLAG_KEYS",
    "default_pdf_parse_status",
    "normalize_pdf_parse_field_flags",
]
