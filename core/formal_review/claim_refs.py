from __future__ import annotations

from dataclasses import dataclass
import re

from .models import ClaimItem, Issue

_CLAIM_REF_RE = re.compile(r"权利要求\s*([0-9至\-—~～、,，和及与\s]+)")
_RANGE_RE = re.compile(r"^\s*(\d+)\s*(?:至|\-|—|~|～)\s*(\d+)\s*$")
_CHOICE_WORD_RE = re.compile(r"(任一项|任一|之一|或|或者)")


@dataclass(slots=True)
class ClaimRefParseResult:
    refs: list[int]
    has_choice_word: bool
    # ref -> (span_start, span_end) in claim.text coordinates (claim body text)
    ref_spans: dict[int, tuple[int, int]]


def parse_claim_references(text: str) -> ClaimRefParseResult:
    source = text or ""
    refs: list[int] = []
    ref_spans: dict[int, tuple[int, int]] = {}
    for match in _CLAIM_REF_RE.finditer(source):
        span_start = int(match.start())
        span_end = int(match.end())
        while span_end > span_start and source[span_end - 1].isspace():
            span_end -= 1
        span = (span_start, span_end)

        chunk = match.group(1)
        normalized = re.sub(r"[、，和及与]", ",", chunk)
        for token in [part.strip() for part in normalized.split(",") if part.strip()]:
            range_match = _RANGE_RE.match(token)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2))
                if start <= end:
                    for ref in range(start, end + 1):
                        refs.append(int(ref))
                        ref_spans.setdefault(int(ref), span)
                else:
                    for ref in range(end, start + 1):
                        refs.append(int(ref))
                        ref_spans.setdefault(int(ref), span)
                continue
            if token.isdigit():
                ref = int(token)
                refs.append(ref)
                ref_spans.setdefault(ref, span)
    dedup = sorted(set(refs))
    return ClaimRefParseResult(
        refs=dedup,
        has_choice_word=bool(_CHOICE_WORD_RE.search(source)),
        ref_spans=ref_spans,
    )


def _fallback_span(source_text: str) -> tuple[int, int]:
    text = str(source_text or "")
    if not text:
        return 0, 0
    return 0, min(10, len(text))


def check_claim_reference_issues(
    claim_num: int,
    refs: list[int],
    has_choice_word: bool,
    max_claim_num: int,
    *,
    source_text: str,
    ref_spans: dict[int, tuple[int, int]] | None,
) -> list[Issue]:
    issues: list[Issue] = []
    spans = dict(ref_spans or {})
    for ref in refs:
        span_start, span_end = spans.get(int(ref), _fallback_span(source_text))
        if int(span_end) <= int(span_start):
            span_start, span_end = _fallback_span(source_text)
        if ref > max_claim_num:
            issues.append(
                Issue(
                    rule_id="claim.ref.missing_target",
                    severity="error",
                    category="rule",
                    section="claims",
                    claim_num=claim_num,
                    message=f"权利要求{claim_num}引用了不存在的权利要求{ref}。",
                    span_start=int(span_start),
                    span_end=int(span_end),
                )
            )
        if ref == claim_num:
            issues.append(
                Issue(
                    rule_id="claim.ref.self",
                    severity="error",
                    category="rule",
                    section="claims",
                    claim_num=claim_num,
                    message=f"权利要求{claim_num}引用了自身。",
                    span_start=int(span_start),
                    span_end=int(span_end),
                )
            )
        if ref > claim_num and ref <= max_claim_num:
            issues.append(
                Issue(
                    rule_id="claim.ref.future",
                    severity="error",
                    category="rule",
                    section="claims",
                    claim_num=claim_num,
                    message=f"权利要求{claim_num}引用了后续权利要求{ref}。",
                    span_start=int(span_start),
                    span_end=int(span_end),
                )
            )
    if len(refs) > 1 and not has_choice_word:
        span_start, span_end = _fallback_span(source_text)
        if spans:
            try:
                span_start, span_end = min(spans.values(), key=lambda s: int(s[0]))
            except Exception:
                span_start, span_end = _fallback_span(source_text)
        issues.append(
            Issue(
                rule_id="claim.ref.choice_word_missing",
                severity="warning",
                category="rule",
                section="claims",
                claim_num=claim_num,
                message=f"权利要求{claim_num}存在多重引用但缺少择一词。",
                span_start=int(span_start),
                span_end=int(span_end),
            )
        )
    return issues


def recursive_multi_reference_hits(claims: list[ClaimItem]) -> dict[int, set[int]]:
    direct_refs = build_claim_reference_graph(claims)
    if not direct_refs:
        return {}

    direct_multi = {claim_num for claim_num, refs in direct_refs.items() if len(list(refs or [])) >= 2}
    if not direct_multi:
        return {}

    hits: dict[int, set[int]] = {}
    for claim_num in sorted(direct_multi):
        stack = list(direct_refs.get(int(claim_num), []) or [])
        visited: set[int] = set()
        found: set[int] = set()
        while stack:
            target = int(stack.pop())
            if target in visited:
                continue
            visited.add(target)
            if target == int(claim_num):
                continue
            if target in direct_multi:
                found.add(target)
            for child in list(direct_refs.get(target, []) or []):
                child_num = int(child)
                if child_num not in visited:
                    stack.append(child_num)
        if found:
            hits[int(claim_num)] = set(found)
    return hits


def build_claim_reference_graph(claims: list[ClaimItem]) -> dict[int, list[int]]:
    claim_list = list(claims or [])
    if not claim_list:
        return {}
    claim_num_set = {int(getattr(claim, "num", 0) or 0) for claim in claim_list if int(getattr(claim, "num", 0) or 0) > 0}
    if not claim_num_set:
        return {}
    graph: dict[int, list[int]] = {}
    for claim in claim_list:
        claim_num = int(getattr(claim, "num", 0) or 0)
        if claim_num <= 0:
            continue
        parsed = parse_claim_references(str(getattr(claim, "text", "") or ""))
        graph[claim_num] = [
            int(ref)
            for ref in list(getattr(parsed, "refs", []) or [])
            if int(ref) in claim_num_set and int(ref) != claim_num
        ]
    return graph


def recursive_referenced_claims(claims: list[ClaimItem]) -> dict[int, set[int]]:
    graph = build_claim_reference_graph(claims)
    if not graph:
        return {}
    result: dict[int, set[int]] = {}
    for claim_num in sorted(graph.keys()):
        visited: set[int] = set()
        stack = list(graph.get(int(claim_num), []) or [])
        while stack:
            current = int(stack.pop())
            if current in visited:
                continue
            visited.add(current)
            for child in list(graph.get(current, []) or []):
                child_num = int(child)
                if child_num not in visited and child_num != int(claim_num):
                    stack.append(child_num)
        if visited:
            result[int(claim_num)] = visited
    return result
