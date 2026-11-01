from __future__ import annotations

import os
import re
from dataclasses import replace
from pathlib import Path

import fitz

from core.official_docs.image_to_pdf import image_bytes_to_pdf_bytes
from core.official_docs.pdf_meta_fallback import (
    extract_doc_serial_from_pdf_lines,
    extract_issue_date_from_pdf_lines,
    parse_pdf_fallback_bytes,
)
from core.official_docs.pdf_entity_extract import extract_pdf_entity_fields
from core.official_docs.process_parse import parse_official_notice_archive
from core.official_docs.zip_reader import NoticeZipReader

from .models import NoticeMeta, ParsedNotice


def _normalize_date8(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    if len(digits) >= 8:
        return digits[:8]
    return digits


def _map_patent_type(raw: str, app_no: str = "") -> str:
    value = str(raw or "").strip()
    if value == "0":
        return "invention"
    if value == "1":
        return "utility_model"
    lowered = value.lower()
    if value in {"发明", "发明专利"} or lowered == "invention":
        return "invention"
    if value in {"实用新型"} or lowered == "utility_model":
        return "utility_model"
    digits = re.sub(r"[^0-9]", "", str(app_no or ""))
    if len(digits) >= 5 and digits[4] in {"2", "3"}:
        return "utility_model"
    if len(digits) >= 5 and digits[4] == "1":
        return "invention"
    return ""


def _field(flat_fields: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = str(flat_fields.get(key, "") or "").strip()
        if value:
            return value
    for raw_key, raw_value in flat_fields.items():
        tail = str(raw_key or "").split("/")[-1].split("@")[0]
        if "[" in tail:
            tail = tail.split("[", 1)[0]
        if tail in keys:
            value = str(raw_value or "").strip()
            if value:
                return value
    return ""


def _infer_notice_code_for_pdf_extract(notice_name: str) -> str:
    name = str(notice_name or "").strip()
    if "补正" in name:
        return "210302"
    if "审查意见" in name:
        return "210401"
    return ""


def _notice_key_for_pdf_extract(notice: NoticeMeta) -> str:
    code = str(notice.notice_code or "").strip() or _infer_notice_code_for_pdf_extract(notice.notice_name)
    name = str(notice.notice_name or "").strip()
    app_no = str(notice.application_no or "").strip()
    if code and name:
        return f"{code}|{name}"
    if app_no and name:
        return f"{app_no}|{name}"
    if code:
        return code
    if app_no:
        return app_no
    if name:
        return name
    return "unknown"


def _extract_applicant_from_pdf_bytes(pdf_bytes: bytes, notice: NoticeMeta, *, notice_kind: str = "") -> str:
    if not pdf_bytes:
        return ""
    result = extract_pdf_entity_fields(
        pdf_bytes=pdf_bytes,
        notice_key=_notice_key_for_pdf_extract(notice),
        notice_kind=str(notice_kind or ""),
        app_no=str(notice.application_no or ""),
    )
    return str(result.applicant or "").strip()


def _read_main_pdf_bytes_from_zip(path: str, parsed) -> bytes:
    source = next((pdf for pdf in (parsed.pdf_entries or []) if str(pdf.kind) == "main"), None)
    if source is None and parsed.pdf_entries:
        source = parsed.pdf_entries[0]
    if source is None:
        return b""
    with NoticeZipReader(path) as zip_reader:
        data = zip_reader.read_bytes(source.raw_name)
    if str(source.source_type or "pdf") == "image":
        return image_bytes_to_pdf_bytes(data)
    return data


def _fill_missing_applicant_from_pdf_bytes(notice: NoticeMeta, pdf_bytes: bytes, *, notice_kind: str = "") -> NoticeMeta:
    if str(notice.applicant or "").strip():
        return notice
    try:
        applicant = _extract_applicant_from_pdf_bytes(pdf_bytes, notice, notice_kind=notice_kind)
    except Exception:
        applicant = ""
    if not applicant:
        return notice
    return replace(notice, applicant=applicant)


def _from_official_meta(meta) -> NoticeMeta:
    return NoticeMeta(
        application_no=str(getattr(meta, "app_no", "") or "").strip(),
        invention_title=str(getattr(meta, "invention_name", "") or "").strip(),
        applicant=str(getattr(meta, "applicant", "") or "").strip(),
        notice_name=str(getattr(meta, "notice_name", "") or "").strip(),
        notice_code=str(getattr(meta, "notice_code", "") or "").strip(),
        issue_date=str(getattr(meta, "issue_date8", "") or "").strip()
        or _normalize_date8(str(getattr(meta, "issue_date_raw", "") or "")),
        doc_serial=str(getattr(meta, "doc_serial", "") or "").strip(),
        patent_type=_map_patent_type(
            str(getattr(meta, "patent_type", "") or "").strip(),
            str(getattr(meta, "app_no", "") or "").strip(),
        ),
        limit_days=str(getattr(meta, "limit_days", "") or "").strip(),
        due_date=str(getattr(meta, "due_date", "") or "").strip(),
        internal_no=str(getattr(meta, "internal_no", "") or "").strip(),
        dossier_no=str(getattr(meta, "dossier_no", "") or "").strip(),
    )


def _finalize_flat_fields(notice: NoticeMeta, flat_fields: dict[str, str] | None = None) -> dict[str, str]:
    fields = dict(flat_fields or {})
    if notice.application_no:
        fields.setdefault("SHENQINGH", notice.application_no)
    if notice.invention_title:
        fields.setdefault("FAMINGMC", notice.invention_title)
    if notice.applicant:
        fields.setdefault("SHENQINGREN", notice.applicant)
    if notice.notice_code:
        fields.setdefault("TONGZHISBM", notice.notice_code)
    if notice.notice_name:
        fields.setdefault("TONGZHISMC", notice.notice_name)
    if notice.issue_date:
        fields.setdefault("FAWENR", notice.issue_date)
    if notice.doc_serial:
        fields.setdefault("FAWENXLH", notice.doc_serial)
    return fields


def _merge_notice_meta(primary: NoticeMeta, fallback: NoticeMeta) -> NoticeMeta:
    return NoticeMeta(
        application_no=str(primary.application_no or "").strip() or str(fallback.application_no or "").strip(),
        invention_title=str(primary.invention_title or "").strip() or str(fallback.invention_title or "").strip(),
        applicant=str(primary.applicant or "").strip() or str(fallback.applicant or "").strip(),
        notice_name=str(primary.notice_name or "").strip() or str(fallback.notice_name or "").strip(),
        notice_code=str(primary.notice_code or "").strip() or str(fallback.notice_code or "").strip(),
        issue_date=str(primary.issue_date or "").strip() or str(fallback.issue_date or "").strip(),
        doc_serial=str(primary.doc_serial or "").strip() or str(fallback.doc_serial or "").strip(),
        patent_type=str(primary.patent_type or "").strip() or str(fallback.patent_type or "").strip(),
        limit_days=str(primary.limit_days or "").strip() or str(fallback.limit_days or "").strip(),
        due_date=str(primary.due_date or "").strip() or str(fallback.due_date or "").strip(),
        internal_no=str(primary.internal_no or "").strip() or str(fallback.internal_no or "").strip(),
        dossier_no=str(primary.dossier_no or "").strip() or str(fallback.dossier_no or "").strip(),
    )


def _from_official_notice(path: str) -> ParsedNotice:
    parsed = parse_official_notice_archive(path)
    flat_fields = dict(parsed.flat_fields or {})
    meta = parsed.meta
    raw_type = _field(flat_fields, "FAMINGLX") or str(meta.patent_type or "").strip()
    notice = replace(_from_official_meta(meta), patent_type=_map_patent_type(raw_type, str(meta.app_no or "")))
    if not notice.applicant:
        try:
            notice = _fill_missing_applicant_from_pdf_bytes(
                notice,
                _read_main_pdf_bytes_from_zip(path, parsed),
                notice_kind=str(parsed.notice_kind or ""),
            )
        except Exception:
            pass
    if notice.applicant and not _field(flat_fields, "SHENQINGREN", "SHENQINGRMC", "申请人", "申请人信息", "专利权人"):
        flat_fields["SHENQINGREN"] = notice.applicant
    return ParsedNotice(
        source_path=path,
        meta=notice,
        meta_source="list_xml" if parsed.meta_source == "list_xml" else "pdf_fallback",
        flat_fields=_finalize_flat_fields(notice, flat_fields),
        errors=tuple(parsed.errors or ()),
    )


_APP_NO_RE = re.compile(r"(?:申请号|专利号|Application\s+No)\s*[:：]?\s*([0-9]{12,13}(?:\.[0-9])?)", re.I)
_APP_NO_BARE_RE = re.compile(r"\b([0-9]{12,13}(?:\.[0-9])?)\b")
_TITLE_RE = re.compile(r"(?:发明名称|发明创造名称|Invention)\s*[:：]?\s*(.+)", re.I)
_DATE_RE = re.compile(
    r"(?:发文日|发文日期|日期|Issue\s+Date)\s*[:：]?\s*(20[0-9]{2}\s*(?:[年./-]\s*[0-9]{1,2}\s*){2}日?)",
    re.I,
)


def _read_pdf_lines(path: str) -> list[str]:
    doc = fitz.open(path)
    try:
        lines: list[str] = []
        for page_index in range(doc.page_count):
            text = str(doc[page_index].get_text("text") or "")
            for raw_line in text.splitlines():
                line = re.sub(r"\s+", " ", str(raw_line or "").replace("\u3000", " ")).strip()
                if line:
                    lines.append(line)
        return lines
    finally:
        doc.close()


def _notice_name_from_lines(lines: list[str]) -> str:
    for line in lines[:30]:
        value = str(line or "").strip()
        if "通知书" in value or "notice" in value.lower():
            return value
    return ""


def _extract_app_no(lines: list[str]) -> str:
    value = _regex_pick(lines, _APP_NO_RE)
    if value:
        return value
    return _regex_pick(lines, _APP_NO_BARE_RE)


def _regex_pick(lines: list[str], pattern: re.Pattern[str]) -> str:
    for line in lines:
        matched = pattern.search(line)
        if matched:
            return str(matched.group(1) or "").strip()
    return ""


def _from_pdf_legacy(path: str, lines: list[str], pdf_bytes: bytes) -> ParsedNotice:
    app_no = _extract_app_no(lines)
    notice_name = _notice_name_from_lines(lines)
    notice = NoticeMeta(
        application_no=app_no,
        invention_title=_regex_pick(lines, _TITLE_RE),
        notice_name=notice_name,
        notice_code=_infer_notice_code_for_pdf_extract(notice_name),
        issue_date=_normalize_date8(extract_issue_date_from_pdf_lines(lines)),
        doc_serial=str(extract_doc_serial_from_pdf_lines(lines) or "").strip(),
        patent_type=_map_patent_type("", app_no),
    )
    notice = _fill_missing_applicant_from_pdf_bytes(notice, pdf_bytes)
    errors: list[str] = []
    if not app_no:
        errors.append("PDF 未识别出申请号")
    if not notice_name:
        errors.append("PDF 未识别出通知书名称")
    return ParsedNotice(
        source_path=path,
        meta=notice,
        meta_source="pdf_fallback",
        flat_fields=_finalize_flat_fields(notice),
        errors=tuple(errors),
    )


def _from_pdf(path: str) -> ParsedNotice:
    try:
        lines = _read_pdf_lines(path)
        pdf_bytes = Path(path).read_bytes()
    except Exception as exc:
        return ParsedNotice(source_path=path, errors=(f"读取 PDF 失败：{exc}",))
    legacy = _from_pdf_legacy(path, lines, pdf_bytes)
    shared = parse_pdf_fallback_bytes(pdf_bytes, raw_name=Path(path).name, display_name=Path(path).name)
    if shared.ok:
        notice = _merge_notice_meta(_from_official_meta(shared.meta), legacy.meta)
        notice = _fill_missing_applicant_from_pdf_bytes(notice, pdf_bytes, notice_kind=str(shared.notice_kind or ""))
        errors: list[str] = []
        if not notice.application_no:
            errors.append("PDF 未识别出申请号")
        if not notice.notice_name:
            errors.append("PDF 未识别出通知书名称")
        return ParsedNotice(
            source_path=path,
            meta=notice,
            meta_source="pdf_fallback",
            flat_fields=_finalize_flat_fields(notice, {**dict(legacy.flat_fields), **dict(shared.flat_fields)}),
            errors=tuple(errors),
        )
    return legacy


def parse_notice_source(path: str, *, mode_hint: str | None = None) -> ParsedNotice:
    source = str(path or "").strip()
    _ = mode_hint
    if not source:
        return ParsedNotice(source_path=source, errors=("通知书路径为空",))
    if not os.path.isfile(source):
        return ParsedNotice(source_path=source, errors=("通知书文件不存在",))
    suffix = Path(source).suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(source)
    if suffix == ".zip":
        return _from_official_notice(source)
    return ParsedNotice(source_path=source, errors=("仅支持通知书 ZIP 或 PDF",))


__all__ = ["parse_notice_source"]
