from __future__ import annotations

import os
import re
from dataclasses import dataclass

from core.config import sanitize_filename

from .field_governance import infer_patent_type_from_app_no
from .kind_detect import detect_notice_kind
from .models import NoticeKind, NoticeMeta, ProcessOptions


class TemplateRenderError(ValueError):
    pass


_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
_APPLICANT_TAIL_KEYS: tuple[str, ...] = (
    "SHENQINGREN",
    "SHENQINGRMC",
    "SHENQINGRXM",
    "APPLICANT",
    "申请人",
    "申请人信息",
    "专利权人",
    "复审请求人",
)


KNOWN_TOKENS: set[str] = {
    "申请号",
    "申请号带点",
    "通知书名称",
    "发明名称",
    "申请人信息",
    "通知书代码",
    "发文日",
    "发文日8",
    "内部编号",
    "逾期日",
    "期限天",
    "发文序号",
    "案卷号",
    "申请日",
    "通知书类型",
    "通知书类别",
    "次数",
    "专利类型",
}


def extract_tokens(template: str) -> set[str]:
    if not template:
        return set()
    return {match.group(1).strip() for match in _TOKEN_RE.finditer(str(template)) if str(match.group(1) or "").strip()}


def validate_template(template: str, *, known: set[str] | None = None) -> list[str]:
    known_set = KNOWN_TOKENS if known is None else set(known)
    unknown: list[str] = []
    for token in sorted(extract_tokens(template)):
        if token not in known_set:
            unknown.append(token)
    return unknown


def _normalize_yyyymmdd(raw: str) -> tuple[str, str]:
    digits = re.sub(r"[^0-9]", "", str(raw or "").strip())
    if len(digits) >= 8:
        y, m, d = digits[0:4], digits[4:6], digits[6:8]
        return f"{y}-{m}-{d}", f"{y}{m}{d}"
    return "", digits


def _derive_app_no_dotted(app_no: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(app_no or "").strip())
    if len(digits) >= 13:
        return f"{digits[:12]}.{digits[12]}"
    return ""


def _normalize_applicant_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip(" ;；,，")
    return text


def _field_key_tail(raw_key: str) -> str:
    key = str(raw_key or "").strip().upper()
    if not key:
        return ""
    tail = key.split("/")[-1]
    tail = tail.split("@")[0]
    if "[" in tail:
        tail = tail.split("[", 1)[0]
    return tail


def _extract_applicant_from_fields(
    fields: dict[str, str],
    *,
    flat_fields: dict[str, str] | None = None,
) -> str:
    direct_keys = (
        "SHENQINGREN",
        "SHENQINGRMC",
        "SHENQINGRXM",
        "APPLICANT",
        "申请人",
        "申请人信息",
        "专利权人",
        "复审请求人",
    )
    for key in direct_keys:
        value = _normalize_applicant_text(str((fields or {}).get(key, "") or ""))
        if value:
            return value

    for raw_key, raw_value in (flat_fields or {}).items():
        key_text = str(raw_key or "").strip()
        value = _normalize_applicant_text(str(raw_value or ""))
        if not key_text or not value:
            continue
        tail = _field_key_tail(key_text)
        if tail in _APPLICANT_TAIL_KEYS:
            return value
    return ""


def _collapse_separators(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"_+", "_", value)
    value = re.sub(r"-+", "-", value)
    value = re.sub(r"\++", "+", value)
    value = re.sub(r"\(\s*[_\-\+ ]*\s*\)", "", value)
    value = re.sub(r"\[\s*[_\-\+ ]*\s*\]", "", value)
    value = re.sub(r"{\s*[_\-\+ ]*\s*}", "", value)
    return value.strip(" _-.+") or ""


def _sanitize_piece(text: str, *, fallback: str) -> str:
    cleaned = sanitize_filename(text)
    cleaned = _collapse_separators(cleaned)
    return cleaned or str(fallback or "output")


def _render_tokens(template: str, values: dict[str, str]) -> str:
    src = str(template or "")

    def _replace(match: re.Match) -> str:
        key = str(match.group(1) or "").strip()
        return str(values.get(key, ""))

    return _TOKEN_RE.sub(_replace, src)


def _ensure_relative_path(rendered: str) -> None:
    value = str(rendered or "").strip()
    if not value:
        return
    if value.startswith(("/", "\\")) or value.startswith("\\\\"):
        raise TemplateRenderError("归档目录模板渲染结果必须是相对路径")
    if re.match(r"^[A-Za-z]:", value):
        raise TemplateRenderError("归档目录模板渲染结果不能包含盘符")


@dataclass(frozen=True)
class RenderedPaths:
    output_pdf_name: str
    archive_rel_dir: str


def build_meta_from_list_fields(
    fields: dict[str, str],
    *,
    notice_round: str = "",
    flat_fields: dict[str, str] | None = None,
) -> NoticeMeta:
    code = str(fields.get("TONGZHISBM", "") or "").strip()
    name = str(fields.get("TONGZHISMC", "") or "").strip()
    invention_name = str(fields.get("FAMINGMC", "") or "").strip()
    app_no = str(fields.get("SHENQINGH", "") or "").strip()
    _type_code, type_label = infer_patent_type_from_app_no(app_no)
    issue_raw = str(fields.get("FAWENR", "") or "").strip()
    issue_date, issue_date8 = _normalize_yyyymmdd(issue_raw)
    apply_raw = str(fields.get("SHENQINGR", "") or "").strip()
    apply_date, _ = _normalize_yyyymmdd(apply_raw)
    applicant = _extract_applicant_from_fields(fields, flat_fields=flat_fields)
    return NoticeMeta(
        notice_code=code,
        notice_name=name,
        invention_name=invention_name,
        notice_round=str(notice_round or "").strip(),
        app_no=app_no,
        app_no_dotted=_derive_app_no_dotted(app_no),
        issue_date_raw=issue_raw,
        issue_date=issue_date,
        issue_date8=issue_date8,
        internal_no=str(fields.get("NEIBUBH", "") or "").strip(),
        due_date=str(fields.get("YUQIRQ", "") or "").strip(),
        limit_days=str(fields.get("QIXIAN", "") or "").strip(),
        doc_serial=str(fields.get("FAWENXLH", "") or "").strip(),
        dossier_no=str(fields.get("ANJUANH", "") or "").strip(),
        patent_type=type_label,
        apply_date=apply_date,
        applicant=applicant,
    )


def compute_notice_category(
    *,
    notice_kind: NoticeKind,
    kind_text: str,
    meta: NoticeMeta,
    options: ProcessOptions,
) -> str:
    mode = str(options.category_mode or "full_name").strip()
    if mode == "short_kind":
        return kind_text

    if mode == "custom":
        if notice_kind == "exam_opinion":
            template = str(options.category_template_exam_opinion or "").strip()
        elif notice_kind == "rectification":
            template = str(options.category_template_rectification or "").strip()
        else:
            template = ""

        if template:
            values = {
                "次数": meta.notice_round,
                "通知书类型": kind_text,
                "通知书名称": meta.notice_name,
                "发明名称": meta.invention_name,
                "通知书代码": meta.notice_code,
                "申请号": meta.app_no,
                "申请号带点": meta.app_no_dotted,
                "发文日": meta.issue_date,
                "发文日8": meta.issue_date8,
                "申请人信息": meta.applicant,
                "内部编号": meta.internal_no,
                "逾期日": meta.due_date,
                "期限天": meta.limit_days,
                "发文序号": meta.doc_serial,
                "案卷号": meta.dossier_no,
                "申请日": meta.apply_date,
                "专利类型": meta.patent_type,
            }
            rendered = _render_tokens(template, values)
            return _sanitize_piece(rendered, fallback=kind_text or meta.notice_name or "分类")

        return meta.notice_name or kind_text

    return meta.notice_name or kind_text


def render_output_paths(
    *,
    notice_kind: NoticeKind,
    meta: NoticeMeta,
    options: ProcessOptions,
) -> RenderedPaths:
    _kind, kind_text, round_text = detect_notice_kind(meta.notice_name)
    if not meta.notice_round:
        meta = NoticeMeta(**{**meta.__dict__, "notice_round": round_text})

    category = compute_notice_category(notice_kind=notice_kind, kind_text=kind_text, meta=meta, options=options)

    filename_template = str(
        (options.filename_template_by_kind or {}).get(str(notice_kind or "").strip(), options.filename_template) or ""
    ).strip()
    archive_dir_template = str(
        (options.archive_dir_template_by_kind or {}).get(str(notice_kind or "").strip(), options.archive_dir_template) or ""
    ).strip()
    if not filename_template:
        filename_template = options.filename_template
    if not archive_dir_template:
        archive_dir_template = options.archive_dir_template

    values = {
        "申请号": meta.app_no,
        "申请号带点": meta.app_no_dotted,
        "通知书名称": meta.notice_name,
        "发明名称": meta.invention_name,
        "申请人信息": meta.applicant,
        "通知书代码": meta.notice_code,
        "发文日": meta.issue_date,
        "发文日8": meta.issue_date8,
        "内部编号": meta.internal_no,
        "逾期日": meta.due_date,
        "期限天": meta.limit_days,
        "发文序号": meta.doc_serial,
        "案卷号": meta.dossier_no,
        "申请日": meta.apply_date,
        "通知书类型": kind_text,
        "通知书类别": category,
        "次数": meta.notice_round,
        "专利类型": meta.patent_type,
    }

    unknown_name = validate_template(filename_template)
    if unknown_name:
        raise TemplateRenderError(f"文件名模板包含未知字段：{', '.join(unknown_name)}")
    unknown_dir = validate_template(archive_dir_template)
    if unknown_dir:
        raise TemplateRenderError(f"归档目录模板包含未知字段：{', '.join(unknown_dir)}")

    name_rendered = _render_tokens(filename_template, values)
    name_clean = _sanitize_piece(name_rendered, fallback=meta.app_no or meta.notice_code or "output")
    output_pdf_name = f"{name_clean}.pdf"

    dir_rendered = _render_tokens(archive_dir_template, values)
    _ensure_relative_path(dir_rendered)
    segs = [seg for seg in re.split(r"[\\/]+", str(dir_rendered or "")) if str(seg or "").strip()]
    segs_clean = [_sanitize_piece(seg, fallback="归档") for seg in segs]
    archive_rel_dir = os.path.join(*segs_clean) if segs_clean else ""

    return RenderedPaths(output_pdf_name=output_pdf_name, archive_rel_dir=archive_rel_dir)


__all__ = [
    "KNOWN_TOKENS",
    "RenderedPaths",
    "TemplateRenderError",
    "build_meta_from_list_fields",
    "compute_notice_category",
    "extract_tokens",
    "render_output_paths",
    "validate_template",
]
