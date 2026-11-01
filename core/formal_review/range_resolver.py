from __future__ import annotations

from dataclasses import dataclass

from core.logging_utils import logger

from .text_projection import (
    ProjectionBundle,
    all_occurrences,
    count_occurrences_before,
    locate_occurrence_in_projection,
    map_span_to_word_range,
    projection_text,
)


@dataclass(slots=True)
class ResolveResult:
    ok: bool
    level: str
    start: int | None
    end: int | None
    reason: str
    reason_code: str
    detail: str
    expected: str
    actual: str


@dataclass(slots=True, frozen=True)
class ResolverPolicy:
    strict: bool = True
    allow_legacy_fallback: bool = False
    require_com_ready: bool = False


@dataclass(slots=True)
class ResolverMetrics:
    total_calls: int = 0
    path_hist: dict[str, int] = None  # type: ignore[assignment]
    reason_hist: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.path_hist is None:
            self.path_hist = {}
        if self.reason_hist is None:
            self.reason_hist = {}


@dataclass(slots=True, frozen=True)
class ComFindReadyResult:
    ok: bool
    reason_code: str
    detail: str


def _safe_int(value, default: int | None = None) -> int | None:
    try:
        return int(value)
    except Exception:
        return default


def check_com_find_ready(doc) -> ComFindReadyResult:
    if doc is None:
        return ComFindReadyResult(False, "word_doc_unavailable", "doc is None")
    try:
        content = getattr(doc, "Content", None)
        if content is not None:
            base_start = _safe_int(getattr(content, "Start", 0), 0) or 0
            base_end = _safe_int(getattr(content, "End", base_start), base_start) or base_start
        else:
            base_start = 0
            base_end = 0
        end = int(base_start + 1) if int(base_end) > int(base_start) else int(base_start)
        probe = doc.Range(int(base_start), int(end))
    except Exception as exc:
        return ComFindReadyResult(False, "com_find_unavailable", f"range_probe_failed:{exc}")
    find_obj = getattr(probe, "Find", None)
    if find_obj is None:
        return ComFindReadyResult(False, "com_find_unavailable", "range.find missing")
    try:
        try:
            find_obj.ClearFormatting()
        except Exception:
            pass
        try:
            replacement = getattr(find_obj, "Replacement", None)
            if replacement is not None:
                replacement.ClearFormatting()
        except Exception:
            pass
        try:
            find_obj.Text = "__formal_review_probe__"
        except Exception:
            # Some fake/test COM objects may not support setting Text. Existence of Find is enough.
            return ComFindReadyResult(True, "ok", "")
        for attr, value in (
            ("Forward", True),
            ("Wrap", 0),
            ("Format", False),
            ("MatchCase", False),
            ("MatchWholeWord", False),
            ("MatchWildcards", False),
            ("MatchSoundsLike", False),
            ("MatchAllWordForms", False),
        ):
            try:
                setattr(find_obj, attr, value)
            except Exception:
                pass
        _execute_find(find_obj)
        return ComFindReadyResult(True, "ok", "")
    except Exception as exc:
        return ComFindReadyResult(False, "com_find_unavailable", str(exc))


def _effective_policy(
    *,
    strict: bool,
    allow_legacy_fallback: bool,
    policy: ResolverPolicy | None,
) -> ResolverPolicy:
    if isinstance(policy, ResolverPolicy):
        return policy
    return ResolverPolicy(
        strict=bool(strict),
        allow_legacy_fallback=bool(allow_legacy_fallback),
        require_com_ready=False,
    )


def _record_metrics(metrics: ResolverMetrics | None, result: ResolveResult) -> None:
    if metrics is None:
        return
    if bool(getattr(result, "ok", False)):
        key = _resolve_path_label(str(getattr(result, "level", "") or ""))
        metrics.path_hist[key] = int(metrics.path_hist.get(key, 0) or 0) + 1
        return
    reason_key = str(getattr(result, "reason_code", "") or "unknown")
    metrics.reason_hist[reason_key] = int(metrics.reason_hist.get(reason_key, 0) or 0) + 1


def _sanitize_word_text(text: str) -> str:
    """Normalize Word Range.Text for strict comparisons.

    Aligns with extractor sanitization:
    - remove \\r (paragraph mark)
    - drop non-visible control chars (keep \\t/\\n)
    """
    if not text:
        return ""
    source = str(text or "").replace("\r", "")
    return "".join(ch for ch in source if (ch in ("\t", "\n") or ord(ch) >= 0x20))


def _sanitize_word_text_with_map(raw_text: str, base_abs_start: int) -> tuple[str, list[int], list[int]]:
    source = str(raw_text or "")
    chars: list[str] = []
    start_map: list[int] = []
    end_map: list[int] = []
    base = int(base_abs_start)
    for idx, ch in enumerate(source):
        if ch == "\r":
            continue
        if ch in ("\t", "\n") or ord(ch) >= 0x20:
            abs_start = base + idx
            chars.append(ch)
            start_map.append(abs_start)
            end_map.append(abs_start + 1)
    return "".join(chars), start_map, end_map


def _is_singleline_text(text: str) -> bool:
    value = str(text or "")
    return ("\n" not in value) and ("\r" not in value)


def _is_lookup_candidate_safe(text: str, *, max_len: int = 240) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    if not _is_singleline_text(value):
        return False
    return len(value) <= int(max_len)


def _is_com_find_candidate_safe(text: str, *, max_len: int = 120) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    if not _is_singleline_text(value):
        return False
    return len(value) <= int(max_len)


def _normalize_candidate_list(candidates) -> list[str]:
    if not isinstance(candidates, (list, tuple)):
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for item in list(candidates):
        text = str(item or "").strip()
        if (not text) or (text in seen):
            continue
        seen.add(text)
        rows.append(text)
    return rows


def _choose_resolver_candidate(
    expected: str,
    snippet: str,
    candidate_list: list[str] | None = None,
) -> tuple[str, str]:
    expected_text = str(expected or "").strip()
    snippet_text = str(snippet or "").strip()
    normalized_list = _normalize_candidate_list(candidate_list)
    for value, source in ((expected_text, "expected_hit"),):
        if _is_lookup_candidate_safe(value):
            return value, source
    for value in normalized_list:
        if _is_lookup_candidate_safe(value):
            return value, "candidate_list"
    if _is_lookup_candidate_safe(snippet_text):
        return snippet_text, "snippet"
    # Keep legacy fallback behavior as last resort when all candidates are unsafe.
    if expected_text:
        return expected_text, "expected_hit"
    if normalized_list:
        return str(normalized_list[0] or ""), "candidate_list"
    if snippet_text:
        return snippet_text, "snippet"
    return "", "none"


def _issue_debug_key(issue) -> str:
    rule_id = str(getattr(issue, "rule_id", "") or "")
    issue_id = str(getattr(issue, "issue_id", "") or "")
    section = str(getattr(issue, "section", "") or "")
    claim_num = getattr(issue, "claim_num", None)
    claim_part = f"#{int(claim_num)}" if claim_num is not None else ""
    if issue_id:
        return f"{rule_id}{claim_part}@{section}({issue_id})"
    return f"{rule_id}{claim_part}@{section}"


def _range_text(doc, start: int, end: int) -> str:
    rng = doc.Range(int(start), int(end))
    return str(getattr(rng, "Text", "") or "")


def _issue_paragraphs(issue, projections: ProjectionBundle | None):
    if projections is None:
        return []
    section = str(getattr(issue, "section", "") or "")
    if section == "claims":
        claim_num = _safe_int(getattr(issue, "claim_num", None), None)
        if claim_num is None:
            return []
        return projections.paragraphs_for(section="claims", claim_num=int(claim_num))
    return projections.paragraphs_for(section=section, claim_num=None)


def _context_score(source: str, index: int, needle: str, pre: str, post: str) -> int:
    score = 0
    if pre:
        left = source[max(0, index - len(pre)) : index]
        if left == pre:
            score += 2
        elif pre in left:
            score += 1
    if post:
        right = source[index + len(needle) : index + len(needle) + len(post)]
        if right == post:
            score += 2
        elif post in right:
            score += 1
    return score


def _paragraph_for_span(paragraphs, span_start: int | None):
    if span_start is None:
        return paragraphs[0] if paragraphs else None
    target = int(span_start)
    for row in list(paragraphs or []):
        start = int(getattr(row, "local_start", 0) or 0)
        end = int(getattr(row, "local_end", 0) or 0)
        if start <= target < end:
            return row
    return paragraphs[0] if paragraphs else None


def _resolve_path_label(level: str) -> str:
    resolved = str(level or "").strip().lower()
    if resolved in {"projection", "occurrence", "context"}:
        return f"projection_{resolved}"
    if resolved == "word_find_com":
        return "word_find_com"
    if resolved in {"word_find", "word_find_legacy"}:
        return "word_find_legacy"
    return resolved or "unknown"


def _log_resolve_result(issue_key: str, result: ResolveResult, *, strict: bool, allow_legacy_fallback: bool) -> None:
    if bool(getattr(result, "ok", False)):
        logger.debug(
            "[formal_review][resolver] resolve_path=%s issue=%s strict=%s allow_legacy_fallback=%s start=%s end=%s detail=%s",
            _resolve_path_label(str(getattr(result, "level", "") or "")),
            issue_key,
            bool(strict),
            bool(allow_legacy_fallback),
            getattr(result, "start", None),
            getattr(result, "end", None),
            str(getattr(result, "detail", "") or ""),
        )
        return
    logger.debug(
        "[formal_review][resolver] resolve_failed issue=%s strict=%s allow_legacy_fallback=%s reason_code=%s detail=%s",
        issue_key,
        bool(strict),
        bool(allow_legacy_fallback),
        str(getattr(result, "reason_code", "") or ""),
        str(getattr(result, "detail", "") or ""),
    )


def _resolve_via_word_find(
    doc,
    *,
    paragraph,
    candidate: str,
    occurrence_idx: int,
    expected: str,
    pre_context: str,
    post_context: str,
    strict: bool,
    require_exact: bool = False,
) -> ResolveResult:
    base_start = _safe_int(getattr(paragraph, "word_start", 0), 0) or 0
    base_end = _safe_int(getattr(paragraph, "word_end", 0), 0) or 0
    if base_end <= base_start:
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "段内回退失败（段落范围无效）",
            "word_find_paragraph_range_invalid",
            f"word_start={base_start}, word_end={base_end}",
            expected,
            "",
        )
    try:
        raw_para = _range_text(doc, int(base_start), int(base_end))
    except Exception as exc:
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "段内回退失败（读取段落范围失败）",
            "word_find_read_failed",
            str(exc),
            expected,
            "",
        )

    para_text, start_map, end_map = _sanitize_word_text_with_map(raw_para, int(base_start))
    if not para_text:
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "段内回退失败（段落文本为空）",
            "word_find_text_empty",
            "",
            expected,
            "",
        )
    target = str(candidate or "")
    matches = all_occurrences(para_text, target)
    if not matches:
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "段内未找到候选命中词",
            "word_find_candidate_not_found",
            "",
            expected,
            "",
        )

    chosen_idx: int | None = None
    idx = int(occurrence_idx or 0)
    if 0 <= idx < len(matches):
        chosen_idx = int(matches[idx])
    else:
        scored: list[tuple[int, int]] = []
        for pos in matches:
            score = _context_score(para_text, int(pos), target, pre_context, post_context)
            scored.append((int(score), int(pos)))
        scored.sort(key=lambda row: row[0], reverse=True)
        top_score = scored[0][0]
        top_rows = [row for row in scored if row[0] == top_score]
        if strict and len(top_rows) != 1:
            return ResolveResult(
                False,
                "fail",
                None,
                None,
                "娈靛唴鍛戒腑浣嶇疆涓嶅敮涓€",
                "word_find_ambiguous",
                f"matches={len(matches)}",
                expected,
                "",
            )
        chosen_idx = int(top_rows[0][1])

    if chosen_idx is None:
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "word_find select failed",
            "word_find_select_failed",
            "",
            expected,
            "",
        )

    end_pos = int(chosen_idx + len(target) - 1)
    if chosen_idx < 0 or end_pos >= len(end_map):
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "娈靛唴鍥為€€澶辫触锛堟槧灏勮竟鐣岃秺鐣岋級",
            "word_find_boundary_out_of_range",
            f"idx={chosen_idx}, end={end_pos}, map_len={len(end_map)}",
            expected,
            "",
        )

    abs_start = int(start_map[int(chosen_idx)])
    abs_end = int(end_map[int(end_pos)])
    try:
        raw_hit = _range_text(doc, abs_start, abs_end)
        actual = _sanitize_word_text(raw_hit)
    except Exception as exc:
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "段内回退失败（读取命中范围失败）",
            "word_find_read_hit_failed",
            str(exc),
            expected,
            "",
        )
    if expected and actual != expected and (strict or require_exact):
        detail = (
            f"candidate={target!r}; idx={chosen_idx}; occurrence_idx={idx}; "
            f"abs_start={abs_start}; abs_end={abs_end}; base_start={base_start}; base_end={base_end}; "
            f"expected_len={len(str(expected or ''))}; actual_len={len(str(actual or ''))}; "
            f"expected={expected!r}; actual={actual!r}; raw_hit={raw_hit!r}; "
            f"strict={bool(strict)}; require_exact={bool(require_exact)}"
        )
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "word_find context mismatch",
            "word_find_mismatch",
            detail,
            expected,
            actual,
        )
    return ResolveResult(True, "word_find_legacy", int(abs_start), int(abs_end), "娈靛唴鍥為€€鍛戒腑", "word_find_hit", "", expected, actual)


def _context_score_word_range(doc, start: int, end: int, pre: str, post: str) -> int:
    score = 0
    pre_text = str(pre or "")
    post_text = str(post or "")
    try:
        if pre_text:
            left_span = max(0, len(pre_text) + 8)
            left = _sanitize_word_text(_range_text(doc, max(0, int(start) - int(left_span)), int(start)))
            if left.endswith(pre_text):
                score += 2
            elif pre_text in left:
                score += 1
        if post_text:
            right_span = max(0, len(post_text) + 8)
            right = _sanitize_word_text(_range_text(doc, int(end), int(end) + int(right_span)))
            if right.startswith(post_text):
                score += 2
            elif post_text in right:
                score += 1
    except Exception:
        return int(score)
    return int(score)


def _execute_find(find_obj) -> bool:
    try:
        return bool(find_obj.Execute())
    except TypeError:
        try:
            return bool(find_obj.Execute(Forward=True, Wrap=0))
        except Exception:
            return False
    except Exception:
        return False


def _resolve_via_com_find(
    doc,
    *,
    paragraph,
    candidate: str,
    occurrence_idx: int,
    expected: str,
    pre_context: str,
    post_context: str,
    strict: bool,
    require_exact: bool = False,
) -> ResolveResult:
    base_start = _safe_int(getattr(paragraph, "word_start", 0), 0) or 0
    base_end = _safe_int(getattr(paragraph, "word_end", 0), 0) or 0
    if base_end <= base_start:
        return ResolveResult(
            False,
            "fail",
            None,
            None,
            "COM Find paragraph range invalid",
            "com_find_paragraph_range_invalid",
            f"word_start={base_start}, word_end={base_end}",
            expected,
            "",
        )
    target = str(candidate or "")
    if not target:
        return ResolveResult(False, "fail", None, None, "candidate empty", "candidate_missing", "", expected, "")

    try:
        probe = doc.Range(int(base_start), int(base_end))
        probe_find = getattr(probe, "Find", None)
    except Exception as exc:
        return ResolveResult(False, "fail", None, None, "COM Find unavailable", "com_find_unavailable", str(exc), expected, "")
    if probe_find is None:
        return ResolveResult(False, "fail", None, None, "COM Find unavailable", "com_find_unavailable", "range.find missing", expected, "")

    matches: list[dict[str, object]] = []
    cursor = int(base_start)
    guard = 0
    while cursor < int(base_end) and guard < 500:
        guard += 1
        try:
            scan = doc.Range(int(cursor), int(base_end))
            find_obj = getattr(scan, "Find", None)
            if find_obj is None:
                return ResolveResult(
                    False,
                    "fail",
                    None,
                    None,
                    "COM Find unavailable",
                    "com_find_unavailable",
                    "scan.find missing",
                    expected,
                    "",
                )
            try:
                find_obj.ClearFormatting()
            except Exception:
                pass
            try:
                replacement = getattr(find_obj, "Replacement", None)
                if replacement is not None:
                    replacement.ClearFormatting()
            except Exception:
                pass
            try:
                find_obj.Text = str(target)
            except Exception:
                return ResolveResult(
                    False,
                    "fail",
                    None,
                    None,
                    "COM Find init failed",
                    "com_find_init_failed",
                    "set Text failed",
                    expected,
                    "",
                )
            for attr, value in (
                ("Forward", True),
                ("Wrap", 0),
                ("Format", False),
                ("MatchCase", False),
                ("MatchWholeWord", False),
                ("MatchWildcards", False),
                ("MatchSoundsLike", False),
                ("MatchAllWordForms", False),
            ):
                try:
                    setattr(find_obj, attr, value)
                except Exception:
                    pass

            found = _execute_find(find_obj)
            if not found:
                break
            found_start = _safe_int(getattr(scan, "Start", None), None)
            found_end = _safe_int(getattr(scan, "End", None), None)
            if found_start is None or found_end is None or int(found_end) <= int(found_start):
                break
            raw_hit = _range_text(doc, int(found_start), int(found_end))
            actual = _sanitize_word_text(raw_hit)
            score = _context_score_word_range(doc, int(found_start), int(found_end), pre_context, post_context)
            matches.append(
                {
                    "start": int(found_start),
                    "end": int(found_end),
                    "actual": str(actual or ""),
                    "score": int(score),
                }
            )
            next_cursor = int(found_end)
            if next_cursor <= int(cursor):
                next_cursor = int(cursor) + 1
            cursor = int(next_cursor)
        except Exception as exc:
            return ResolveResult(
                False,
                "fail",
                None,
                None,
                "COM Find execute failed",
                "com_find_execute_failed",
                str(exc),
                expected,
                "",
            )

    if not matches:
        return ResolveResult(False, "fail", None, None, "COM Find candidate not found", "word_find_candidate_not_found", "", expected, "")

    idx = int(occurrence_idx or 0)
    chosen: dict[str, object] | None = None
    if 0 <= idx < len(matches):
        chosen = dict(matches[int(idx)])
    else:
        scored = sorted(
            [(int(row.get("score", 0) or 0), row) for row in matches],
            key=lambda item: item[0],
            reverse=True,
        )
        top_score = int(scored[0][0])
        top_rows = [row for score, row in scored if int(score) == int(top_score)]
        if strict and len(top_rows) != 1:
            return ResolveResult(
                False,
                "fail",
                None,
                None,
                "COM Find ambiguous",
                "word_find_ambiguous",
                f"matches={len(matches)}",
                expected,
                "",
            )
        chosen = dict(top_rows[0])

    if chosen is None:
        return ResolveResult(False, "fail", None, None, "COM Find select failed", "word_find_select_failed", "", expected, "")

    chosen_actual = str(chosen.get("actual", "") or "")
    if expected and chosen_actual != expected and (strict or require_exact):
        exact_rows = [row for row in matches if str(row.get("actual", "") or "") == str(expected or "")]
        if len(exact_rows) == 1:
            chosen = dict(exact_rows[0])
            chosen_actual = str(chosen.get("actual", "") or "")
        elif len(exact_rows) > 1:
            scored = sorted(
                [(int(row.get("score", 0) or 0), row) for row in exact_rows],
                key=lambda item: item[0],
                reverse=True,
            )
            top_score = int(scored[0][0])
            top_rows = [row for score, row in scored if int(score) == int(top_score)]
            if strict and len(top_rows) != 1:
                detail = f"candidate={target!r}; exact_matches={len(exact_rows)}; expected={expected!r}"
                return ResolveResult(
                    False,
                    "fail",
                    None,
                    None,
                    "COM Find mismatch",
                    "word_find_mismatch",
                    detail,
                    expected,
                    chosen_actual,
                )
            chosen = dict(top_rows[0])
            chosen_actual = str(chosen.get("actual", "") or "")
        else:
            detail = (
                f"candidate={target!r}; occurrence_idx={idx}; expected={expected!r}; actual={chosen_actual!r}; "
                f"matches={len(matches)}"
            )
            return ResolveResult(
                False,
                "fail",
                None,
                None,
                "COM Find mismatch",
                "word_find_mismatch",
                detail,
                expected,
                chosen_actual,
            )

    return ResolveResult(
        True,
        "word_find_com",
        int(chosen.get("start", 0) or 0),
        int(chosen.get("end", 0) or 0),
        "COM Find hit",
        "word_find_hit",
        "",
        expected,
        str(chosen_actual or ""),
    )


def resolve_issue_range(
    doc,
    issue,
    projections: ProjectionBundle | None,
    *,
    strict: bool = True,
    allow_legacy_fallback: bool = False,
    policy: ResolverPolicy | None = None,
    metrics: ResolverMetrics | None = None,
) -> ResolveResult:
    effective_policy = _effective_policy(
        strict=bool(strict),
        allow_legacy_fallback=bool(allow_legacy_fallback),
        policy=policy,
    )
    strict = bool(effective_policy.strict)
    allow_legacy_fallback = bool(effective_policy.allow_legacy_fallback)
    require_com_ready = bool(effective_policy.require_com_ready)
    if metrics is not None:
        metrics.total_calls = int(getattr(metrics, "total_calls", 0) or 0) + 1

    if doc is None:
        result = ResolveResult(False, "fail", None, None, "Word document unavailable", "word_doc_unavailable", "", "", "")
        _record_metrics(metrics, result)
        return result

    if require_com_ready:
        ready = check_com_find_ready(doc)
        if not bool(getattr(ready, "ok", False)):
            result = ResolveResult(
                False,
                "fail",
                None,
                None,
                "COM Find unavailable (blocked)",
                "com_find_unavailable_blocked",
                f"{getattr(ready, 'reason_code', '')}:{getattr(ready, 'detail', '')}",
                "",
                "",
            )
            _record_metrics(metrics, result)
            _log_resolve_result(_issue_debug_key(issue), result, strict=bool(strict), allow_legacy_fallback=bool(allow_legacy_fallback))
            return result

    paragraphs = _issue_paragraphs(issue, projections)
    if not paragraphs:
        result = ResolveResult(False, "fail", None, None, "missing projection paragraphs", "projection_missing", "", "", "")
        _record_metrics(metrics, result)
        return result

    anchor = getattr(issue, "anchor", None)
    if not isinstance(anchor, dict):
        anchor = {}
    expected = str(anchor.get("expected_hit", "") or "").strip()
    expected_hit_candidates = _normalize_candidate_list(anchor.get("expected_hit_candidates", []))
    section = str(getattr(issue, "section", "") or "")
    require_exact = bool(section == "claims" and expected)
    pre_context = str(anchor.get("pre_context", "") or "")
    post_context = str(anchor.get("post_context", "") or "")

    span_start = _safe_int(getattr(issue, "span_start", None), None)
    span_end = _safe_int(getattr(issue, "span_end", None), None)

    issue_key = _issue_debug_key(issue)

    # 1) Projection direct span mapping.
    last_failure: ResolveResult | None = None
    if span_start is not None and span_end is not None and span_end > span_start:
        mapped = map_span_to_word_range(paragraphs, int(span_start), int(span_end))
        if mapped is not None:
            start, end = mapped
            try:
                raw = _range_text(doc, start, end)
                actual = _sanitize_word_text(raw)
            except Exception as exc:
                result = ResolveResult(False, "fail", None, None, "read range failed", "read_range_failed", str(exc), expected, "")
                _record_metrics(metrics, result)
                return result
            if (not expected) or actual == expected:
                result = ResolveResult(True, "projection", int(start), int(end), "鎶曞奖鏄犲皠鎴愬姛", "projection_span", "", expected, actual)
                _log_resolve_result(issue_key, result, strict=bool(strict), allow_legacy_fallback=bool(allow_legacy_fallback))
                _record_metrics(metrics, result)
                return result
            if not strict and expected and not require_exact and expected in actual:
                result = ResolveResult(True, "projection", int(start), int(end), "projection contains expected", "projection_contains", "", expected, actual)
                _log_resolve_result(issue_key, result, strict=bool(strict), allow_legacy_fallback=bool(allow_legacy_fallback))
                _record_metrics(metrics, result)
                return result
            if raw != actual:
                logger.debug(
                    "[formal_review][resolver] projection_mismatch sanitized (%s): expected=%r actual=%r raw_len=%s actual_len=%s",
                    issue_key,
                    expected,
                    actual,
                    len(str(raw or "")),
                    len(str(actual or "")),
                )
            projection_reason = "projection_mismatch"
            last_failure = ResolveResult(False, "fail", None, None, "鎶曞奖鏄犲皠鏍￠獙澶辫触", "projection_mismatch", "", expected, actual)
        else:
            projection_reason = "projection_cross_paragraph_or_newline"
            last_failure = ResolveResult(
                False,
                "fail",
                None,
                None,
                "鎶曞奖鏄犲皠澶辫触锛堣法娈垫垨璺ㄦ崲琛岋級",
                "projection_cross_paragraph_or_newline",
                "",
                expected,
                "",
            )
    else:
        projection_reason = "span_missing"

    # 2) Paragraph-scoped occurrence mapping (no full-doc fallback).
    snippet_text = str(getattr(issue, "snippet", "") or "").strip()
    candidate, candidate_source = _choose_resolver_candidate(expected, snippet_text, expected_hit_candidates)
    if not candidate:
        detail = f"{projection_reason}:candidate_missing:candidate_source={candidate_source}"
        result = ResolveResult(False, "fail", None, None, "candidate missing", "candidate_missing", detail, expected, "")
        _record_metrics(metrics, result)
        return result
    expected_for_match = str(expected or "")
    if expected_for_match and candidate and (candidate != expected_for_match) and (not bool(require_exact)):
        expected_for_match = ""

    source = projection_text(paragraphs)
    if not source:
        detail = f"{projection_reason}:projection_text_empty:candidate_source={candidate_source}"
        result = ResolveResult(False, "fail", None, None, "projection text empty", "projection_text_empty", detail, expected, "")
        _record_metrics(metrics, result)
        return result

    # Prefer the same occurrence index inferred from span position.
    occurrence_idx = 0
    if span_start is not None and span_start >= 0:
        occurrence_idx = count_occurrences_before(source, candidate, int(span_start))
    mapped = locate_occurrence_in_projection(paragraphs, candidate, int(occurrence_idx))
    if mapped is not None:
        start, end = mapped
        try:
            actual = _sanitize_word_text(_range_text(doc, start, end))
        except Exception as exc:
            result = ResolveResult(False, "fail", None, None, "read occurrence failed", "read_occurrence_failed", str(exc), expected, "")
            _record_metrics(metrics, result)
            return result
        if expected_for_match and actual != expected_for_match and (strict or require_exact):
            # Continue to context disambiguation as last in-scope attempt.
            pass
        else:
            result = ResolveResult(
                True,
                "occurrence",
                int(start),
                int(end),
                "段内 occurrence 命中",
                "projection_occurrence",
                f"candidate_source={candidate_source}",
                expected,
                actual,
            )
            _log_resolve_result(issue_key, result, strict=bool(strict), allow_legacy_fallback=bool(allow_legacy_fallback))
            _record_metrics(metrics, result)
            return result

    # 3) Context disambiguation in section scope.
    matches = all_occurrences(source, candidate)
    if not matches:
        detail = f"{projection_reason}:candidate_not_found:candidate_source={candidate_source}"
        last_failure = ResolveResult(False, "fail", None, None, "段内未找到候选命中词", "candidate_not_found", detail, expected, "")
    else:
        scored: list[tuple[int, int, tuple[int, int]]] = []
        for idx in matches:
            mapped_row = map_span_to_word_range(paragraphs, int(idx), int(idx + len(candidate)))
            if mapped_row is None:
                continue
            score = _context_score(source, int(idx), candidate, pre_context, post_context)
            scored.append((int(score), int(idx), mapped_row))
        if not scored:
            detail = f"{projection_reason}:candidate_cross_boundary:candidate_source={candidate_source}"
            last_failure = ResolveResult(False, "fail", None, None, "候选命中词跨段边界", "candidate_cross_boundary", detail, expected, "")
        else:
            scored.sort(key=lambda row: row[0], reverse=True)
            top_score = scored[0][0]
            top_rows = [row for row in scored if row[0] == top_score]
            if strict and len(top_rows) != 1:
                last_failure = ResolveResult(
                    False,
                    "fail",
                    None,
                    None,
                    "段内命中位置不唯一",
                    "ambiguous_occurrence",
                    f"candidate_source={candidate_source}",
                    expected,
                    "",
                )
            else:
                chosen = top_rows[0]
                start, end = chosen[2]
                try:
                    actual = _sanitize_word_text(_range_text(doc, start, end))
                except Exception as exc:
                    result = ResolveResult(False, "fail", None, None, "read context range failed", "read_context_failed", str(exc), expected, "")
                    _record_metrics(metrics, result)
                    return result
                if expected_for_match and actual != expected_for_match and (strict or require_exact):
                    last_failure = ResolveResult(
                        False,
                        "fail",
                        None,
                        None,
                        "context mismatch",
                        "context_mismatch",
                        f"candidate_source={candidate_source}",
                        expected,
                        actual,
                    )
                else:
                    result = ResolveResult(
                        True,
                        "context",
                        int(start),
                        int(end),
                        "上下文 disambiguation 命中",
                        "projection_context",
                        f"candidate_source={candidate_source}",
                        expected,
                        actual,
                    )
                    _log_resolve_result(issue_key, result, strict=bool(strict), allow_legacy_fallback=bool(allow_legacy_fallback))
                    _record_metrics(metrics, result)
                    return result

    # 4) Paragraph-scoped COM Find fallback (no full-doc match).
    word_find_failure: ResolveResult | None = None
    fallback_paragraph = _paragraph_for_span(paragraphs, span_start)
    if fallback_paragraph is not None:
        # IMPORTANT: find runs inside a single paragraph range, so occurrence index must
        # be computed against paragraph-local text. Passing a section-level occurrence_idx
        # will often be out-of-range and cause multiple hits to collapse to the same spot.
        para_occurrence_idx = 0
        if span_start is not None and span_start >= 0:
            try:
                para_local_start = _safe_int(getattr(fallback_paragraph, "local_start", 0), 0) or 0
                local_pos = max(0, int(span_start) - int(para_local_start))
                para_source = str(getattr(fallback_paragraph, "text", "") or "")
                para_occurrence_idx = count_occurrences_before(para_source, candidate, int(local_pos))
            except Exception:
                para_occurrence_idx = int(occurrence_idx or 0)
        candidate_text = str(candidate or "")
        if not _is_com_find_candidate_safe(candidate_text):
            fallback = ResolveResult(
                False,
                "fail",
                None,
                None,
                "COM Find candidate unsafe",
                "com_find_candidate_unsafe",
                f"len={len(candidate_text)}; multiline={not _is_singleline_text(candidate_text)}; candidate_source={candidate_source}",
                expected,
                "",
            )
        else:
            fallback = _resolve_via_com_find(
                doc,
                paragraph=fallback_paragraph,
                candidate=str(candidate_text or ""),
                occurrence_idx=int(para_occurrence_idx),
                expected=str(expected_for_match or ""),
                pre_context=str(pre_context or ""),
                post_context=str(post_context or ""),
                strict=bool(strict),
                require_exact=bool(require_exact),
            )
        if not bool(getattr(fallback, "ok", False)) and str(getattr(fallback, "reason_code", "") or "") == "com_find_unavailable":
            if bool(require_com_ready):
                fallback = ResolveResult(
                    False,
                    "fail",
                    None,
                    None,
                    "COM Find unavailable (blocked)",
                    "com_find_unavailable_blocked",
                    str(getattr(fallback, "detail", "") or ""),
                    expected,
                    str(getattr(fallback, "actual", "") or ""),
                )
            elif bool(allow_legacy_fallback):
                fallback = _resolve_via_word_find(
                    doc,
                    paragraph=fallback_paragraph,
                    candidate=str(candidate or ""),
                    occurrence_idx=int(para_occurrence_idx),
                    expected=str(expected_for_match or ""),
                    pre_context=str(pre_context or ""),
                    post_context=str(post_context or ""),
                    strict=bool(strict),
                    require_exact=bool(require_exact),
                )
            else:
                fallback = ResolveResult(
                    False,
                    "fail",
                    None,
                    None,
                    "COM Find unavailable (blocked)",
                    "com_find_unavailable_blocked",
                    str(getattr(fallback, "detail", "") or ""),
                    expected,
                    str(getattr(fallback, "actual", "") or ""),
                )
        if bool(getattr(fallback, "ok", False)):
            _log_resolve_result(
                issue_key,
                fallback,
                strict=bool(strict),
                allow_legacy_fallback=bool(allow_legacy_fallback),
            )
            _record_metrics(metrics, fallback)
            return fallback
        word_find_failure = fallback
        _log_resolve_result(
            issue_key,
            fallback,
            strict=bool(strict),
            allow_legacy_fallback=bool(allow_legacy_fallback),
        )

    # When word_find is the last in-scope attempt, prefer its failure reason_code/detail.
    if word_find_failure is not None:
        _record_metrics(metrics, word_find_failure)
        return word_find_failure
    if last_failure is not None:
        _log_resolve_result(
            issue_key,
            last_failure,
            strict=bool(strict),
            allow_legacy_fallback=bool(allow_legacy_fallback),
        )
        _record_metrics(metrics, last_failure)
        return last_failure
    final_failure = ResolveResult(
        False,
        "fail",
        None,
        None,
        "未能在段内安全定位该问题",
        "resolve_failed",
        projection_reason,
        expected,
        "",
    )
    _log_resolve_result(
        issue_key,
        final_failure,
        strict=bool(strict),
        allow_legacy_fallback=bool(allow_legacy_fallback),
    )
    _record_metrics(metrics, final_failure)
    return final_failure


__all__ = [
    "ResolveResult",
    "ResolverPolicy",
    "ResolverMetrics",
    "ComFindReadyResult",
    "check_com_find_ready",
    "resolve_issue_range",
]
