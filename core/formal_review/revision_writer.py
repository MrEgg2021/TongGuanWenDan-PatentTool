from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .annotator import apply_comments_to_doc, build_comment_plan
from .models import Issue

_SUPPORTED_WORD_SUFFIXES = {".doc", ".docx"}


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except Exception:
        return default


def _normalized_word_suffix(path: str) -> str:
    return str(Path(str(path or "").strip()).suffix or "").lower()


def _to_word_text(text: str) -> str:
    source = str(text or "")
    return source.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r")


def _section_label(section: str) -> str:
    return {
        "claims": "权利要求书",
        "description": "说明书",
        "abstract": "摘要",
        "drawings": "附图说明",
    }.get(str(section or ""), str(section or ""))


def _segment_comment_text(segment: dict[str, Any], reason: str) -> str:
    section = str(segment.get("section") or "")
    claim_num = _safe_int(segment.get("claim_num"), None)
    location = f"@{_section_label(section)}"
    if claim_num is not None:
        location = f"{location} @权利要求{claim_num}"
    edited_display_text = str(segment.get("edited_display_text") or "").strip()
    if len(edited_display_text) > 400:
        edited_display_text = f"{edited_display_text[:400]}..."
    return f"[未能直接修改，已添加批注] {reason}\n{location}\n建议修改：{edited_display_text}"


def _add_comment_to_doc(doc, *, start: int | None, end: int | None, text: str) -> bool:
    target_range = None
    try:
        if start is not None and end is not None:
            target_range = doc.Range(int(start), int(end))
    except Exception:
        target_range = None
    if target_range is None:
        try:
            target_range = doc.Paragraphs(1).Range
        except Exception:
            return False
    try:
        doc.Comments.Add(target_range, text)
        return True
    except Exception:
        return False


def export_revised_annotated_copy(
    word_engine,
    *,
    source_path: str,
    output_path: str,
    edited_segments: list[dict[str, Any]],
    issues: list[Issue],
    author_name: str,
) -> dict[str, int]:
    source_file = str(source_path or "").strip()
    output_file = str(output_path or "").strip()
    source_suffix = _normalized_word_suffix(source_file)
    output_suffix = _normalized_word_suffix(output_file)
    if not source_file or not output_file:
        raise ValueError("source_path/output_path 不能为空")
    if str(Path(source_file).resolve()) == str(Path(output_file).resolve()):
        raise ValueError("导出路径不能与源文件相同")

    if source_suffix not in _SUPPORTED_WORD_SUFFIXES:
        raise ValueError(f"Unsupported source extension: {source_suffix or '(none)'}")
    if output_suffix not in _SUPPORTED_WORD_SUFFIXES:
        raise ValueError(f"Unsupported output extension: {output_suffix or '(none)'}")
    if source_suffix != output_suffix:
        raise ValueError(f"Output extension must match source extension: {source_suffix}")

    target = Path(output_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, output_file)

    comment_plan = build_comment_plan(list(issues or []))
    revision_written = 0
    downgraded_segments = 0
    downgraded_comment_written = 0
    issue_comment_stats = {"written": 0, "skipped": 0}

    original_user_name = None
    original_initials = None

    doc2 = word_engine.app.Documents.Open(
        FileName=output_path,
        ReadOnly=False,
        Visible=False,
        AddToRecentFiles=False,
    )
    word_engine.doc = doc2

    try:
        app = word_engine.app
        original_user_name = str(getattr(app, "UserName", "") or "")
        original_initials = str(getattr(app, "UserInitials", "") or "")
        custom_author = str(author_name or "").strip()
        if custom_author:
            app.UserName = custom_author
            app.UserInitials = custom_author[:2]
        try:
            doc2.TrackRevisions = True
        except Exception:
            pass

        writable_segments: list[dict[str, Any]] = []
        downgraded_rows: list[tuple[dict[str, Any], str]] = []
        for row in list(edited_segments or []):
            segment = dict(row or {})
            start = _safe_int(segment.get("word_start"), None)
            end = _safe_int(segment.get("word_end"), None)
            edited_word_text = str(segment.get("edited_word_text") or "")
            original_word_text = str(segment.get("original_word_text") or "")
            reason = str(segment.get("downgrade_reason") or "").strip()
            if reason:
                downgraded_rows.append((segment, reason))
                continue
            if start is None or end is None or end < start:
                downgraded_rows.append((segment, "Word 定位区间无效"))
                continue
            if edited_word_text == original_word_text:
                continue
            writable_segments.append(segment)

        for segment in sorted(writable_segments, key=lambda item: int(item.get("word_start") or 0), reverse=True):
            start = int(segment.get("word_start"))
            end = int(segment.get("word_end"))
            replacement = _to_word_text(str(segment.get("edited_word_text") or ""))
            try:
                target_range = doc2.Range(start, end)
                target_range.Text = replacement
                revision_written += 1
            except Exception:
                downgraded_rows.append((segment, "Word 回写失败，已降级为批注"))

        for segment, reason in downgraded_rows:
            downgraded_segments += 1
            ok = _add_comment_to_doc(
                doc2,
                start=_safe_int(segment.get("word_start"), None),
                end=_safe_int(segment.get("word_end"), None),
                text=_segment_comment_text(segment, reason),
            )
            if ok:
                downgraded_comment_written += 1

        issue_comment_stats = apply_comments_to_doc(
            doc2,
            issues=list(issues or []),
            comment_plan=comment_plan,
        )
        doc2.Save()
    finally:
        try:
            if original_user_name is not None:
                word_engine.app.UserName = original_user_name
            if original_initials is not None:
                word_engine.app.UserInitials = original_initials
        except Exception:
            pass
        try:
            doc2.Close(False)
        except Exception:
            pass
        try:
            if getattr(word_engine, "doc", None) is doc2:
                word_engine.doc = None
        except Exception:
            pass

    return {
        "revision_written": revision_written,
        "downgraded_segments": downgraded_segments,
        "downgraded_comment_written": downgraded_comment_written,
        "comment_written": int(issue_comment_stats.get("written", 0)),
        "comment_skipped": int(issue_comment_stats.get("skipped", 0)),
    }
