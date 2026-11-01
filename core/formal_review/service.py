from __future__ import annotations

from collections.abc import Callable, Iterable
from hashlib import sha1
from typing import TypeVar

from core.logging_utils import logger

from .deterministic_rules import (
    check_abstract_deterministic_issues,
    check_claim_numbering_issues,
    check_claim_text_issues,
    check_description_deterministic_issues,
    check_drawings_deterministic_issues,
    check_text_consistency_issues,
)
from .matcher import match_terms
from .models import ClaimItem, FormalReviewDocument, Issue
from .rule_registry import RULE_REGISTRY
from .rules import (
    check_abstract_word_count,
    check_claim1_threshold_issues,
    check_claim_reference_basis_issues,
    check_claim_period_structure_issues,
    check_claim_recursive_multi_reference_issues,
    check_claim_reference_rules,
    check_punctuation_issues,
)
from .rule_params import merged_refer_words, normalize_rule_params
from .semantic_rules import (
    check_description_heading_issues,
    check_description_title_issues,
    check_drawings_cross_section_consistency_issues,
    check_drawings_duplicate_figure_issues,
    check_drawings_figure_reference_issues,
    check_repeated_word_issues,
    check_theme_consistency_issues,
)
from .wordlists import normalize_wordlists

_CheckerResult = TypeVar("_CheckerResult")


def build_issue_id(issue: Issue) -> str:
    anchor_start = 0
    if isinstance(issue.anchor, dict):
        try:
            anchor_start = int(issue.anchor.get("word_range_start") or 0)
        except Exception:
            anchor_start = 0
    claim_num = int(issue.claim_num) if issue.claim_num is not None else -1
    span_start = int(issue.span_start) if issue.span_start is not None else -1
    span_end = int(issue.span_end) if issue.span_end is not None else -1
    snippet = str(issue.snippet or issue.message or "")
    snippet_hash = sha1(snippet.encode("utf-8")).hexdigest()[:12]
    parts = [issue.rule_id, issue.section, str(claim_num), str(anchor_start), str(span_start), str(span_end), snippet_hash]
    return "|".join(parts)


def _apply_issue_id(issues: list[Issue], default_anchor_start: int = 0) -> None:
    for issue in issues:
        if not isinstance(issue.anchor, dict):
            issue.anchor = {}
        issue.anchor.setdefault("word_range_start", int(default_anchor_start))
        issue.issue_id = build_issue_id(issue)


def _claim_anchor(claim: ClaimItem) -> int:
    try:
        return int(claim.anchor_start or 0)
    except Exception:
        return 0


def _wordlist_message(section: str, category: str, term: str) -> str:
    section_label = "权利要求书" if section == "claims" else "说明书"
    if category == "forbidden":
        return f"{section_label}中不得出现禁用词：\"{term}\""
    return f"{section_label}中出现敏感词：\"{term}\""


def _merge_summary_row(summary_store: dict[str, dict[str, object]], row: dict[str, object]) -> None:
    term = str(row.get("term") or "")
    if not term:
        return
    existing = summary_store.get(term)
    if existing is None:
        summary_store[term] = dict(row)
        return
    existing["count"] = int(existing.get("count") or 0) + int(row.get("count") or 0)


def _wordlist_terms(wordlists_v2: dict[str, dict[str, list[str]]], section: str, category: str) -> list[str]:
    bucket = wordlists_v2.get(section) if isinstance(wordlists_v2, dict) else None
    if not isinstance(bucket, dict):
        return []
    terms = bucket.get(category)
    return list(terms or [])


def _execute_checker(
    checker_id: str,
    callback: Callable[[], Iterable[_CheckerResult] | None],
    rule_errors: list[dict[str, str]],
) -> list[_CheckerResult]:
    try:
        result = callback()
        return list(result or [])
    except Exception as exc:
        logger.exception("[formal_review][rule_error] checker_id=%s", checker_id)
        rule_errors.append(
            {
                "checker_id": str(checker_id),
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        )
        return []


def _apply_document_issue_ids(issues: list[Issue], document: FormalReviewDocument) -> None:
    for issue in issues:
        anchor_start = 0
        if str(issue.section or "") == "claims" and issue.claim_num is not None:
            for claim in document.claims:
                if int(claim.num) == int(issue.claim_num):
                    anchor_start = _claim_anchor(claim)
                    break
        if not isinstance(issue.anchor, dict):
            issue.anchor = {"word_range_start": int(anchor_start)}
        else:
            issue.anchor.setdefault("word_range_start", int(anchor_start))
    _apply_issue_id(issues)


def _enrich_issue(issue: Issue) -> None:
    metadata = RULE_REGISTRY.get(str(issue.rule_id or ""), {})
    if not issue.rule_name:
        issue.rule_name = str(metadata.get("label") or issue.rule_id)
    if not issue.suggestion:
        issue.suggestion = str(metadata.get("suggestion") or "")
    if issue.location is None:
        issue.location = {
            "section": str(issue.section or ""),
            "claim_num": issue.claim_num,
            "span_start": issue.span_start,
            "span_end": issue.span_end,
        }
    if issue.evidence is None:
        issue.evidence = {
            "snippet": str(issue.snippet or ""),
            "anchor": dict(issue.anchor or {}),
        }


def run_formal_review(
    document: FormalReviewDocument,
    *,
    wordlists: dict[str, object],
    ignored_issue_ids: set[str] | None = None,
    abstract_threshold: int = 300,
    enabled_rule_ids: set[str] | None = None,
    rule_params: dict[str, object] | None = None,
    marker_note_map: dict[str, str] | None = None,
) -> dict[str, object]:
    enabled_rules = set(enabled_rule_ids) if enabled_rule_ids is not None else None
    normalized_rule_params = normalize_rule_params(rule_params)

    def _is_enabled(rule_id: str) -> bool:
        if enabled_rules is None:
            return True
        return str(rule_id or "") in enabled_rules

    issues: list[Issue] = []
    rule_errors: list[dict[str, str]] = []

    deterministic_checks = (
        (
            "claim.numbering",
            lambda: check_claim_numbering_issues(document.claims),
        ),
        (
            "claim.text",
            lambda: check_claim_text_issues(
                document.claims,
                marker_note_map=dict(marker_note_map or {}),
                description_text=document.description,
            ),
        ),
        (
            "description.deterministic",
            lambda: check_description_deterministic_issues(document),
        ),
        (
            "abstract.deterministic",
            lambda: check_abstract_deterministic_issues(document),
        ),
        (
            "drawings.deterministic",
            lambda: check_drawings_deterministic_issues(document),
        ),
        (
            "text.consistency",
            lambda: check_text_consistency_issues(document),
        ),
    )
    for checker_id, callback in deterministic_checks:
        checker_issues = [
            issue
            for issue in _execute_checker(checker_id, callback, rule_errors)
            if _is_enabled(issue.rule_id)
        ]
        if checker_issues:
            _apply_document_issue_ids(checker_issues, document)
            issues.extend(checker_issues)

    abstract_issues = [
        issue
        for issue in _execute_checker(
            "abstract.word_count",
            lambda: check_abstract_word_count(document.abstract, threshold=abstract_threshold),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    if abstract_issues:
        _apply_issue_id(abstract_issues, default_anchor_start=0)
        issues.extend(abstract_issues)

    desc_punc_issues = [
        issue
        for issue in _execute_checker(
            "description.punctuation",
            lambda: check_punctuation_issues(document.description, section="description"),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    if desc_punc_issues:
        _apply_issue_id(desc_punc_issues, default_anchor_start=0)
        issues.extend(desc_punc_issues)

    abstract_punc_issues = [
        issue
        for issue in _execute_checker(
            "abstract.punctuation",
            lambda: check_punctuation_issues(document.abstract, section="abstract"),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    if abstract_punc_issues:
        _apply_issue_id(abstract_punc_issues, default_anchor_start=0)
        issues.extend(abstract_punc_issues)

    desc_repeated_word_issues = [
        issue
        for issue in _execute_checker(
            "description.repeated_word",
            lambda: check_repeated_word_issues(document.description, section="description"),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    if desc_repeated_word_issues:
        _apply_issue_id(desc_repeated_word_issues, default_anchor_start=0)
        issues.extend(desc_repeated_word_issues)

    abstract_repeated_word_issues = [
        issue
        for issue in _execute_checker(
            "abstract.repeated_word",
            lambda: check_repeated_word_issues(document.abstract, section="abstract"),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    if abstract_repeated_word_issues:
        _apply_issue_id(abstract_repeated_word_issues, default_anchor_start=0)
        issues.extend(abstract_repeated_word_issues)

    claim_ref_issues = [
        issue
        for issue in _execute_checker(
            "claim.references",
            lambda: check_claim_reference_rules(document.claims),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    for item in claim_ref_issues:
        anchor = 0
        for claim in document.claims:
            if claim.num == item.claim_num:
                anchor = _claim_anchor(claim)
                break
        item.anchor = {"word_range_start": anchor}
    if claim_ref_issues:
        _apply_issue_id(claim_ref_issues)
        issues.extend(claim_ref_issues)

    claim1_threshold_issues = [
        issue
        for issue in _execute_checker(
            "claim1.thresholds",
            lambda: check_claim1_threshold_issues(
                document.claims,
                word_limit=int(normalized_rule_params.get("claim1_word_limit", 500) or 500),
                marker_limit=int(normalized_rule_params.get("claim1_marker_limit", 20) or 20),
            ),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    for item in claim1_threshold_issues:
        anchor = 0
        for claim in document.claims:
            if int(getattr(claim, "num", 0) or 0) == 1:
                anchor = _claim_anchor(claim)
                break
        item.anchor = {
            "word_range_start": int(anchor),
            "expected_hit": str(getattr(item, "snippet", "") or ""),
        }
    if claim1_threshold_issues:
        _apply_issue_id(claim1_threshold_issues)
        issues.extend(claim1_threshold_issues)

    claim_basis_issues = [
        issue
        for issue in _execute_checker(
            "claim.reference_basis",
            lambda: check_claim_reference_basis_issues(
                document.claims,
                refer_words=merged_refer_words(normalized_rule_params),
                marker_note_map=dict(marker_note_map or {}),
            ),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    for item in claim_basis_issues:
        anchor = 0
        current_claim_num = int(getattr(item, "claim_num", 0) or 0)
        for claim in document.claims:
            if int(getattr(claim, "num", 0) or 0) == current_claim_num:
                anchor = _claim_anchor(claim)
                break
        item.anchor = {"word_range_start": int(anchor)}
    if claim_basis_issues:
        _apply_issue_id(claim_basis_issues)
        issues.extend(claim_basis_issues)

    claim_recursive_multi_issues = [
        issue
        for issue in _execute_checker(
            "claim.recursive_multi_reference",
            lambda: check_claim_recursive_multi_reference_issues(document.claims),
            rule_errors,
        )
        if _is_enabled(issue.rule_id)
    ]
    for item in claim_recursive_multi_issues:
        anchor = 0
        for claim in document.claims:
            if int(getattr(claim, "num", 0) or 0) == int(getattr(item, "claim_num", 0) or 0):
                anchor = _claim_anchor(claim)
                break
        item.anchor = {"word_range_start": int(anchor)}
    if claim_recursive_multi_issues:
        _apply_issue_id(claim_recursive_multi_issues)
        issues.extend(claim_recursive_multi_issues)

    claim_punc_total = 0
    claim_punc_by_claim: dict[int, int] = {}
    claim_punc_samples: list[str] = []
    for claim in document.claims:
        claim_period_structure_issues = [
            issue
            for issue in _execute_checker(
                f"claim.{claim.num}.period_structure",
                lambda: check_claim_period_structure_issues(claim),
                rule_errors,
            )
            if _is_enabled(issue.rule_id)
        ]
        if claim_period_structure_issues:
            _apply_issue_id(claim_period_structure_issues, default_anchor_start=_claim_anchor(claim))
            issues.extend(claim_period_structure_issues)

        claim_punc_issues = [
            issue
            for issue in _execute_checker(
                f"claim.{claim.num}.punctuation",
                lambda: check_punctuation_issues(claim.text, section="claims", claim_num=claim.num),
                rule_errors,
            )
            if _is_enabled(issue.rule_id)
        ]
        if claim_punc_issues:
            _apply_issue_id(claim_punc_issues, default_anchor_start=_claim_anchor(claim))
            issues.extend(claim_punc_issues)
        if claim_punc_issues:
            claim_punc_total += len(claim_punc_issues)
            claim_punc_by_claim[int(claim.num)] = int(len(claim_punc_issues))
            for item in claim_punc_issues[:2]:
                snippet = str(getattr(item, "snippet", "") or getattr(item, "message", "") or "")
                claim_punc_samples.append(f"#{claim.num}:{snippet}@{int(item.span_start or 0)}")

        claim_repeated_word_issues = [
            issue
            for issue in _execute_checker(
                f"claim.{claim.num}.repeated_word",
                lambda: check_repeated_word_issues(
                    claim.text,
                    section="claims",
                    claim_num=claim.num,
                ),
                rule_errors,
            )
            if _is_enabled(issue.rule_id)
        ]
        if claim_repeated_word_issues:
            _apply_issue_id(claim_repeated_word_issues, default_anchor_start=_claim_anchor(claim))
            issues.extend(claim_repeated_word_issues)

    semantic_issues: list[Issue] = []
    semantic_checks = (
        ("description.headings", lambda: check_description_heading_issues(document)),
        ("description.title", lambda: check_description_title_issues(document)),
        (
            "drawings.cross_section",
            lambda: check_drawings_cross_section_consistency_issues(document),
        ),
        (
            "drawings.duplicate_figure",
            lambda: check_drawings_duplicate_figure_issues(document),
        ),
        (
            "drawings.figure_reference",
            lambda: check_drawings_figure_reference_issues(document),
        ),
        ("theme.consistency", lambda: check_theme_consistency_issues(document)),
    )
    for checker_id, callback in semantic_checks:
        semantic_issues.extend(
            issue
            for issue in _execute_checker(checker_id, callback, rule_errors)
            if _is_enabled(issue.rule_id)
        )
    if semantic_issues:
        for item in semantic_issues:
            if str(getattr(item, "section", "") or "") != "claims":
                continue
            claim_num = int(getattr(item, "claim_num", 0) or 0)
            if claim_num <= 0:
                continue
            for claim in document.claims:
                if int(getattr(claim, "num", 0) or 0) != claim_num:
                    continue
                item.anchor = {"word_range_start": int(_claim_anchor(claim))}
                break
        _apply_issue_id(semantic_issues, default_anchor_start=0)
        issues.extend(semantic_issues)

    # Observability: help diagnose section coverage gaps via conversion.log.
    try:
        desc_samples = [str(getattr(row, "snippet", "") or getattr(row, "message", "") or "") for row in list(desc_punc_issues or [])[:6]]
        abstract_samples = [str(getattr(row, "snippet", "") or getattr(row, "message", "") or "") for row in list(abstract_punc_issues or [])[:6]]
        claims_nonzero = {k: v for k, v in dict(claim_punc_by_claim).items() if int(v) > 0}
        logger.debug(
            "[formal_review][punct] claims: total=%s by_claim=%s sample=%s",
            int(claim_punc_total),
            claims_nonzero,
            "; ".join(claim_punc_samples[:6]),
        )
        logger.debug(
            "[formal_review][punct] description: total=%s sample=%s",
            int(len(list(desc_punc_issues or []))),
            "; ".join(desc_samples),
        )
        logger.debug(
            "[formal_review][punct] abstract: total=%s sample=%s",
            int(len(list(abstract_punc_issues or []))),
            "; ".join(abstract_samples),
        )
    except Exception:
        pass

    wordlists_v2 = normalize_wordlists(wordlists)
    wordlist_summary: dict[str, dict[str, dict[str, dict[str, object]]]] = {
        "claims": {"forbidden": {}, "sensitive": {}},
        "description": {"forbidden": {}, "sensitive": {}},
    }

    for category, severity in (("forbidden", "high"), ("sensitive", "medium")):
        description_terms = _wordlist_terms(wordlists_v2, "description", category)
        description_rule_id = f"wordlist.description.{category}"
        description_matches = _execute_checker(
            f"wordlist.description.{category}",
            lambda: [
                match_terms(
                    document.description,
                    description_terms,
                    category=category,
                    severity=severity,
                    section="description",
                )
            ],
            rule_errors,
        )
        description_match = (
            description_matches[0]
            if description_matches
            else {"summary": [], "occurrences": []}
        )
        if _is_enabled(description_rule_id):
            for row in description_match["summary"]:
                _merge_summary_row(wordlist_summary["description"][category], row)
        for item in description_match["occurrences"]:
            rule_id = description_rule_id
            if not _is_enabled(rule_id):
                continue
            issue = Issue(
                rule_id=rule_id,
                severity=severity,
                category=category,
                section="description",
                span_start=int(item["start"]),
                span_end=int(item["end"]),
                snippet=str(item["snippet"]),
                message=_wordlist_message("description", category, str(item["term"])),
                anchor={"word_range_start": 0},
            )
            issue.issue_id = build_issue_id(issue)
            issues.append(issue)

        claim_terms = _wordlist_terms(wordlists_v2, "claims", category)
        claim_rule_id = f"wordlist.claims.{category}"
        for claim in document.claims:
            claim_matches = _execute_checker(
                f"wordlist.claims.{category}.claim_{claim.num}",
                lambda: [
                    match_terms(
                        claim.text,
                        claim_terms,
                        category=category,
                        severity=severity,
                        section="claims",
                        claim_num=claim.num,
                    )
                ],
                rule_errors,
            )
            claim_match = (
                claim_matches[0]
                if claim_matches
                else {"summary": [], "occurrences": []}
            )
            if _is_enabled(claim_rule_id):
                for row in claim_match["summary"]:
                    _merge_summary_row(wordlist_summary["claims"][category], row)
            for item in claim_match["occurrences"]:
                rule_id = claim_rule_id
                if not _is_enabled(rule_id):
                    continue
                issue = Issue(
                    rule_id=rule_id,
                    severity=severity,
                    category=category,
                    section="claims",
                    claim_num=claim.num,
                    span_start=int(item["start"]),
                    span_end=int(item["end"]),
                    snippet=str(item["snippet"]),
                    message=_wordlist_message("claims", category, str(item["term"])),
                    anchor={"word_range_start": _claim_anchor(claim)},
                )
                issue.issue_id = build_issue_id(issue)
                issues.append(issue)

    ignored_set = set(ignored_issue_ids or set())
    for issue in issues:
        _enrich_issue(issue)
        if issue.issue_id and issue.issue_id in ignored_set:
            issue.ignored = True

    return {
        "issues": issues,
        "rule_errors": rule_errors,
        "wordlist_summary": wordlist_summary,
        "counts": {
            "total": len(issues),
            "ignored": len([issue for issue in issues if issue.ignored]),
        },
    }
