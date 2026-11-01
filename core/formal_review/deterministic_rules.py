from __future__ import annotations

from collections import Counter
import re
import unicodedata
from typing import Iterable

from .models import ClaimItem, FormalReviewDocument, Issue

_MAX_HITS_PER_RULE = 100

_HEADING_ALIASES = (
    "技术领域",
    "背景技术",
    "发明内容",
    "实用新型内容",
    "技术方案",
    "有益效果",
    "附图说明",
    "具体实施方式",
    "具体实施例",
    "实施例",
)
_IMPL_HEADINGS = ("具体实施方式", "具体实施例", "实施例")
_HEADING_PREFIX_RE = re.compile(
    r"^\s*(?:(?:[0-9０-９]{1,4}|[一二三四五六七八九十]+)\s*[.．、]|[（(][一二三四五六七八九十0-9０-９]+[）)])?\s*"
)
_PLACEHOLDER_PATTERN = r"\bXXX+\b|\bTODO\b|待补充|未填写|【\s*】"
_PLACEHOLDER_RE = re.compile(_PLACEHOLDER_PATTERN, re.IGNORECASE)
_TEMPLATE_RESIDUE_RE = re.compile(r"此处省略|后续完善|根据客户补充|请在此处")
_IMPL_CLAIM_REFERENCE_RE = re.compile(r"如\s*权利要求\s*\d+(?:\s*[至\-—~～、,，和及与]\s*\d+)*\s*所述")
_ABSTRACT_PROMOTIONAL_RE = re.compile(r"国际领先|国内领先|世界领先|全球领先|性能卓越|效果最佳|最先进|填补空白")
_ABSTRACT_CLAIM_NUMBER_RE = re.compile(r"(?m)^\s*(?:权利要求\s*)?\d{1,4}\s*[.．、)）]")
_UNCLEAR_REFERENCE_RE = re.compile(r"如图所示|如说明书所述|参见附图|见说明书")
_WEAK_LIMITATION_RE = re.compile(r"优选地|较佳地|例如|举例来说|可以")
_NON_CLAIM_ARTIFACT_RE = re.compile(r"流程图|方框图|框图|曲线图|相图")
_FORMULA_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*\s*=\s*[A-Za-z0-9_+\-*/^().]+")
_FORMULA_EXPLANATION_RE = re.compile(r"其中|式中|表示|代表|参数|系数|常数|变量")
_ABNORMAL_WHITESPACE_RE = re.compile(r"[ \t\u3000]{2,}")
_FIGURE_ARABIC_RE = re.compile(r"图(?P<space>\s*)(?P<number>\d{1,4})", re.IGNORECASE)
_FIGURE_CHINESE_RE = re.compile(r"图\s*([零〇一二三四五六七八九十百]{1,6})")

_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _make_issue(
    *,
    rule_id: str,
    severity: str,
    section: str,
    message: str,
    claim_num: int | None = None,
    span_start: int = 0,
    span_end: int = 0,
    snippet: str = "",
) -> Issue:
    start = max(0, int(span_start))
    end = max(start, int(span_end))
    return Issue(
        rule_id=rule_id,
        severity=severity,
        category=section,
        section=section,
        message=message,
        claim_num=claim_num,
        span_start=start,
        span_end=end,
        snippet=snippet,
    )


def _append_bounded(
    issues: list[Issue],
    issue: Issue,
    hit_counts: Counter[str],
) -> None:
    rule_id = str(issue.rule_id or "")
    if hit_counts[rule_id] >= _MAX_HITS_PER_RULE:
        return
    issues.append(issue)
    hit_counts[rule_id] += 1


def _normalize_heading(line: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(line or "")).strip()
    normalized = _HEADING_PREFIX_RE.sub("", normalized, count=1)
    return re.sub(r"\s+", "", normalized)


def _heading_name(line: str) -> str:
    normalized = _normalize_heading(line)
    for heading in _HEADING_ALIASES:
        if normalized == heading:
            return heading
    return ""


def _line_offsets(text: str) -> list[tuple[str, int, int]]:
    source = str(text or "")
    rows: list[tuple[str, int, int]] = []
    cursor = 0
    for piece in source.splitlines(keepends=True):
        raw = piece.rstrip("\r\n")
        stripped = raw.strip()
        if stripped:
            left = len(raw) - len(raw.lstrip())
            start = cursor + left
            rows.append((stripped, start, start + len(stripped)))
        cursor += len(piece)
    if cursor < len(source):
        raw = source[cursor:]
        stripped = raw.strip()
        if stripped:
            left = len(raw) - len(raw.lstrip())
            start = cursor + left
            rows.append((stripped, start, start + len(stripped)))
    return rows


def _missing_numbers(numbers: Iterable[int]) -> list[int]:
    unique = sorted({int(number) for number in numbers if int(number) > 0})
    if len(unique) < 2:
        return []
    expected = set(range(unique[0], unique[-1] + 1))
    return sorted(expected.difference(unique))


def _chinese_numeral_to_int(text: str) -> int | None:
    source = str(text or "")
    if not source:
        return None
    if all(ch in _CHINESE_DIGITS for ch in source):
        value = 0
        for ch in source:
            value = value * 10 + _CHINESE_DIGITS[ch]
        return value

    total = 0
    current = 0
    for ch in source:
        if ch in _CHINESE_DIGITS:
            current = _CHINESE_DIGITS[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current


def _extract_figure_numbers(text: str) -> list[int]:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    numbers = [int(matched.group("number")) for matched in _FIGURE_ARABIC_RE.finditer(normalized)]
    for matched in _FIGURE_CHINESE_RE.finditer(normalized):
        value = _chinese_numeral_to_int(matched.group(1))
        if value is not None:
            numbers.append(value)
    return numbers


def _figure_section_text(description: str) -> str:
    source = str(description or "")
    rows = _line_offsets(source)
    start: int | None = None
    end = len(source)
    for line, line_start, _line_end in rows:
        heading = _heading_name(line)
        if start is None:
            if heading == "附图说明":
                start = line_start
            continue
        if heading and heading != "附图说明":
            end = line_start
            break
    if start is None:
        return ""
    return source[start:end]


def _implementation_text(description: str) -> tuple[str, int]:
    source = str(description or "")
    for line, line_start, _line_end in _line_offsets(source):
        if _heading_name(line) in _IMPL_HEADINGS:
            return source[line_start:], line_start
    return "", 0


def _first_match_issue(
    *,
    pattern: re.Pattern[str],
    text: str,
    rule_id: str,
    severity: str,
    section: str,
    message: str,
) -> list[Issue]:
    matched = pattern.search(str(text or ""))
    if matched is None:
        return []
    return [
        _make_issue(
            rule_id=rule_id,
            severity=severity,
            section=section,
            message=message,
            span_start=matched.start(),
            span_end=matched.end(),
            snippet=matched.group(0),
        )
    ]


def check_claim_numbering_issues(claims: list[ClaimItem]) -> list[Issue]:
    claim_list = list(claims or [])
    if not claim_list:
        return []

    numbers = [int(claim.num) for claim in claim_list if int(claim.num) > 0]
    if not numbers:
        return []

    issues: list[Issue] = []
    if min(numbers) != 1:
        issues.append(
            _make_issue(
                rule_id="claim.number.start_at_one",
                severity="error",
                section="claims",
                message=f"权利要求编号应从1开始，当前最小编号为{min(numbers)}。",
                claim_num=numbers[0],
            )
        )

    duplicates = sorted(number for number, count in Counter(numbers).items() if count > 1)
    if duplicates:
        issues.append(
            _make_issue(
                rule_id="claim.number.duplicate",
                severity="error",
                section="claims",
                message=f"权利要求编号重复：{', '.join(str(number) for number in duplicates)}。",
                claim_num=duplicates[0],
            )
        )

    missing = _missing_numbers(numbers)
    if missing:
        issues.append(
            _make_issue(
                rule_id="claim.number.gap",
                severity="error",
                section="claims",
                message=f"权利要求编号不连续，缺少：{', '.join(str(number) for number in missing)}。",
                claim_num=missing[0],
            )
        )
    return issues


def check_claim_text_issues(
    claims: list[ClaimItem],
    *,
    marker_note_map: dict[str, str] | None = None,
    description_text: str = "",
) -> list[Issue]:
    issues: list[Issue] = []
    hit_counts: Counter[str] = Counter()
    normalized_map = {
        str(marker).strip(): str(name).strip()
        for marker, name in dict(marker_note_map or {}).items()
        if str(marker).strip() and str(name).strip()
    }
    description = unicodedata.normalize("NFKC", str(description_text or ""))

    for claim in list(claims or []):
        source = str(claim.text or "")
        claim_num = int(claim.num)

        for marker, name in normalized_map.items():
            pattern = re.compile(
                rf"{re.escape(name)}\s*(?P<marker>{re.escape(marker)})(?![0-9A-Za-z/])"
            )
            matched = pattern.search(source)
            if matched is not None:
                prefix = source[max(0, matched.start("marker") - 1) : matched.start("marker")]
                if prefix not in {"(", "（", "[", "【"}:
                    _append_bounded(
                        issues,
                        _make_issue(
                            rule_id="claim.marker.parentheses_missing",
                            severity="warning",
                            section="claims",
                            claim_num=claim_num,
                            span_start=matched.start("marker"),
                            span_end=matched.end("marker"),
                            snippet=matched.group(0),
                            message=f"权利要求{claim_num}中的附图标记{marker}未使用括号。",
                        ),
                        hit_counts,
                    )
                    break

        for rule_id, severity, pattern, message in (
            (
                "claim.reference.unclear_external",
                "warning",
                _UNCLEAR_REFERENCE_RE,
                f"权利要求{claim_num}包含不清楚的外部引用表达。",
            ),
            (
                "claim.language.weak_limitation",
                "info",
                _WEAK_LIMITATION_RE,
                f"权利要求{claim_num}包含可能削弱限定清晰度的提示词，请人工复核。",
            ),
            (
                "claim.content.non_claim_artifact",
                "warning",
                _NON_CLAIM_ARTIFACT_RE,
                f"权利要求{claim_num}包含图表类内容提示，请确认是否应保留在权利要求文本中。",
            ),
        ):
            matched = pattern.search(source)
            if matched is not None:
                _append_bounded(
                    issues,
                    _make_issue(
                        rule_id=rule_id,
                        severity=severity,
                        section="claims",
                        claim_num=claim_num,
                        span_start=matched.start(),
                        span_end=matched.end(),
                        snippet=matched.group(0),
                        message=message,
                    ),
                    hit_counts,
                )

        formula = _FORMULA_RE.search(source)
        if formula is not None:
            context_start = max(0, formula.start() - 20)
            context_end = min(len(source), formula.end() + 80)
            context = source[context_start:context_end]
            if _FORMULA_EXPLANATION_RE.search(context) is None:
                _append_bounded(
                    issues,
                    _make_issue(
                        rule_id="claim.formula.parameter_explanation_missing",
                        severity="info",
                        section="claims",
                        claim_num=claim_num,
                        span_start=formula.start(),
                        span_end=formula.end(),
                        snippet=formula.group(0),
                        message=f"权利要求{claim_num}中的公式附近未检测到明显参数说明，请人工复核。",
                    ),
                    hit_counts,
                )

        for marker in dict.fromkeys(str(item).strip() for item in list(claim.markers or [])):
            if not marker or marker in normalized_map:
                continue
            marker_pattern = re.compile(rf"(?<![0-9A-Za-z/]){re.escape(marker)}(?![0-9A-Za-z/])")
            if marker_pattern.search(description) is not None:
                continue
            _append_bounded(
                issues,
                _make_issue(
                    rule_id="claim.marker.missing_in_description",
                    severity="warning",
                    section="claims",
                    claim_num=claim_num,
                    snippet=marker,
                    message=f"权利要求{claim_num}中的附图标记{marker}未在说明书中找到对应编号。",
                ),
                hit_counts,
            )
            break
    return issues


def check_description_deterministic_issues(document: FormalReviewDocument) -> list[Issue]:
    source = str(document.description or "")
    if not source:
        return []

    issues: list[Issue] = []
    headings: list[tuple[str, int, int]] = []
    for line, start, end in _line_offsets(source):
        heading = _heading_name(line)
        if heading:
            headings.append((heading, start, end))
    duplicates = sorted(name for name, count in Counter(name for name, _start, _end in headings).items() if count > 1)
    if duplicates:
        name = duplicates[0]
        start, end = next((start, end) for heading, start, end in headings if heading == name)
        issues.append(
            _make_issue(
                rule_id="description.heading.duplicate",
                severity="warning",
                section="description",
                span_start=start,
                span_end=end,
                snippet=name,
                message=f"说明书章节标题重复：{', '.join(duplicates)}。",
            )
        )

    figure_text = _figure_section_text(source)
    missing = _missing_numbers(_extract_figure_numbers(figure_text))
    if missing:
        section_start = source.find(figure_text)
        issues.append(
            _make_issue(
                rule_id="description.figure.number.gap",
                severity="error",
                section="description",
                span_start=max(0, section_start),
                span_end=max(0, section_start) + min(len(figure_text), 40),
                snippet=figure_text[:40],
                message=f"附图说明图号不连续，缺少：{', '.join(f'图{number}' for number in missing)}。",
            )
        )

    issues.extend(
        _first_match_issue(
            pattern=_PLACEHOLDER_RE,
            text=source,
            rule_id="description.placeholder.residue",
            severity="error",
            section="description",
            message="说明书中存在未完成占位符。",
        )
    )
    issues.extend(
        _first_match_issue(
            pattern=_TEMPLATE_RESIDUE_RE,
            text=source,
            rule_id="description.template.residue",
            severity="warning",
            section="description",
            message="说明书中存在模板残留文字。",
        )
    )

    implementation, offset = _implementation_text(source)
    matched = _IMPL_CLAIM_REFERENCE_RE.search(implementation)
    if matched is not None:
        issues.append(
            _make_issue(
                rule_id="description.impl.claim_reference_style",
                severity="warning",
                section="description",
                span_start=offset + matched.start(),
                span_end=offset + matched.end(),
                snippet=matched.group(0),
                message="具体实施方式中使用了权利要求引用式写法，建议改为完整描述。",
            )
        )
    return issues


def check_abstract_deterministic_issues(document: FormalReviewDocument) -> list[Issue]:
    source = str(document.abstract or "")
    if not source.strip():
        return [
            _make_issue(
                rule_id="abstract.missing",
                severity="error",
                section="abstract",
                message="缺少摘要内容。",
            )
        ]

    issues: list[Issue] = []
    issues.extend(
        _first_match_issue(
            pattern=_ABSTRACT_PROMOTIONAL_RE,
            text=source,
            rule_id="abstract.promotional_language",
            severity="warning",
            section="abstract",
            message="摘要中存在宣传性或评价性词语。",
        )
    )
    placeholder = re.compile(rf"(?:{_PLACEHOLDER_PATTERN})|(?:{_TEMPLATE_RESIDUE_RE.pattern})", re.IGNORECASE)
    issues.extend(
        _first_match_issue(
            pattern=placeholder,
            text=source,
            rule_id="abstract.placeholder.residue",
            severity="error",
            section="abstract",
            message="摘要中存在占位符或模板残留。",
        )
    )
    issues.extend(
        _first_match_issue(
            pattern=_ABSTRACT_CLAIM_NUMBER_RE,
            text=source,
            rule_id="abstract.claim_numbering_style",
            severity="warning",
            section="abstract",
            message="摘要使用了权利要求式编号，请改为连续摘要文本。",
        )
    )
    return issues


def check_drawings_deterministic_issues(document: FormalReviewDocument) -> list[Issue]:
    source = str(document.drawings or "")
    if not source.strip():
        return []

    issues: list[Issue] = []
    missing = _missing_numbers(_extract_figure_numbers(source))
    if missing:
        issues.append(
            _make_issue(
                rule_id="drawings.figure.number.gap",
                severity="error",
                section="drawings",
                span_start=0,
                span_end=min(len(source), 40),
                snippet=source[:40],
                message=f"附图编号不连续，缺少：{', '.join(f'图{number}' for number in missing)}。",
            )
        )

    styles: set[str] = set()
    normalized = unicodedata.normalize("NFKC", source)
    for matched in _FIGURE_ARABIC_RE.finditer(normalized):
        styles.add("arabic_spaced" if matched.group("space") else "arabic_compact")
    if _FIGURE_CHINESE_RE.search(normalized):
        styles.add("chinese")
    if len(styles) > 1:
        issues.append(
            _make_issue(
                rule_id="drawings.figure.format.mixed",
                severity="warning",
                section="drawings",
                span_start=0,
                span_end=min(len(source), 40),
                snippet=source[:40],
                message="附图图号格式混用，请统一为同一种编号格式。",
            )
        )
    return issues


def check_text_consistency_issues(document: FormalReviewDocument) -> list[Issue]:
    sections = [
        ("claims", "\n".join(str(claim.text or "") for claim in list(document.claims or []))),
        ("description", str(document.description or "")),
        ("abstract", str(document.abstract or "")),
        ("drawings", str(document.drawings or "")),
    ]
    combined = "\n".join(text for _section, text in sections if text)
    if not combined:
        return []

    issues: list[Issue] = []
    if re.search(r"[0-9]", combined) and re.search(r"[０-９]", combined):
        section, section_text = next(
            ((section, text) for section, text in sections if re.search(r"[０-９]", text)),
            ("description", combined),
        )
        matched = re.search(r"[０-９]", section_text)
        issues.append(
            _make_issue(
                rule_id="text.numbering.width.mixed",
                severity="warning",
                section=section,
                span_start=matched.start() if matched else 0,
                span_end=matched.end() if matched else 0,
                snippet=matched.group(0) if matched else "",
                message="全文混用了全角和半角数字。",
            )
        )

    symbol_pairs = (("（", "("), ("）", ")"), ("，", ","), ("：", ":"), ("；", ";"))
    if any(full in combined and half in combined for full, half in symbol_pairs):
        section = next(
            (
                section
                for section, text in sections
                if any(full in text or half in text for full, half in symbol_pairs)
            ),
            "description",
        )
        issues.append(
            _make_issue(
                rule_id="text.symbol.width.mixed",
                severity="warning",
                section=section,
                message="全文混用了对应的中文和英文符号。",
            )
        )

    for section, text in sections:
        matched = _ABNORMAL_WHITESPACE_RE.search(text)
        if matched is None:
            continue
        issues.append(
            _make_issue(
                rule_id="text.abnormal_whitespace",
                severity="warning",
                section=section,
                span_start=matched.start(),
                span_end=matched.end(),
                snippet=matched.group(0),
                message="文本中存在连续空格、Tab或全角空格。",
            )
        )
        break
    return issues


__all__ = [
    "check_abstract_deterministic_issues",
    "check_claim_numbering_issues",
    "check_claim_text_issues",
    "check_description_deterministic_issues",
    "check_drawings_deterministic_issues",
    "check_text_consistency_issues",
]
