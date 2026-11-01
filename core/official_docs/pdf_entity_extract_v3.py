from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import fitz

from .field_governance import infer_patent_type_from_app_no
from .resource_mirror import get_resource_mirror_paths, sync_embedded_resource_to_mirror

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    _CV2_AVAILABLE = True
except Exception:
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False


_RESOURCE_FILE = "official_doc_pdf_field_matrix.json"


@dataclass(frozen=True)
class PdfFieldMatrixHealth:
    healthy: bool
    source: str
    path: str
    warning: str
    error: str
    embedded_path: str
    mirror_path: str


_MATRIX_HEALTH = PdfFieldMatrixHealth(
    healthy=False,
    source="uninitialized",
    path="",
    warning="",
    error="matrix not loaded",
    embedded_path="",
    mirror_path="",
)


def clear_pdf_field_matrix_cache() -> None:
    _load_matrix.cache_clear()
    global _MATRIX_HEALTH
    _MATRIX_HEALTH = PdfFieldMatrixHealth(
        healthy=False,
        source="uninitialized",
        path="",
        warning="",
        error="matrix not loaded",
        embedded_path="",
        mirror_path="",
    )

_FIELD_ALL: tuple[str, ...] = (
    "department",
    "center",
    "applicant",
    "inventor",
    "agent",
    "agency_raw",
    "examiner",
    "examiner_phone",
    "panel_head",
    "panel_main",
    "panel_member",
    "reject_reason",
    "prior_art",
    "dossier_no",
    "authorization_pub_no",
    "authorization_pub_date",
    "certificate_no",
    "qrcode_link",
    "qrcode_image",
)

_LABEL_APPLICANT = "申请人"
_LABEL_OWNER = "专利权人"
_LABEL_REQUESTER = "请求人"
_LABEL_REEXAM_REQUESTER = "复审请求人"
_LABEL_INVENTOR = "发明人"
_LABEL_DESIGNER = "设计人"
_LABEL_DEPARTMENT = "审查部门"
_LABEL_AGENCY = "代理机构"
_LABEL_PATENT_AGENCY = "专利代理机构"
_LABEL_PATENT_AGENCY_NAME = "专利代理机构名称"
_LABEL_AGENCY_NAME = "代理机构名称"
_LABEL_AGENT = "代理人"
_LABEL_AGENT_ALT = "代理师"
_LABEL_EXAMINER = "审查员"
_LABEL_EXAMINER_NAME = "审查员名称"
_LABEL_EXAMINER_FULL_NAME = "审查员姓名"
_LABEL_EXAMINER_PHONE = "审查员电话"
_LABEL_PHONE = "电话"
_LABEL_PANEL_HEAD = "合议组组长"
_LABEL_PANEL_MAIN = "主审员"
_LABEL_PANEL_MEMBER = "参审员"
_LABEL_DOSSIER_NO = "申请方案卷号"
_LABEL_AUTHORIZATION_PUB_NO = "授权公告号"
_LABEL_AUTHORIZATION_PUB_DATE = "授权公告日"
_LABEL_CERTIFICATE_NO = "证书号"
_LABEL_APP_NO = "申请号"
_LABEL_APP_NO_OR_PATENT_NO = "申请号或专利号"

_CN_PUB_RE = re.compile(r"CN\s*\d{6,12}(?:\.[0-9A-Z]+|[A-Z][0-9]?)?", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?86[-\s]?)?(?:0\d{2,3}[-\s]?)?\d{7,11}")
_CERT_NO_RE = re.compile(r"证书号\s*(?:[:：])?\s*(第?[A-Za-z0-9\-]+号?)")
_REJECT_REASON_LINE_RE = re.compile(
    r"^[（(]?[一二三四五六七八九十\d]*[)）]?\s*权利要求\s*[0-9０-９一二三四五六七八九十,，、\-—~至]+\s*.*(?:不符合专利法|不具备专利法|不具备创造性)"
)
_REJECT_CLAIM_NO_RE = re.compile(r"权利要求\s*([0-9０-９一二三四五六七八九十,，、\-—~至]+)")
_CHECKED_MARKERS: tuple[str, ...] = ("☒", "☑", "✓", "✔", "√", "✗", "×", "☓")
_UNCHECKED_MARKERS: tuple[str, ...] = ("☐", "□")
_GENERIC_LABEL_LINE_RE = re.compile(r"^\s*[A-Za-z0-9\u4e00-\u9fff（）()]{2,20}\s*[:：]\s*")

_APPLICANT_START_LABELS: tuple[str, ...] = (
    f"{_LABEL_APPLICANT}或{_LABEL_OWNER}",
    f"{_LABEL_APPLICANT}或{_LABEL_REQUESTER}",
    _LABEL_APPLICANT,
    _LABEL_OWNER,
    _LABEL_REEXAM_REQUESTER,
)
_APPLICANT_END_LABELS: tuple[str, ...] = (
    _LABEL_INVENTOR,
    _LABEL_DESIGNER,
    "发明名称",
    "发明创造名称",
    "地址",
    "邮编",
    "国籍",
    "联系人",
    _LABEL_PHONE,
    _LABEL_PATENT_AGENCY_NAME,
    _LABEL_PATENT_AGENCY,
    _LABEL_AGENCY,
    "代理人",
    _LABEL_EXAMINER,
    _LABEL_EXAMINER_PHONE,
    _LABEL_APP_NO,
    _LABEL_APP_NO_OR_PATENT_NO,
    "国际申请号",
    "国际申请日",
    "档案号",
    "答复期限",
    "缴费期限",
    "优先权日",
    "案卷号",
    _LABEL_DOSSIER_NO,
    "发文日",
    _LABEL_AUTHORIZATION_PUB_NO,
    _LABEL_AUTHORIZATION_PUB_DATE,
    _LABEL_CERTIFICATE_NO,
    _LABEL_PANEL_HEAD,
    _LABEL_PANEL_MAIN,
    _LABEL_PANEL_MEMBER,
)

_AGENCY_START_LABELS: tuple[str, ...] = (
    _LABEL_PATENT_AGENCY_NAME,
    _LABEL_AGENCY_NAME,
    _LABEL_PATENT_AGENCY,
    _LABEL_AGENCY,
)
_AGENCY_END_LABELS: tuple[str, ...] = (
    "代理人",
    _LABEL_EXAMINER,
    _LABEL_EXAMINER_PHONE,
    "联系电话",
    _LABEL_PHONE,
    "地址",
    "邮编",
    "联系人",
    _LABEL_APP_NO,
    _LABEL_APP_NO_OR_PATENT_NO,
    "案卷号",
    _LABEL_DOSSIER_NO,
    "发文日",
    _LABEL_AUTHORIZATION_PUB_NO,
    _LABEL_AUTHORIZATION_PUB_DATE,
    _LABEL_CERTIFICATE_NO,
    _LABEL_PANEL_HEAD,
    _LABEL_PANEL_MAIN,
    _LABEL_PANEL_MEMBER,
    "驳回理由",
    "对比文件",
)
_AGENCY_HEADER_STOP_MARKERS: tuple[str, ...] = (
    _LABEL_APP_NO,
    _LABEL_APP_NO_OR_PATENT_NO,
    "申请人或专利权人",
    _LABEL_APPLICANT,
    _LABEL_OWNER,
    _LABEL_INVENTOR,
    _LABEL_DESIGNER,
)
_AGENT_END_LABELS: tuple[str, ...] = (
    _LABEL_EXAMINER,
    _LABEL_EXAMINER_PHONE,
    "联系电话",
    _LABEL_PHONE,
    "地址",
    "邮编",
    "联系人",
    _LABEL_APP_NO,
    _LABEL_APP_NO_OR_PATENT_NO,
    "案卷号",
    _LABEL_DOSSIER_NO,
    "发文日",
    _LABEL_AUTHORIZATION_PUB_NO,
    _LABEL_AUTHORIZATION_PUB_DATE,
    _LABEL_CERTIFICATE_NO,
    _LABEL_PANEL_HEAD,
    _LABEL_PANEL_MAIN,
    _LABEL_PANEL_MEMBER,
    "驳回理由",
    "对比文件",
)
_APPLICANT_NOISE_TOKENS: tuple[str, ...] = (
    "档案号",
    "国际申请号",
    "国际申请日",
    "答复期限",
    "缴费期限",
    "优先权日",
    "后续行为",
    "重要通知",
    "全部规定费用",
    "未缴纳规定的费用",
    "复审通知书",
    "复审决定书",
    "第3项",
    "第2项",
)
_AGENCY_BODY_NOISE_TOKENS: tuple[str, ...] = (
    "委托书",
    "当事人",
    "口头审理",
    "办理系统",
    "提交",
    "会晤",
    "应当",
    "不得",
)
_EXAMINER_NOISE_TOKENS: tuple[str, ...] = (
    "认为",
    "对上述",
    "通知书",
    "申请人",
    "复审请求人",
    "权利要求",
    "不具备",
    "不符合",
    "意见陈述",
)
_DOC_TITLE_LINE_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9（）()·\-]{4,40}(?:通知书|决定书|结案通知书|请求书|回执)$")
_KNOWN_CITY_PREFIX: tuple[tuple[str, str], ...] = (
    ("北京市", "北京"),
    ("上海市", "上海"),
    ("天津市", "天津"),
    ("重庆市", "重庆"),
    ("广州市", "广州"),
    ("深圳市", "深圳"),
    ("杭州市", "杭州"),
    ("南京市", "南京"),
    ("西安市", "西安"),
    ("武汉市", "武汉"),
    ("成都市", "成都"),
)


@dataclass(frozen=True)
class PdfEntityExtractResult:
    status: str = "失败"
    error: str = ""
    applicable_fields: tuple[str, ...] = field(default_factory=tuple)
    department: str = ""
    center: str = ""
    applicant: str = ""
    inventor: str = ""
    agent: str = ""
    agency_raw: str = ""
    examiner: str = ""
    examiner_phone: str = ""
    panel_head: str = ""
    panel_main: str = ""
    panel_member: str = ""
    reject_reason: str = ""
    prior_art: str = ""
    dossier_no: str = ""
    authorization_pub_no: str = ""
    authorization_pub_date: str = ""
    certificate_no: str = ""
    qrcode_link: str = ""
    qrcode_image_bytes: bytes = b""
    evidence: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _ExtractedValue:
    value: str = ""
    evidence: str = ""
    image_bytes: bytes = b""


def _normalize_text_line(line: str) -> str:
    text = str(line or "").replace("\u3000", " ").replace("\uff1a", ":")
    text = text.replace("\r", " ").replace("\t", " ").strip()
    return re.sub(r"\s+", " ", text)


def _compact_text(text: str) -> str:
    src = str(text or "").replace("\u3000", " ").replace("\uff1a", ":").strip()
    return re.sub(r"\s+", "", src)


def _notice_code_from_key(notice_key: str) -> str:
    src = str(notice_key or "").strip()
    if "|" not in src:
        return src
    return str(src.split("|", 1)[0] or "").strip()


def _dedup_join(values: list[str], sep: str = ";") -> str:
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = str(item or "").strip()
        if not value:
            continue
        key = _compact_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return sep.join(out)


def _split_by_labels(text: str, labels: list[str]) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    compact = _compact_text(value)
    for label in labels:
        mark = _compact_text(label) + ":"
        if not mark:
            continue
        index = compact.find(mark)
        if index <= 0:
            continue
        compact = compact[:index]
    return compact.strip(" :,，；")


def _extract_after_labels(line: str, labels: list[str], next_labels: list[str] | None = None) -> str:
    return _extract_after_labels_with_options(line, labels, next_labels=next_labels, require_delimiter_labels=None)


def _extract_after_labels_with_options(
    line: str,
    labels: list[str],
    *,
    next_labels: list[str] | None = None,
    require_delimiter_labels: set[str] | None = None,
) -> str:
    normalized = _normalize_text_line(line)
    if not normalized:
        return ""
    next_list = [str(item or "").strip() for item in (next_labels or []) if str(item or "").strip()]
    strict_labels = {str(item or "").strip() for item in (require_delimiter_labels or set()) if str(item or "").strip()}

    for label in labels:
        lab = str(label or "").strip()
        if not lab:
            continue
        if lab in strict_labels:
            pattern = re.compile(re.escape(lab) + r"\s*[:：]\s*(.+)")
        else:
            pattern = re.compile(re.escape(lab) + r"\s*[:：]?\s*(.+)")
        matched = pattern.search(normalized)
        if matched:
            raw_value = str(matched.group(1) or "").strip()
            value = _split_by_labels(raw_value, next_list)
            if value:
                return value

    compact = _compact_text(normalized)
    for label in labels:
        base = _compact_text(label)
        if not base:
            continue
        marks = [base + ":"]
        if str(label or "").strip() not in strict_labels:
            marks.append(base)
        for mark in marks:
            index = compact.find(mark)
            if index < 0:
                continue
            raw_value = compact[index + len(mark) :]
            value = _split_by_labels(raw_value, next_list)
            if value:
                return value
    return ""


def _first_labeled_value(
    lines: list[str],
    *,
    labels: list[str],
    next_labels: list[str] | None = None,
    reject_line_contains: tuple[str, ...] = (),
    reject_value_contains: tuple[str, ...] = (),
    require_delimiter_labels: tuple[str, ...] = (),
) -> _ExtractedValue:
    strict_labels = {str(item or "").strip() for item in require_delimiter_labels if str(item or "").strip()}
    for line in lines:
        if any(keyword in line for keyword in reject_line_contains):
            continue
        value = _extract_after_labels_with_options(
            line,
            labels,
            next_labels=next_labels,
            require_delimiter_labels=strict_labels,
        )
        if not value:
            continue
        if any(keyword in value for keyword in reject_value_contains):
            continue
        return _ExtractedValue(value=value, evidence=line)
    return _ExtractedValue()


def _normalize_anchor_value(text: str) -> str:
    src = str(text or "").replace("\u3000", " ")
    src = re.sub(r"[ \t\r\n]+", " ", src).strip()
    return src


def _is_notice_title_line(line: str) -> bool:
    src = _normalize_anchor_value(line)
    if not src:
        return False
    compact = re.sub(r"\s+", "", src)
    return bool(_DOC_TITLE_LINE_RE.match(compact))


def _find_anchor(line: str, labels: tuple[str, ...], *, require_delimiter: bool) -> tuple[str, str] | None:
    src = str(line or "")
    for label in labels:
        if require_delimiter:
            matched = re.search(re.escape(label) + r"\s*[:：]\s*(.*)$", src)
            if matched:
                return label, str(matched.group(1) or "")
            continue
        matched = re.search(re.escape(label) + r"\s*[:：]?\s*(.*)$", src)
        if not matched:
            continue
        # no-delimiter fallback only accepts near-start label to avoid sentence false positives
        prefix = src[: matched.start()]
        if _normalize_anchor_value(prefix):
            continue
        return label, str(matched.group(1) or "")
    return None


def _find_first_end_pos(line: str, end_labels: tuple[str, ...]) -> int | None:
    best: int | None = None
    for label in end_labels:
        for pattern in (
            re.compile(re.escape(label) + r"\s*[:：]"),
            re.compile(r"^\s*" + re.escape(label) + r"\s*(?:[:：]\s*|\s+|$)"),
        ):
            matched = pattern.search(line)
            if not matched:
                continue
            if best is None or matched.start() < best:
                best = matched.start()
    return best


def _collect_anchor_chunks(
    lines: list[str],
    *,
    start_idx: int,
    start_rest: str,
    end_labels: tuple[str, ...],
    fallback_max_lines: int,
) -> str:
    chunks: list[str] = []
    rest = _normalize_anchor_value(start_rest)
    if rest:
        chunks.append(rest)

    consumed = 0
    for idx in range(start_idx + 1, len(lines)):
        consumed += 1
        line = _normalize_anchor_value(lines[idx])
        if not line:
            continue

        end_pos = _find_first_end_pos(line, end_labels)
        if end_pos is not None:
            head = line[:end_pos].strip()
            if head:
                chunks.append(head)
            break

        if chunks and _is_notice_title_line(line):
            break

        if chunks and _GENERIC_LABEL_LINE_RE.match(line):
            break

        chunks.append(line)
        if consumed >= fallback_max_lines:
            break

    return _normalize_anchor_value(" ".join(chunks))


def _extract_by_positional_anchors(
    lines: list[str],
    *,
    start_labels: tuple[str, ...],
    end_labels: tuple[str, ...],
    fallback_max_lines: int = 8,
    allow_no_delimiter: bool = True,
) -> _ExtractedValue:
    for require_delimiter in ((True, False) if allow_no_delimiter else (True,)):
        for idx, raw in enumerate(lines):
            hit = _find_anchor(raw, start_labels, require_delimiter=require_delimiter)
            if hit is None:
                continue
            _label, start_rest = hit
            value = _collect_anchor_chunks(
                lines,
                start_idx=idx,
                start_rest=start_rest,
                end_labels=end_labels,
                fallback_max_lines=fallback_max_lines,
            )
            if not value:
                continue
            evidence = _normalize_anchor_value(lines[idx] if idx < len(lines) else "")
            return _ExtractedValue(value=value, evidence=evidence)
    return _ExtractedValue()


def _is_applicant_noise_candidate(value: str) -> bool:
    src = _normalize_anchor_value(value)
    if not src:
        return True
    compact = _compact_text(src)
    if not compact:
        return True
    if compact.startswith("或代理人的档案号") or compact.startswith("申请人或代理人的档案号"):
        return True
    if any(mark in src for mark in _CHECKED_MARKERS):
        return True
    if any(token in src for token in _APPLICANT_NOISE_TOKENS):
        return True
    if ("申请号" in src) and ("申请日" in src):
        return True
    if (len(compact) > 90) and any(token in src for token in ("申请号", "地址", "电话", "优先权日")):
        return True
    return False


def _trim_applicant_tail(value: str) -> str:
    src = _normalize_anchor_value(value)
    if not src:
        return ""
    patterns = (
        r"\s+地\s*址\s*[:：]",
        r"\s+发\s*明\s*人\s*[:：]",
        r"\s+发\s*明\s*名\s*称\s*(?:[:：]|$)",
        r"\s+发\s*明\s*创\s*造\s*名\s*称\s*(?:[:：]|$)",
        r"\s+设\s*计\s*人\s*[:：]",
        r"\s+专\s*利\s*号\s*[:：]",
        r"\s+按\s*照\s*条\s*约\s*第\s*\d+\s*条.*$",
        r"\s+兹\s*通\s*知\s*申\s*请\s*人.*$",
        r"\s+通\s*知\s*申\s*请\s*人.*$",
        r"\s+复\s*审\s*(?:通\s*知\s*书|决\s*定\s*书)",
        r"\s+延\s*长\s*期\s*限\s*审\s*批\s*通\s*知\s*书",
        r"\s+第\s*\d[\d\s]{2,}\s*号",
    )
    cut_pos = len(src)
    for pattern in patterns:
        matched = re.search(pattern, src)
        if not matched:
            continue
        if matched.start() < cut_pos:
            cut_pos = matched.start()
    trimmed = src[:cut_pos]
    return _normalize_anchor_value(trimmed).strip("：:，,；;")


def _normalize_applicant_entities(value: str) -> str:
    src = _normalize_anchor_value(value)
    if not src:
        return ""
    if re.search(r"[；;,，、]", src):
        return src
    matched = re.match(
        r"^\s*(.+?(?:大学|学院|研究院|研究所|医院|中心|学校|委员会|集团|有限责任公司|有限公司|公司|事务所))\s+"
        r"(.+?(?:大学|学院|研究院|研究所|医院|中心|学校|委员会|集团|有限责任公司|有限公司|公司|事务所))\s*$",
        src,
    )
    if not matched:
        return src
    left = _normalize_anchor_value(str(matched.group(1) or ""))
    right = _normalize_anchor_value(str(matched.group(2) or ""))
    if (not left) or (not right):
        return src
    return f"{left}；{right}"


def _extract_applicant_or_owner(lines: list[str]) -> _ExtractedValue:
    for require_delimiter in (True, False):
        for idx, raw in enumerate(lines):
            hit = _find_anchor(raw, _APPLICANT_START_LABELS, require_delimiter=require_delimiter)
            if hit is None:
                continue
            _label, start_rest = hit
            candidate = _collect_anchor_chunks(
                lines,
                start_idx=idx,
                start_rest=start_rest,
                end_labels=_APPLICANT_END_LABELS,
                fallback_max_lines=8,
            )
            candidate = _trim_applicant_tail(candidate)
            if (not candidate) or _is_applicant_noise_candidate(candidate):
                continue
            candidate = _normalize_applicant_entities(candidate)
            return _ExtractedValue(
                value=_normalize_anchor_value(candidate),
                evidence=_normalize_anchor_value(lines[idx] if idx < len(lines) else ""),
            )
    return _ExtractedValue()


def _normalize_multi_value_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("；", "，").replace(";", "，").replace("、", "，").replace(",", "，")
    text = re.sub(r"\s{2,}", "，", text)
    return text


def _normalize_person_values(value: str) -> str:
    text = _normalize_multi_value_text(value)
    if not text:
        return ""
    parts = [part.strip() for part in text.split("，") if part.strip()]
    return _dedup_join(parts, sep="，")


def _is_agent_context_stop_line(line: str) -> bool:
    src = _normalize_anchor_value(line)
    if not src:
        return False
    stop_tokens = (
        "发文日",
        "申请号",
        "专利号",
        "案卷号",
        "申请人",
        "专利权人",
        "复审请求人",
        "发明人",
        "设计人",
        "审查员",
        "审查部门",
        "联系电话",
        "地址",
        "邮编",
        "自动受理",
    )
    if any(token in src for token in stop_tokens):
        return True
    return bool(_GENERIC_LABEL_LINE_RE.match(src))


def _extract_agent_tail_after_agency(line: str, agency_value: str) -> str:
    src = _normalize_anchor_value(line)
    if not src:
        return ""
    probe_agencies = [_normalize_anchor_value(agency_value), _cleanup_agency_candidate(src)]
    compact_src = _compact_text(src)
    for agency in probe_agencies:
        if not agency:
            continue
        index = src.find(agency)
        if index >= 0:
            return src[index + len(agency) :].strip()
        compact_agency = _compact_text(agency)
        if not compact_agency:
            continue
        compact_index = compact_src.find(compact_agency)
        if compact_index >= 0:
            return compact_src[compact_index + len(compact_agency) :].strip()
    return ""


def _extract_agent_names_from_context(raw: str) -> str:
    text = _normalize_anchor_value(raw)
    if (not text) or _is_agent_context_stop_line(text):
        return ""
    text = re.sub(_PHONE_RE, "", text)
    text = re.sub(r"[（(][^()（）]{0,40}[)）]", "", text)
    text = re.sub(r"(联系人|联系电话|电话)\s*[:：]?\s*.*$", "", text)
    text = text.strip(" :：，,；;、()（）")
    if (not text) or any(mark in text for mark in ("。", "？", "！", ":", "：", ";")):
        return ""

    tokens = re.split(r"[，,、/；;\s]+", text)
    names: list[str] = []
    for token in tokens:
        candidate = str(token or "").strip(" :：，,；;、()（）")
        if not candidate:
            continue
        if re.search(r"\d", candidate):
            continue
        if any(mark in candidate for mark in ("公司", "事务所", "代理", "专利", "知识产权", "大学", "学院", "研究", "医院", "中心", "酒店", "大街", "街道", "路", "号", "室", "邮编", "地址", "自动受理")):
            continue
        if not re.fullmatch(r"[A-Za-z\u4e00-\u9fff·]{2,16}", candidate):
            continue
        names.append(candidate)
    return _normalize_person_values("，".join(names))


def _extract_agent_from_agency_context(lines: list[str], agency_hit: _ExtractedValue) -> _ExtractedValue:
    if not agency_hit.value:
        return _ExtractedValue()

    evidence = _normalize_anchor_value(agency_hit.evidence)
    agency_value = _normalize_anchor_value(agency_hit.value)
    anchor_index: int | None = None
    if evidence:
        for idx, raw in enumerate(lines):
            if _normalize_anchor_value(raw) == evidence:
                anchor_index = idx
                break
    if anchor_index is None and agency_value:
        compact_agency = _compact_text(agency_value)
        for idx, raw in enumerate(lines):
            if compact_agency and compact_agency in _compact_text(raw):
                anchor_index = idx
                break
    if anchor_index is None:
        return _ExtractedValue()

    current_line = _normalize_anchor_value(lines[anchor_index])
    same_line_value = _extract_agent_names_from_context(_extract_agent_tail_after_agency(current_line, agency_value))
    if same_line_value:
        return _ExtractedValue(value=same_line_value, evidence=current_line)

    seen_non_empty = 0
    for probe in range(anchor_index + 1, len(lines)):
        candidate_line = _normalize_anchor_value(lines[probe])
        if not candidate_line:
            continue
        if _is_agent_context_stop_line(candidate_line):
            break
        seen_non_empty += 1
        candidate_value = _extract_agent_names_from_context(candidate_line)
        if candidate_value:
            return _ExtractedValue(value=candidate_value, evidence=candidate_line)
        if seen_non_empty >= 2:
            break
    return _ExtractedValue()


def _extract_agent(lines: list[str], agency_hit: _ExtractedValue | None = None) -> _ExtractedValue:
    labels = [_LABEL_AGENT, _LABEL_AGENT_ALT]
    reject_line_contains = (
        "申请人和/或代理师不得",
        "申请人和/或代理人不得",
        "未经预约",
    )
    hit = _first_labeled_value(
        lines,
        labels=labels,
        next_labels=list(_AGENT_END_LABELS),
        reject_line_contains=reject_line_contains,
        reject_value_contains=("不得", "会晤", "办理系统", "提交"),
        require_delimiter_labels=tuple(labels),
    )
    value = _normalize_person_values(hit.value)
    value = re.sub(r"(联系电话|电话)\s*[:：].*$", "", value).strip(" :：，,；;")
    if value:
        return _ExtractedValue(value=value, evidence=hit.evidence)
    if agency_hit is not None:
        fallback = _extract_agent_from_agency_context(lines, agency_hit)
        if fallback.value:
            return fallback
    return _ExtractedValue()


def _cleanup_agency_candidate(raw_line: str) -> str:
    text = _normalize_anchor_value(raw_line)
    if not text:
        return ""
    for label in _AGENCY_START_LABELS:
        text = re.sub(r"^\s*" + re.escape(label) + r"\s*[:：]?\s*", "", text)
    text = re.sub(r"^\s*名\s*称\s*[:：]\s*", "", text)
    # Trim trailing contact like "张三(010-12345678)" or similar variants.
    text = re.sub(r"\s+\S{1,16}\(\s*\d[\d\-\s]{5,}\)\s*$", "", text)
    text = re.sub(r"\s*(联系人|联系电话|电话)\s*[:：].*$", "", text)
    return _normalize_anchor_value(text).strip("：:，,；;")


def _is_agency_noise_candidate(value: str) -> bool:
    src = _normalize_anchor_value(value)
    if not src:
        return True
    compact = _compact_text(src)
    if not compact:
        return True
    if ("代理" not in compact) and ("事务所" not in compact):
        return True
    if any(token in compact for token in _AGENCY_BODY_NOISE_TOKENS):
        return True
    if any(token in src for token in ("。", "？", "！")):
        return True
    return False


def _score_agency_candidate(value: str) -> int:
    if _is_agency_noise_candidate(value):
        return -10**6
    compact = _compact_text(value)
    score = min(len(compact), 90)
    if "专利代理" in compact:
        score += 80
    if "知识产权" in compact:
        score += 40
    if compact.endswith(
        (
            "专利代理有限公司",
            "知识产权代理有限公司",
            "有限责任公司",
            "有限公司",
            "律师事务所",
            "专利代理事务所",
            "事务所",
            "合伙",
        )
    ):
        score += 30
    if re.search(r"\d{2,}", compact):
        score -= 60
    if any(token in value for token in ("大街", "街道", "路", "号", "室", "酒店", "大厦")):
        score -= 80
    if len(compact) > 90:
        score -= 40
    return score


def _is_agency_prefix_fragment(text: str) -> bool:
    src = _normalize_anchor_value(text)
    if not src:
        return False
    compact = _compact_text(src)
    if (not compact) or (len(compact) > 24):
        return False
    if re.search(r"\d", compact):
        return False
    if any(token in src for token in ("号", "室", "路", "街", "酒店", "大厦")):
        return False
    return True


def _infer_city_prefix_from_context(line: str) -> str:
    src = _normalize_anchor_value(line)
    if not src:
        return ""
    for marker, prefix in _KNOWN_CITY_PREFIX:
        if marker in src:
            return prefix
    return ""


def _infer_city_prefix_around(lines: list[str], idx: int, min_idx: int) -> tuple[str, ...]:
    seen: set[str] = set()
    prefixes: list[str] = []
    for back in range(1, 6):
        probe = idx - back
        if probe < min_idx:
            break
        src = _normalize_anchor_value(lines[probe])
        if not src:
            continue
        inferred = _infer_city_prefix_from_context(src)
        if not inferred or inferred in seen:
            continue
        seen.add(inferred)
        prefixes.append(inferred)
    return tuple(prefixes)


def _starts_with_known_city_prefix(value: str) -> bool:
    src = _normalize_anchor_value(value)
    if not src:
        return False
    return any(src.startswith(prefix) for _, prefix in _KNOWN_CITY_PREFIX)


def _extract_agency_prefix_fragment(raw_line: str) -> str:
    def _is_ascii_only_fragment(value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z]{1,3}", value or ""))

    src = _normalize_anchor_value(raw_line)
    if not src:
        return ""
    cleaned = _cleanup_agency_candidate(src)
    if _is_agency_prefix_fragment(cleaned) and (not _is_ascii_only_fragment(cleaned)):
        return cleaned
    matched = re.search(r"([A-Za-z\u4e00-\u9fff（）()]{1,28})\s*$", cleaned)
    if not matched:
        return ""
    tail = _normalize_anchor_value(str(matched.group(1) or ""))
    if _is_ascii_only_fragment(tail):
        return ""
    if _is_agency_prefix_fragment(tail):
        return tail
    return ""


def _build_agency_context_candidates(
    lines: list[str],
    *,
    idx: int,
    min_idx: int,
    max_prefix_parts: int = 4,
) -> tuple[str, ...]:
    line = _normalize_anchor_value(lines[idx])
    if not line:
        return ()
    current = _cleanup_agency_candidate(line)
    if (not current) or (("代理" not in current) and ("事务所" not in current)):
        return ()

    variants: list[str] = [current]
    prefix_parts: list[str] = []
    for probe in range(idx - 1, min_idx - 1, -1):
        if len(prefix_parts) >= max_prefix_parts:
            break
        prev_src = _normalize_anchor_value(lines[probe])
        if not prev_src:
            continue
        if any(marker in prev_src for marker in _AGENCY_HEADER_STOP_MARKERS):
            break
        if _is_notice_title_line(prev_src) or _GENERIC_LABEL_LINE_RE.match(prev_src):
            break

        prefix_fragment = _extract_agency_prefix_fragment(prev_src)
        if not prefix_fragment:
            break
        if current.startswith(prefix_fragment):
            continue
        if prefix_parts and prefix_parts[0].startswith(prefix_fragment):
            continue
        prefix_parts.insert(0, prefix_fragment)
        variants.append("".join(prefix_parts + [current]))

    city_prefixes = _infer_city_prefix_around(lines, idx, min_idx=min_idx)
    expanded: list[str] = []
    for item in variants:
        value = _normalize_anchor_value(item)
        if not value:
            continue
        expanded.append(value)
        for city in city_prefixes:
            if city and (not value.startswith(city)) and (not _starts_with_known_city_prefix(value)):
                expanded.append(f"{city}{value}")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in expanded:
        key = _compact_text(item)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return tuple(deduped)


def _extract_agency_from_header_context(lines: list[str]) -> _ExtractedValue:
    if not lines:
        return _ExtractedValue()
    anchor_index: int | None = None
    for idx, line in enumerate(lines):
        src = _normalize_anchor_value(line)
        if "发文日" in src:
            anchor_index = idx
            break
    if anchor_index is None:
        for idx, line in enumerate(lines):
            src = _normalize_anchor_value(line)
            if (_LABEL_APP_NO in src) or (_LABEL_APP_NO_OR_PATENT_NO in src):
                anchor_index = idx
                break
    if anchor_index is None:
        return _ExtractedValue()

    start = max(0, anchor_index - 24)
    best: tuple[int, int, str, str] | None = None
    for idx in range(anchor_index - 1, start - 1, -1):
        line = _normalize_anchor_value(lines[idx])
        if not line:
            continue
        if any(marker in line for marker in _AGENCY_HEADER_STOP_MARKERS):
            break
        for candidate in _build_agency_context_candidates(lines, idx=idx, min_idx=start):
            score = _score_agency_candidate(candidate)
            if score < 0:
                continue
            evidence = _normalize_anchor_value(lines[idx])
            if (best is None) or (score > best[0]):
                best = (score, idx, candidate, evidence)

    if best is None:
        return _ExtractedValue()
    _score, _idx, value, evidence = best
    return _ExtractedValue(value=value, evidence=evidence)


def _extract_agency_from_global_context(lines: list[str]) -> _ExtractedValue:
    if not lines:
        return _ExtractedValue()
    best: tuple[int, int, str, str] | None = None
    for idx, raw in enumerate(lines):
        line = _normalize_anchor_value(raw)
        if not line or (("代理" not in line) and ("事务所" not in line)):
            continue
        min_idx = max(0, idx - 10)
        for candidate in _build_agency_context_candidates(lines, idx=idx, min_idx=min_idx):
            score = _score_agency_candidate(candidate)
            if score < 0:
                continue
            evidence = _normalize_anchor_value(raw)
            if (best is None) or (score > best[0]):
                best = (score, idx, candidate, evidence)
    if best is None:
        return _ExtractedValue()
    _score, _idx, value, evidence = best
    return _ExtractedValue(value=value, evidence=evidence)


def _extract_agency_raw(lines: list[str]) -> _ExtractedValue:
    def _normalize_hit(hit: _ExtractedValue) -> _ExtractedValue:
        if not hit.value:
            return _ExtractedValue()
        cleaned = _cleanup_agency_candidate(hit.value)
        if not cleaned:
            return _ExtractedValue()
        return _ExtractedValue(value=cleaned, evidence=hit.evidence)

    header_hit = _normalize_hit(_extract_agency_from_header_context(lines))
    anchor_hit = _normalize_hit(
        _extract_by_positional_anchors(
        lines,
        start_labels=_AGENCY_START_LABELS,
        end_labels=_AGENCY_END_LABELS,
        fallback_max_lines=8,
    )
    )
    global_hit = _normalize_hit(_extract_agency_from_global_context(lines))
    candidates = [hit for hit in (header_hit, anchor_hit, global_hit) if hit.value]
    if not candidates:
        return _ExtractedValue()
    return max(candidates, key=lambda hit: _score_agency_candidate(hit.value))


def _extract_department(lines: list[str]) -> _ExtractedValue:
    labeled = _first_labeled_value(lines, labels=[_LABEL_DEPARTMENT])
    if labeled.value:
        return labeled
    for line in lines:
        src = str(line or "").strip()
        if not src:
            continue
        if "初审及流程管理部" in src:
            return _ExtractedValue(value="初审及流程管理部", evidence=src)
    for line in lines:
        src = str(line or "").strip()
        if not src or ("管理部" not in src and "审查部" not in src):
            continue
        matched = re.search(r"([A-Za-z0-9\u4e00-\u9fff]{2,}(?:管理部|审查部))", src)
        if matched:
            return _ExtractedValue(value=str(matched.group(1) or "").strip(), evidence=src)
    return _ExtractedValue()


def _extract_examiner(lines: list[str]) -> _ExtractedValue:
    def _normalize_examiner_candidate(raw: str) -> str:
        text = _normalize_anchor_value(raw)
        text = re.sub(_PHONE_RE, "", text)
        text = re.sub(r"(联系电话|电话)\s*[:：]?\s*.*$", "", text)
        text = text.strip(" :：，,；;()（）")
        text = re.sub(r"\s+", "", text)
        text = re.sub(r"^审查员(?:姓名|名称)?", "", text).strip()
        return text

    def _is_examiner_noise(value: str) -> bool:
        src = _normalize_anchor_value(value)
        compact = _compact_text(src)
        if (not compact) or (len(compact) < 2) or (len(compact) > 12):
            return True
        if re.search(r"[。；，,！？!?:：;]", src):
            return True
        if any(token in src for token in _EXAMINER_NOISE_TOKENS):
            return True
        return False

    strict_labels = (_LABEL_EXAMINER_FULL_NAME, _LABEL_EXAMINER_NAME, _LABEL_EXAMINER)
    for line in lines:
        src = _normalize_anchor_value(line)
        if not src:
            continue
        matched_any = False
        for label in strict_labels:
            matched = re.search(r"^\s*" + re.escape(label) + r"\s*[:：]\s*(.+)$", src)
            if not matched:
                continue
            matched_any = True
            value = _normalize_examiner_candidate(str(matched.group(1) or ""))
            if _is_examiner_noise(value):
                continue
            return _ExtractedValue(value=value, evidence=src)
        if matched_any:
            continue
        matched_plain = re.search(r"^\s*" + re.escape(_LABEL_EXAMINER) + r"\s+(.+)$", src)
        if not matched_plain:
            continue
        value = _normalize_examiner_candidate(str(matched_plain.group(1) or ""))
        if _is_examiner_noise(value):
            continue
        return _ExtractedValue(value=value, evidence=src)
    return _ExtractedValue()


def _extract_examiner_phone(lines: list[str], examiner_line: str) -> _ExtractedValue:
    normalized_lines = [_normalize_anchor_value(line) for line in lines]
    for line in normalized_lines:
        if _LABEL_EXAMINER_PHONE not in line:
            continue
        matched = _PHONE_RE.search(line)
        if matched:
            return _ExtractedValue(value=str(matched.group(0) or "").strip(), evidence=line)

    examiner_idx: int | None = None
    examiner_src = _normalize_anchor_value(examiner_line)
    if examiner_src:
        for idx, line in enumerate(normalized_lines):
            if line == examiner_src:
                examiner_idx = idx
                break

    for idx, line in enumerate(normalized_lines):
        if ("联系电话" not in line) and ((_LABEL_PHONE not in line) or (_LABEL_EXAMINER not in line)):
            continue
        matched = _PHONE_RE.search(line)
        if matched:
            return _ExtractedValue(value=str(matched.group(0) or "").strip(), evidence=line)

    if examiner_idx is not None:
        for idx in range(max(0, examiner_idx - 2), min(len(normalized_lines), examiner_idx + 3)):
            line = normalized_lines[idx]
            if ("联系电话" not in line) and (_LABEL_PHONE not in line) and (_LABEL_EXAMINER_PHONE not in line):
                continue
            matched = _PHONE_RE.search(line)
            if matched:
                return _ExtractedValue(value=str(matched.group(0) or "").strip(), evidence=line)

    if examiner_line and ("(" in examiner_line or "（" in examiner_line):
        matched = _PHONE_RE.search(examiner_src)
        if matched:
            return _ExtractedValue(value=str(matched.group(0) or "").strip(), evidence=examiner_src)
    return _ExtractedValue()


def _extract_prior_art(lines: list[str]) -> _ExtractedValue:
    values: list[str] = []
    evidence = ""
    for line in lines:
        found = _CN_PUB_RE.findall(line)
        if not found:
            continue
        if not evidence:
            evidence = line
        for item in found:
            values.append(re.sub(r"\s+", "", str(item or "").upper()))
    return _ExtractedValue(value=_dedup_join(values, sep=";"), evidence=evidence)


def _extract_center(department: _ExtractedValue) -> _ExtractedValue:
    value = str(department.value or "").strip()
    if value and ("专利审查协作" in value) and ("中心" in value):
        return _ExtractedValue(value=value, evidence=department.evidence)
    return _ExtractedValue()


def _is_checked_claim_line(line: str) -> bool:
    src = str(line or "").strip()
    if not src or "权利要求" not in src:
        return False
    index = src.find("权利要求")
    prefix = src[:index]
    if any(mark in prefix for mark in _CHECKED_MARKERS):
        return True
    if any(mark in prefix for mark in _UNCHECKED_MARKERS):
        return False
    return False


def _clean_checked_reason_line(line: str) -> str:
    src = str(line or "").strip()
    src = re.sub(r"^[\s☒☑☓☐□✓✔√✗×]+", "", src)
    src = re.sub(r"^[（(]?[一二三四五六七八九十\d]+[)）]\s*", "", src)
    src = re.sub(r"_{2,}", "_", src)
    return _normalize_text_line(src)


def _pick_primary_reject_reason_line(lines: list[str]) -> str:
    best = ""
    best_score = -10**9
    for line in lines:
        src = str(line or "").strip()
        if not src:
            continue
        claim_token = ""
        matched = _REJECT_CLAIM_NO_RE.search(src)
        if matched:
            claim_token = str(matched.group(1) or "")
        score = 0
        if claim_token:
            score += len(claim_token)
        if any(symbol in claim_token for symbol in ("-", "—", "~", "至", ",", "，", "、")):
            score += 30
        if "第22 条第3 款" in src or "第二十二条第三款" in src:
            score += 25
        if "不具备专利法" in src:
            score += 20
        if src.startswith("权利要求"):
            score += 10
        if "因此" in src or "基于" in src:
            score -= 20
        if score > best_score:
            best_score = score
            best = src
    return best


def _extract_reject_reason(*, lines: list[str], patent_type_label: str) -> _ExtractedValue:
    if str(patent_type_label or "").strip() != "发明专利":
        return _ExtractedValue()
    matched_lines: list[str] = []
    for line in lines:
        if not _is_checked_claim_line(line):
            continue
        cleaned = _clean_checked_reason_line(line)
        if cleaned and _REJECT_REASON_LINE_RE.search(cleaned):
            matched_lines.append(cleaned)
    if not matched_lines:
        fallback_lines: list[str] = []
        keywords = ("不符合专利法", "不具备专利法", "不具备创造性", "不符合专利法第")
        for line in lines:
            src = str(line or "").strip()
            if not src or ("权利要求" not in src):
                continue
            if any(mark in src for mark in _UNCHECKED_MARKERS):
                continue
            if not any(keyword in src for keyword in keywords):
                continue
            cleaned = _clean_checked_reason_line(src)
            if cleaned and _REJECT_REASON_LINE_RE.search(cleaned):
                fallback_lines.append(cleaned)
        if not fallback_lines:
            return _ExtractedValue()
        primary = _pick_primary_reject_reason_line(list(dict.fromkeys(fallback_lines)))
        if not primary:
            return _ExtractedValue()
        return _ExtractedValue(
            value=primary,
            evidence=primary,
        )
    primary = _pick_primary_reject_reason_line(list(dict.fromkeys(matched_lines)))
    if not primary:
        return _ExtractedValue()
    return _ExtractedValue(
        value=primary,
        evidence=primary,
    )


def _extract_certificate_no(lines: list[str]) -> _ExtractedValue:
    for line in lines:
        src = str(line or "").strip()
        if not src or "证书号" not in src:
            continue
        matched = _CERT_NO_RE.search(src)
        if matched:
            value = str(matched.group(1) or "").strip()
            if value:
                return _ExtractedValue(value=value, evidence=src)
        value = _extract_after_labels(src, [_LABEL_CERTIFICATE_NO])
        if value:
            return _ExtractedValue(value=value, evidence=src)
    return _ExtractedValue()


def _extract_app_no(lines: list[str]) -> str:
    value = _first_labeled_value(
        lines,
        labels=[_LABEL_APP_NO_OR_PATENT_NO, _LABEL_APP_NO],
    )
    return str(value.value or "").strip()


def _decode_qrcode_from_image_array(image: Any) -> tuple[str, bytes]:
    if (not _CV2_AVAILABLE) or image is None:
        return "", b""
    detector = cv2.QRCodeDetector()
    text, points, _ = detector.detectAndDecode(image)
    value = str(text or "").strip()
    if not value:
        return "", b""

    png_bytes = b""
    try:
        if points is not None and len(points):
            pts = points[0] if hasattr(points, "__len__") and len(points.shape) > 2 else points
            xs = [int(p[0]) for p in pts]
            ys = [int(p[1]) for p in pts]
            x0, x1 = max(min(xs) - 4, 0), min(max(xs) + 4, image.shape[1])
            y0, y1 = max(min(ys) - 4, 0), min(max(ys) + 4, image.shape[0])
            crop = image[y0:y1, x0:x1]
            if crop.size > 0:
                ok, encoded = cv2.imencode(".png", crop)
                if ok:
                    png_bytes = bytes(encoded.tobytes())
        if not png_bytes:
            ok, encoded = cv2.imencode(".png", image)
            if ok:
                png_bytes = bytes(encoded.tobytes())
    except Exception:
        png_bytes = b""
    return value, png_bytes


def _extract_qrcode_from_doc(doc: fitz.Document) -> _ExtractedValue:
    if not _CV2_AVAILABLE:
        return _ExtractedValue()

    for page_index in range(doc.page_count):
        page = doc[page_index]
        get_images = getattr(page, "get_images", None)
        if callable(get_images):
            for image_info in get_images(full=True):
                try:
                    xref = int(image_info[0])
                    extracted = doc.extract_image(xref)
                    raw = bytes(extracted.get("image") or b"")
                    if not raw:
                        continue
                    array = np.frombuffer(raw, dtype=np.uint8)
                    mat = cv2.imdecode(array, cv2.IMREAD_COLOR)
                    value, png = _decode_qrcode_from_image_array(mat)
                    if value:
                        return _ExtractedValue(
                            value=value,
                            evidence=f"第{page_index + 1}页二维码图片",
                            image_bytes=png,
                        )
                except Exception:
                    continue

        get_pixmap = getattr(page, "get_pixmap", None)
        if callable(get_pixmap):
            try:
                pix = get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                data = np.frombuffer(pix.samples, dtype=np.uint8)
                mat = data.reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    mat = cv2.cvtColor(mat, cv2.COLOR_RGBA2BGR)
                elif pix.n == 3:
                    mat = cv2.cvtColor(mat, cv2.COLOR_RGB2BGR)
                value, png = _decode_qrcode_from_image_array(mat)
                if value:
                    return _ExtractedValue(
                        value=value,
                        evidence=f"第{page_index + 1}页页面扫描",
                        image_bytes=png,
                    )
            except Exception:
                continue

    return _ExtractedValue()


def _load_matrix_json(path: str) -> dict[str, Any]:
    if not path:
        raise FileNotFoundError("empty matrix path")
    with open(path, "r", encoding="utf-8") as file_obj:
        raw = json.load(file_obj)
    if not isinstance(raw, dict):
        raise ValueError(f"matrix payload must be JSON object: {path}")
    return raw


@lru_cache(maxsize=1)
def _load_matrix() -> dict[str, Any]:
    global _MATRIX_HEALTH
    mirror_paths = get_resource_mirror_paths(_RESOURCE_FILE)
    raw: dict[str, Any] | None = None
    source = "missing"
    path = ""
    warning = ""
    error = ""

    if os.path.exists(mirror_paths.embedded_path):
        try:
            raw = _load_matrix_json(mirror_paths.embedded_path)
            source = "embedded"
            path = mirror_paths.embedded_path
            sync_warning = sync_embedded_resource_to_mirror(mirror_paths)
            if sync_warning:
                warning = sync_warning
        except Exception as exc:
            warning = f"embedded matrix load failed: {exc}"

    if raw is None and os.path.exists(mirror_paths.mirror_path):
        try:
            raw = _load_matrix_json(mirror_paths.mirror_path)
            source = "mirror"
            path = mirror_paths.mirror_path
        except Exception as exc:
            error = f"mirror matrix load failed: {exc}"

    if raw is None:
        if not error:
            error = (
                "matrix resource unavailable: "
                f"embedded={mirror_paths.embedded_path}, mirror={mirror_paths.mirror_path}"
            )
        _MATRIX_HEALTH = PdfFieldMatrixHealth(
            healthy=False,
            source=source,
            path=path,
            warning=warning,
            error=error,
            embedded_path=mirror_paths.embedded_path,
            mirror_path=mirror_paths.mirror_path,
        )
        raw = {}
    else:
        _MATRIX_HEALTH = PdfFieldMatrixHealth(
            healthy=True,
            source=source,
            path=path,
            warning=warning,
            error="",
            embedded_path=mirror_paths.embedded_path,
            mirror_path=mirror_paths.mirror_path,
        )

    default_fields = raw.get("default_fields")
    if not isinstance(default_fields, list):
        default_fields = []

    by_notice_key = raw.get("by_notice_key")
    if not isinstance(by_notice_key, dict):
        by_notice_key = {}

    by_notice_code = raw.get("by_notice_code")
    if not isinstance(by_notice_code, dict):
        by_notice_code = {}

    return {
        "default_fields": [str(item or "").strip() for item in default_fields if str(item or "").strip() in _FIELD_ALL],
        "by_notice_key": {
            str(key or "").strip(): [str(item or "").strip() for item in values if str(item or "").strip() in _FIELD_ALL]
            for key, values in by_notice_key.items()
            if isinstance(values, list)
        },
        "by_notice_code": {
            str(key or "").strip(): [str(item or "").strip() for item in values if str(item or "").strip() in _FIELD_ALL]
            for key, values in by_notice_code.items()
            if isinstance(values, list)
        },
    }


def get_pdf_field_matrix_health() -> PdfFieldMatrixHealth:
    _load_matrix()
    return _MATRIX_HEALTH


def resolve_pdf_applicable_fields(*, notice_key: str, notice_kind: str = "") -> tuple[str, ...]:
    matrix = _load_matrix()
    key = str(notice_key or "").strip()
    by_notice_key = matrix.get("by_notice_key", {})
    by_notice_code = matrix.get("by_notice_code", {})
    default_fields = list(matrix.get("default_fields", []) or [])

    fields: list[str] = []
    if key and key in by_notice_key:
        fields = list(by_notice_key.get(key, []) or [])
    else:
        code = _notice_code_from_key(key) if key else str(notice_kind or "").strip()
        fields = list(by_notice_code.get(str(code or "").strip(), []) or [])

    if not fields:
        fields = default_fields
    deduped: list[str] = []
    seen: set[str] = set()
    for field_name in fields:
        item = str(field_name or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    if "agency_raw" in deduped and "agent" not in deduped:
        deduped.append("agent")
    return tuple(deduped)


def extract_pdf_entity_fields(
    *,
    pdf_bytes: bytes,
    notice_key: str,
    notice_kind: str = "",
    app_no: str = "",
) -> PdfEntityExtractResult:
    applicable = resolve_pdf_applicable_fields(notice_key=notice_key, notice_kind=notice_kind)
    if not applicable:
        return PdfEntityExtractResult(status="未适用", applicable_fields=tuple())
    if not pdf_bytes:
        return PdfEntityExtractResult(status="失败", error="主PDF为空", applicable_fields=applicable)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        return PdfEntityExtractResult(status="失败", error=f"打开PDF失败：{exc}", applicable_fields=applicable)

    try:
        lines: list[str] = []
        for index in range(doc.page_count):
            page_text = doc[index].get_text("text")
            page_lines = [_normalize_text_line(line) for line in str(page_text or "").splitlines()]
            lines.extend(line for line in page_lines if line)
    except Exception as exc:
        doc.close()
        return PdfEntityExtractResult(status="失败", error=f"提取PDF文本失败：{exc}", applicable_fields=applicable)

    source_app_no = str(app_no or "").strip() or _extract_app_no(lines)
    _type_code, patent_type_label = infer_patent_type_from_app_no(source_app_no)

    department = _extract_department(lines)
    center = _extract_center(department)
    applicant_raw = _extract_applicant_or_owner(lines)
    applicant = _ExtractedValue(
        value=_normalize_anchor_value(applicant_raw.value),
        evidence=applicant_raw.evidence,
    )
    inventor_raw = _first_labeled_value(lines, labels=[_LABEL_INVENTOR, _LABEL_DESIGNER])
    inventor = _ExtractedValue(
        value=_normalize_person_values(inventor_raw.value),
        evidence=inventor_raw.evidence,
    )
    agency_raw = _extract_agency_raw(lines)
    agent = _extract_agent(lines, agency_hit=agency_raw)
    examiner = _extract_examiner(lines)
    panel_head = _first_labeled_value(
        lines,
        labels=[_LABEL_PANEL_HEAD],
        next_labels=[_LABEL_PANEL_MAIN, _LABEL_PANEL_MEMBER],
    )
    panel_main = _first_labeled_value(
        lines,
        labels=[_LABEL_PANEL_MAIN],
        next_labels=[_LABEL_PANEL_MEMBER],
    )
    panel_member = _first_labeled_value(lines, labels=[_LABEL_PANEL_MEMBER])
    examiner_phone = _extract_examiner_phone(lines, examiner.evidence)
    reject_reason = _extract_reject_reason(lines=lines, patent_type_label=patent_type_label)
    prior_art = _extract_prior_art(lines)
    dossier_no = _first_labeled_value(lines, labels=[_LABEL_DOSSIER_NO], reject_value_contains=("档案号",))
    authorization_pub_no = _first_labeled_value(lines, labels=[_LABEL_AUTHORIZATION_PUB_NO])
    authorization_pub_date = _first_labeled_value(lines, labels=[_LABEL_AUTHORIZATION_PUB_DATE])
    certificate_no = _extract_certificate_no(lines)
    qrcode = _extract_qrcode_from_doc(doc)
    doc.close()

    values = {
        "department": department,
        "center": center,
        "applicant": applicant,
        "inventor": inventor,
        "agent": agent,
        "agency_raw": agency_raw,
        "examiner": examiner,
        "examiner_phone": examiner_phone,
        "panel_head": panel_head,
        "panel_main": panel_main,
        "panel_member": panel_member,
        "reject_reason": reject_reason,
        "prior_art": prior_art,
        "dossier_no": dossier_no,
        "authorization_pub_no": authorization_pub_no,
        "authorization_pub_date": authorization_pub_date,
        "certificate_no": certificate_no,
        "qrcode_link": _ExtractedValue(value=qrcode.value, evidence=qrcode.evidence),
        "qrcode_image": _ExtractedValue(value="yes" if qrcode.image_bytes else "", evidence=qrcode.evidence, image_bytes=qrcode.image_bytes),
    }

    effective_values = {name: values[name] for name in applicable if name in values}
    hit = any(bool(item.value) for item in effective_values.values())
    status = "成功" if hit else "未命中"

    evidence: dict[str, str] = {}
    for field_name in applicable:
        item = values.get(field_name)
        if isinstance(item, _ExtractedValue) and item.evidence:
            evidence[f"evidence_{field_name}"] = item.evidence

    return PdfEntityExtractResult(
        status=status,
        applicable_fields=applicable,
        department=department.value if "department" in applicable else "",
        center=center.value if "center" in applicable else "",
        applicant=applicant.value if "applicant" in applicable else "",
        inventor=inventor.value if "inventor" in applicable else "",
        agent=agent.value if "agent" in applicable else "",
        agency_raw=agency_raw.value if "agency_raw" in applicable else "",
        examiner=examiner.value if "examiner" in applicable else "",
        examiner_phone=examiner_phone.value if "examiner_phone" in applicable else "",
        panel_head=panel_head.value if "panel_head" in applicable else "",
        panel_main=panel_main.value if "panel_main" in applicable else "",
        panel_member=panel_member.value if "panel_member" in applicable else "",
        reject_reason=reject_reason.value if "reject_reason" in applicable else "",
        prior_art=prior_art.value if "prior_art" in applicable else "",
        dossier_no=dossier_no.value if "dossier_no" in applicable else "",
        authorization_pub_no=authorization_pub_no.value if "authorization_pub_no" in applicable else "",
        authorization_pub_date=authorization_pub_date.value if "authorization_pub_date" in applicable else "",
        certificate_no=certificate_no.value if "certificate_no" in applicable else "",
        qrcode_link=qrcode.value if "qrcode_link" in applicable else "",
        qrcode_image_bytes=qrcode.image_bytes if "qrcode_image" in applicable else b"",
        evidence=evidence,
    )


__all__ = [
    "PdfFieldMatrixHealth",
    "PdfEntityExtractResult",
    "clear_pdf_field_matrix_cache",
    "extract_pdf_entity_fields",
    "get_pdf_field_matrix_health",
    "resolve_pdf_applicable_fields",
]
