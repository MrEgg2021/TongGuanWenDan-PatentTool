from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from pathlib import Path
import shutil

from core.logging_utils import logger

from .annotator import (
    TOOL_COMMENT_PREFIX,
    apply_comments_to_doc,
    build_comment_plan,
    clear_tool_comments as clear_tool_comments_in_doc,
    preflight_comment_targets,
)
from .models import Issue
from .rule_registry import RULE_REGISTRY
from .text_projection import ProjectionBundle
from .word_highlight_sync import clear_tool_highlights_via_comments

_SUPPORTED_WORD_SUFFIXES = {".doc", ".docx"}
_RULE_ID_DESC_MISSING_IN_DRAWINGS = "description.drawings.figure.ref.missing_in_drawings_section"
_RULE_ID_DRAWINGS_MISSING_IN_DESC = "drawings.figure.ref.missing_in_description_drawings"


@dataclass(slots=True)
class CommentSyncResult:
    output_path: str
    written: int
    skipped: int
    cleared_tool_comments: int
    cleared_tool_highlights: int
    used_existing_doc: bool
    highlighted: int = 0
    source_saved: bool = False
    source_closed: bool = False
    failed_issue_count: int = 0
    failed_issue_ids: list[str] | None = None
    failed_reason_codes: list[str] | None = None
    strict_failed: int = 0
    loose_rescued: int = 0
    final_failed: int = 0
    resolver_path_hist: dict[str, int] | None = None
    resolver_reason_hist: dict[str, int] | None = None
    blocked_by_com: bool = False


def _normalize_path(path: str) -> str:
    try:
        return str(Path(str(path or "")).resolve())
    except Exception:
        return str(path or "")


def _normalized_word_suffix(path: str) -> str:
    return str(Path(str(path or "").strip()).suffix or "").lower()


def _find_open_doc_by_path(app, target_norm: str):
    docs = getattr(app, "Documents", None)
    if docs is None:
        return None
    try:
        count = int(getattr(docs, "Count", 0) or 0)
    except Exception:
        count = 0
    for idx in range(1, count + 1):
        try:
            row = docs(idx)
        except Exception:
            continue
        row_path = _normalize_path(str(getattr(row, "FullName", "") or ""))
        if row_path == target_norm:
            return row
    return None


def _save_copy_from_live_doc(app, source_norm: str, target_norm: str) -> bool:
    source_doc = _find_open_doc_by_path(app, source_norm)
    if source_doc is None:
        return False
    target_path = Path(target_norm)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_doc.SaveCopyAs(target_norm)
    return True


def _prepare_author(app, author_name: str) -> tuple[str, str]:
    original_user_name = str(getattr(app, "UserName", "") or "")
    original_initials = str(getattr(app, "UserInitials", "") or "")
    custom_author = str(author_name or "").strip()
    if custom_author:
        app.UserName = custom_author
        app.UserInitials = custom_author[:2]
    return original_user_name, original_initials


def _restore_author(app, user_name: str, initials: str) -> None:
    try:
        app.UserName = str(user_name or "")
        app.UserInitials = str(initials or "")
    except Exception:
        pass


def sync_comments_to_doc(
    doc,
    issues: list[Issue],
    *,
    author_name: str,
    clear_tool_comments: bool,
    tool_prefix: str = TOOL_COMMENT_PREFIX,
    projections: ProjectionBundle | None = None,
    color_map: dict[str, str] | None = None,
    apply_highlights: bool = False,
    clear_tool_highlights: bool = True,
    allow_loose_fallback: bool = False,
    allow_legacy_fallback: bool = False,
    require_com_ready: bool = False,
    allow_partial_on_preflight_failure: bool = False,
    preserve_failed_existing_comments: bool = False,
) -> CommentSyncResult:
    if doc is None:
        raise RuntimeError("Word 文档对象不可用，无法写入批注。")
    app = getattr(doc, "Application", None)
    if app is None:
        raise RuntimeError("Word 应用对象不可用，无法写入批注。")

    old_user_name, old_initials = _prepare_author(app, author_name)
    undo_record = None
    undo_started = False
    undo_available = False
    try:
        plan = build_comment_plan(list(issues or []), tool_prefix=tool_prefix)

        def _end_undo_record() -> None:
            nonlocal undo_started
            if not undo_started or undo_record is None:
                return
            try:
                undo_record.EndCustomRecord()
            except Exception:
                pass
            undo_started = False

        def _rollback_or_raise(*, reason: str, rollback_exc: Exception | None = None) -> None:
            # End record before undo to avoid "rollback_failed: <unknown>.Undo".
            _end_undo_record()
            if not undo_available:
                return
            try:
                app.Undo()
                logger.info("[formal_review][comment_sync] rolled_back_after_%s", reason)
            except Exception as exc:
                logger.warning("[formal_review][comment_sync] rollback_failed (%s): %s", reason, exc)
                # This is serious: the document may be partially modified. Force the caller to surface it.
                hint = "回滚失败：文档可能已被部分修改。请立即关闭该副本且不要保存，然后重新打开副本再重试。"
                raise RuntimeError(hint) from (rollback_exc or exc)

        issue_rows = list(issues or [])
        cross_desc_count = len(
            [row for row in issue_rows if str(getattr(row, "rule_id", "") or "") == _RULE_ID_DESC_MISSING_IN_DRAWINGS]
        )
        cross_drawings_count = len(
            [row for row in issue_rows if str(getattr(row, "rule_id", "") or "") == _RULE_ID_DRAWINGS_MISSING_IN_DESC]
        )

        logger.info(
            "[formal_review][comment_sync] begin: issues=%s apply_highlights=%s clear_tool_highlights=%s clear_tool_comments=%s allow_loose_fallback=%s allow_legacy_fallback=%s require_com_ready=%s allow_partial_on_preflight_failure=%s preserve_failed_existing_comments=%s strict_level_hist=%s loose_level_hist=%s resolver_path_hist=%s resolver_reason_hist=%s blocked_by_com=%s cross_desc=%s cross_drawings=%s",
            len(issue_rows),
            bool(apply_highlights),
            bool(clear_tool_highlights),
            bool(clear_tool_comments),
            bool(allow_loose_fallback),
            bool(allow_legacy_fallback),
            bool(require_com_ready),
            bool(allow_partial_on_preflight_failure),
            bool(preserve_failed_existing_comments),
            {},
            {},
            {},
            {},
            False,
            int(cross_desc_count),
            int(cross_drawings_count),
        )

        def _failure_histogram(failures) -> str:
            counter = Counter([str(getattr(item, "reason_code", "") or "unknown") for item in list(failures or [])])
            if not counter:
                return ""
            parts = [f"{key}={counter[key]}" for key in sorted(counter.keys())]
            return ", ".join(parts)

        def _hex_to_bgr_int(value: str) -> int:
            text = str(value or "").strip()
            if not text.startswith("#"):
                text = f"#{text}"
            if len(text) != 7:
                raise ValueError(f"invalid hex color: {value!r}")
            red = int(text[1:3], 16)
            green = int(text[3:5], 16)
            blue = int(text[5:7], 16)
            return int((blue << 16) | (green << 8) | red)

        def _issue_color(issue: Issue) -> str:
            cmap = dict(color_map or {})
            rule_id = str(getattr(issue, "rule_id", "") or "")
            meta = RULE_REGISTRY.get(rule_id, {}) if isinstance(RULE_REGISTRY, dict) else {}
            key = str((meta or {}).get("color_key") or "default")
            return str(cmap.get(rule_id) or cmap.get(key) or cmap.get("default") or "#E0E0E0")

        def _apply_highlights_for_targets(targets, issue_by_id: dict[str, Issue]) -> tuple[int, list[str]]:
            warnings: list[str] = []
            applied = 0
            for target in list(targets or []):
                issue_id = str(getattr(target, "issue_id", "") or "")
                issue = issue_by_id.get(issue_id)
                if issue is None:
                    continue
                try:
                    rng = doc.Range(int(getattr(target, "start")), int(getattr(target, "end")))
                except Exception as exc:
                    warnings.append(f"{issue_id}: range_failed: {exc}")
                    continue
                try:
                    bgr = _hex_to_bgr_int(_issue_color(issue))
                except Exception as exc:
                    warnings.append(f"{issue_id}: invalid_color: {exc}")
                    continue
                applied_one = False
                try:
                    rng.Shading.BackgroundPatternColor = int(bgr)
                    applied_one = True
                except Exception:
                    pass
                if not applied_one:
                    try:
                        rng.HighlightColorIndex = 7  # wdYellow
                        applied_one = True
                    except Exception:
                        pass
                if applied_one:
                    applied += 1
                else:
                    warnings.append(f"{issue_id}: highlight_apply_failed")
            return int(applied), warnings

        removed = 0
        highlighted = 0
        cleared_highlights = 0

        preflight = preflight_comment_targets(
            doc,
            issues=list(issues or []),
            comment_plan=plan,
            tool_prefix=tool_prefix,
            projections=projections,
            allow_loose_fallback=bool(allow_loose_fallback),
            allow_legacy_fallback=bool(allow_legacy_fallback),
            require_com_ready=bool(require_com_ready),
        )
        failures = list(preflight.get("failures", []) or [])
        targets = list(preflight.get("targets", []) or [])
        skipped_ignored = int(preflight.get("skipped_ignored", 0) or 0)
        strict_failed = int(preflight.get("strict_failed", len(failures)) or 0)
        loose_rescued = int(preflight.get("loose_rescued", 0) or 0)
        final_failed = int(preflight.get("final_failed", len(failures)) or 0)
        strict_level_hist = dict(preflight.get("strict_level_hist", {}) or {})
        loose_level_hist = dict(preflight.get("loose_level_hist", {}) or {})
        resolver_path_hist = dict(preflight.get("resolver_path_hist", {}) or {})
        resolver_reason_hist = dict(preflight.get("resolver_reason_hist", {}) or {})
        blocked_by_com = bool(resolver_reason_hist.get("com_find_unavailable_blocked"))
        partial_preflight_mode = bool(
            failures
            and targets
            and bool(allow_partial_on_preflight_failure)
        )
        if failures:
            failed_ids = [str(getattr(item, "issue_id", "") or "") for item in failures]
            failed_reason_codes = [str(getattr(item, "reason_code", "") or "unknown") for item in failures]
            blocked_by_com = blocked_by_com or any(code == "com_find_unavailable_blocked" for code in failed_reason_codes)
            logger.warning(
                "[formal_review][comment_sync] preflight_failed: strict_failed=%s loose_rescued=%s final_failed=%s skipped_ignored=%s strict_level_hist=%s loose_level_hist=%s resolver_path_hist=%s resolver_reason_hist=%s blocked_by_com=%s reason_hist=%s sample=%s cross_desc=%s cross_drawings=%s",
                strict_failed,
                loose_rescued,
                final_failed,
                skipped_ignored,
                strict_level_hist,
                loose_level_hist,
                resolver_path_hist,
                resolver_reason_hist,
                bool(blocked_by_com),
                _failure_histogram(failures),
                ", ".join(failed_ids[:6]),
                int(cross_desc_count),
                int(cross_drawings_count),
            )
            if not partial_preflight_mode:
                return CommentSyncResult(
                    output_path=str(getattr(doc, "FullName", "") or ""),
                    written=0,
                    skipped=int(skipped_ignored + len(failures)),
                    cleared_tool_comments=0,
                    cleared_tool_highlights=0,
                    used_existing_doc=True,
                    highlighted=0,
                    failed_issue_count=int(len(failures)),
                    failed_issue_ids=failed_ids,
                    failed_reason_codes=failed_reason_codes,
                    strict_failed=int(strict_failed),
                    loose_rescued=int(loose_rescued),
                    final_failed=int(final_failed),
                    resolver_path_hist=resolver_path_hist,
                    resolver_reason_hist=resolver_reason_hist,
                    blocked_by_com=bool(blocked_by_com),
                )
            logger.info(
                "[formal_review][comment_sync] preflight_partial_continue: failures=%s targets=%s cross_desc=%s cross_drawings=%s",
                int(len(failures)),
                int(len(targets)),
                int(cross_desc_count),
                int(cross_drawings_count),
            )

        # Commit phase: start UndoRecord *after* preflight passes so preflight failures can be strictly "no mutation".
        try:
            undo_record = getattr(app, "UndoRecord", None)
            if undo_record is not None:
                undo_record.StartCustomRecord("形式审查批注同步")
                undo_started = True
                undo_available = True
        except Exception:
            undo_record = None
            undo_started = False
            undo_available = False

        target_ranges: set[tuple[int, int]] | None = None
        if bool(partial_preflight_mode and preserve_failed_existing_comments):
            rows = set()
            for target in targets:
                start = int(getattr(target, "start", 0) or 0)
                end = int(getattr(target, "end", 0) or 0)
                if int(end) > int(start):
                    rows.add((int(start), int(end)))
            target_ranges = rows

        if bool(clear_tool_highlights):
            try:
                cleared_highlights = int(
                    clear_tool_highlights_via_comments(
                        doc,
                        tool_prefix=tool_prefix,
                        target_ranges=target_ranges,
                    )
                )
            except Exception as exc:
                logger.debug("[formal_review][comment_sync] clear_tool_highlights failed: %s", exc)
                cleared_highlights = 0

        removed = (
            clear_tool_comments_in_doc(doc, prefix=tool_prefix, target_ranges=target_ranges)
            if clear_tool_comments
            else 0
        )

        stats = apply_comments_to_doc(
            doc,
            issues=list(issues or []),
            comment_plan=plan,
            tool_prefix=tool_prefix,
            projections=projections,
            preflight=preflight,
            allow_partial_preflight_failures=bool(allow_partial_on_preflight_failure),
        )
        failed_items = list(stats.get("failed_items", []) or [])
        failed_ids = list(stats.get("failed_issue_ids", []) or [])
        failed_count = int(stats.get("failed_issue_count", len(failed_items)) or 0)
        failed_reason_codes = [str((row or {}).get("reason_code") or "unknown") for row in failed_items]
        apply_failed_count = len([row for row in failed_items if str((row or {}).get("reason_code") or "") == "comment_add_failed"])
        if apply_failed_count > 0:
            logger.warning(
                "[formal_review][comment_sync] apply_failed: failed=%s sample=%s",
                int(apply_failed_count),
                ", ".join([str(x) for x in failed_ids[:6]]),
            )
            _rollback_or_raise(reason="apply_fail")
            return CommentSyncResult(
                output_path=str(getattr(doc, "FullName", "") or ""),
                written=0,
                skipped=int(stats.get("skipped", 0) or 0),
                cleared_tool_comments=0,
                cleared_tool_highlights=0,
                used_existing_doc=True,
                highlighted=0,
                failed_issue_count=int(failed_count),
                failed_issue_ids=list(failed_ids or []),
                failed_reason_codes=list(failed_reason_codes or []),
                strict_failed=int(strict_failed),
                loose_rescued=int(loose_rescued),
                final_failed=int(failed_count),
                resolver_path_hist=resolver_path_hist,
                resolver_reason_hist=resolver_reason_hist,
                blocked_by_com=bool(blocked_by_com),
            )
        final_failed = int(failed_count)

        if apply_highlights:
            try:
                issue_by_id = {str(getattr(row, "issue_id", "") or ""): row for row in list(issues or [])}
                highlighted, warnings = _apply_highlights_for_targets(targets, issue_by_id)
                for warning in warnings[:10]:
                    logger.debug("[formal_review][comment_sync] highlight_warning: %s", warning)
            except Exception as exc:
                logger.warning("[formal_review][comment_sync] highlight_sync_failed: %s", exc)
                highlighted = 0

        doc.Save()
        _end_undo_record()
        logger.info(
            "[formal_review][comment_sync] done: written=%s skipped=%s cleared_comments=%s cleared_highlights=%s highlighted=%s strict_failed=%s loose_rescued=%s final_failed=%s strict_level_hist=%s loose_level_hist=%s resolver_path_hist=%s resolver_reason_hist=%s blocked_by_com=%s cross_desc=%s cross_drawings=%s",
            int(stats.get("written", 0) or 0),
            int(stats.get("skipped", 0) or 0),
            int(removed),
            int(cleared_highlights),
            int(highlighted),
            int(strict_failed),
            int(loose_rescued),
            int(final_failed),
            strict_level_hist,
            loose_level_hist,
            resolver_path_hist,
            resolver_reason_hist,
            bool(blocked_by_com),
            int(cross_desc_count),
            int(cross_drawings_count),
        )
    except Exception as exc:
        logger.exception("[formal_review][comment_sync] exception: %s", exc)
        _rollback_or_raise(reason="exception", rollback_exc=exc)
        raise
    finally:
        _end_undo_record()
        _restore_author(app, old_user_name, old_initials)

    return CommentSyncResult(
        output_path=str(getattr(doc, "FullName", "") or ""),
        written=int(stats.get("written", 0)),
        skipped=int(stats.get("skipped", 0)),
        cleared_tool_comments=int(removed),
        cleared_tool_highlights=int(cleared_highlights),
        used_existing_doc=True,
        highlighted=int(highlighted),
        failed_issue_count=int(failed_count),
        failed_issue_ids=list(failed_ids or []),
        failed_reason_codes=list(failed_reason_codes or []),
        strict_failed=int(strict_failed),
        loose_rescued=int(loose_rescued),
        final_failed=int(failed_count),
        resolver_path_hist=resolver_path_hist,
        resolver_reason_hist=resolver_reason_hist,
        blocked_by_com=bool(blocked_by_com),
    )


def sync_comments_inplace(
    doc,
    issues: list[Issue],
    *,
    author_name: str,
    tool_prefix: str = TOOL_COMMENT_PREFIX,
    projections: ProjectionBundle | None = None,
    color_map: dict[str, str] | None = None,
    apply_highlights: bool = False,
    clear_tool_highlights: bool = True,
    allow_loose_fallback: bool = False,
    allow_legacy_fallback: bool = False,
    require_com_ready: bool = False,
    allow_partial_on_preflight_failure: bool = False,
    preserve_failed_existing_comments: bool = False,
) -> CommentSyncResult:
    return sync_comments_to_doc(
        doc,
        list(issues or []),
        author_name=author_name,
        clear_tool_comments=True,
        tool_prefix=tool_prefix,
        projections=projections,
        color_map=dict(color_map or {}),
        apply_highlights=bool(apply_highlights),
        clear_tool_highlights=bool(clear_tool_highlights),
        allow_loose_fallback=bool(allow_loose_fallback),
        allow_legacy_fallback=bool(allow_legacy_fallback),
        require_com_ready=bool(require_com_ready),
        allow_partial_on_preflight_failure=bool(allow_partial_on_preflight_failure),
        preserve_failed_existing_comments=bool(preserve_failed_existing_comments),
    )


def sync_comments_to_copy(
    session,
    *,
    source_path: str,
    output_path: str,
    issues: list[Issue],
    author_name: str,
    tool_prefix: str = TOOL_COMMENT_PREFIX,
    allow_inplace: bool = False,
    close_source_after_copy: bool = True,
    projections: ProjectionBundle | None = None,
    color_map: dict[str, str] | None = None,
    apply_highlights: bool = False,
    clear_tool_highlights: bool = True,
    allow_loose_fallback: bool = False,
    allow_legacy_fallback: bool = False,
    require_com_ready: bool = False,
    allow_partial_on_preflight_failure: bool = False,
    preserve_failed_existing_comments: bool = False,
) -> CommentSyncResult:
    if session is None:
        raise RuntimeError("伴侣会话不可用，无法同步批注。")
    app = getattr(session, "app", None)
    if app is None:
        raise RuntimeError("Word 应用对象不可用，无法同步批注。")

    source_file = str(source_path or "").strip()
    target_file = str(output_path or "").strip()
    if not source_file or not target_file:
        raise ValueError("source_path/output_path 不能为空")
    source_suffix = _normalized_word_suffix(source_file)
    target_suffix = _normalized_word_suffix(target_file)
    if source_suffix not in _SUPPORTED_WORD_SUFFIXES:
        raise ValueError(f"Unsupported source extension: {source_suffix or '(none)'}")
    if target_suffix not in _SUPPORTED_WORD_SUFFIXES:
        raise ValueError(f"Unsupported output extension: {target_suffix or '(none)'}")
    if source_suffix != target_suffix:
        raise ValueError(f"Output extension must match source extension: {source_suffix}")

    source_norm = _normalize_path(source_file)
    target_norm = _normalize_path(target_file)
    if (not allow_inplace) and source_norm == target_norm:
        raise ValueError("批注副本路径不能与源文件相同")

    target_path = Path(target_file)
    used_existing_doc = target_path.exists()
    if not used_existing_doc:
        copied = False
        try:
            copied = _save_copy_from_live_doc(app, source_norm, target_norm)
        except Exception:
            copied = False
        if not copied:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)

    doc = _find_open_doc_by_path(app, target_norm)
    docs = getattr(app, "Documents", None)
    if docs is None:
        raise RuntimeError("当前 Word 实例不可用（Documents 不可访问）。")
    if doc is None:
        doc = docs.Open(target_norm, ReadOnly=False, AddToRecentFiles=False)

    result = sync_comments_to_doc(
        doc,
        list(issues or []),
        author_name=author_name,
        clear_tool_comments=True,
        tool_prefix=tool_prefix,
        projections=projections,
        color_map=dict(color_map or {}),
        apply_highlights=bool(apply_highlights),
        clear_tool_highlights=bool(clear_tool_highlights),
        allow_loose_fallback=bool(allow_loose_fallback),
        allow_legacy_fallback=bool(allow_legacy_fallback),
        require_com_ready=bool(require_com_ready),
        allow_partial_on_preflight_failure=bool(allow_partial_on_preflight_failure),
        preserve_failed_existing_comments=bool(preserve_failed_existing_comments),
    )

    source_saved = False
    source_closed = False
    if bool(close_source_after_copy) and source_norm != target_norm:
        source_doc = _find_open_doc_by_path(app, source_norm)
        if source_doc is not None:
            source_doc.Save()
            source_saved = True
            source_doc.Close(SaveChanges=0)
            source_closed = True

    result.output_path = target_norm
    result.used_existing_doc = bool(used_existing_doc)
    result.source_saved = bool(source_saved)
    result.source_closed = bool(source_closed)
    return result


__all__ = ["CommentSyncResult", "sync_comments_inplace", "sync_comments_to_copy", "sync_comments_to_doc"]
