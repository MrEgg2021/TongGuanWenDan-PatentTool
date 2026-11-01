from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from core.logging_utils import logger

from .models import ClaimItem, FormalReviewDocument, Issue
from .text_utils import count_effective_chars

_REPEATED_WORD_RE = re.compile(r"([A-Za-z0-9\u4E00-\u9FFF]{2,})([ \t]*)(\1)")
_FIGURE_RANGE_RE = re.compile(
    r"图\s*(\d{1,4})([A-Za-z]?)\s*(?:-|~|～|至|到)\s*(?:图\s*)?(\d{1,4})([A-Za-z]?)"
)
_FIGURE_SINGLE_RE = re.compile(r"图\s*(\d{1,4})([A-Za-z]?)")
_DRAWINGS_LEADING_FIGURE_RE = re.compile(r"^\u56fe\s*(\d{1,4})([A-Za-z]?)")

_HEADING_PREFIX_PATTERNS = (
    re.compile(r"^[\s\u3000]*[\[\(（【]?\s*[0-9０-９]{1,4}\s*[\]\)）】]?\s*[\.．、]?\s*"),
    re.compile(r"^[\s\u3000]*[一二三四五六七八九十]+\s*[\.．、]\s*"),
    re.compile(r"^[\s\u3000]*[（(][一二三四五六七八九十]+[）)]\s*"),
)

_IMPL_HEADINGS = ("具体实施方式", "具体实施例", "实施例")
_DISCLOSURE_HEADINGS = ("发明内容", "实用新型内容", "技术方案", "有益效果")
_HEADING_GROUPS: dict[str, tuple[str, ...]] = {
    "technical_field": ("技术领域",),
    "background_art": ("背景技术",),
    "disclosure": _DISCLOSURE_HEADINGS,
    "impl": _IMPL_HEADINGS,
    "drawings": ("附图说明",),
}

_THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "method": ("方法", "工艺", "流程", "步骤"),
    "system": ("系统", "平台", "架构"),
    "device": ("装置", "设备", "机构", "组件"),
    "structure": ("结构", "构造"),
    "medium": ("计算机可读存储介质", "存储介质"),
    "program": ("计算机程序", "程序产品", "程序"),
}
_THEME_LABELS: dict[str, str] = {
    "method": "方法/工艺",
    "system": "系统/平台",
    "device": "装置/设备",
    "structure": "结构/构造",
    "medium": "存储介质",
    "program": "计算机程序",
}


@dataclass(slots=True, frozen=True)
class _LineInfo:
    text: str
    start: int
    end: int


@dataclass(slots=True, frozen=True)
class _DescriptionInfo:
    title: str
    title_start: int
    title_end: int
    title_missing: bool
    heading_presence: dict[str, bool]
    impl_heading_start: int | None
    lines: list[_LineInfo]


@dataclass(slots=True, frozen=True)
class _DescriptionDrawingsSection:
    text: str
    start: int
    end: int
    heading_text: str
    heading_start: int
    heading_end: int


@dataclass(slots=True, frozen=True)
class _DrawingsLeadingFigureRef:
    label: str
    span_start: int
    span_end: int
    line_text: str


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or ""))


def _normalize_heading_candidate(text: str) -> str:
    normalized = _normalize_text(text)
    normalized = re.sub(r"\s+", "", normalized)
    for pattern in _HEADING_PREFIX_PATTERNS:
        updated = pattern.sub("", normalized, count=1)
        if updated != normalized:
            normalized = updated
            break
    return normalized.strip()


def _effective_lines_with_offsets(text: str) -> list[_LineInfo]:
    source = str(text or "")
    if not source:
        return []

    lines: list[_LineInfo] = []
    cursor = 0
    for piece in source.splitlines(True):
        raw = str(piece or "").rstrip("\r\n")
        line_start = int(cursor)
        stripped = str(raw or "").strip()
        if stripped:
            left_trim = len(raw) - len(raw.lstrip())
            start = int(line_start + left_trim)
            end = int(start + len(stripped))
            lines.append(_LineInfo(text=stripped, start=start, end=end))
        cursor += len(piece)
    if cursor < len(source):
        raw = source[cursor:]
        stripped = str(raw or "").strip()
        if stripped:
            left_trim = len(raw) - len(raw.lstrip())
            start = int(cursor + left_trim)
            end = int(start + len(stripped))
            lines.append(_LineInfo(text=stripped, start=start, end=end))
    return lines


def _detect_heading_group(line: str) -> str | None:
    normalized = _normalize_heading_candidate(line)
    if not normalized:
        return None
    for group, keywords in _HEADING_GROUPS.items():
        if any(normalized.startswith(keyword) for keyword in keywords):
            return group
    return None


def _analyze_description(description_text: str) -> _DescriptionInfo:
    source = str(description_text or "")
    lines = _effective_lines_with_offsets(source)

    heading_presence: dict[str, bool] = {key: False for key in _HEADING_GROUPS}
    impl_heading_start: int | None = None
    for line in lines:
        group = _detect_heading_group(line.text)
        if not group:
            continue
        heading_presence[group] = True
        if group == "impl" and impl_heading_start is None:
            impl_heading_start = int(line.start)

    title = ""
    title_start = 0
    title_end = 0
    title_missing = True
    if lines:
        first = lines[0]
        if _detect_heading_group(first.text) is None:
            title = str(first.text or "")
            title_start = int(first.start)
            title_end = int(first.end)
            title_missing = False
        else:
            title_start = int(first.start)
            title_end = int(first.end)

    return _DescriptionInfo(
        title=title,
        title_start=title_start,
        title_end=title_end,
        title_missing=bool(title_missing),
        heading_presence=heading_presence,
        impl_heading_start=impl_heading_start,
        lines=lines,
    )


def _make_issue(
    *,
    rule_id: str,
    severity: str,
    section: str,
    message: str,
    snippet: str = "",
    span_start: int = 0,
    span_end: int = 0,
    claim_num: int | None = None,
    anchor: dict[str, object] | None = None,
) -> Issue:
    resolved_anchor = dict(anchor or {})
    rid = str(rule_id or "")
    if not str(resolved_anchor.get("intent", "") or ""):
        if rid == "description.drawings.figure.ref.missing_in_drawings_section":
            resolved_anchor["intent"] = "drawings_heading_line"
        elif rid == "drawings.figure.ref.missing_in_description_drawings":
            resolved_anchor["intent"] = "drawings_heading_line"
        elif rid == "drawings.figure.ref.missing_in_impl" or rid.startswith("description.impl_heading."):
            resolved_anchor["intent"] = "impl_heading_line"
        elif rid.startswith("description.title.") or rid.startswith("description.heading."):
            resolved_anchor["intent"] = "title_line"
    return Issue(
        rule_id=str(rule_id or ""),
        severity=str(severity or "warning"),
        category="rule",
        section=str(section or ""),
        claim_num=claim_num,
        span_start=int(max(0, span_start)),
        span_end=int(max(span_start, span_end)),
        snippet=str(snippet or ""),
        message=str(message or ""),
        anchor=resolved_anchor or None,
    )


def _select_primary_claim(claims: list[ClaimItem]) -> ClaimItem | None:
    if not claims:
        return None
    for claim in claims:
        if int(getattr(claim, "num", 0) or 0) == 1:
            return claim
    return sorted(list(claims), key=lambda row: int(getattr(row, "num", 0) or 0))[0]


def _figure_sort_key(label: str) -> tuple[int, str]:
    matched = re.match(r"^图(\d+)([A-Za-z]?)$", str(label or ""))
    if not matched:
        return (10**9, str(label or ""))
    return (int(matched.group(1)), str(matched.group(2) or "").upper())


def _format_figure_label(number: int, suffix: str) -> str:
    return f"图{int(number)}{str(suffix or '').upper()}"


def _is_inside_any_span(position: int, spans: list[tuple[int, int]]) -> bool:
    for start, end in spans:
        if int(start) <= int(position) < int(end):
            return True
    return False


def _extract_figure_refs(text: str, *, expand_limit: int = 200) -> set[str]:
    source = _normalize_text(text)
    if not source:
        return set()

    labels: set[str] = set()
    consumed_spans: list[tuple[int, int]] = []

    for matched in _FIGURE_RANGE_RE.finditer(source):
        consumed_spans.append((int(matched.start()), int(matched.end())))
        start_num = int(matched.group(1))
        start_suffix = str(matched.group(2) or "").upper()
        end_num = int(matched.group(3))
        end_suffix = str(matched.group(4) or "").upper()

        if start_suffix or end_suffix:
            labels.add(_format_figure_label(start_num, start_suffix))
            labels.add(_format_figure_label(end_num, end_suffix))
            continue

        low = min(start_num, end_num)
        high = max(start_num, end_num)
        if (high - low + 1) > int(max(1, expand_limit)):
            labels.add(_format_figure_label(start_num, ""))
            labels.add(_format_figure_label(end_num, ""))
            continue
        for number in range(low, high + 1):
            labels.add(_format_figure_label(number, ""))

    for matched in _FIGURE_SINGLE_RE.finditer(source):
        if _is_inside_any_span(int(matched.start()), consumed_spans):
            continue
        number = int(matched.group(1))
        suffix = str(matched.group(2) or "").upper()
        labels.add(_format_figure_label(number, suffix))

    return labels


def _format_case_sensitive_figure_label(number: int, suffix: str) -> str:
    return f"\u56fe{int(number)}{str(suffix or '')}"


def _extract_drawings_leading_figure_refs_with_spans(drawings_text: str) -> list[_DrawingsLeadingFigureRef]:
    source = str(drawings_text or "")
    if not source:
        return []

    refs: list[_DrawingsLeadingFigureRef] = []
    for line in _effective_lines_with_offsets(source):
        matched = _DRAWINGS_LEADING_FIGURE_RE.match(str(line.text or ""))
        if not matched:
            continue
        label = _format_case_sensitive_figure_label(
            int(matched.group(1)),
            str(matched.group(2) or ""),
        )
        span_start = int(line.start + matched.start())
        span_end = int(line.start + matched.end())
        refs.append(
            _DrawingsLeadingFigureRef(
                label=str(label),
                span_start=int(span_start),
                span_end=int(max(span_start, span_end)),
                line_text=str(line.text or ""),
            )
        )
    return refs


def _extract_description_drawings_section(description_text: str) -> _DescriptionDrawingsSection:
    source = str(description_text or "")
    if not source:
        return _DescriptionDrawingsSection("", 0, 0, "", 0, 0)
    lines = _effective_lines_with_offsets(source)
    if not lines:
        return _DescriptionDrawingsSection("", 0, 0, "", 0, 0)

    drawings_idx: int | None = None
    for idx, line in enumerate(lines):
        if _detect_heading_group(line.text) == "drawings":
            drawings_idx = int(idx)
            break
    if drawings_idx is None:
        return _DescriptionDrawingsSection("", 0, 0, "", 0, 0)

    heading = lines[drawings_idx]
    start = int(heading.start)
    end = int(len(source))
    for line in lines[drawings_idx + 1 :]:
        group = _detect_heading_group(line.text)
        if group is None:
            continue
        if group == "drawings":
            continue
        end = int(line.start)
        break

    return _DescriptionDrawingsSection(
        text=str(source[start:end] or ""),
        start=int(start),
        end=int(max(start, end)),
        heading_text=str(heading.text or ""),
        heading_start=int(heading.start),
        heading_end=int(max(heading.start, heading.end)),
    )


def _first_non_empty_line(text: str) -> str:
    for raw in str(text or "").splitlines():
        row = str(raw or "").strip()
        if row:
            return row
    return ""


def _format_theme_labels(tags: set[str]) -> str:
    if not tags:
        return ""
    ordered = sorted(list(tags), key=lambda tag: _THEME_LABELS.get(tag, tag))
    return "、".join([_THEME_LABELS.get(tag, tag) for tag in ordered])


def _extract_theme_tags(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", _normalize_text(text))
    if not compact:
        return set()

    found: set[str] = set()
    for tag, keywords in _THEME_KEYWORDS.items():
        for keyword in sorted(list(keywords), key=len, reverse=True):
            if keyword and keyword in compact:
                found.add(tag)
                break
    return found


def check_repeated_word_issues(
    text: str,
    *,
    section: str,
    claim_num: int | None = None,
    max_hits: int = 200,
) -> list[Issue]:
    source = str(text or "")
    if not source:
        return []

    issues: list[Issue] = []
    for idx, matched in enumerate(_REPEATED_WORD_RE.finditer(source), start=1):
        if idx > int(max(1, max_hits)):
            break
        start = int(matched.start())
        end = int(matched.end())
        snippet = str(source[start:end] or "")
        issues.append(
            _make_issue(
                rule_id="text.repeated_word",
                severity="warning",
                section=section,
                claim_num=claim_num,
                span_start=start,
                span_end=end,
                snippet=snippet,
                message=f"\u68c0\u6d4b\u5230\u76f8\u90bb\u91cd\u590d\u8bcd\u8bed\uff1a{snippet}",
            )
        )
    return issues


def check_description_heading_issues(document: FormalReviewDocument) -> list[Issue]:
    description = str(getattr(document, "description", "") or "")
    drawings = str(getattr(document, "drawings", "") or "")
    info = _analyze_description(description)
    has_drawings = bool(drawings.strip()) or bool(_extract_figure_refs(drawings))

    missing_labels: list[str] = []
    if not bool(info.heading_presence.get("technical_field")):
        missing_labels.append("\u6280\u672f\u9886\u57df")
    if not bool(info.heading_presence.get("background_art")):
        missing_labels.append("\u80cc\u666f\u6280\u672f")
    if not bool(info.heading_presence.get("disclosure")):
        missing_labels.append("\u53d1\u660e\u5185\u5bb9/\u5b9e\u7528\u65b0\u578b\u5185\u5bb9/\u6280\u672f\u65b9\u6848/\u6709\u76ca\u6548\u679c")
    if not bool(info.heading_presence.get("impl")):
        missing_labels.append("\u5177\u4f53\u5b9e\u65bd\u65b9\u5f0f/\u5177\u4f53\u5b9e\u65bd\u4f8b/\u5b9e\u65bd\u4f8b")
    if has_drawings and (not bool(info.heading_presence.get("drawings"))):
        missing_labels.append("\u9644\u56fe\u8bf4\u660e")

    if not missing_labels:
        return []

    snippet = str(info.title or (description[:20] if description else ""))
    return [
        _make_issue(
            rule_id="description.heading.missing.required",
            severity="error",
            section="description",
            span_start=int(info.title_start),
            span_end=int(info.title_end),
            snippet=snippet,
            message=f"\u8bf4\u660e\u4e66\u5c0f\u6807\u9898\u7f3a\u5931\uff1a{'; '.join(missing_labels)}",
        )
    ]


def check_description_title_issues(
    document: FormalReviewDocument,
    *,
    max_title_chars: int = 25,
) -> list[Issue]:
    description = str(getattr(document, "description", "") or "")
    info = _analyze_description(description)
    issues: list[Issue] = []

    if bool(info.title_missing):
        snippet = description[:20] if description else ""
        issues.append(
            _make_issue(
                rule_id="description.title.missing",
                severity="error",
                section="description",
                span_start=int(info.title_start),
                span_end=int(info.title_end),
                snippet=snippet,
                message="\u672a\u8bc6\u522b\u5230\u8bf4\u660e\u4e66\u6807\u9898\uff08\u8bf4\u660e\u4e66\u9996\u884c\u4e0d\u662f\u6807\u9898\u6216\u5185\u5bb9\u4e3a\u7a7a\uff09",
            )
        )
        return issues

    title = str(info.title or "")
    title_chars = int(count_effective_chars(title))
    if title_chars > int(max(1, max_title_chars)):
        issues.append(
            _make_issue(
                rule_id="description.title.length.exceeded",
                severity="warning",
                section="description",
                span_start=int(info.title_start),
                span_end=int(info.title_end),
                snippet=title,
                message=(
                    f"\u8bf4\u660e\u4e66\u6807\u9898\u957f\u5ea6\u8d85\u9650\uff1a{title_chars}\u5b57\uff08\u4e0a\u9650 "
                    f"{int(max(1, max_title_chars))}\u5b57\uff0c\u6309Word\u4e0d\u542b\u7a7a\u683c\u5b57\u7b26\u53e3\u5f84\uff09"
                ),
            )
        )
    return issues


def check_drawings_figure_reference_issues(
    document: FormalReviewDocument,
    *,
    expand_limit: int = 200,
) -> list[Issue]:
    description = str(getattr(document, "description", "") or "")
    drawings = str(getattr(document, "drawings", "") or "")
    drawing_refs = _extract_figure_refs(drawings, expand_limit=expand_limit)
    if not drawing_refs:
        return []

    info = _analyze_description(description)
    if info.impl_heading_start is None:
        snippet = str(info.title or (description[:20] if description else ""))
        return [
            _make_issue(
                rule_id="description.impl_heading.missing_for_figure_check",
                severity="error",
                section="description",
                span_start=int(info.title_start),
                span_end=int(info.title_end),
                snippet=snippet,
                message="\u672a\u627e\u5230\u201c\u5177\u4f53\u5b9e\u65bd\u65b9\u5f0f/\u5177\u4f53\u5b9e\u65bd\u4f8b/\u5b9e\u65bd\u4f8b\u201d\u8d77\u70b9\uff0c\u65e0\u6cd5\u6267\u884c\u9644\u56fe\u56fe\u53f7\u8986\u76d6\u6821\u5bf9",
            )
        ]

    impl_start = int(max(0, info.impl_heading_start))
    impl_text = description[impl_start:]
    impl_refs = _extract_figure_refs(impl_text, expand_limit=expand_limit)
    missing = sorted(list(drawing_refs - impl_refs), key=_figure_sort_key)
    if not missing:
        return []

    line_start = description.rfind("\n", 0, impl_start)
    if line_start < 0:
        line_start = 0
    else:
        line_start += 1
    line_end = description.find("\n", impl_start)
    if line_end < 0:
        line_end = len(description)
    snippet = str(description[line_start:line_end] or "")
    return [
        _make_issue(
            rule_id="drawings.figure.ref.missing_in_impl",
            severity="warning",
            section="description",
            span_start=int(line_start),
            span_end=int(line_end),
            snippet=snippet,
            message=f"\u9644\u56fe\u56fe\u53f7\u672a\u5728\u5b9e\u65bd\u65b9\u5f0f\u5185\u8986\u76d6\uff1a{', '.join(missing)}",
        )
    ]


def check_drawings_cross_section_consistency_issues(
    document: FormalReviewDocument,
    *,
    expand_limit: int = 200,
) -> list[Issue]:
    description = str(getattr(document, "description", "") or "")
    drawings = str(getattr(document, "drawings", "") or "")

    desc_drawings = _extract_description_drawings_section(description)
    desc_refs = _extract_figure_refs(desc_drawings.text, expand_limit=expand_limit)
    drawing_refs = _extract_figure_refs(drawings, expand_limit=expand_limit)
    if (not desc_refs) or (not drawing_refs):
        return []

    issues: list[Issue] = []
    missing_in_drawings = sorted(list(desc_refs - drawing_refs), key=_figure_sort_key)
    if missing_in_drawings:
        snippet = str(desc_drawings.heading_text or "").strip() or _first_non_empty_line(desc_drawings.text) or "附图说明"
        span_start = int(
            desc_drawings.heading_start
            if desc_drawings.heading_end > desc_drawings.heading_start
            else desc_drawings.start
        )
        span_end = int(
            desc_drawings.heading_end
            if desc_drawings.heading_end > span_start
            else span_start + max(1, len(str(snippet or "")))
        )
        issues.append(
            _make_issue(
                rule_id="description.drawings.figure.ref.missing_in_drawings_section",
                severity="error",
                section="description",
                span_start=int(span_start),
                span_end=int(span_end),
                snippet=snippet,
                message=f"附图说明图号未在说明书附图中出现：{', '.join(missing_in_drawings)}",
                anchor={
                    "intent": "drawings_heading_line",
                    "expected_hit": str(snippet or ""),
                    "expected_hit_candidates": [str(snippet or "")],
                },
            )
        )

    missing_in_description = sorted(list(drawing_refs - desc_refs), key=_figure_sort_key)
    if missing_in_description:
        fallback_used = False
        fallback_suffix = ""
        heading_text = str(desc_drawings.heading_text or "").strip()
        heading_start = int(desc_drawings.heading_start)
        heading_end = int(desc_drawings.heading_end)
        has_heading = bool(heading_text) and heading_end > heading_start
        if has_heading:
            span_start = int(heading_start)
            span_end = int(heading_end)
            snippet = heading_text
            expected_hit = "附图说明"
            expected_hit_candidates = [expected_hit]
            if heading_text not in expected_hit_candidates:
                expected_hit_candidates.append(heading_text)
        else:
            lines = _effective_lines_with_offsets(description)
            if lines:
                first_line = lines[0]
                span_start = int(first_line.start)
                span_end = int(max(first_line.start, first_line.end))
                snippet = str(first_line.text or "").strip() or "附图说明"
            else:
                span_start = 0
                snippet = "附图说明"
                span_end = int(max(1, len(snippet)))
            expected_hit = snippet
            expected_hit_candidates = [snippet]
            fallback_used = True
            fallback_suffix = "（未识别附图说明标题，已回退定位）"
        issues.append(
            _make_issue(
                rule_id="drawings.figure.ref.missing_in_description_drawings",
                severity="error",
                section="description",
                span_start=int(span_start),
                span_end=int(span_end),
                snippet=snippet,
                message=f"说明书附图图号未在附图说明中出现：{', '.join(missing_in_description)}{fallback_suffix}",
                anchor={
                    "intent": "drawings_heading_line",
                    "expected_hit": str(expected_hit or ""),
                    "expected_hit_candidates": list(expected_hit_candidates),
                    "fallback_used": bool(fallback_used),
                },
            )
        )

    return issues


def check_drawings_duplicate_figure_issues(document: FormalReviewDocument) -> list[Issue]:
    drawings = str(getattr(document, "drawings", "") or "")
    refs = _extract_drawings_leading_figure_refs_with_spans(drawings)
    if not refs:
        return []

    issues: list[Issue] = []
    samples: list[str] = []
    seen_counts: dict[str, int] = {}
    for ref in refs:
        key = str(ref.label or "")
        if not key:
            continue
        seen_counts[key] = int(seen_counts.get(key, 0)) + 1
        occurrence = int(seen_counts[key])
        if occurrence <= 1:
            continue
        issues.append(
            _make_issue(
                rule_id="drawings.figure.ref.duplicate_in_drawings_section",
                severity="error",
                section="drawings",
                span_start=int(ref.span_start),
                span_end=int(ref.span_end),
                snippet=str(ref.label),
                message=(
                    f"\u8bf4\u660e\u4e66\u9644\u56fe\u56fe\u53f7\u91cd\u590d\uff1a{ref.label}"
                    f"\uff08\u7b2c{occurrence}\u6b21\u51fa\u73b0\uff09"
                ),
                anchor={
                    "intent": "drawings_section_lead",
                    "expected_hit": str(ref.label or ""),
                    "expected_hit_candidates": [str(ref.label or ""), str(ref.line_text or "")],
                },
            )
        )
        samples.append(f"{ref.label}@{int(ref.span_start)}-{int(ref.span_end)}")
    if issues:
        try:
            logger.debug(
                "[formal_review][semantic][drawings_duplicate] duplicate_figures_hits=%s samples=%s",
                int(len(issues)),
                "; ".join(samples[:6]),
            )
        except Exception:
            pass
    return issues


def check_theme_consistency_issues(document: FormalReviewDocument) -> list[Issue]:
    description = str(getattr(document, "description", "") or "")
    abstract = str(getattr(document, "abstract", "") or "")
    info = _analyze_description(description)
    if info.title_missing:
        return []

    issues: list[Issue] = []
    title = str(info.title or "")
    title_tags = _extract_theme_tags(title)
    if not title_tags:
        issues.append(
            _make_issue(
                rule_id="theme.title.unrecognized",
                severity="warning",
                section="description",
                span_start=int(info.title_start),
                span_end=int(info.title_end),
                snippet=title,
                message="\u8bf4\u660e\u4e66\u6807\u9898\u672a\u8bc6\u522b\u51fa\u4e3b\u9898\u7c7b\u578b\uff08\u65b9\u6cd5/\u7cfb\u7edf/\u88c5\u7f6e/\u7ed3\u6784/\u4ecb\u8d28/\u7a0b\u5e8f\uff09",
            )
        )

    claim1 = _select_primary_claim(list(getattr(document, "claims", []) or []))
    if claim1 is not None:
        claim_text = str(getattr(claim1, "text", "") or "")
        claim_tags = _extract_theme_tags(claim_text)
        claim_num = int(getattr(claim1, "num", 0) or 0)
        if len(claim_tags) > 1:
            issues.append(
                _make_issue(
                    rule_id="theme.claim1.multi_subject",
                    severity="warning",
                    section="claims",
                    claim_num=claim_num if claim_num > 0 else None,
                    span_start=0,
                    span_end=min(len(claim_text), 30),
                    snippet=claim_text[:30],
                    message=f"\u6743\u5229\u8981\u6c421\u8bc6\u522b\u5230\u591a\u4e2a\u4e3b\u9898\uff1a{_format_theme_labels(claim_tags)}",
                )
            )
        if title_tags and claim_tags and (not claim_tags.issubset(title_tags)):
            issues.append(
                _make_issue(
                    rule_id="theme.title_claim1.mismatch",
                    severity="warning",
                    section="claims",
                    claim_num=claim_num if claim_num > 0 else None,
                    span_start=0,
                    span_end=min(len(claim_text), 30),
                    snippet=claim_text[:30],
                    message=(
                        f"\u6807\u9898\u4e3b\u9898\uff08{_format_theme_labels(title_tags)}\uff09"
                        f"\u4e0e\u6743\u5229\u8981\u6c421\u4e3b\u9898\uff08{_format_theme_labels(claim_tags)}\uff09\u4e0d\u4e00\u81f4"
                    ),
                )
            )

    abstract_tags = _extract_theme_tags(abstract)
    if title_tags and abstract_tags and title_tags.isdisjoint(abstract_tags):
        issues.append(
            _make_issue(
                rule_id="theme.title_abstract.mismatch",
                severity="warning",
                section="abstract",
                span_start=0,
                span_end=min(len(abstract), 30),
                snippet=abstract[:30],
                message=(
                    f"\u6807\u9898\u4e3b\u9898\uff08{_format_theme_labels(title_tags)}\uff09"
                    f"\u4e0e\u6458\u8981\u4e3b\u9898\uff08{_format_theme_labels(abstract_tags)}\uff09\u65e0\u4ea4\u96c6"
                ),
            )
        )

    return issues


__all__ = [
    "check_description_heading_issues",
    "check_description_title_issues",
    "check_drawings_cross_section_consistency_issues",
    "check_drawings_duplicate_figure_issues",
    "check_drawings_figure_reference_issues",
    "check_repeated_word_issues",
    "check_theme_consistency_issues",
]

