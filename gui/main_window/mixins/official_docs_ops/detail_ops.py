from __future__ import annotations

from .shared import (
    NoticeZipReader,
    Path,
    PdfSource,
    ParsedNotice,
    ProcessOptions,
    _canonical_notice_name_for_display,
    _leaf_display_name,
    image_bytes_to_pdf_bytes,
    normalize_notice_name_for_meta,
    os,
    render_notice_output,
    render_notice_output_preview,
)
from core.official_docs import mask_app_no_for_preview
from core.user_messages import user_error_text


def _official_docs_pdf_source_kind_text(kind: str) -> str:
    mapping = {
        "main": "主文",
        "attachment": "附件",
        "extra": "其他",
    }
    return str(mapping.get(str(kind or "").strip().lower(), "其他"))


def _format_official_docs_pdf_sources(parsed: ParsedNotice) -> str:
    entries = list(parsed.pdf_entries or [])
    if not entries:
        return "未识别到来源文件"

    lines: list[str] = []
    for index, source in enumerate(entries, start=1):
        display_name = str(source.display_name or source.raw_name or "").strip() or "-"
        suffix = " | 图片来源" if str(getattr(source, "source_type", "pdf") or "pdf").strip().lower() == "image" else ""
        lines.append(f"{index}. {_official_docs_pdf_source_kind_text(source.kind)} | {display_name}{suffix}")
    return "\n".join(lines)


def _build_preview_paths(self, parsed: ParsedNotice, options: ProcessOptions) -> tuple[str, str, str]:
    rendered = render_notice_output(meta=parsed.meta, notice_kind=parsed.notice_kind, options=options)
    preview = render_notice_output_preview(meta=parsed.meta, notice_kind=parsed.notice_kind, options=options)
    preview_name = str(preview.preview_pdf_name or rendered.output_pdf_name or "").strip()
    if not preview_name:
        preview_name = "notice.pdf"
    summary_root = str(options.summary_root_dir or "").strip()
    archive_root = str(options.archive_root_dir or "").strip()
    summary_preview = ""
    archive_preview = ""
    if bool(options.write_summary) and summary_root:
        summary_preview = os.path.join(summary_root, "<本次任务目录>", preview_name)
    if bool(options.write_archive) and archive_root:
        archive_rel_dir_preview = str(rendered.archive_rel_dir or "").strip()
        raw_app_no = str(parsed.meta.app_no or "").strip()
        if raw_app_no:
            masked_app_no = mask_app_no_for_preview(raw_app_no)
            if archive_rel_dir_preview == raw_app_no:
                archive_rel_dir_preview = masked_app_no
            elif raw_app_no in archive_rel_dir_preview:
                archive_rel_dir_preview = archive_rel_dir_preview.replace(raw_app_no, masked_app_no)
        archive_preview = os.path.join(archive_root, archive_rel_dir_preview, preview_name)
    return preview_name, summary_preview, archive_preview


def _official_docs_result_status_text(status: str) -> str:
    normalized = str(status or "").strip().lower()
    mapping = {
        "success": "处理成功",
        "skip": "已跳过",
        "fail": "处理失败",
    }
    return str(mapping.get(normalized, normalized or "-"))


def _build_official_docs_result_preview(
    *,
    preview_name: str,
    summary_preview: str,
    archive_preview: str,
    result_payload: dict[str, str] | None,
) -> tuple[str, str]:
    preview_parts = [
        "预计信息",
        f"预计输出 PDF 名称: {preview_name or '-'}",
        f"预计汇总路径: {summary_preview or '-'}",
        f"预计归档路径: {archive_preview or '-'}",
    ]

    error_text = ""
    if not isinstance(result_payload, dict):
        return "\n".join(preview_parts), error_text

    actual_output_name = str(result_payload.get("output_pdf_name", "") or "").strip()
    actual_summary_path = str(result_payload.get("summary_pdf_path", "") or "").strip()
    actual_archive_path = str(result_payload.get("archive_pdf_path", "") or "").strip()
    actual_reason = str(result_payload.get("reason", "") or "").strip()
    actual_status = _official_docs_result_status_text(result_payload.get("status", ""))

    result_parts = [
        "实际结果",
        f"处理状态: {actual_status or '-'}",
        f"实际输出 PDF 名称: {actual_output_name or '-'}",
        f"实际汇总路径: {actual_summary_path or '-'}",
        f"实际归档路径: {actual_archive_path or '-'}",
    ]
    if actual_reason:
        error_text = f"处理说明: {actual_reason}"
    return "\n".join(result_parts + ["", *preview_parts]), error_text


def _refresh_official_docs_detail(self) -> None:
    self._init_official_docs_state()
    selected_leaf_id = str(getattr(self, "_official_docs_selected_leaf_id", "") or "").strip()
    leaves = getattr(self, "_official_docs_leaves", {})
    leaf = leaves.get(selected_leaf_id) if isinstance(leaves, dict) else None

    current_label = getattr(self, "official_docs_current_label", None)
    meta_label = getattr(self, "official_docs_meta_label", None)
    pdf_sources_label = getattr(self, "official_docs_pdf_sources_text", None)
    preview_label = getattr(self, "official_docs_output_preview", None)
    error_label = getattr(self, "official_docs_validation_error", None)
    start_btn = getattr(self, "official_docs_start_button", None)

    if not isinstance(leaf, dict):
        if current_label is not None:
            current_label.setText("未选择通知书")
        if meta_label is not None:
            meta_label.setText("")
        if pdf_sources_label is not None:
            pdf_sources_label.setText("")
        if preview_label is not None:
            preview_label.setText("")
        if error_label is not None:
            error_label.setText("")
        if start_btn is not None:
            start_btn.setEnabled(False)
        return

    parsed = self._parse_official_docs_leaf_if_needed(selected_leaf_id)
    display_name = _leaf_display_name(leaf)
    if current_label is not None:
        current_label.setText(display_name)

    if parsed is None:
        if meta_label is not None:
            meta_label.setText("当前条目无法解析。")
        if pdf_sources_label is not None:
            pdf_sources_label.setText("")
        if preview_label is not None:
            preview_label.setText("")
        if error_label is not None:
            error_label.setText("该条目无法解析。")
        if start_btn is not None:
            start_btn.setEnabled(False)
        return

    meta_lines = [
        f"申请号: {parsed.meta.app_no or '-'}",
        f"通知书名称: {_canonical_notice_name_for_display(normalize_notice_name_for_meta(parsed.meta) or parsed.meta.notice_name) or '-'}",
        f"发文日: {parsed.meta.issue_date or parsed.meta.issue_date_raw or '-'}",
        f"内部编号: {parsed.meta.internal_no or '-'}",
        f"通知书代码: {parsed.meta.notice_code or '-'}",
    ]
    if meta_label is not None:
        meta_label.setText("\n".join(meta_lines))
    if pdf_sources_label is not None:
        pdf_sources_label.setText(_format_official_docs_pdf_sources(parsed))

    options = self._build_official_docs_options(use_saved=False)
    output_name = ""
    summary_preview = ""
    archive_preview = ""
    result_payload = leaf.get("last_result") if isinstance(leaf.get("last_result"), dict) else None
    try:
        output_name, summary_preview, archive_preview = self._build_preview_paths(parsed, options)
    except Exception:
        output_name = ""

    if preview_label is not None:
        preview_text, result_error_text = _build_official_docs_result_preview(
            preview_name=output_name,
            summary_preview=summary_preview,
            archive_preview=archive_preview,
            result_payload=result_payload,
        )
        preview_label.setText(preview_text)
    else:
        result_error_text = ""

    setting_errors = self._validate_official_docs_settings(self._get_official_docs_settings_snapshot(sync_current_type=True))
    parse_error_text = "; ".join(parsed.errors) if parsed.errors else ""
    merged_error = result_error_text or parse_error_text
    if not merged_error and not isinstance(result_payload, dict):
        merged_error = setting_errors[0] if setting_errors else ""
    if error_label is not None:
        error_label.setText(user_error_text(merged_error))

    if start_btn is not None:
        has_checked = any(True for _ in self._iter_checked_leaf_ids())
        start_btn.setEnabled(has_checked and not bool(setting_errors))

def _extract_pdf_to_temp(self, *, zip_path: str, source: PdfSource, preferred_stem: str = "") -> str | None:
    if not zip_path:
        return None
    try:
        with NoticeZipReader(zip_path) as reader:
            data = reader.read_bytes(source.raw_name)
            if str(getattr(source, "source_type", "pdf") or "pdf") == "image":
                data = image_bytes_to_pdf_bytes(data)
    except Exception:
        return None

    temp_root = self._ensure_official_docs_temp_root()
    stem = str(preferred_stem or "").strip()
    if not stem:
        stem = Path(str(source.display_name or source.raw_name or "notice")).stem
    stem = "".join([ch for ch in stem if ch not in '<>:"/\\|?*']).strip() or "notice"
    filename = f"{stem}_{abs(hash((zip_path, source.raw_name))) & 0xFFFFFFFF:08x}.pdf"
    out_path = os.path.join(temp_root, filename)
    try:
        with open(out_path, "wb") as file_obj:
            file_obj.write(data)
    except Exception:
        return None
    self._official_docs_temp_files.append(out_path)
    return out_path

def _open_pdf_source_for_leaf(self, leaf_id: str, source: PdfSource) -> bool:
    leaf = (getattr(self, "_official_docs_leaves", {}) or {}).get(leaf_id)
    if not isinstance(leaf, dict):
        return False
    zip_path = str(leaf.get("zip_path", "") or "").strip()
    out_path = self._extract_pdf_to_temp(zip_path=zip_path, source=source, preferred_stem=_leaf_display_name(leaf))
    if not out_path:
        return False
    try:
        os.startfile(out_path)
        return True
    except Exception:
        return False

