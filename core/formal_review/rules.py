from __future__ import annotations

import re
import unicodedata

from .claim_refs import (
    check_claim_reference_issues,
    parse_claim_references,
    recursive_multi_reference_hits,
    recursive_referenced_claims,
)
from .models import ClaimItem, Issue
from .text_utils import count_effective_chars, extract_figure_markers, normalize_marker_token

_INLINE_SPACE_RE = re.compile(r"[^\S\r\n]+")
_OPEN_WRAPPER_PUNCTS = {
    "(",
    "[",
    "{",
    "（",
    "【",
    "〔",
    "〈",
    "《",
    "「",
    "『",
    "“",
    "‘",
    "'",
    '"',
}
_CLOSE_WRAPPER_PUNCTS = {
    ")",
    "]",
    "}",
    "）",
    "】",
    "〕",
    "〉",
    "》",
    "」",
    "』",
    "”",
    "’",
    "'",
    '"',
}
_BRIDGE_CONNECTOR_PUNCTS = set("，、；：,.!?？！。")
_REFER_PHRASE_STOP_CHARS = set("，、；：。！？,.!?\r\n")
_REFER_INLINE_SPACE_RE = re.compile(r"[^\S\r\n]+")
_REFER_INLINE_WS_PATTERN = r"[^\S\r\n]*"
_CLAIM_CHARACTERIZING_RE = re.compile(
    r"(?:其[^\S\r\n]*特[^\S\r\n]*征[^\S\r\n]*在[^\S\r\n]*于|特[^\S\r\n]*征[^\S\r\n]*在[^\S\r\n]*于)"
)
_CLAIM_PREAMBLE_DELIMS = set("，,；;：:")
_ADJACENT_TERM_BREAK_CHARS = set("，、；：。！？,.!?()[]{}（）【】《》“”‘’\"'\t\r\n ")
_ADJACENT_TERM_HINT_BREAK_CHARS = set("在于并且和及或与上中下内外前后里处端部面侧为有由将还")


def _is_punct_char(ch: str) -> bool:
    return bool(ch) and unicodedata.category(ch).startswith("P")


def _tokenize_punct_cluster(source: str, start: int) -> tuple[int, list[str]]:
    idx = int(start)
    length = len(source)
    punct_chars: list[str] = []
    while idx < length:
        ch = source[idx]
        if _is_punct_char(ch):
            punct_chars.append(ch)
            idx += 1
            continue
        matched = _INLINE_SPACE_RE.match(source, idx)
        if not matched:
            break
        next_idx = int(matched.end())
        if next_idx >= length or (not _is_punct_char(source[next_idx])):
            break
        idx = next_idx
    return int(idx), punct_chars


def _consume_punct_cluster(source: str, start: int) -> tuple[int, list[str]]:
    return _tokenize_punct_cluster(source, start)


def _is_open_wrapper_punct(ch: str) -> bool:
    return str(ch or "") in _OPEN_WRAPPER_PUNCTS


def _is_close_wrapper_punct(ch: str) -> bool:
    return str(ch or "") in _CLOSE_WRAPPER_PUNCTS


def _is_wrapper_punct(ch: str) -> bool:
    return _is_open_wrapper_punct(ch) or _is_close_wrapper_punct(ch)


def _is_bridge_connector_punct(ch: str) -> bool:
    return str(ch or "") in _BRIDGE_CONNECTOR_PUNCTS


def _should_skip_cluster_b_mode(tokens: list[str]) -> bool:
    token_list = list(tokens or [])
    if len(token_list) < 2:
        return False
    if any(not _is_close_wrapper_punct(ch) for ch in token_list[:-1]):
        return False
    tail = token_list[-1]
    return (not _is_wrapper_punct(tail)) and _is_punct_char(tail)


def _should_skip_cluster_bridge_mode(tokens: list[str]) -> bool:
    token_list = list(tokens or [])
    if len(token_list) < 3:
        return False
    close_end = 0
    while close_end < len(token_list) and _is_close_wrapper_punct(token_list[close_end]):
        close_end += 1
    if close_end <= 0:
        return False
    if close_end >= len(token_list):
        return False
    connector = token_list[close_end]
    if not _is_bridge_connector_punct(connector):
        return False
    open_tokens = token_list[close_end + 1 :]
    if not open_tokens:
        return False
    return all(_is_open_wrapper_punct(ch) for ch in open_tokens)


def check_abstract_word_count(text: str, threshold: int = 300) -> list[Issue]:
    count = count_effective_chars(text or "")
    if count <= int(threshold):
        return []
    source = str(text or "")
    span_start = 0
    span_end = min(10, len(source))
    return [
        Issue(
            rule_id="abstract.word_count.exceeded",
            severity="error",
            category="rule",
            section="abstract",
            message=f"摘要字数超过 {threshold}（当前 {count}）。",
            span_start=int(span_start),
            span_end=int(span_end),
        )
    ]


def check_punctuation_issues(text: str, *, section: str, claim_num: int | None = None) -> list[Issue]:
    source = text or ""
    issues: list[Issue] = []
    idx = 0
    size = len(source)
    while idx < size:
        ch = source[idx]
        if not _is_punct_char(ch):
            idx += 1
            continue
        end, punct_chars = _consume_punct_cluster(source, idx)
        if len(punct_chars) >= 2:
            if _should_skip_cluster_b_mode(punct_chars):
                idx = max(int(end), idx + 1)
                continue
            if _should_skip_cluster_bridge_mode(punct_chars):
                idx = max(int(end), idx + 1)
                continue
            snippet = source[idx:end]
            unique_count = len(set(punct_chars))
            if unique_count <= 1:
                rule_id = "punctuation.repeated"
                message = f"存在连续标点：{snippet}"
            else:
                rule_id = "punctuation.invalid_combo"
                message = f"存在不规范连续标点组合：{snippet}"
            issues.append(
                Issue(
                    rule_id=rule_id,
                    severity="warning",
                    category="rule",
                    section=section,
                    claim_num=claim_num,
                    span_start=int(idx),
                    span_end=int(end),
                    snippet=str(snippet),
                    message=message,
                )
            )
        idx = max(int(end), idx + 1)
    return issues


def check_claim_reference_rules(claims: list[ClaimItem]) -> list[Issue]:
    issues: list[Issue] = []
    max_claim_num = 0
    if claims:
        max_claim_num = max(claim.num for claim in claims)
    for claim in claims:
        parsed = parse_claim_references(claim.text)
        issues.extend(
            check_claim_reference_issues(
                claim_num=claim.num,
                refs=parsed.refs,
                has_choice_word=parsed.has_choice_word,
                max_claim_num=max_claim_num,
                source_text=str(claim.text or ""),
                ref_spans=dict(getattr(parsed, "ref_spans", {}) or {}),
            )
        )
    return issues


def _fallback_span(source_text: str) -> tuple[int, int]:
    text = str(source_text or "")
    if not text:
        return 0, 0
    return 0, min(10, len(text))


def check_claim_recursive_multi_reference_issues(claims: list[ClaimItem]) -> list[Issue]:
    claim_list = list(claims or [])
    if not claim_list:
        return []

    hits = recursive_multi_reference_hits(claim_list)
    if not hits:
        return []

    issues: list[Issue] = []
    for claim in claim_list:
        claim_num = int(getattr(claim, "num", 0) or 0)
        found = sorted(set(hits.get(claim_num, set()) or set()))
        if not found:
            continue
        found_text = "{" + ",".join([str(item) for item in found]) + "}"
        parsed = parse_claim_references(str(getattr(claim, "text", "") or ""))
        span_start, span_end = _fallback_span(str(getattr(claim, "text", "") or ""))
        spans = dict(getattr(parsed, "ref_spans", {}) or {})
        if spans:
            try:
                span_start, span_end = min(spans.values(), key=lambda row: int(row[0]))
            except Exception:
                span_start, span_end = _fallback_span(str(getattr(claim, "text", "") or ""))
        issues.append(
            Issue(
                rule_id="claim.ref.multi_to_multi.recursive",
                severity="error",
                category="rule",
                section="claims",
                claim_num=int(claim_num),
                message=f"权利要求{claim_num}存在多引多链路：递归命中 {found_text}。",
                span_start=int(span_start),
                span_end=int(span_end),
                snippet=str(getattr(claim, "text", "") or "")[int(span_start) : int(span_end)],
            )
        )
    return issues


def check_claim_period_structure_issues(claim: ClaimItem) -> list[Issue]:
    source = str(getattr(claim, "text", "") or "")
    claim_num = int(getattr(claim, "num", 0) or 0)
    if not source.strip() or claim_num <= 0:
        return []

    issues: list[Issue] = []
    last_non_blank = -1
    for idx in range(len(source) - 1, -1, -1):
        if not source[idx].isspace():
            last_non_blank = int(idx)
            break

    tail_has_period = bool(last_non_blank >= 0 and source[last_non_blank] == "。")
    period_indexes = [idx for idx, ch in enumerate(source) if ch == "。"]
    if len(period_indexes) > 1:
        extra_period_indexes = list(period_indexes[:-1] if tail_has_period else period_indexes)
        hit_idx = int(extra_period_indexes[0]) if extra_period_indexes else int(period_indexes[0])
        span_start = int(hit_idx)
        span_end = int(hit_idx + 1)
        issues.append(
            Issue(
                rule_id="claim.punctuation.period.extra",
                severity="error",
                category="rule",
                section="claims",
                claim_num=claim_num,
                message=f"权利要求{claim_num}包含多个句号（共{len(period_indexes)}个），应仅保留末尾一个句号。",
                span_start=int(span_start),
                span_end=int(span_end),
                snippet=str(source[span_start:span_end]),
            )
        )

    if last_non_blank >= 0 and source[last_non_blank] != "。":
        issues.append(
            Issue(
                rule_id="claim.punctuation.period.tail_missing",
                severity="error",
                category="rule",
                section="claims",
                claim_num=claim_num,
                message=f"权利要求{claim_num}末尾缺少句号。",
                span_start=int(last_non_blank),
                span_end=int(last_non_blank + 1),
                snippet=str(source[last_non_blank : last_non_blank + 1]),
            )
        )
    return issues


def _normalize_match_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"[^\w\u4E00-\u9FFF]+", "", text)
    return str(text or "").strip().casefold()


def _match_contains(left: str, right: str) -> bool:
    lhs = _normalize_match_text(left)
    rhs = _normalize_match_text(right)
    if not lhs or not rhs:
        return False
    return lhs in rhs or rhs in lhs


def _build_refer_word_pattern(refer_words: list[str]) -> re.Pattern[str] | None:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in list(refer_words or []):
        word = str(raw or "").strip()
        if not word:
            continue
        key = _normalize_match_text(word)
        if not key or key in seen:
            continue
        seen.add(key)
        token = "".join([re.escape(ch) + _REFER_INLINE_WS_PATTERN for ch in word])
        if token.endswith(_REFER_INLINE_WS_PATTERN):
            token = token[: -len(_REFER_INLINE_WS_PATTERN)]
        rows.append(token)
    if not rows:
        return None
    rows.sort(key=len, reverse=True)
    return re.compile("|".join([f"(?:{row})" for row in rows]))


def _claim_reference_scan_start(source_text: str) -> int:
    source = str(source_text or "")
    if not source:
        return 0

    matched = _CLAIM_CHARACTERIZING_RE.search(source)
    if matched is not None:
        idx = int(matched.end())
        size = len(source)
        while idx < size and (source[idx].isspace() or source[idx] in _CLAIM_PREAMBLE_DELIMS):
            idx += 1
        return int(idx)

    for idx, ch in enumerate(source):
        if ch not in _CLAIM_PREAMBLE_DELIMS:
            continue
        next_idx = int(idx + 1)
        size = len(source)
        while next_idx < size and (source[next_idx].isspace() or source[next_idx] in _CLAIM_PREAMBLE_DELIMS):
            next_idx += 1
        return int(next_idx)
    return 0


def _build_note_name_matchers(marker_note_map: dict[str, str] | None) -> list[tuple[str, re.Pattern[str]]]:
    rows: list[tuple[str, re.Pattern[str], int]] = []
    seen: set[str] = set()
    for _marker, raw_name in dict(marker_note_map or {}).items():
        name = str(raw_name or "").strip()
        key = _normalize_match_text(name)
        if not key or key in seen:
            continue
        seen.add(key)
        token = "".join([re.escape(ch) + _REFER_INLINE_WS_PATTERN for ch in name])
        if token.endswith(_REFER_INLINE_WS_PATTERN):
            token = token[: -len(_REFER_INLINE_WS_PATTERN)]
        rows.append((name, re.compile(token), int(len(key))))
    rows.sort(key=lambda item: item[2], reverse=True)
    return [(name, pattern) for name, pattern, _ in rows]


def _match_note_name_at(
    source: str,
    start: int,
    matchers: list[tuple[str, re.Pattern[str]]],
) -> tuple[str, int] | None:
    for name, pattern in list(matchers or []):
        matched = pattern.match(source, int(start))
        if matched is None or int(matched.start()) != int(start):
            continue
        return str(name), int(matched.end())
    return None


def _extract_adjacent_term_candidate(source: str, start: int) -> tuple[str, int, int]:
    size = len(source)
    term_start = int(start)
    while term_start < size:
        whitespace = _REFER_INLINE_SPACE_RE.match(source, term_start)
        if whitespace is None:
            break
        term_start = int(whitespace.end())
    if term_start >= size:
        return "", int(term_start), int(term_start)

    idx = int(term_start)
    chars: list[str] = []
    while idx < size:
        ch = source[idx]
        if ch in _REFER_PHRASE_STOP_CHARS or ch in _ADJACENT_TERM_BREAK_CHARS:
            break
        if ch.isspace():
            break
        if chars and ch in _ADJACENT_TERM_HINT_BREAK_CHARS:
            break
        chars.append(ch)
        idx += 1
        if len(chars) >= 40:
            break

    if not chars:
        idx = int(term_start)
        while idx < size:
            ch = source[idx]
            if ch in _REFER_PHRASE_STOP_CHARS or ch in _ADJACENT_TERM_BREAK_CHARS or ch.isspace():
                break
            chars.append(ch)
            idx += 1
            if len(chars) >= 40:
                break
    term_text = "".join(chars).strip()
    return str(term_text), int(term_start), int(max(idx, term_start))


def _extract_refer_adjacent_term_units(
    claim_text: str,
    refer_words: list[str],
    note_name_matchers: list[tuple[str, re.Pattern[str]]],
) -> list[dict[str, object]]:
    source = str(claim_text or "")
    if not source:
        return []
    pattern = _build_refer_word_pattern(list(refer_words or []))
    if pattern is None:
        return []
    scan_start = int(_claim_reference_scan_start(source))
    rows: list[dict[str, object]] = []
    for matched in pattern.finditer(source):
        if int(matched.start()) < int(scan_start):
            continue
        tail_start = int(matched.end())
        if tail_start >= len(source):
            continue
        while tail_start < len(source):
            whitespace = _REFER_INLINE_SPACE_RE.match(source, tail_start)
            if whitespace is None:
                break
            tail_start = int(whitespace.end())
        if tail_start >= len(source):
            continue
        note_name_hit = _match_note_name_at(source, int(tail_start), note_name_matchers)
        if note_name_hit is not None:
            term_text, term_end = note_name_hit
            span_end = int(max(term_end, matched.end()))
            rows.append(
                {
                    "term_text": str(term_text),
                    "term_matched": True,
                    "span_start": int(matched.start()),
                    "span_end": int(span_end),
                    "snippet": str(source[int(matched.start()) : int(span_end)]),
                }
            )
            continue

        term_text, _term_start, term_end = _extract_adjacent_term_candidate(source, int(tail_start))
        if not str(term_text).strip():
            continue
        if str(term_text).startswith(("的", "任一项", "任意一项", "任一", "任意")):
            continue
        span_end = int(max(term_end, matched.end()))
        rows.append(
            {
                "term_text": str(term_text),
                "term_matched": False,
                "span_start": int(matched.start()),
                "span_end": int(span_end),
                "snippet": str(source[int(matched.start()) : int(span_end)]),
            }
        )
    return rows


def check_claim1_threshold_issues(
    claims: list[ClaimItem],
    *,
    word_limit: int,
    marker_limit: int,
) -> list[Issue]:
    claim1 = None
    for item in list(claims or []):
        if int(getattr(item, "num", 0) or 0) == 1:
            claim1 = item
            break
    if claim1 is None:
        return []
    source = str(getattr(claim1, "text", "") or "")
    claim_num = int(getattr(claim1, "num", 1) or 1)
    first_para = str(source.split("\n", 1)[0] if source else "")
    anchor_text = str(first_para[:10] if first_para else source[:10]).strip()
    if not anchor_text:
        anchor_text = str(source[:30]).strip()
    if not anchor_text:
        anchor_text = str(source[:1] or "")
    span_start = 0
    span_end = int(min(len(source), max(1, len(anchor_text))))
    issues: list[Issue] = []

    current_word_count = int(count_effective_chars(source))
    if current_word_count > int(max(1, word_limit)):
        issues.append(
            Issue(
                rule_id="claim1.word_count.exceeded",
                severity="warning",
                category="rule",
                section="claims",
                claim_num=claim_num,
                span_start=span_start,
                span_end=span_end,
                snippet=str(anchor_text or source[:span_end]),
                message=(
                    f"权利要求1字数超限：{current_word_count}（上限 "
                    f"{int(max(1, word_limit))}）"
                ),
            )
        )

    markers = list(getattr(claim1, "markers", []) or [])
    if not markers:
        markers = list(extract_figure_markers(source) or [])
    marker_set = {
        marker
        for marker in [normalize_marker_token(str(row)) for row in markers]
        if marker
    }
    marker_count = int(len(marker_set))
    if marker_count > int(max(1, marker_limit)):
        issues.append(
            Issue(
                rule_id="claim1.marker_count.exceeded",
                severity="warning",
                category="rule",
                section="claims",
                claim_num=claim_num,
                span_start=span_start,
                span_end=span_end,
                snippet=str(anchor_text or source[:span_end]),
                message=(
                    f"权利要求1去重附图标记数超限：{marker_count}（上限 "
                    f"{int(max(1, marker_limit))}）"
                ),
            )
        )
    return issues


def check_claim_reference_basis_issues(
    claims: list[ClaimItem],
    *,
    refer_words: list[str],
    marker_note_map: dict[str, str] | None,
) -> list[Issue]:
    claim_list = list(claims or [])
    if not claim_list:
        return []

    units_by_claim: dict[int, list[dict[str, object]]] = {}
    scan_start_by_claim: dict[int, int] = {}
    note_name_matchers = _build_note_name_matchers(marker_note_map)
    for claim in claim_list:
        claim_num = int(getattr(claim, "num", 0) or 0)
        if claim_num <= 0:
            continue
        claim_text = str(getattr(claim, "text", "") or "")
        units = _extract_refer_adjacent_term_units(
            claim_text,
            list(refer_words or []),
            note_name_matchers,
        )
        units_by_claim[claim_num] = units
        scan_start_by_claim[claim_num] = int(_claim_reference_scan_start(claim_text))

    referenced_map = recursive_referenced_claims(claim_list)
    claim_text_map: dict[int, str] = {
        int(getattr(claim, "num", 0) or 0): str(getattr(claim, "text", "") or "")
        for claim in claim_list
        if int(getattr(claim, "num", 0) or 0) > 0
    }

    issues: list[Issue] = []
    for claim in claim_list:
        claim_num = int(getattr(claim, "num", 0) or 0)
        if claim_num <= 0:
            continue
        claim_text = str(claim_text_map.get(claim_num, "") or "")
        claim_scan_start = int(scan_start_by_claim.get(claim_num, 0) or 0)
        claim_scan_start = max(0, min(claim_scan_start, len(claim_text)))
        reachable = set(referenced_map.get(claim_num, set()) or set())
        if not reachable:
            continue
        units = list(units_by_claim.get(claim_num, []) or [])
        if not units:
            continue

        base_texts = [str(claim_text_map.get(int(ref_num), "") or "") for ref_num in sorted(reachable)]
        chain_text = "{" + ",".join([str(item) for item in sorted(reachable)]) + "}"
        for unit in units:
            term_text = str(unit.get("term_text") or "").strip()
            term_matched = bool(unit.get("term_matched", False))
            if not term_text:
                continue
            span_start = int(unit.get("span_start") or 0)
            span_end = int(unit.get("span_end") or span_start)
            snippet = str(unit.get("snippet") or "")

            if not term_matched:
                issues.append(
                    Issue(
                        rule_id="claim.ref.term_basis.missing",
                        severity="warning",
                        category="rule",
                        section="claims",
                        claim_num=claim_num,
                        span_start=span_start,
                        span_end=span_end,
                        snippet=snippet or term_text,
                        message=f"术语未在标号说明中匹配：权利要求{claim_num}“{term_text}”。",
                    )
                )
                continue

            chain_basis = any(_match_contains(term_text, base_text) for base_text in list(base_texts or []))
            local_prefix_end = max(span_start, claim_scan_start)
            local_prefix_end = min(local_prefix_end, len(claim_text))
            local_prefix = str(claim_text[claim_scan_start:local_prefix_end] or "")
            local_basis = _match_contains(term_text, local_prefix)
            has_basis = bool(chain_basis or local_basis)
            if not has_basis:
                issues.append(
                    Issue(
                        rule_id="claim.ref.marker_basis.missing",
                        severity="warning",
                        category="rule",
                        section="claims",
                        claim_num=claim_num,
                        span_start=span_start,
                        span_end=span_end,
                        snippet=snippet or term_text,
                        message=f"紧邻术语引用基础缺失：权利要求{claim_num}“{term_text}”在被引链{chain_text}未命中。",
                    )
                )
    return issues
