from __future__ import annotations

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import fitz
import openpyxl


OUTPUT_SUBDIR = os.path.join("official_docs_struct_anchor")

DEFAULT_FIELDS: tuple[str, ...] = ("applicant", "agency_raw", "examiner", "examiner_phone")
SUPPORTED_FIELDS: tuple[str, ...] = DEFAULT_FIELDS

FIELD_TO_HEADER: dict[str, str] = {
    "applicant": "申请人信息",
    "agency_raw": "代理机构信息",
    "examiner": "审查员姓名",
    "examiner_phone": "审查员电话",
}
HEADER_TO_FIELD: dict[str, str] = {value: key for key, value in FIELD_TO_HEADER.items()}
HEADER_TO_FIELD["代理信息原文"] = "agency_raw"

STRIKE_SOURCE_ZIP = "源ZIP"
STRIKE_OUTPUT_PDF_NAME = "输出PDF名称"
STRIKE_SUMMARY_PDF_PATH = "汇总PDF路径"
STRIKE_ARCHIVE_PDF_PATH = "归档PDF路径"

CHECKED_MARKERS: tuple[str, ...] = ("✓", "✔", "☑", "√", "■", "▣")
APPLICANT_NOISE_TOKENS: tuple[str, ...] = (
    "国际申请号",
    "国际申请日",
    "档案号",
    "重要通知",
    "全部规定费用",
)
APPLICANT_TITLE_TOKENS: tuple[str, ...] = (
    "通知书",
    "决定书",
    "审批通知书",
    "受理通知书",
)
APPLICANT_BODY_TOKENS: tuple[str, ...] = (
    "本通知书",
    "根据专利法",
    "审查员对上述",
    "意见陈述",
    "本局决定",
    "国家知识产权局对上述",
    "复审请求已经开始审理",
    "发明创造名称",
    "提出复审请求时",
)
APPLICANT_ADDRESS_TOKENS: tuple[str, ...] = (
    "地址",
    "发明人",
    "设计人",
    "专利号",
    "邮编",
    "国籍",
    "联系人",
)
AGENCY_NOISE_TOKENS: tuple[str, ...] = ("委托书", "会晤", "口头审理", "办理系统", "提交")
EXAMINER_NOISE_TOKENS: tuple[str, ...] = ("认为", "对上述申请", "权利要求", "通知书", "不符合", "不具备")

PHONE_RE = re.compile(r"(?:\+?86[-\s]?)?(?:0\d{2,3}[-\s]?)?\d{7,11}")
NUMBERED_ITEM_RE = re.compile(r"^\s*(?:[（(]?\d+[)）.、]|第[一二三四五六七八九十百千0-9]+项)")
REVIEW_APPLICANT_INLINE_RE = re.compile(
    r"(?:应|由)?申请人\s*[:：]?\s*(?P<name>[^（()，。；;:：]{1,120}?)(?=（\s*下称复审请求人\s*）|\(\s*下称复审请求人\s*\)|下称复审请求人)"
)

APPLICANT_START_LABELS: tuple[str, ...] = ("申请人", "专利权人", "复审请求人")
APPLICANT_STOP_LABELS: tuple[str, ...] = (
    "发明人",
    "设计人",
    "发明名称",
    "发明创造名称",
    "地址",
    "邮编",
    "专利代理机构名称",
    "专利代理机构",
    "代理机构",
    "代理人",
    "审查员",
    "审查员电话",
    "申请号",
    "申请号或专利号",
    "国际申请号",
    "国际申请日",
    "档案号",
    "申请方案卷号",
)

AGENCY_START_LABELS: tuple[str, ...] = ("专利代理机构名称", "专利代理机构", "代理机构")
AGENCY_STOP_LABELS: tuple[str, ...] = (
    "代理人",
    "审查员",
    "审查员电话",
    "联系电话",
    "电话",
    "地址",
    "邮编",
    "联系人",
    "申请号",
    "申请号或专利号",
    "申请方案卷号",
)

EXAMINER_START_LABELS: tuple[str, ...] = ("审查员姓名", "审查员名称", "审查员")
EXAMINER_STOP_LABELS: tuple[str, ...] = ("审查员电话", "联系电话", "电话", "代理人", "申请号")

PHONE_START_LABELS: tuple[str, ...] = ("审查员电话", "联系电话", "电话")
PHONE_STOP_LABELS: tuple[str, ...] = ("代理人", "申请号", "申请号或专利号")

ALL_STOP_LABELS: tuple[str, ...] = tuple(
    dict.fromkeys(
        APPLICANT_START_LABELS
        + APPLICANT_STOP_LABELS
        + AGENCY_START_LABELS
        + AGENCY_STOP_LABELS
        + EXAMINER_START_LABELS
        + EXAMINER_STOP_LABELS
        + PHONE_START_LABELS
        + PHONE_STOP_LABELS
    )
)


@dataclass(frozen=True)
class VisualLine:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    line_id: str


@dataclass
class FieldEvidence:
    evidence_text: str = ""
    page: int = 0
    bbox: tuple[float, float, float, float] | None = None
    anchor_label: str = ""
    stop_reason: str = ""
    confidence: float = 0.0
    start_mode: str = ""
    line_index: int = -1
    auto_category: str = ""


@dataclass
class FieldResult:
    value: str = ""
    evidence: FieldEvidence = field(default_factory=FieldEvidence)


@dataclass(frozen=True)
class FieldConfig:
    field: str
    start_labels: tuple[str, ...]
    stop_labels: tuple[str, ...]
    max_follow_lines: int
    allow_no_colon: bool = True


FIELD_CONFIGS: dict[str, FieldConfig] = {
    "applicant": FieldConfig(
        field="applicant",
        start_labels=APPLICANT_START_LABELS,
        stop_labels=APPLICANT_STOP_LABELS,
        max_follow_lines=8,
        allow_no_colon=True,
    ),
    "agency_raw": FieldConfig(
        field="agency_raw",
        start_labels=AGENCY_START_LABELS,
        stop_labels=AGENCY_STOP_LABELS,
        max_follow_lines=8,
        allow_no_colon=True,
    ),
    "examiner": FieldConfig(
        field="examiner",
        start_labels=EXAMINER_START_LABELS,
        stop_labels=EXAMINER_STOP_LABELS,
        max_follow_lines=2,
        allow_no_colon=True,
    ),
    "examiner_phone": FieldConfig(
        field="examiner_phone",
        start_labels=PHONE_START_LABELS,
        stop_labels=PHONE_STOP_LABELS,
        max_follow_lines=2,
        allow_no_colon=True,
    ),
}


def _normalize_space(text: str) -> str:
    src = str(text or "").replace("\u3000", " ").replace("\r", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", src).strip()


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", _normalize_space(text))


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _output_dir(output_root: str) -> str:
    root = os.path.abspath(str(output_root or "").strip() or "output")
    return os.path.join(root, OUTPUT_SUBDIR, _timestamp())


def _write_csv(path: str, headers: list[str], rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: str(row.get(name, "") or "") for name in headers})


def _write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)


def _write_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False))
            file_obj.write("\n")


def _collect_pdf_paths(pdf_root: str) -> list[str]:
    root = os.path.abspath(str(pdf_root or "").strip())
    if (not root) or (not os.path.isdir(root)):
        return []
    results: list[str] = []
    for dir_path, _dir_names, file_names in os.walk(root):
        for file_name in file_names:
            if str(file_name).lower().endswith(".pdf"):
                results.append(os.path.abspath(os.path.join(dir_path, file_name)))
    results.sort()
    return results


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _bbox_union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float] | None:
    if not boxes:
        return None
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[2] for box in boxes)
    y1 = max(box[3] for box in boxes)
    return (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))


def _bbox_text(bbox: tuple[float, float, float, float] | None) -> str:
    if bbox is None:
        return ""
    return ",".join(f"{item:.2f}" for item in bbox)


def _build_lines_from_words(page_index: int, words: list[Any]) -> list[VisualLine]:
    grouped: dict[tuple[int, int], list[tuple[float, float, float, float, str]]] = {}
    for item in words or []:
        if not isinstance(item, (list, tuple)) or len(item) < 5:
            continue
        text = _normalize_space(str(item[4] or ""))
        if not text:
            continue
        x0 = _safe_float(item[0])
        y0 = _safe_float(item[1])
        x1 = _safe_float(item[2])
        y1 = _safe_float(item[3])
        if len(item) >= 7:
            key = (int(_safe_float(item[5], 0)), int(_safe_float(item[6], 0)))
        else:
            key = (0, int(round(y0 * 2)))
        grouped.setdefault(key, []).append((x0, y0, x1, y1, text))

    results: list[VisualLine] = []
    for order, (key, tokens) in enumerate(sorted(grouped.items(), key=lambda kv: min(token[1] for token in kv[1]))):
        tokens.sort(key=lambda token: (token[0], token[1]))
        text = "".join(token[4] for token in tokens)
        x0 = min(token[0] for token in tokens)
        y0 = min(token[1] for token in tokens)
        x1 = max(token[2] for token in tokens)
        y1 = max(token[3] for token in tokens)
        line_id = f"{page_index}:{key[0]}:{key[1]}:w:{order}"
        results.append(VisualLine(page=page_index, x0=x0, y0=y0, x1=x1, y1=y1, text=text, line_id=line_id))
    results.sort(key=lambda line: (line.page, line.y0, line.x0))
    return results


def _build_lines_from_rawdict(page_index: int, rawdict: dict[str, Any]) -> list[VisualLine]:
    blocks = list(rawdict.get("blocks") or [])
    results: list[VisualLine] = []
    order = 0
    for block_idx, block in enumerate(blocks):
        if int(block.get("type", 0)) != 0:
            continue
        for line_idx, line in enumerate(list(block.get("lines") or [])):
            spans = list(line.get("spans") or [])
            text = "".join(str(span.get("text", "") or "") for span in spans)
            text = _normalize_space(text)
            if not text:
                continue
            bbox = list(line.get("bbox") or [0, 0, 0, 0])
            if len(bbox) != 4:
                bbox = [0, 0, 0, 0]
            x0 = _safe_float(bbox[0])
            y0 = _safe_float(bbox[1])
            x1 = _safe_float(bbox[2])
            y1 = _safe_float(bbox[3])
            line_id = f"{page_index}:{block_idx}:{line_idx}:r:{order}"
            order += 1
            results.append(VisualLine(page=page_index, x0=x0, y0=y0, x1=x1, y1=y1, text=text, line_id=line_id))
    results.sort(key=lambda line: (line.page, line.y0, line.x0))
    return results


def _collect_document_lines(doc: Any) -> tuple[list[VisualLine], dict[int, float], dict[str, int]]:
    lines: list[VisualLine] = []
    page_widths: dict[int, float] = {}
    word_lines_count = 0
    raw_lines_count = 0

    page_count = int(getattr(doc, "page_count", 0) or 0)
    for page_index in range(page_count):
        page = doc[page_index]
        page_width = _safe_float(getattr(getattr(page, "rect", None), "width", 0.0), 0.0) or 1000.0
        page_widths[page_index] = page_width

        rawdict = page.get_text("rawdict")
        words = page.get_text("words")
        word_lines = _build_lines_from_words(page_index, list(words or []))
        raw_lines = _build_lines_from_rawdict(page_index, dict(rawdict or {}))
        word_lines_count += len(word_lines)
        raw_lines_count += len(raw_lines)
        page_lines = word_lines if word_lines else raw_lines
        lines.extend(page_lines)

    lines.sort(key=lambda line: (line.page, line.y0, line.x0))
    return lines, page_widths, {"word_lines": word_lines_count, "raw_lines": raw_lines_count}


def _anchor_match(
    line_text: str,
    labels: tuple[str, ...],
    *,
    allow_no_colon: bool,
) -> tuple[str, str, str] | None:
    src = _normalize_space(line_text)
    if not src:
        return None
    for label in labels:
        matched = re.match(r"^\s*" + re.escape(label) + r"\s*[:：]\s*(.*)$", src)
        if matched:
            return label, _normalize_space(str(matched.group(1) or "")), "colon"
    if not allow_no_colon:
        return None
    for label in labels:
        matched = re.match(r"^\s*" + re.escape(label) + r"\s*(.*)$", src)
        if not matched:
            continue
        if len(_compact(src)) > 48:
            continue
        rest = _normalize_space(str(matched.group(1) or "")).lstrip(":：")
        return label, _normalize_space(rest), "no_colon"
    return None


def _starts_with_label(line_text: str, labels: tuple[str, ...]) -> bool:
    src = _normalize_space(line_text)
    if not src:
        return False
    for label in labels:
        if re.match(r"^\s*" + re.escape(label) + r"(?:\s*[:：]|\s+|$)", src):
            return True
    return False


def _is_checkbox_noise(text: str) -> bool:
    src = _normalize_space(text)
    if not src:
        return False
    if not any(marker in src for marker in CHECKED_MARKERS):
        return False
    if len(_compact(src)) <= 2:
        return True
    return ("规定费用" in src) or ("缴纳" in src)


def _is_numbered_item_start(text: str) -> bool:
    return bool(NUMBERED_ITEM_RE.match(_normalize_space(text)))


def _is_applicant_anchor_noise(text: str) -> bool:
    src = _normalize_space(text)
    compact = _compact(src)
    if not src:
        return True
    if "或代理人的档案号" in src:
        return True
    if ("档案号" in src) and (("国际申请号" in src) or ("国际申请日" in src)):
        return True
    if len(compact) > 80:
        return True
    return False


def _is_title_like_line(text: str) -> bool:
    src = _normalize_space(text)
    compact = _compact(src)
    if (not compact) or (len(compact) > 60):
        return False
    if any(token in src for token in APPLICANT_TITLE_TOKENS):
        return True
    return False


def _is_long_body_line(text: str) -> bool:
    src = _normalize_space(text)
    compact = _compact(src)
    if any(token in src for token in APPLICANT_BODY_TOKENS):
        return True
    if len(compact) < 35:
        return False
    punctuation_hits = sum(src.count(mark) for mark in ("。", "；", "，", "：", "、"))
    if punctuation_hits >= 3:
        return True
    return False


def _trim_by_labels(value: str, labels: tuple[str, ...]) -> str:
    src = _normalize_space(value)
    cut = len(src)
    for label in labels:
        for pattern in (
            re.compile(r"\s*" + re.escape(label) + r"\s*[:：].*$"),
            re.compile(r"\s+" + re.escape(label) + r"\s+.*$"),
        ):
            matched = pattern.search(src)
            if matched and matched.start() < cut:
                cut = matched.start()
    return _normalize_space(src[:cut]).strip("：:，,；;")


def _postprocess_applicant(value: str) -> str:
    src = _tighten_cjk_spaces(value)
    src = _trim_by_labels(src, APPLICANT_STOP_LABELS)
    if not src:
        return ""
    if _is_checkbox_noise(src):
        return ""
    if _is_numbered_item_start(src):
        return ""
    src = re.sub(r"\s*(复审通知书|复审决定书|受理通知书|延长期限审批通知书).*$", "", src)
    src = re.sub(r"\s*(地址|发明人|设计人|专利号|邮编|国籍|联系人)\s*[:：].*$", "", src)
    src = re.sub(r"\s*(地址|发明人|设计人|专利号|邮编|国籍|联系人).*$", "", src)
    src = re.sub(r"\s*发明创造名称\s*[:：].*$", "", src)
    src = re.sub(r"\s*发明名称\s*[:：].*$", "", src)
    src = re.sub(r"\s*国家知识产权局对上述.*$", "", src)
    src = re.sub(r"\s*提出复审请求时.*$", "", src)
    src = re.sub(r"\s*[✓✔☑]\s*$", "", src)
    src = _normalize_space(src)
    if any(token in src for token in APPLICANT_NOISE_TOKENS):
        return ""
    return _normalize_space(src).strip("：:，,")


def _classify_applicant_value(value: str) -> str:
    src = _normalize_space(value)
    if not src:
        return "suspect_body_pollution"
    if _is_checkbox_noise(src):
        return "suspect_checkbox_pollution"
    if any(token in src for token in APPLICANT_ADDRESS_TOKENS):
        return "suspect_address_pollution"
    if _is_title_like_line(src):
        return "suspect_title_pollution"
    if _is_long_body_line(src):
        return "suspect_body_pollution"
    if any(token in src for token in APPLICANT_BODY_TOKENS):
        return "suspect_body_pollution"
    return "clean_candidate"


def _postprocess_agency(value: str) -> str:
    src = _trim_by_labels(value, AGENCY_STOP_LABELS)
    if not src:
        return ""
    for token in AGENCY_NOISE_TOKENS:
        if token in src:
            return ""
    src = re.sub(r"\s*(联系人|联系电话|电话)\s*[:：].*$", "", src)
    src = re.sub(r"\s+\S{1,16}[（(]\s*\d[\d\-\s]{5,}\s*[)）]\s*$", "", src)
    if any(mark in src for mark in ("。", "！", "？")):
        return ""
    return _normalize_space(src).strip("：:，,")


def _postprocess_examiner(value: str) -> str:
    src = _trim_by_labels(value, EXAMINER_STOP_LABELS)
    if not src:
        return ""
    src = re.sub(PHONE_RE, "", src)
    src = re.sub(r"(联系电话|电话)\s*[:：]?\s*.*$", "", src)
    src = re.sub(r"^审查员(?:姓名|名称)?", "", src).strip("：:，,；;()（） ")
    src = _normalize_space(src)
    src = re.sub(r"\s+", "", src)
    if (not src) or (len(src) < 2) or (len(src) > 16):
        return ""
    if any(token in src for token in EXAMINER_NOISE_TOKENS):
        return ""
    if re.search(r"[。！？!?:：;，,]", src):
        return ""
    return src


def _normalize_phone(value: str) -> str:
    src = _normalize_space(value)
    matched = PHONE_RE.search(src)
    if not matched:
        return ""
    phone = str(matched.group(0) or "").strip()
    phone = re.sub(r"\s+", "", phone)
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return ""
    return phone


def _tighten_cjk_spaces(value: str) -> str:
    src = _normalize_space(value)
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", src)


def _postprocess_phone(value: str) -> str:
    src = _trim_by_labels(value, PHONE_STOP_LABELS)
    if not src:
        return ""
    return _normalize_phone(src)


def _extract_applicant_from_review_body(lines: list[VisualLine]) -> FieldResult:
    for index, line in enumerate(lines):
        current = _tighten_cjk_spaces(_normalize_space(line.text))
        if not current:
            continue
        candidates = [current]
        if index + 1 < len(lines):
            next_line = lines[index + 1]
            if next_line.page == line.page:
                nxt = _tighten_cjk_spaces(_normalize_space(next_line.text))
                if nxt:
                    candidates.append(current + nxt)
        for candidate in candidates:
            matched = REVIEW_APPLICANT_INLINE_RE.search(candidate)
            if not matched:
                continue
            value = _postprocess_value("applicant", str(matched.group("name") or ""))
            if not value:
                continue
            return FieldResult(
                value=value,
                evidence=FieldEvidence(
                    evidence_text=current,
                    page=int(line.page) + 1,
                    bbox=_bbox_union([(line.x0, line.y0, line.x1, line.y1)]),
                    anchor_label="应申请人回退",
                    stop_reason="review_body_fallback",
                    confidence=0.56,
                    start_mode="fallback_pattern",
                    line_index=index,
                    auto_category=_classify_applicant_value(value),
                ),
            )
    return FieldResult()


def _apply_applicant_fallback(lines: list[VisualLine], primary: FieldResult) -> FieldResult:
    fallback = _extract_applicant_from_review_body(lines)
    if not fallback.value:
        return primary
    if not primary.value:
        return fallback
    if _normalize_space(primary.evidence.anchor_label) != "复审请求人":
        return primary
    if _classify_applicant_value(primary.value) != "clean_candidate":
        return fallback
    return primary


def _postprocess_value(field_name: str, value: str) -> str:
    if field_name == "applicant":
        return _tighten_cjk_spaces(_postprocess_applicant(value))
    if field_name == "agency_raw":
        return _tighten_cjk_spaces(_postprocess_agency(value))
    if field_name == "examiner":
        return _tighten_cjk_spaces(_postprocess_examiner(value))
    if field_name == "examiner_phone":
        return _postprocess_phone(value)
    return _normalize_space(value)


def _compute_confidence(
    *,
    start_mode: str,
    stop_reason: str,
    captured_lines: int,
) -> float:
    score = 0.4
    if start_mode == "colon":
        score += 0.25
    elif start_mode == "no_colon":
        score += 0.1
    if stop_reason == "next_label":
        score += 0.15
    elif stop_reason == "max_lines":
        score -= 0.05
    if captured_lines <= 1:
        score += 0.1
    score = max(0.0, min(1.0, score))
    return round(score, 3)


def _extract_field(lines: list[VisualLine], page_widths: dict[int, float], config: FieldConfig) -> FieldResult:
    for index, line in enumerate(lines):
        page_width = float(page_widths.get(line.page, 1000.0) or 1000.0)
        if line.x0 > page_width * 0.45:
            continue
        matched = _anchor_match(line.text, config.start_labels, allow_no_colon=config.allow_no_colon)
        if matched is None:
            continue
        anchor_label, same_line_rest, start_mode = matched
        if config.field == "applicant" and _is_applicant_anchor_noise(line.text):
            continue

        segments: list[str] = []
        evidence_lines: list[str] = [_normalize_space(line.text)]
        boxes: list[tuple[float, float, float, float]] = []
        if config.field == "applicant" and (not same_line_rest) and (index > 0):
            prev_line = lines[index - 1]
            prev_text = _normalize_space(prev_line.text)
            if (
                prev_line.page == line.page
                and abs(float(prev_line.y0) - float(line.y0)) <= 2.5
                and prev_line.x0 > line.x0 + 15
                and prev_text
                and (not _starts_with_label(prev_text, ALL_STOP_LABELS))
            ):
                segments.append(prev_text)
                evidence_lines.append(prev_text)
                boxes.append((prev_line.x0, prev_line.y0, prev_line.x1, prev_line.y1))
        if same_line_rest:
            segments.append(same_line_rest)
            boxes.append((line.x0, line.y0, line.x1, line.y1))

        stop_reason = "eof"
        consumed = 0
        for next_index in range(index + 1, len(lines)):
            next_line = lines[next_index]
            next_text = _normalize_space(next_line.text)
            if not next_text:
                continue
            if next_line.page != line.page:
                stop_reason = "page_change"
                break
            if config.field == "applicant":
                if _is_title_like_line(next_text):
                    stop_reason = "title_line"
                    break
                if _is_numbered_item_start(next_text):
                    stop_reason = "numbered_item"
                    break
                if _is_checkbox_noise(next_text):
                    stop_reason = "checkbox_noise"
                    break
                if _is_long_body_line(next_text):
                    stop_reason = "long_body"
                    break
            if _starts_with_label(next_text, config.stop_labels):
                stop_reason = "next_label"
                break
            if _starts_with_label(next_text, ALL_STOP_LABELS):
                stop_reason = "next_label"
                break
            segments.append(next_text)
            evidence_lines.append(next_text)
            boxes.append((next_line.x0, next_line.y0, next_line.x1, next_line.y1))
            consumed += 1
            if consumed >= config.max_follow_lines:
                stop_reason = "max_lines"
                break

        value = _postprocess_value(config.field, " ".join(segments))
        if not value:
            continue
        auto_category = ""
        if config.field == "applicant":
            auto_category = _classify_applicant_value(value)
        bbox = _bbox_union(boxes if boxes else [(line.x0, line.y0, line.x1, line.y1)])
        return FieldResult(
            value=value,
            evidence=FieldEvidence(
                evidence_text=_normalize_space(" | ".join(evidence_lines[:4])),
                page=int(line.page) + 1,
                bbox=bbox,
                anchor_label=anchor_label,
                stop_reason=stop_reason,
                confidence=_compute_confidence(
                    start_mode=start_mode,
                    stop_reason=stop_reason,
                    captured_lines=max(1, len(segments)),
                ),
                start_mode=start_mode,
                line_index=index,
                auto_category=auto_category,
            ),
        )
    return FieldResult()


def _extract_phone_near_examiner(lines: list[VisualLine], examiner_result: FieldResult) -> FieldResult:
    anchor_index = int(examiner_result.evidence.line_index)
    if anchor_index < 0:
        return FieldResult()
    if anchor_index >= len(lines):
        return FieldResult()
    anchor_line = lines[anchor_index]
    start = max(0, anchor_index - 2)
    end = min(len(lines), anchor_index + 3)
    for index in range(start, end):
        line = lines[index]
        if line.page != anchor_line.page:
            continue
        text = _normalize_space(line.text)
        if ("电话" not in text) and ("联系电话" not in text):
            continue
        value = _normalize_phone(text)
        if not value:
            continue
        return FieldResult(
            value=value,
            evidence=FieldEvidence(
                evidence_text=text,
                page=int(line.page) + 1,
                bbox=_bbox_union([(line.x0, line.y0, line.x1, line.y1)]),
                anchor_label="审查员邻近电话",
                stop_reason="neighbor_window",
                confidence=0.72,
                start_mode="fallback_neighbor",
                line_index=index,
            ),
        )
    return FieldResult()


def _extract_from_doc(doc: Any, fields: tuple[str, ...]) -> tuple[dict[str, FieldResult], dict[str, int]]:
    lines, page_widths, stats = _collect_document_lines(doc)
    results: dict[str, FieldResult] = {field_name: FieldResult() for field_name in fields}

    if "applicant" in results:
        applicant = _extract_field(lines, page_widths, FIELD_CONFIGS["applicant"])
        results["applicant"] = _apply_applicant_fallback(lines, applicant)
    if "agency_raw" in results:
        results["agency_raw"] = _extract_field(lines, page_widths, FIELD_CONFIGS["agency_raw"])
    if "examiner" in results:
        results["examiner"] = _extract_field(lines, page_widths, FIELD_CONFIGS["examiner"])
    if "examiner_phone" in results:
        phone = _extract_field(lines, page_widths, FIELD_CONFIGS["examiner_phone"])
        if (not phone.value) and ("examiner" in results):
            phone = _extract_phone_near_examiner(lines, results["examiner"])
        results["examiner_phone"] = phone

    return results, stats


def extract_pdf_file(pdf_path: str, fields: tuple[str, ...]) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    try:
        field_results, stats = _extract_from_doc(doc, fields)
    finally:
        doc.close()

    values: dict[str, str] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for field_name in fields:
        result = field_results.get(field_name, FieldResult())
        values[field_name] = str(result.value or "")
        evidence[field_name] = {
            "evidence_text": str(result.evidence.evidence_text or ""),
            "page": int(result.evidence.page or 0),
            "bbox": list(result.evidence.bbox) if result.evidence.bbox else [],
            "anchor_label": str(result.evidence.anchor_label or ""),
            "stop_reason": str(result.evidence.stop_reason or ""),
            "confidence": float(result.evidence.confidence or 0.0),
            "auto_category": str(result.evidence.auto_category or ""),
        }

    return {
        "pdf_path": os.path.abspath(pdf_path),
        "pdf_name": os.path.basename(pdf_path),
        "values": values,
        "evidence": evidence,
        "rawdict_line_count": int(stats.get("raw_lines", 0)),
        "word_line_count": int(stats.get("word_lines", 0)),
    }


def extract_pdf_directory(pdf_root: str, fields: tuple[str, ...]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pdf_paths = _collect_pdf_paths(pdf_root)
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for pdf_path in pdf_paths:
        try:
            records.append(extract_pdf_file(pdf_path, fields))
        except Exception as exc:
            errors.append({"pdf_path": os.path.abspath(pdf_path), "error": str(exc)})
    summary = {
        "pdf_root": os.path.abspath(str(pdf_root or "").strip()),
        "total_pdfs": len(pdf_paths),
        "success_pdfs": len(records),
        "failed_pdfs": len(errors),
        "errors": errors,
        "fields": list(fields),
    }
    return records, summary


def _flatten_extract_row(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pdf_path": str(record.get("pdf_path", "") or ""),
        "pdf_name": str(record.get("pdf_name", "") or ""),
    }
    values = dict(record.get("values") or {})
    evidence = dict(record.get("evidence") or {})
    for field_name in fields:
        row[field_name] = str(values.get(field_name, "") or "")
        field_evidence = dict(evidence.get(field_name) or {})
        row[f"{field_name}_evidence_text"] = str(field_evidence.get("evidence_text", "") or "")
        row[f"{field_name}_page"] = str(field_evidence.get("page", "") or "")
        bbox = field_evidence.get("bbox") or []
        if isinstance(bbox, list) and len(bbox) == 4:
            row[f"{field_name}_bbox"] = _bbox_text(
                (
                    _safe_float(bbox[0]),
                    _safe_float(bbox[1]),
                    _safe_float(bbox[2]),
                    _safe_float(bbox[3]),
                )
            )
        else:
            row[f"{field_name}_bbox"] = ""
        row[f"{field_name}_anchor_label"] = str(field_evidence.get("anchor_label", "") or "")
        row[f"{field_name}_stop_reason"] = str(field_evidence.get("stop_reason", "") or "")
        row[f"{field_name}_confidence"] = str(field_evidence.get("confidence", "") or "")
        row[f"{field_name}_auto_category"] = str(field_evidence.get("auto_category", "") or "")
    row["rawdict_line_count"] = str(record.get("rawdict_line_count", "") or "")
    row["word_line_count"] = str(record.get("word_line_count", "") or "")
    return row


def _build_extract_headers(fields: tuple[str, ...]) -> list[str]:
    headers: list[str] = ["pdf_path", "pdf_name"]
    for field_name in fields:
        headers.extend(
            [
                field_name,
                f"{field_name}_evidence_text",
                f"{field_name}_page",
                f"{field_name}_bbox",
                f"{field_name}_anchor_label",
                f"{field_name}_stop_reason",
                f"{field_name}_confidence",
                f"{field_name}_auto_category",
            ]
        )
    headers.extend(["rawdict_line_count", "word_line_count"])
    return headers


def _write_extract_outputs(
    *,
    output_dir: str,
    fields: tuple[str, ...],
    records: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, str]:
    csv_path = os.path.join(output_dir, "extract_results.csv")
    jsonl_path = os.path.join(output_dir, "extract_results.jsonl")
    summary_path = os.path.join(output_dir, "extract_summary.json")
    rows = [_flatten_extract_row(record, fields) for record in records]
    _write_csv(csv_path, _build_extract_headers(fields), rows)
    _write_jsonl(jsonl_path, records)
    _write_json(summary_path, summary)
    return {"extract_csv": csv_path, "extract_jsonl": jsonl_path, "extract_summary_json": summary_path}


def run_extract_only(pdf_root: str, output_root: str, fields: tuple[str, ...]) -> dict[str, Any]:
    output_dir = _output_dir(output_root)
    _safe_mkdir(output_dir)
    records, summary = extract_pdf_directory(pdf_root, fields)

    non_empty_counts: dict[str, int] = {}
    for field_name in fields:
        non_empty_counts[field_name] = sum(
            1
            for record in records
            if str(dict(record.get("values") or {}).get(field_name, "") or "").strip()
        )
    summary["non_empty_counts"] = non_empty_counts
    summary["generated_at"] = datetime.now().isoformat(timespec="seconds")
    paths = _write_extract_outputs(output_dir=output_dir, fields=fields, records=records, summary=summary)

    return {
        "output_dir": output_dir,
        "pdf_root": os.path.abspath(str(pdf_root or "").strip()),
        "fields": list(fields),
        "total_pdfs": int(summary.get("total_pdfs", 0) or 0),
        "success_pdfs": int(summary.get("success_pdfs", 0) or 0),
        "failed_pdfs": int(summary.get("failed_pdfs", 0) or 0),
        **paths,
    }


def _read_strike_rows(xlsx_path: str) -> list[dict[str, str]]:
    workbook = openpyxl.load_workbook(xlsx_path)
    sheet = workbook[workbook.sheetnames[0]]
    headers = [str(sheet.cell(1, col).value or "").strip() for col in range(1, sheet.max_column + 1)]
    header_index = {name: idx + 1 for idx, name in enumerate(headers) if name}

    for required in (STRIKE_SOURCE_ZIP, STRIKE_OUTPUT_PDF_NAME, STRIKE_SUMMARY_PDF_PATH, STRIKE_ARCHIVE_PDF_PATH):
        if required not in header_index:
            workbook.close()
            raise ValueError(f"XLSX 缺少必要列: {required}")

    strike_rows: list[dict[str, str]] = []
    for row_idx in range(2, sheet.max_row + 1):
        row_base = {
            "row_index": str(row_idx),
            STRIKE_SOURCE_ZIP: str(sheet.cell(row_idx, header_index[STRIKE_SOURCE_ZIP]).value or "").strip(),
            STRIKE_OUTPUT_PDF_NAME: str(sheet.cell(row_idx, header_index[STRIKE_OUTPUT_PDF_NAME]).value or "").strip(),
            STRIKE_SUMMARY_PDF_PATH: str(sheet.cell(row_idx, header_index[STRIKE_SUMMARY_PDF_PATH]).value or "").strip(),
            STRIKE_ARCHIVE_PDF_PATH: str(sheet.cell(row_idx, header_index[STRIKE_ARCHIVE_PDF_PATH]).value or "").strip(),
        }
        for header, field_name in HEADER_TO_FIELD.items():
            col_index = header_index.get(header)
            if not col_index:
                continue
            cell = sheet.cell(row_idx, col_index)
            if not (cell.font and bool(cell.font.strike)):
                continue
            strike_rows.append(
                {
                    **row_base,
                    "field_name": field_name,
                    "field_header": header,
                    "old_value": str(cell.value or "").strip(),
                }
            )
    workbook.close()
    return strike_rows


def _normalize_file_key(name_or_path: str) -> str:
    return str(os.path.basename(str(name_or_path or "").strip())).strip().lower()


def _candidate_pdf_names(row: dict[str, str]) -> list[str]:
    names: list[str] = []
    for key in (STRIKE_OUTPUT_PDF_NAME, STRIKE_SUMMARY_PDF_PATH, STRIKE_ARCHIVE_PDF_PATH):
        value = str(row.get(key, "") or "").strip()
        if value:
            names.append(os.path.basename(value))
    source_zip = str(row.get(STRIKE_SOURCE_ZIP, "") or "").strip()
    if source_zip:
        base = os.path.basename(source_zip)
        if base.lower().endswith(".zip"):
            names.append(base[:-4] + ".pdf")
        names.append(base)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in names:
        norm = _normalize_file_key(item)
        if (not norm) or (norm in seen):
            continue
        seen.add(norm)
        deduped.append(item)
    return deduped


def _normalize_compare_value(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _is_suspect_category(category: str) -> bool:
    src = str(category or "").strip()
    return src.startswith("suspect_") or (not src)


def run_eval_strike(pdf_root: str, strike_xlsx: str, output_root: str) -> dict[str, Any]:
    output_dir = _output_dir(output_root)
    _safe_mkdir(output_dir)

    fields = DEFAULT_FIELDS
    records, extract_summary = extract_pdf_directory(pdf_root, fields)
    extract_summary["generated_at"] = datetime.now().isoformat(timespec="seconds")
    extract_paths = _write_extract_outputs(output_dir=output_dir, fields=fields, records=records, summary=extract_summary)

    strike_rows = _read_strike_rows(strike_xlsx)
    record_index: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        key = _normalize_file_key(str(record.get("pdf_name", "") or ""))
        if not key:
            continue
        record_index.setdefault(key, []).append(record)

    eval_rows: list[dict[str, Any]] = []
    unmapped_rows: list[dict[str, Any]] = []
    field_breakdown: dict[str, dict[str, int]] = {
        field_name: {"strike_total": 0, "mapped_total": 0, "unchanged_wrong": 0, "changed_candidate_fixed": 0, "empty_or_missing": 0}
        for field_name in fields
    }

    mapped_total = 0
    unchanged_wrong_total = 0
    changed_candidate_fixed_total = 0
    empty_or_missing_total = 0
    applicant_suspect_total = 0
    applicant_clean_total = 0

    for strike_row in strike_rows:
        field_name = str(strike_row.get("field_name", "") or "").strip()
        if field_name not in field_breakdown:
            continue
        field_breakdown[field_name]["strike_total"] += 1

        candidates = _candidate_pdf_names(strike_row)
        mapped_record: dict[str, Any] | None = None
        mapped_by = ""
        for candidate in candidates:
            matched = record_index.get(_normalize_file_key(candidate), [])
            if not matched:
                continue
            mapped_record = matched[0]
            mapped_by = candidate
            break

        old_value = str(strike_row.get("old_value", "") or "")
        new_value = ""
        reason = ""
        result = ""
        mapped_pdf_path = ""
        auto_category = ""
        if mapped_record is None:
            result = "empty_or_missing"
            reason = "unmapped_pdf"
            empty_or_missing_total += 1
            field_breakdown[field_name]["empty_or_missing"] += 1
            unmapped_rows.append(
                {
                    "row_index": strike_row.get("row_index", ""),
                    "field_name": strike_row.get("field_header", ""),
                    "source_zip": strike_row.get(STRIKE_SOURCE_ZIP, ""),
                    "output_pdf_name": strike_row.get(STRIKE_OUTPUT_PDF_NAME, ""),
                    "summary_pdf_path": strike_row.get(STRIKE_SUMMARY_PDF_PATH, ""),
                    "archive_pdf_path": strike_row.get(STRIKE_ARCHIVE_PDF_PATH, ""),
                    "candidates": ";".join(candidates),
                }
            )
        else:
            mapped_total += 1
            field_breakdown[field_name]["mapped_total"] += 1
            mapped_pdf_path = str(mapped_record.get("pdf_path", "") or "")
            new_value = str(dict(mapped_record.get("values") or {}).get(field_name, "") or "")
            auto_category = str(dict(dict(mapped_record.get("evidence") or {}).get(field_name) or {}).get("auto_category", "") or "")
            if not _normalize_compare_value(new_value):
                result = "empty_or_missing"
                reason = "empty_extracted"
                empty_or_missing_total += 1
                field_breakdown[field_name]["empty_or_missing"] += 1
            elif _normalize_compare_value(new_value) == _normalize_compare_value(old_value):
                result = "unchanged_wrong"
                reason = "same_as_strike_baseline"
                unchanged_wrong_total += 1
                field_breakdown[field_name]["unchanged_wrong"] += 1
            else:
                result = "changed_candidate_fixed"
                reason = "different_from_strike_baseline"
                changed_candidate_fixed_total += 1
                field_breakdown[field_name]["changed_candidate_fixed"] += 1

        if field_name == "applicant":
            if _is_suspect_category(auto_category):
                applicant_suspect_total += 1
            else:
                applicant_clean_total += 1

        eval_rows.append(
            {
                "row_index": strike_row.get("row_index", ""),
                "field_name": strike_row.get("field_header", ""),
                "old_value": old_value,
                "new_value": new_value,
                "result": result,
                "reason": reason,
                "auto_category": auto_category,
                "mapped_pdf_path": mapped_pdf_path,
                "mapped_by": mapped_by,
                STRIKE_SOURCE_ZIP: strike_row.get(STRIKE_SOURCE_ZIP, ""),
                STRIKE_OUTPUT_PDF_NAME: strike_row.get(STRIKE_OUTPUT_PDF_NAME, ""),
                STRIKE_SUMMARY_PDF_PATH: strike_row.get(STRIKE_SUMMARY_PDF_PATH, ""),
                STRIKE_ARCHIVE_PDF_PATH: strike_row.get(STRIKE_ARCHIVE_PDF_PATH, ""),
            }
        )

    strike_eval_path = os.path.join(output_dir, "strike_eval.csv")
    strike_summary_path = os.path.join(output_dir, "strike_eval_summary.json")
    unmapped_path = os.path.join(output_dir, "unmapped_rows.csv")
    applicant_review_path = os.path.join(output_dir, "applicant_round2_review.csv")

    _write_csv(
        strike_eval_path,
        [
            "row_index",
            "field_name",
            "old_value",
            "new_value",
            "result",
            "reason",
            "auto_category",
            "mapped_pdf_path",
            "mapped_by",
            STRIKE_SOURCE_ZIP,
            STRIKE_OUTPUT_PDF_NAME,
            STRIKE_SUMMARY_PDF_PATH,
            STRIKE_ARCHIVE_PDF_PATH,
        ],
        eval_rows,
    )
    _write_csv(
        unmapped_path,
        [
            "row_index",
            "field_name",
            "source_zip",
            "output_pdf_name",
            "summary_pdf_path",
            "archive_pdf_path",
            "candidates",
        ],
        unmapped_rows,
    )
    applicant_eval_rows = [row for row in eval_rows if str(row.get("field_name", "") or "").strip() == FIELD_TO_HEADER["applicant"]]
    applicant_review_rows: list[dict[str, Any]] = []
    for row in applicant_eval_rows:
        applicant_review_rows.append(
            {
                "row_index": row.get("row_index", ""),
                "mapped_pdf_path": row.get("mapped_pdf_path", ""),
                "old_value": row.get("old_value", ""),
                "new_value": row.get("new_value", ""),
                "auto_category": row.get("auto_category", ""),
                "人工确认正确值": "",
                "人工判定(pass/fail)": "",
                "备注": "",
            }
        )
    _write_csv(
        applicant_review_path,
        [
            "row_index",
            "mapped_pdf_path",
            "old_value",
            "new_value",
            "auto_category",
            "人工确认正确值",
            "人工判定(pass/fail)",
            "备注",
        ],
        applicant_review_rows,
    )

    strike_summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pdf_root": os.path.abspath(str(pdf_root or "").strip()),
        "strike_xlsx": os.path.abspath(str(strike_xlsx or "").strip()),
        "strike_total": len(strike_rows),
        "mapped_total": mapped_total,
        "unchanged_wrong_total": unchanged_wrong_total,
        "changed_candidate_fixed_total": changed_candidate_fixed_total,
        "empty_or_missing_total": empty_or_missing_total,
        "applicant_suspect_total": applicant_suspect_total,
        "applicant_clean_total": applicant_clean_total,
        "field_breakdown": field_breakdown,
    }
    _write_json(strike_summary_path, strike_summary)

    return {
        "output_dir": output_dir,
        "pdf_root": os.path.abspath(str(pdf_root or "").strip()),
        "strike_xlsx": os.path.abspath(str(strike_xlsx or "").strip()),
        **extract_paths,
        "strike_eval_csv": strike_eval_path,
        "strike_eval_summary_json": strike_summary_path,
        "unmapped_rows_csv": unmapped_path,
        "applicant_round2_review_csv": applicant_review_path,
        "strike_total": len(strike_rows),
        "mapped_total": mapped_total,
        "unchanged_wrong_total": unchanged_wrong_total,
        "changed_candidate_fixed_total": changed_candidate_fixed_total,
        "empty_or_missing_total": empty_or_missing_total,
        "applicant_suspect_total": applicant_suspect_total,
        "applicant_clean_total": applicant_clean_total,
    }


def _parse_fields(value: str) -> tuple[str, ...]:
    src = str(value or "").strip()
    if not src:
        return DEFAULT_FIELDS
    fields = [item.strip() for item in src.split(",") if item.strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for field_name in fields:
        if field_name not in SUPPORTED_FIELDS:
            raise ValueError(f"不支持的字段: {field_name}")
        if field_name in seen:
            continue
        seen.add(field_name)
        deduped.append(field_name)
    if not deduped:
        return DEFAULT_FIELDS
    return tuple(deduped)


def main() -> int:
    parser = argparse.ArgumentParser(description="数字PDF结构锚点实验脚本（独立于生产链路）。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract-only", help="仅提取并输出结构化结果。")
    extract_parser.add_argument("--pdf-root", required=True, help="数字PDF目录。")
    extract_parser.add_argument("--output-root", default="output", help="输出根目录，默认 output。")
    extract_parser.add_argument(
        "--fields",
        default="applicant,agency_raw,examiner,examiner_phone",
        help="字段列表，逗号分隔。",
    )

    eval_parser = subparsers.add_parser("eval-strike", help="按删除线XLSX评估结构锚点提取结果。")
    eval_parser.add_argument("--pdf-root", required=True, help="数字PDF目录。")
    eval_parser.add_argument("--strike-xlsx", required=True, help="删除线标注的XLSX文件。")
    eval_parser.add_argument("--output-root", default="output", help="输出根目录，默认 output。")

    args = parser.parse_args()
    if args.command == "extract-only":
        fields = _parse_fields(args.fields)
        result = run_extract_only(args.pdf_root, args.output_root, fields)
    else:
        result = run_eval_strike(args.pdf_root, args.strike_xlsx, args.output_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
