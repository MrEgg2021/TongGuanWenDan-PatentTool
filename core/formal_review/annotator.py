from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from .models import Issue
from .range_resolver import ResolverPolicy, resolve_issue_range
from .text_projection import ProjectionBundle

TOOL_COMMENT_PREFIX = "[形式审查]"


@dataclass(slots=True)
class CommentPlanItem:
    issue_id: str
    section: str
    claim_num: int | None
    range_start: int | None
    range_end: int | None
    expected_hit: str
    comment_text: str
    ignored: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CommentTarget:
    issue_id: str
    start: int
    end: int
    comment_text: str
    resolve_mode: Literal["strict", "loose"] = "strict"


@dataclass(slots=True)
class CommentTargetFailure:
    issue_id: str
    reason_code: str
    detail: str


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except Exception:
        return default


def is_tool_comment(text: str, prefix: str = TOOL_COMMENT_PREFIX) -> bool:
    content = str(text or "").lstrip()
    token = str(prefix or "").strip()
    return bool(token) and content.startswith(token)


def _scope_tuple_for_comment(row) -> tuple[int, int] | None:
    scope = getattr(row, "Scope", None) or getattr(row, "Reference", None) or getattr(row, "Range", None)
    if scope is None:
        return None
    start = _safe_int(getattr(scope, "Start", None), None)
    end = _safe_int(getattr(scope, "End", None), None)
    if start is None or end is None or int(end) <= int(start):
        return None
    return int(start), int(end)


def clear_tool_comments(
    doc,
    prefix: str = TOOL_COMMENT_PREFIX,
    target_ranges: set[tuple[int, int]] | None = None,
) -> int:
    removed = 0
    if doc is None:
        return removed
    comments = getattr(doc, "Comments", None)
    if comments is None:
        return removed
    targets = set(target_ranges or set())
    use_targets = bool(targets)
    try:
        total = int(getattr(comments, "Count", 0) or 0)
    except Exception:
        total = 0
    for idx in range(total, 0, -1):
        try:
            row = comments(idx)
            text = str(getattr(getattr(row, "Range", None), "Text", "") or "")
            if not is_tool_comment(text, prefix=prefix):
                continue
            if use_targets:
                scope = _scope_tuple_for_comment(row)
                if scope is None or scope not in targets:
                    continue
            row.Delete()
            removed += 1
        except Exception:
            continue
    return removed


def build_comment_text(issue: Issue, *, tool_prefix: str = TOOL_COMMENT_PREFIX) -> str:
    section = str(issue.section or "")
    section_label = {
        "claims": "权利要求书",
        "description": "说明书",
        "abstract": "摘要",
        "drawings": "附图说明",
    }.get(section, section)
    suffix = [f"@{section_label}"]
    if issue.claim_num is not None:
        suffix.append(f"@权利要求{issue.claim_num}")
    if isinstance(issue.anchor, dict):
        anchor_start = _safe_int(issue.anchor.get("word_range_start"), default=None)
        if anchor_start is not None and issue.span_start is not None:
            suffix.append(f"@{anchor_start + int(issue.span_start)}")
    prefix = str(tool_prefix or "").strip()
    return f"{prefix}\n{issue.rule_id} ({issue.severity})\n{issue.message}\n" + " ".join(suffix)


def build_comment_plan(issues: list[Issue], *, tool_prefix: str = TOOL_COMMENT_PREFIX) -> list[CommentPlanItem]:
    plan: list[CommentPlanItem] = []
    for issue in issues:
        anchor_start = None
        if isinstance(issue.anchor, dict):
            anchor_start = _safe_int(issue.anchor.get("word_range_start"), default=None)
        range_start = None
        range_end = None
        if anchor_start is not None and issue.span_start is not None and issue.span_end is not None:
            range_start = anchor_start + int(issue.span_start)
            range_end = anchor_start + int(issue.span_end)
        plan.append(
            CommentPlanItem(
                issue_id=str(issue.issue_id or ""),
                section=issue.section,
                claim_num=issue.claim_num,
                range_start=range_start,
                range_end=range_end,
                expected_hit=str((issue.anchor or {}).get("expected_hit", "") if isinstance(issue.anchor, dict) else ""),
                comment_text=build_comment_text(issue, tool_prefix=tool_prefix),
                ignored=bool(issue.ignored),
            )
        )
    return plan


def preflight_comment_targets(
    doc,
    *,
    issues: list[Issue],
    comment_plan: list[CommentPlanItem] | None = None,
    tool_prefix: str = TOOL_COMMENT_PREFIX,
    projections: ProjectionBundle | None = None,
    allow_loose_fallback: bool = False,
    allow_legacy_fallback: bool = False,
    require_com_ready: bool = False,
) -> dict[str, Any]:
    plan = list(comment_plan or build_comment_plan(issues, tool_prefix=tool_prefix))
    issue_map = {str(getattr(row, "issue_id", "") or ""): row for row in list(issues or [])}
    targets: list[CommentTarget] = []
    failures: list[CommentTargetFailure] = []
    skipped_ignored = 0
    strict_failed = 0
    loose_rescued = 0
    strict_level_hist: dict[str, int] = {}
    loose_level_hist: dict[str, int] = {}
    resolver_path_hist: dict[str, int] = {}
    resolver_reason_hist: dict[str, int] = {}

    def _normalize_path_level(level: str) -> str:
        resolved = str(level or "").strip().lower()
        if resolved in {"projection", "occurrence", "context"}:
            return f"projection_{resolved}"
        if resolved == "word_find_com":
            return "word_find_com"
        if resolved in {"word_find", "word_find_legacy"}:
            return "word_find_legacy"
        return resolved or "unknown"

    def _record_resolver_result(resolved) -> None:
        if bool(getattr(resolved, "ok", False)):
            key = _normalize_path_level(str(getattr(resolved, "level", "") or ""))
            resolver_path_hist[key] = int(resolver_path_hist.get(key, 0) or 0) + 1
            return
        key = str(getattr(resolved, "reason_code", "") or "unknown")
        resolver_reason_hist[key] = int(resolver_reason_hist.get(key, 0) or 0) + 1

    def _bump_hist(hist: dict[str, int], level: str) -> None:
        key = str(level or "unknown")
        hist[key] = int(hist.get(key, 0) or 0) + 1

    for item in plan:
        if item.ignored:
            skipped_ignored += 1
            continue

        issue = issue_map.get(str(item.issue_id or ""))
        if issue is None:
            failures.append(CommentTargetFailure(str(item.issue_id or ""), "issue_missing", "issue_not_found_in_runtime_set"))
            continue

        resolved = resolve_issue_range(
            doc,
            issue,
            projections,
            strict=True,
            allow_legacy_fallback=bool(allow_legacy_fallback),
            policy=ResolverPolicy(
                strict=True,
                allow_legacy_fallback=bool(allow_legacy_fallback),
                require_com_ready=bool(require_com_ready),
            ),
        )
        _record_resolver_result(resolved)
        _bump_hist(strict_level_hist, str(getattr(resolved, "level", "") or ""))
        resolve_mode: Literal["strict", "loose"] = "strict"
        if not bool(getattr(resolved, "ok", False)):
            strict_failed += 1
            if bool(allow_loose_fallback):
                loose = resolve_issue_range(
                    doc,
                    issue,
                    projections,
                    strict=False,
                    allow_legacy_fallback=bool(allow_legacy_fallback),
                    policy=ResolverPolicy(
                        strict=False,
                        allow_legacy_fallback=bool(allow_legacy_fallback),
                        require_com_ready=bool(require_com_ready),
                    ),
                )
                _record_resolver_result(loose)
                _bump_hist(loose_level_hist, str(getattr(loose, "level", "") or ""))
                if bool(getattr(loose, "ok", False)):
                    resolved = loose
                    resolve_mode = "loose"
                    loose_rescued += 1
                else:
                    failures.append(
                        CommentTargetFailure(
                            str(item.issue_id or ""),
                            str(getattr(loose, "reason_code", "") or "resolve_failed"),
                            str(getattr(loose, "detail", "") or getattr(loose, "reason", "") or ""),
                        )
                    )
                    continue
            else:
                failures.append(
                    CommentTargetFailure(
                        str(item.issue_id or ""),
                        str(getattr(resolved, "reason_code", "") or "resolve_failed"),
                        str(getattr(resolved, "detail", "") or getattr(resolved, "reason", "") or ""),
                    )
                )
                continue

        start = _safe_int(getattr(resolved, "start", None), None)
        end = _safe_int(getattr(resolved, "end", None), None)
        if start is None or end is None or end <= start:
            failures.append(CommentTargetFailure(str(item.issue_id or ""), "resolved_range_invalid", "start_or_end_invalid"))
            continue

        targets.append(
            CommentTarget(
                issue_id=str(item.issue_id or ""),
                start=int(start),
                end=int(end),
                comment_text=str(item.comment_text or ""),
                resolve_mode=resolve_mode,
            )
        )

    return {
        "targets": targets,
        "failures": failures,
        "skipped_ignored": int(skipped_ignored),
        "strict_failed": int(strict_failed),
        "loose_rescued": int(loose_rescued),
        "final_failed": int(len(failures)),
        "strict_level_hist": dict(strict_level_hist),
        "loose_level_hist": dict(loose_level_hist),
        "resolver_path_hist": dict(resolver_path_hist),
        "resolver_reason_hist": dict(resolver_reason_hist),
    }


def apply_comments_to_doc(
    doc,
    *,
    issues: list[Issue],
    comment_plan: list[CommentPlanItem] | None = None,
    tool_prefix: str = TOOL_COMMENT_PREFIX,
    projections: ProjectionBundle | None = None,
    preflight: dict[str, Any] | None = None,
    allow_partial_preflight_failures: bool = False,
) -> dict[str, Any]:
    if preflight is None:
        preflight = preflight_comment_targets(
            doc,
            issues=list(issues or []),
            comment_plan=comment_plan,
            tool_prefix=tool_prefix,
            projections=projections,
        )

    targets: list[CommentTarget] = list(preflight.get("targets", []) or [])
    preflight_failures: list[CommentTargetFailure] = list(preflight.get("failures", []) or [])
    skipped_ignored = int(preflight.get("skipped_ignored", 0) or 0)
    preflight_failed_ids = [str(item.issue_id or "") for item in preflight_failures]
    preflight_failed_items = [asdict(item) for item in preflight_failures]

    if preflight_failures and (not bool(allow_partial_preflight_failures) or not targets):
        return {
            "written": 0,
            "skipped": int(skipped_ignored + len(preflight_failures)),
            "failed_issue_count": int(len(preflight_failures)),
            "failed_issue_ids": list(preflight_failed_ids),
            "failed_items": list(preflight_failed_items),
        }

    written = 0
    created_rows: list[Any] = []
    targets.sort(key=lambda item: int(getattr(item, "start", 0) or 0), reverse=True)
    for target in targets:
        try:
            rng = doc.Range(int(target.start), int(target.end))
            row = doc.Comments.Add(rng, str(target.comment_text or ""))
            if row is not None:
                created_rows.append(row)
            written += 1
        except Exception as exc:
            for item in reversed(created_rows):
                try:
                    item.Delete()
                except Exception:
                    pass
            failed = CommentTargetFailure(str(getattr(target, "issue_id", "") or ""), "comment_add_failed", str(exc))
            return {
                "written": 0,
                "skipped": int(skipped_ignored + len(preflight_failures) + len(targets)),
                "failed_issue_count": int(len(preflight_failures) + 1),
                "failed_issue_ids": list(preflight_failed_ids) + [str(getattr(target, "issue_id", "") or "")],
                "failed_items": list(preflight_failed_items) + [asdict(failed)],
            }

    return {
        "written": int(written),
        "skipped": int(skipped_ignored + len(preflight_failures)),
        "failed_issue_count": int(len(preflight_failures)),
        "failed_issue_ids": list(preflight_failed_ids),
        "failed_items": list(preflight_failed_items),
    }
