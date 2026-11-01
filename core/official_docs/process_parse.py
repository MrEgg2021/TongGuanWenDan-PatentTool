from __future__ import annotations

import os
import re
from typing import Literal

from .kind_detect import detect_notice_kind
from .listxml_parser import parse_list_xml
from .models import AttachmentMeta, NoticeKind, ParsedNotice, PdfSource
from .pdf_meta_fallback import resolve_pdf_fallback_notice
from .template_render import build_meta_from_list_fields
from .zip_reader import NoticeZipReader, ZipEntry


def _normalize_match_key(text: str) -> str:
    src = str(text or "").strip().lower()
    src = os.path.splitext(src)[0]
    parts = re.findall(r"[0-9a-z\u4e00-\u9fff]+", src)
    return "".join(parts)


def _entry_stem(raw_name: str) -> str:
    try:
        base = os.path.basename(str(raw_name or "").replace("\\", "/"))
    except Exception:
        base = str(raw_name or "")
    return os.path.splitext(base)[0]


def _entry_source_type(entry: ZipEntry) -> Literal["pdf", "image"]:
    ext = os.path.splitext(str(entry.raw_name or ""))[1].lower()
    return "pdf" if ext == ".pdf" else "image"


def _select_main_entry(*, notice_code: str, entries: list[ZipEntry]) -> ZipEntry | None:
    code = str(notice_code or "").strip()
    if not entries:
        return None
    if code:
        for entry in entries:
            if _entry_stem(entry.raw_name) == code:
                return entry
        for entry in entries:
            if _entry_stem(entry.display_name) == code:
                return entry
    if len(entries) == 1:
        return entries[0]
    ordered = sorted(entries, key=lambda item: str(item.display_name or item.raw_name or ""))
    return ordered[0] if ordered else None


def _pick_best_attachment_entry(*, attachment: AttachmentMeta, candidates: list[ZipEntry]) -> ZipEntry | None:
    att_key = _normalize_match_key(attachment.name)
    if not att_key or not candidates:
        return None

    best: tuple[int, int, ZipEntry] | None = None
    for entry in candidates:
        key = _normalize_match_key(_entry_stem(entry.display_name) or _entry_stem(entry.raw_name))
        if not key:
            continue

        score = 0
        if key == att_key:
            score = 100
        elif att_key in key:
            score = 80
        elif key in att_key:
            score = 70
        else:
            continue

        diff = abs(len(key) - len(att_key))
        candidate = (score, -diff, entry)
        if best is None or candidate > best:
            best = candidate

    return best[2] if best else None


def _build_pdf_sources(
    *,
    notice_code: str,
    attachments: list[AttachmentMeta],
    pdfs: list[ZipEntry],
    images: list[ZipEntry],
    main_raw_name: str = "",
) -> tuple[list[PdfSource], list[str]]:
    errors: list[str] = []
    merge_entries = list(pdfs) + list(images)
    if not merge_entries:
        return [], ["ZIP 内未发现可合并文件（PDF/图片）"]

    remaining = list(merge_entries)
    main = None
    preferred_raw = str(main_raw_name or "").strip()
    if preferred_raw:
        main = next((entry for entry in remaining if str(entry.raw_name or "").strip() == preferred_raw), None)
    if main is None:
        main = _select_main_entry(notice_code=notice_code, entries=remaining)

    if main is not None:
        remaining = [entry for entry in remaining if entry.raw_name != main.raw_name]
    elif len(merge_entries) > 1:
        preferred = preferred_raw or str(notice_code or "").strip()
        if preferred:
            errors.append(f"缺少主通知书文件：{preferred}.pdf")
        else:
            errors.append("无法确定主通知书：缺少通知书标识，且压缩包内有多个文件，请核对通知书压缩包。")

    ordered: list[PdfSource] = []
    if main is not None:
        ordered.append(
            PdfSource(
                raw_name=main.raw_name,
                display_name=main.display_name,
                kind="main",
                source_type=_entry_source_type(main),
            )
        )

    used_raw: set[str] = set()
    for attachment in attachments or ():
        pick = _pick_best_attachment_entry(
            attachment=attachment,
            candidates=[entry for entry in remaining if entry.raw_name not in used_raw],
        )
        if pick is None:
            continue
        used_raw.add(pick.raw_name)
        ordered.append(
            PdfSource(
                raw_name=pick.raw_name,
                display_name=pick.display_name,
                kind="attachment",
                source_type=_entry_source_type(pick),
            )
        )

    extras = [entry for entry in remaining if entry.raw_name not in used_raw]
    extras.sort(key=lambda x: str(x.display_name or x.raw_name))
    for entry in extras:
        ordered.append(
            PdfSource(
                raw_name=entry.raw_name,
                display_name=entry.display_name,
                kind="extra",
                source_type=_entry_source_type(entry),
            )
        )

    return ordered, errors


def parse_official_notice_archive(zip_path: str) -> ParsedNotice:
    source = str(zip_path or "").strip()
    errors: list[str] = []
    meta_fields: dict[str, str] = {}
    flat_fields: dict[str, str] = {}
    attachments: list[AttachmentMeta] = []
    notice_kind: NoticeKind = "unknown"
    pdf_sources: list[PdfSource] = []
    meta_source = "unknown"

    if not source:
        return ParsedNotice(
            source_zip_path=source,
            notice_kind="unknown",
            meta=build_meta_from_list_fields({}),
            meta_source=meta_source,
            errors=["空的 ZIP 路径"],
        )

    try:
        with NoticeZipReader(source) as zip_reader:
            meta = build_meta_from_list_fields(meta_fields, flat_fields=flat_fields)
            main_raw_name = ""
            list_xml_error = ""

            list_entry = zip_reader.find_list_xml()
            if list_entry is None:
                list_xml_error = "未找到 list.xml"
            else:
                try:
                    parsed = parse_list_xml(zip_reader.read_bytes(list_entry.raw_name))
                    meta_fields = dict(parsed.meta or {})
                    flat_fields = dict(parsed.flat_fields or {})
                    attachments = list(parsed.attachments or [])
                    meta = build_meta_from_list_fields(meta_fields, flat_fields=flat_fields)
                    notice_kind, _kind_text, round_text = detect_notice_kind(meta.notice_name)
                    meta = build_meta_from_list_fields(meta_fields, notice_round=round_text, flat_fields=flat_fields)
                    meta_source = "list_xml"
                except Exception as exc:
                    list_xml_error = f"解析 list.xml 失败：{exc}"

            if meta_source != "list_xml":
                fallback = resolve_pdf_fallback_notice(zip_reader)
                if fallback.ok:
                    meta = fallback.meta
                    notice_kind = str(fallback.notice_kind or "unknown")
                    flat_fields = dict(fallback.flat_fields or {})
                    main_raw_name = str(fallback.main_pdf_raw_name or "").strip()
                    meta_source = "pdf_fallback"
                else:
                    if list_xml_error:
                        errors.append(list_xml_error)
                    if str(fallback.error or "").strip():
                        errors.append(str(fallback.error or "").strip())

            pdf_sources, pdf_errors = _build_pdf_sources(
                notice_code=meta.notice_code,
                attachments=attachments,
                pdfs=zip_reader.iter_pdfs(),
                images=zip_reader.iter_images(),
                main_raw_name=main_raw_name,
            )
            errors.extend(pdf_errors)

            return ParsedNotice(
                source_zip_path=source,
                notice_kind=notice_kind,
                meta=meta,
                meta_source=meta_source,
                flat_fields=flat_fields,
                attachments=attachments,
                pdf_entries=pdf_sources,
                errors=errors,
            )
    except FileNotFoundError:
        errors.append("文件不存在")
    except Exception as exc:
        errors.append(f"读取 ZIP 失败：{exc}")

    return ParsedNotice(
        source_zip_path=source,
        notice_kind=notice_kind,
        meta=build_meta_from_list_fields(meta_fields),
        meta_source=meta_source,
        flat_fields=flat_fields,
        attachments=attachments,
        pdf_entries=pdf_sources,
        errors=errors,
    )


__all__ = ["parse_official_notice_archive"]
