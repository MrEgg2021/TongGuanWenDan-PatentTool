from __future__ import annotations

from .field_governance import build_field_layers
from .models import ParsedNotice, PdfSource, ProcessItemResult


def _merged_source_label(source: PdfSource) -> str:
    name = str(source.display_name or source.raw_name or "").strip()
    if str(source.source_type or "pdf") == "image":
        return f"{name} (image->pdf)"
    return name


def build_item_result(
    *,
    source_zip_path: str,
    status: str,
    parsed: ParsedNotice,
    reason: str = "",
    output_pdf_name: str = "",
    summary_pdf_path: str = "",
    archive_pdf_path: str = "",
    pdf_parse_status: str = "",
    pdf_parse_error: str = "",
    pdf_reject_reason: str = "",
    pdf_reject_reasons: str = "",
    pdf_clauses: str = "",
    pdf_cn_pubnos: str = "",
    pdf_examiner_name: str = "",
    pdf_examiner_phone: str = "",
    pdf_department: str = "",
    pdf_center: str = "",
    pdf_applicant: str = "",
    pdf_inventor: str = "",
    pdf_agent: str = "",
    pdf_agency_raw: str = "",
    pdf_panel_head: str = "",
    pdf_panel_main: str = "",
    pdf_panel_member: str = "",
    pdf_dossier_no: str = "",
    pdf_authorization_pub_no: str = "",
    pdf_authorization_pub_date: str = "",
    pdf_certificate_no: str = "",
    pdf_qrcode_link: str = "",
    pdf_qrcode_image_bytes: bytes = b"",
    pdf_evidence: dict[str, str] | None = None,
) -> ProcessItemResult:
    field_layers = build_field_layers(meta=parsed.meta, raw_fields=parsed.flat_fields)
    return ProcessItemResult(
        source_zip_path=source_zip_path,
        status=status,
        reason=str(reason or ""),
        notice_kind=parsed.notice_kind,
        notice_key=field_layers.notice_key,
        meta=parsed.meta,
        meta_source=parsed.meta_source,
        output_pdf_name=output_pdf_name,
        summary_pdf_path=summary_pdf_path,
        archive_pdf_path=archive_pdf_path,
        merged_sources=[_merged_source_label(p) for p in (parsed.pdf_entries or [])],
        business_fields=field_layers.business_fields,
        uncertain_fields=field_layers.uncertain_fields,
        raw_fields=field_layers.raw_fields,
        flat_fields=field_layers.raw_fields,
        pdf_parse_status=str(pdf_parse_status or ""),
        pdf_parse_error=str(pdf_parse_error or ""),
        pdf_reject_reason=str(pdf_reject_reason or ""),
        pdf_reject_reasons=str(pdf_reject_reasons or pdf_reject_reason or ""),
        pdf_clauses=str(pdf_clauses or ""),
        pdf_cn_pubnos=str(pdf_cn_pubnos or ""),
        pdf_examiner_name=str(pdf_examiner_name or ""),
        pdf_examiner_phone=str(pdf_examiner_phone or ""),
        pdf_department=str(pdf_department or ""),
        pdf_center=str(pdf_center or ""),
        pdf_applicant=str(pdf_applicant or ""),
        pdf_inventor=str(pdf_inventor or ""),
        pdf_agent=str(pdf_agent or ""),
        pdf_agency_raw=str(pdf_agency_raw or ""),
        pdf_panel_head=str(pdf_panel_head or ""),
        pdf_panel_main=str(pdf_panel_main or ""),
        pdf_panel_member=str(pdf_panel_member or ""),
        pdf_dossier_no=str(pdf_dossier_no or ""),
        pdf_authorization_pub_no=str(pdf_authorization_pub_no or ""),
        pdf_authorization_pub_date=str(pdf_authorization_pub_date or ""),
        pdf_certificate_no=str(pdf_certificate_no or ""),
        pdf_qrcode_link=str(pdf_qrcode_link or ""),
        pdf_qrcode_image_bytes=bytes(pdf_qrcode_image_bytes or b""),
        pdf_evidence=dict(pdf_evidence or {}),
    )


__all__ = ["build_item_result"]
