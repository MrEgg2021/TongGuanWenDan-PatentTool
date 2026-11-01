from __future__ import annotations

from collections import defaultdict


def _sorted_terms(terms: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = str(term or "").strip()
        if not cleaned:
            continue
        lower = cleaned.casefold()
        if lower in seen:
            continue
        seen.add(lower)
        normalized.append(cleaned)
    normalized.sort(key=lambda item: (-len(item), item.casefold()))
    return normalized


def match_terms(
    text: str,
    terms: list[str],
    *,
    category: str,
    severity: str,
    section: str,
    claim_num: int | None = None,
) -> dict[str, object]:
    raw_text = text or ""
    folded_text = raw_text.casefold()
    ordered_terms = _sorted_terms(terms)
    folded_pairs = [(term, term.casefold()) for term in ordered_terms]

    occurrences: list[dict[str, object]] = []
    summary: dict[str, dict[str, object]] = defaultdict(lambda: {"count": 0, "first_span": None})

    idx = 0
    n = len(raw_text)
    while idx < n:
        matched = None
        for term, folded in folded_pairs:
            term_len = len(term)
            if term_len <= 0:
                continue
            if idx + term_len > n:
                continue
            if folded_text[idx : idx + term_len] == folded:
                matched = term
                break
        if not matched:
            idx += 1
            continue

        end = idx + len(matched)
        snippet = raw_text[max(0, idx - 8) : min(n, end + 8)]
        occurrence = {
            "term": matched,
            "start": idx,
            "end": end,
            "snippet": snippet,
            "category": category,
            "severity": severity,
            "section": section,
            "claim_num": claim_num,
        }
        occurrences.append(occurrence)

        item = summary[matched]
        item["count"] = int(item["count"]) + 1
        if item["first_span"] is None:
            item["first_span"] = (idx, end)
        idx = end

    summary_rows = [
        {"term": term, "count": item["count"], "first_span": item["first_span"]}
        for term, item in summary.items()
    ]
    summary_rows.sort(key=lambda row: (-int(row["count"]), str(row["term"])))
    return {"summary": summary_rows, "occurrences": occurrences}
