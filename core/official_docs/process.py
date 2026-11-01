from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from datetime import datetime
from typing import Callable, Iterable, Literal

from .excel_report import build_default_excel_name, write_excel_report
from .field_governance import build_notice_key, should_skip_by_filter
from .image_to_pdf import image_bytes_to_pdf_bytes
from .models import CollisionResolver, ParsedNotice, ProcessOptions, ProcessSummary
from .naming_rules import notice_output_uses_field, render_notice_output
from .pdf_entity_extract import extract_pdf_entity_fields, resolve_pdf_applicable_fields
from .pdf_merge import merge_pdf_bytes
from .process_merge import ensure_dir as _ensure_dir
from .process_merge import resolve_collision as _resolve_collision
from .process_parse import parse_official_notice_archive
from .process_pdf_parse import (
    PDF_PARSE_EVIDENCE_KEYS_BY_FLAG as _PDF_PARSE_EVIDENCE_KEYS_BY_FLAG,
)
from .process_pdf_parse import (
    default_pdf_parse_status as _default_pdf_parse_status,
)
from .process_pdf_parse import (
    normalize_pdf_parse_field_flags as _normalize_pdf_parse_field_flags,
)
from .process_report import build_item_result as _build_item_result
from .template_render import build_meta_from_list_fields
from .zip_reader import NoticeZipReader


ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]
ConfirmAction = Literal["continue", "skip", "cancel"]
ConfirmCallback = Callable[[ParsedNotice, str, str], ConfirmAction]
_APPLICANT_FIELD_NAME = "申请人信息"


def _write_pdf_atomically(path: str, data: bytes) -> None:
    _ensure_dir(os.path.dirname(path))
    temporary_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".官文_", suffix=".tmp", dir=os.path.dirname(path), delete=False) as file_obj:
            temporary_path = file_obj.name
            file_obj.write(data)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _read_main_pdf_bytes(zip_path: str, parsed: ParsedNotice) -> bytes:
    source = next((pdf for pdf in (parsed.pdf_entries or []) if str(pdf.kind) == "main"), None)
    if source is None and parsed.pdf_entries:
        source = parsed.pdf_entries[0]
    if source is None:
        return b""
    with NoticeZipReader(zip_path) as zip_reader:
        data = zip_reader.read_bytes(source.raw_name)
    if str(source.source_type or "pdf") == "image":
        return image_bytes_to_pdf_bytes(data)
    return data


def _extract_pdf_entities_for_notice(*, pdf_bytes: bytes, parsed: ParsedNotice):
    return extract_pdf_entity_fields(
        pdf_bytes=pdf_bytes,
        notice_key=build_notice_key(parsed.meta),
        notice_kind=parsed.notice_kind,
        app_no=str(parsed.meta.app_no or ""),
    )


def _should_preparse_applicant_for_filename(parsed: ParsedNotice, options: ProcessOptions) -> bool:
    if not parsed.ok:
        return False
    if str(parsed.meta.applicant or "").strip():
        return False
    return notice_output_uses_field(
        meta=parsed.meta,
        notice_kind=parsed.notice_kind,
        options=options,
        field_name=_APPLICANT_FIELD_NAME,
    )


def process_official_notice_archives(
    zip_paths: Iterable[str],
    options: ProcessOptions,
    *,
    collision_resolver: CollisionResolver | None = None,
    confirm_cb: ConfirmCallback | None = None,
    progress_cb: ProgressCallback | None = None,
    cancel_cb: CancelCallback | None = None,
) -> ProcessSummary:
    zips = [str(path or "").strip() for path in (zip_paths or []) if str(path or "").strip()]
    total = len(zips)

    summary_root = os.path.abspath(str(options.summary_root_dir or "").strip())
    archive_root = os.path.abspath(str(options.archive_root_dir or "").strip())
    _ensure_dir(summary_root)
    run_dir = tempfile.mkdtemp(prefix=f"官文处理_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_", dir=summary_root)

    items = []
    pdf_parse_field_flags = _normalize_pdf_parse_field_flags(options)
    any_pdf_parse_field_selected = any(pdf_parse_field_flags.values())
    source_label_by_zip_path = dict(options.source_label_by_zip_path or {})

    def _result_source_label(zip_path: str) -> str:
        text = str(zip_path or "").strip()
        return str(source_label_by_zip_path.get(text, text) or text)

    def _progress(index: int, message: str) -> None:
        if progress_cb is None:
            return
        try:
            progress_cb(index, total, message)
        except Exception:
            pass

    cancel_from_index: int | None = None
    stopped_reason = "任务已取消"
    for index, zip_path in enumerate(zips, start=1):
        if cancel_cb is not None:
            try:
                if bool(cancel_cb()):
                    cancel_from_index = index
                    break
            except Exception:
                pass

        _progress(index, f"解析：{os.path.basename(zip_path)}")
        parsed = parse_official_notice_archive(zip_path)
        default_pdf_status = _default_pdf_parse_status(
            parsed=parsed,
            options=options,
            resolve_pdf_applicable_fields_fn=resolve_pdf_applicable_fields,
        )
        filter_skip_reason = should_skip_by_filter(meta=parsed.meta, raw_fields=parsed.flat_fields)
        if filter_skip_reason:
            items.append(
                _build_item_result(
                    source_zip_path=_result_source_label(zip_path),
                    status="skip",
                    parsed=parsed,
                    reason=filter_skip_reason,
                    pdf_parse_status=default_pdf_status,
                )
            )
            continue

        preparsed_pdf_result = None
        preparsed_pdf_error = ""
        preparsed_main_pdf_bytes = b""
        if _should_preparse_applicant_for_filename(parsed, options):
            try:
                preparsed_main_pdf_bytes = _read_main_pdf_bytes(zip_path, parsed)
                if preparsed_main_pdf_bytes:
                    preparsed_pdf_result = _extract_pdf_entities_for_notice(
                        pdf_bytes=preparsed_main_pdf_bytes,
                        parsed=parsed,
                    )
                    applicant = str(preparsed_pdf_result.applicant or "").strip()
                    if applicant:
                        parsed = replace(parsed, meta=replace(parsed.meta, applicant=applicant))
            except Exception as exc:
                preparsed_pdf_error = str(exc)

        rendered = None
        render_err = ""
        if parsed.ok:
            try:
                rendered = render_notice_output(meta=parsed.meta, notice_kind=parsed.notice_kind, options=options)
            except Exception as exc:
                render_err = f"渲染输出路径失败：{exc}"

        if bool(options.confirm_each):
            summary_preview = ""
            archive_preview = ""
            if rendered is not None:
                summary_preview = os.path.join(run_dir, rendered.output_pdf_name) if bool(options.write_summary) else ""
                archive_preview = (
                    os.path.join(archive_root, rendered.archive_rel_dir, rendered.output_pdf_name)
                    if bool(options.write_archive)
                    else ""
                )

            action: ConfirmAction | None = None
            confirmation_error = ""
            try:
                if confirm_cb is None:
                    raise ValueError("未提供逐个确认回调")
                action = confirm_cb(parsed, summary_preview, archive_preview)
            except Exception as exc:
                confirmation_error = f"逐个确认失败：{type(exc).__name__}: {exc}"

            if action not in ("continue", "skip", "cancel"):
                items.append(
                    _build_item_result(
                        source_zip_path=_result_source_label(zip_path),
                        status="fail",
                        parsed=parsed,
                        reason=confirmation_error or f"逐个确认返回无效动作：{action!r}",
                        pdf_parse_status=default_pdf_status,
                    )
                )
                cancel_from_index = index + 1
                stopped_reason = "逐个确认失败，任务已停止"
                break

            if action == "skip":
                items.append(
                    _build_item_result(
                        source_zip_path=_result_source_label(zip_path),
                        status="skip",
                        parsed=parsed,
                        reason="用户逐个确认时跳过",
                        pdf_parse_status=default_pdf_status,
                    )
                )
                continue
            if action == "cancel":
                items.append(
                    _build_item_result(
                        source_zip_path=_result_source_label(zip_path),
                        status="skip",
                        parsed=parsed,
                        reason="用户取消任务",
                        pdf_parse_status=default_pdf_status,
                    )
                )
                cancel_from_index = index + 1
                break

        if not parsed.ok:
            items.append(
                _build_item_result(
                    source_zip_path=_result_source_label(zip_path),
                    status="fail",
                    parsed=parsed,
                    reason="; ".join(parsed.errors),
                    pdf_parse_status=default_pdf_status,
                )
            )
            continue

        if rendered is None:
            items.append(
                _build_item_result(
                    source_zip_path=_result_source_label(zip_path),
                    status="fail",
                    parsed=parsed,
                    reason=render_err or "渲染输出路径失败",
                    pdf_parse_status=default_pdf_status,
                )
            )
            continue

        output_name = rendered.output_pdf_name
        summary_path = os.path.join(run_dir, output_name) if bool(options.write_summary) else ""
        archive_dir = os.path.join(archive_root, rendered.archive_rel_dir) if bool(options.write_archive) else ""
        archive_path = os.path.join(archive_dir, output_name) if archive_dir else ""

        collision = (bool(summary_path) and os.path.exists(summary_path)) or (bool(archive_path) and os.path.exists(archive_path))
        if collision:
            policy, new_name = _resolve_collision(
                output_pdf_name=output_name,
                summary_path=summary_path,
                archive_path=archive_path,
                collision_resolver=collision_resolver,
            )
            if policy == "skip":
                items.append(
                    _build_item_result(
                        source_zip_path=_result_source_label(zip_path),
                        status="skip",
                        parsed=parsed,
                        reason="同名冲突：已跳过",
                        output_pdf_name=output_name,
                        summary_pdf_path=summary_path,
                        archive_pdf_path=archive_path,
                        pdf_parse_status=default_pdf_status,
                    )
                )
                continue

            output_name = new_name
            summary_path = os.path.join(run_dir, output_name) if bool(options.write_summary) else ""
            archive_path = os.path.join(archive_dir, output_name) if archive_dir else ""

        _progress(index, f"合并：{output_name}")
        main_pdf_bytes = b""
        try:
            with NoticeZipReader(zip_path) as zip_reader:
                ordered_bytes = []
                for pdf in (parsed.pdf_entries or []):
                    data = zip_reader.read_bytes(pdf.raw_name)
                    if str(pdf.source_type or "pdf") == "image":
                        data = image_bytes_to_pdf_bytes(data)
                    ordered_bytes.append(data)
                    if (not main_pdf_bytes) and str(pdf.kind) == "main":
                        main_pdf_bytes = data
            merged_bytes = merge_pdf_bytes(ordered_bytes)
        except Exception as exc:
            items.append(
                _build_item_result(
                    source_zip_path=_result_source_label(zip_path),
                    status="fail",
                    parsed=parsed,
                    reason=f"PDF 合并失败：{exc}",
                    output_pdf_name=output_name,
                    summary_pdf_path=summary_path,
                    archive_pdf_path=archive_path,
                    pdf_parse_status=default_pdf_status,
                )
            )
            continue

        written_summary_path = ""
        written_archive_path = ""
        try:
            if summary_path:
                _write_pdf_atomically(summary_path, merged_bytes)
                written_summary_path = summary_path
            if archive_path:
                _write_pdf_atomically(archive_path, merged_bytes)
                written_archive_path = archive_path
        except Exception as exc:
            partial = f"；汇总 PDF 已写入：{written_summary_path}" if written_summary_path else ""
            items.append(
                _build_item_result(
                    source_zip_path=_result_source_label(zip_path),
                    status="fail",
                    parsed=parsed,
                    reason=f"写入输出失败：{exc}{partial}；未完成目标的原文件已保留",
                    output_pdf_name=output_name,
                    summary_pdf_path=written_summary_path,
                    archive_pdf_path=written_archive_path,
                    pdf_parse_status=default_pdf_status,
                )
            )
            continue

        if (not main_pdf_bytes) and ordered_bytes:
            main_pdf_bytes = ordered_bytes[0]
        if (not main_pdf_bytes) and preparsed_main_pdf_bytes:
            main_pdf_bytes = preparsed_main_pdf_bytes

        pdf_parse_status = default_pdf_status
        pdf_parse_error = ""
        pdf_reject_reason = ""
        pdf_reject_reasons = ""
        pdf_clauses = ""
        pdf_cn_pubnos = ""
        pdf_examiner_name = ""
        pdf_examiner_phone = ""
        pdf_department = ""
        pdf_center = ""
        pdf_applicant = ""
        pdf_inventor = ""
        pdf_agent = ""
        pdf_agency_raw = ""
        pdf_panel_head = ""
        pdf_panel_main = ""
        pdf_panel_member = ""
        pdf_dossier_no = ""
        pdf_authorization_pub_no = ""
        pdf_authorization_pub_date = ""
        pdf_certificate_no = ""
        pdf_qrcode_link = ""
        pdf_qrcode_image_bytes = b""
        pdf_evidence: dict[str, str] = {}

        if bool(options.enable_exam_pdf_parse) and any_pdf_parse_field_selected:
            try:
                if preparsed_pdf_result is not None:
                    result = preparsed_pdf_result
                elif preparsed_pdf_error:
                    raise RuntimeError(preparsed_pdf_error)
                else:
                    result = _extract_pdf_entities_for_notice(pdf_bytes=main_pdf_bytes, parsed=parsed)
                pdf_parse_status = str(result.status or "失败")
                pdf_parse_error = str(result.error or "")
                pdf_reject_reason = str(result.reject_reason or "")
                pdf_reject_reasons = str(result.reject_reason or "")
                pdf_clauses = ""
                pdf_cn_pubnos = str(result.prior_art or "")
                pdf_examiner_name = str(result.examiner or "")
                pdf_examiner_phone = str(result.examiner_phone or "")
                pdf_department = str(result.department or "")
                pdf_center = str(result.center or "")
                pdf_applicant = str(result.applicant or "")
                pdf_inventor = str(result.inventor or "")
                pdf_agent = str(result.agent or "")
                pdf_agency_raw = str(result.agency_raw or "")
                pdf_panel_head = str(result.panel_head or "")
                pdf_panel_main = str(result.panel_main or "")
                pdf_panel_member = str(result.panel_member or "")
                pdf_dossier_no = str(result.dossier_no or "")
                pdf_authorization_pub_no = str(result.authorization_pub_no or "")
                pdf_authorization_pub_date = str(result.authorization_pub_date or "")
                pdf_certificate_no = str(result.certificate_no or "")
                pdf_qrcode_link = str(result.qrcode_link or "")
                pdf_qrcode_image_bytes = bytes(result.qrcode_image_bytes or b"")
                pdf_evidence = dict(result.evidence or {})
            except Exception as exc:
                pdf_parse_status = "失败"
                pdf_parse_error = str(exc)

            if not pdf_parse_field_flags.get("applicant", False):
                pdf_applicant = ""
            if not pdf_parse_field_flags.get("inventor", False):
                pdf_inventor = ""
            if not pdf_parse_field_flags.get("agent", False):
                pdf_agent = ""
            if not pdf_parse_field_flags.get("agency_raw", False):
                pdf_agency_raw = ""
            if not pdf_parse_field_flags.get("department", False):
                pdf_department = ""
            if not pdf_parse_field_flags.get("center", False):
                pdf_center = ""
            if not pdf_parse_field_flags.get("examiner", False):
                pdf_examiner_name = ""
                pdf_examiner_phone = ""
            if not pdf_parse_field_flags.get("panel", False):
                pdf_panel_head = ""
                pdf_panel_main = ""
                pdf_panel_member = ""
            if not pdf_parse_field_flags.get("reject_reason", False):
                pdf_reject_reason = ""
                pdf_reject_reasons = ""
                pdf_clauses = ""
            if not pdf_parse_field_flags.get("prior_art", False):
                pdf_cn_pubnos = ""
            if not pdf_parse_field_flags.get("dossier_no", False):
                pdf_dossier_no = ""
            if not pdf_parse_field_flags.get("authorization_pub_no", False):
                pdf_authorization_pub_no = ""
            if not pdf_parse_field_flags.get("authorization_pub_date", False):
                pdf_authorization_pub_date = ""
            if not pdf_parse_field_flags.get("certificate_no", False):
                pdf_certificate_no = ""
            if not pdf_parse_field_flags.get("qrcode_link", False):
                pdf_qrcode_link = ""
            if not pdf_parse_field_flags.get("qrcode_image", False):
                pdf_qrcode_image_bytes = b""

            if pdf_applicant and (not str(parsed.meta.applicant or "").strip()):
                parsed = replace(parsed, meta=replace(parsed.meta, applicant=pdf_applicant))

            for flag_key, evidence_keys in _PDF_PARSE_EVIDENCE_KEYS_BY_FLAG.items():
                if pdf_parse_field_flags.get(flag_key, False):
                    continue
                for evidence_key in evidence_keys:
                    pdf_evidence.pop(evidence_key, None)

        items.append(
            _build_item_result(
                source_zip_path=_result_source_label(zip_path),
                status="success",
                parsed=parsed,
                output_pdf_name=output_name,
                summary_pdf_path=summary_path,
                archive_pdf_path=archive_path,
                pdf_parse_status=pdf_parse_status,
                pdf_parse_error=pdf_parse_error,
                pdf_reject_reason=pdf_reject_reason,
                pdf_reject_reasons=pdf_reject_reasons,
                pdf_clauses=pdf_clauses,
                pdf_cn_pubnos=pdf_cn_pubnos,
                pdf_examiner_name=pdf_examiner_name,
                pdf_examiner_phone=pdf_examiner_phone,
                pdf_department=pdf_department,
                pdf_center=pdf_center,
                pdf_applicant=pdf_applicant,
                pdf_inventor=pdf_inventor,
                pdf_agent=pdf_agent,
                pdf_agency_raw=pdf_agency_raw,
                pdf_panel_head=pdf_panel_head,
                pdf_panel_main=pdf_panel_main,
                pdf_panel_member=pdf_panel_member,
                pdf_dossier_no=pdf_dossier_no,
                pdf_authorization_pub_no=pdf_authorization_pub_no,
                pdf_authorization_pub_date=pdf_authorization_pub_date,
                pdf_certificate_no=pdf_certificate_no,
                pdf_qrcode_link=pdf_qrcode_link,
                pdf_qrcode_image_bytes=pdf_qrcode_image_bytes,
                pdf_evidence=pdf_evidence,
            )
        )

    if cancel_from_index is not None:
        for zip_path in zips[max(0, int(cancel_from_index) - 1) :]:
            dummy = ParsedNotice(
                source_zip_path=zip_path,
                notice_kind="unknown",
                meta=build_meta_from_list_fields({}),
                errors=[],
            )
            items.append(
                _build_item_result(
                    source_zip_path=_result_source_label(zip_path),
                    status="skip",
                    parsed=dummy,
                    reason=stopped_reason,
                    pdf_parse_status=_default_pdf_parse_status(
                        parsed=dummy,
                        options=options,
                        resolve_pdf_applicable_fields_fn=resolve_pdf_applicable_fields,
                    ),
                )
            )

    excel_path = ""
    try:
        excel_name = build_default_excel_name()
        excel_path = os.path.join(run_dir, excel_name)
        write_excel_report(
            excel_path,
            items=items,
            include_exam_pdf_columns=bool(options.enable_exam_pdf_parse),
        )
    except Exception:
        try:
            if excel_path and os.path.exists(excel_path):
                os.remove(excel_path)
        except Exception:
            pass
        excel_path = ""

    success = sum(1 for item in items if item.status == "success")
    skipped = sum(1 for item in items if item.status == "skip")
    failed = sum(1 for item in items if item.status == "fail")

    return ProcessSummary(
        summary_run_dir=run_dir,
        excel_path=excel_path,
        total=len(items),
        success=success,
        skipped=skipped,
        failed=failed,
        items=items,
    )


__all__ = ["parse_official_notice_archive", "process_official_notice_archives"]
