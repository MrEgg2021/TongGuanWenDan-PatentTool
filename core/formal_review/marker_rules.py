from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from core.logging_utils import logger

from .models import ClaimItem, FormalReviewDocument
from .range_resolver import ResolverPolicy, resolve_issue_range
from .text_utils import normalize_marker_token
from .text_projection import ProjectionBundle
from .write_commands import MarkerNormalizationWritePlan, WriteCommand

_HEADING_NORMALIZE_RE = re.compile(r"\s+")
_IMPL_HEADING_KEYS = ("具体实施方式", "具体实施例", "实施例")
_MARKER_NUM_CHARS = "0-9０-９"
_MARKER_ALPHA_CHARS = "A-Za-zＡ-Ｚａ-ｚ"
_BRACKET_MARKER_AT_START_RE = re.compile(
    r"^[ \t\u3000]*[（(\[【][ \t\u3000]*([^）)\]】]{1,80}?)[ \t\u3000]*[）)\]】]"
)
_PLAIN_MARKER_AT_START_RE = re.compile(
    rf"^[ \t\u3000]*([{_MARKER_NUM_CHARS}]{{1,6}}[{_MARKER_ALPHA_CHARS}]?"
    rf"(?:[ \t\u3000]*(?:/|／|、|,|，|-|—)[ \t\u3000]*[{_MARKER_NUM_CHARS}]{{1,6}}[{_MARKER_ALPHA_CHARS}]?){{0,8}})"
)
_MARKER_PART_RE = re.compile(r"^\d{1,6}[A-Za-z]?$")


@dataclass(slots=True, frozen=True)
class _NameHit:
    start: int
    end: int
    name: str
    marker: str


def _normalize_heading_text(text: str) -> str:
    return _HEADING_NORMALIZE_RE.sub("", str(text or "").strip())


def _name_priority_rows(name_to_marker: dict[str, str]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for name, marker in dict(name_to_marker or {}).items():
        clean_name = str(name or "").strip()
        clean_marker = normalize_marker_token(marker)
        if not clean_name or not clean_marker:
            continue
        rows.append((clean_name, clean_marker))
    rows.sort(key=lambda item: (-len(item[0]), item[0]))
    return rows


def _find_non_overlapping_hits(text: str, rows: list[tuple[str, str]]) -> list[_NameHit]:
    if not text or not rows:
        return []

    occupied = [False] * len(text)
    accepted: list[_NameHit] = []
    for name, marker in rows:
        start = 0
        while True:
            idx = text.find(name, start)
            if idx < 0:
                break
            end = idx + len(name)
            if not any(occupied[idx:end]):
                accepted.append(_NameHit(start=idx, end=end, name=name, marker=marker))
                for pos in range(idx, end):
                    occupied[pos] = True
            start = idx + 1
    accepted.sort(key=lambda item: item.start)
    return accepted


def _expected_marker_fragment(section: str, marker: str) -> str:
    if section == "claims":
        return f"（{marker}）"
    return marker


def _normalize_marker_run_token(raw_token: str) -> tuple[str, bool]:
    source = unicodedata.normalize("NFKC", str(raw_token or ""))
    source = source.replace(" ", "").replace("\t", "").replace("\u3000", "")
    for sep in ("、", "，", ",", "／", "-", "—"):
        source = source.replace(sep, "/")
    source = re.sub(r"/{2,}", "/", source).strip("/")
    if not source:
        return "", False
    parts = [str(part or "").strip() for part in source.split("/") if str(part or "").strip()]
    if not parts:
        return "", False
    for part in parts:
        if _MARKER_PART_RE.match(part) is None:
            return "/".join(parts), False
    return normalize_marker_token("/".join(parts)), True


def _is_marker_run_prefix(fragment: str) -> bool:
    for ch in str(fragment or ""):
        if ch.isspace() or ch in (
            "\u3000",
            "（",
            "）",
            "(",
            ")",
            "[",
            "]",
            "【",
            "】",
            "/",
            "／",
            "、",
            ",",
            "，",
            "-",
            "—",
        ):
            continue
        return ch.isdigit()
    return False


def _detect_marker_action(section: str, suffix_text: str, marker: str) -> tuple[str, str, str]:
    expected_marker = normalize_marker_token(marker)
    expected = _expected_marker_fragment(section, expected_marker)
    if not suffix_text:
        return ("insert", "", expected)

    # Consume a "marker run" at the start of suffix (supports duplicates like （3）（3）, 33, 3 3, 3/3).
    fragments: list[str] = []
    tokens: list[str] = []
    remaining = str(suffix_text or "")
    while True:
        bracket_match = _BRACKET_MARKER_AT_START_RE.match(remaining)
        if bracket_match:
            frag = str(bracket_match.group(0) or "")
            tok, _valid = _normalize_marker_run_token(bracket_match.group(1))
            if not frag:
                break
            fragments.append(frag)
            tokens.append(tok)
            remaining = remaining[len(frag) :]
            continue
        plain_match = _PLAIN_MARKER_AT_START_RE.match(remaining)
        if plain_match:
            frag = str(plain_match.group(0) or "")
            if not _is_marker_run_prefix(frag):
                break
            tok, _valid = _normalize_marker_run_token(plain_match.group(1))
            if not frag:
                break
            fragments.append(frag)
            tokens.append(tok)
            remaining = remaining[len(frag) :]
            continue
        break

    if fragments:
        run = "".join(fragments)
        # Strict correctness: exact expected fragment only, and only a single fragment.
        if len(fragments) == 1 and tokens and tokens[0] == expected_marker and run == expected:
            return ("correct", expected, expected)
        return ("replace", run, expected)

    return ("insert", "", expected)


def _safe_int(value, default: int | None = 0) -> int | None:
    try:
        return int(value)
    except Exception:
        if default is None:
            return None
        try:
            return int(default)
        except Exception:
            return None


def _map_local_to_word(local_index: int, segments: Iterable[object]) -> int | None:
    target = _safe_int(local_index)
    for seg in list(segments or []):
        local_start = _safe_int(getattr(seg, "local_start", 0))
        local_end = _safe_int(getattr(seg, "local_end", 0))
        word_start = _safe_int(getattr(seg, "word_range_start", 0))
        if target < local_start or target > local_end:
            continue
        if local_start <= target < local_end:
            return int(word_start + (target - local_start))
        if target == local_end:
            return int(word_start + (local_end - local_start))
    return None


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


def _sanitize_word_text(raw_text: str) -> str:
    sanitized, _start_map, _end_map = _sanitize_word_text_with_map(str(raw_text or ""), 0)
    return str(sanitized or "")


def _read_range_text(doc, start: int, length: int) -> str:
    if doc is None:
        return ""
    base = int(start)
    want = max(0, int(length))
    if want <= 0:
        return ""
    # Try progressively smaller reads to avoid COM boundary errors.
    for step in (want, min(32, want), min(16, want), min(8, want)):
        try:
            rng = doc.Range(int(base), int(base + step))
            return str(getattr(rng, "Text", "") or "")
        except Exception:
            continue
    return ""


def _has_insert_revision_with_text(doc, start: int, length: int, expected_text: str) -> bool:
    if doc is None:
        return False
    expected = re.sub(r"\s+", "", str(expected_text or ""))
    if not expected:
        return False
    base = int(start)
    span = max(8, int(length), len(expected) + 8)
    try:
        rng = doc.Range(int(base), int(base + span))
        revs = getattr(rng, "Revisions", None)
        if revs is None:
            return False
        total = int(getattr(revs, "Count", 0) or 0)
    except Exception:
        return False
    for idx in range(1, total + 1):
        try:
            rev = revs(idx)
            # wdRevisionInsert == 1. Keep compatibility when Type is unavailable.
            rev_type = int(getattr(rev, "Type", 0) or 0)
            if rev_type not in (0, 1):
                continue
            rev_text = str(getattr(getattr(rev, "Range", None), "Text", "") or "")
        except Exception:
            continue
        sanitized, _start_map, _end_map = _sanitize_word_text_with_map(rev_text, 0)
        compact = re.sub(r"\s+", "", str(sanitized or ""))
        if compact and expected in compact:
            return True
    return False


def _has_any_revision(doc, start: int, length: int) -> bool:
    if doc is None:
        return False
    base = int(start)
    span = max(8, int(length))
    try:
        rng = doc.Range(int(base), int(base + span))
        revs = getattr(rng, "Revisions", None)
        if revs is None:
            return False
        total = int(getattr(revs, "Count", 0) or 0)
    except Exception:
        return False
    return bool(total > 0)


def _looks_like_revision_applied(
    *,
    doc,
    name_end: int,
    suffix_text: str,
    old_fragment: str,
    replacement: str,
) -> bool:
    old_compact = re.sub(r"\s+", "", str(old_fragment or ""))
    new_compact = re.sub(r"\s+", "", str(replacement or ""))
    suffix_compact = re.sub(r"\s+", "", str(suffix_text or ""))
    if not old_compact or not new_compact or not suffix_compact:
        return False
    # If target marker already leads the suffix and Word keeps revisions around this range,
    # treat as already applied to avoid repeat planning on subsequent runs.
    if suffix_compact.startswith(new_compact) and _has_any_revision(doc, int(name_end), 64):
        return True
    if not suffix_compact.startswith(old_compact):
        return False
    # Typical revision view after replacement: old+new may coexist at the same anchor.
    # When an insertion revision containing the replacement exists nearby, treat it as already handled.
    if not _has_insert_revision_with_text(doc, int(name_end), 64, str(replacement or "")):
        return False
    tail = suffix_compact[len(old_compact) :]
    return bool(tail.startswith(new_compact) or new_compact in tail[: max(16, len(new_compact) + 4)])


def _build_issue_like(
    *,
    section: str,
    claim_num: int | None,
    span_start: int,
    span_end: int,
    expected_hit: str,
    source_text: str,
):
    pre = str(source_text[max(0, int(span_start) - 10) : int(span_start)] or "")
    post = str(source_text[int(span_end) : int(span_end) + 10] or "")

    class _IssueLike:
        pass

    issue = _IssueLike()
    issue.section = str(section or "")
    issue.claim_num = claim_num
    issue.span_start = int(span_start)
    issue.span_end = int(span_end)
    issue.snippet = ""
    issue.rule_id = "marker.normalization"
    issue.issue_id = f"marker:{issue.section}:{claim_num or 0}:{span_start}:{span_end}"
    issue.anchor = {"expected_hit": str(expected_hit or ""), "pre_context": pre, "post_context": post}
    return issue


def _word_range_matches_name(doc, start: int, end: int, expected_name: str) -> bool:
    if doc is None:
        return False
    try:
        raw = str(getattr(doc.Range(int(start), int(end)), "Text", "") or "")
    except Exception:
        return False
    actual = _sanitize_word_text(raw)
    expected = _sanitize_word_text(str(expected_name or ""))
    return bool(expected and actual == expected)


def _rescue_claim_name_word_range(
    doc,
    *,
    approx_start: int,
    approx_end: int,
    expected_name: str,
) -> tuple[int, int] | None:
    if doc is None:
        return None
    expected = _sanitize_word_text(str(expected_name or ""))
    if not expected:
        return None

    anchor = max(0, int(approx_start))
    expected_len = int(len(expected))
    window_before = max(24, expected_len * 3)
    window_after = max(64, expected_len * 6)
    window_start = max(0, int(anchor - window_before))
    window_size = int(window_before + window_after)
    raw = _read_range_text(doc, int(window_start), int(window_size))
    if not raw:
        return None
    sanitized, start_map, end_map = _sanitize_word_text_with_map(raw, int(window_start))
    if not sanitized:
        return None

    candidates: list[tuple[int, int, int]] = []
    find_from = 0
    while True:
        idx = int(sanitized.find(expected, int(find_from)))
        if idx < 0:
            break
        end_idx = int(idx + expected_len - 1)
        if 0 <= idx < len(start_map) and 0 <= end_idx < len(end_map):
            start = int(start_map[idx])
            end = int(end_map[end_idx])
            distance = abs(int(start) - int(approx_start)) + abs(int(end) - int(approx_end))
            candidates.append((distance, start, end))
        find_from = int(idx + 1)

    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0])
    _score, start, end = candidates[0]
    return int(start), int(end)


def _description_scope_start(segments: list[object]) -> int | None:
    for index, seg in enumerate(list(segments or [])):
        raw_text = _normalize_heading_text(getattr(seg, "raw_text", ""))
        if raw_text not in _IMPL_HEADING_KEYS:
            continue
        seg_end = _safe_int(getattr(seg, "local_end", 0))
        return int(seg_end + (1 if index < len(segments) - 1 else 0))
    return None


def _bump_claim_resolve_path_counter(plan: MarkerNormalizationWritePlan, level: str) -> None:
    resolved = str(level or "").strip().lower()
    if resolved in {"projection", "occurrence", "context"}:
        plan.claim_resolve_projection_count += 1
        return
    if resolved == "word_find_com":
        plan.claim_resolve_word_find_com_count += 1
        return
    if resolved in {"word_find", "word_find_legacy"}:
        plan.claim_resolve_word_find_legacy_count += 1


def _append_commands_for_claim(
    claim: ClaimItem,
    *,
    rows: list[tuple[str, str]],
    plan: MarkerNormalizationWritePlan,
    cmd_seq: list[int],
) -> None:
    text = str(getattr(claim, "text", "") or "")
    if not text:
        return

    anchor_start = getattr(claim, "anchor_start", None)
    hits = _find_non_overlapping_hits(text, rows)
    if anchor_start is None:
        plan.skipped_unsupported_count += len(hits)
        return

    base = _safe_int(anchor_start, 0)
    for hit in hits:
        plan.candidate_claims += 1
        suffix = text[hit.end :]
        status, old_fragment, replacement = _detect_marker_action("claims", suffix, hit.marker)
        if status == "correct":
            plan.skipped_correct_count += 1
            continue
        start_local = int(hit.end)
        end_local = int(hit.end + len(old_fragment))
        cmd_seq[0] += 1
        plan.commands.append(
            WriteCommand(
                cmd_id=f"marker-cmd-{cmd_seq[0]}",
                action_kind="insert_after_name" if status == "insert" else "replace_marker_after_name",
                section="claims",
                claim_num=_safe_int(getattr(claim, "num", None), 0),
                name=hit.name,
                marker=hit.marker,
                local_start=start_local,
                local_end=end_local,
                word_start=int(base + start_local),
                word_end=int(base + end_local),
                expected_old_fragment=str(old_fragment or ""),
                replacement_text=str(replacement or ""),
            )
        )
        if status == "insert":
            plan.inserted_count += 1
        else:
            plan.replaced_count += 1


def _append_commands_for_description(
    description_text: str,
    *,
    rows: list[tuple[str, str]],
    description_segments: list[object],
    plan: MarkerNormalizationWritePlan,
    cmd_seq: list[int],
) -> None:
    if not description_text:
        return

    scope_start = _description_scope_start(description_segments)
    if scope_start is None:
        plan.description_scope_found = False
        plan.errors.append("说明书未找到“具体实施方式/具体实施例”标题，说明书部分已阻断。")
        return

    hits = _find_non_overlapping_hits(description_text, rows)
    for hit in hits:
        if hit.start < scope_start:
            continue
        plan.candidate_description += 1
        suffix = description_text[hit.end :]
        status, old_fragment, replacement = _detect_marker_action("description", suffix, hit.marker)
        if status == "correct":
            plan.skipped_correct_count += 1
            continue
        start_local = int(hit.end)
        end_local = int(hit.end + len(old_fragment))
        word_start = _map_local_to_word(start_local, description_segments)
        word_end = _map_local_to_word(end_local, description_segments)
        if word_start is None or word_end is None:
            plan.warnings.append(
                f"说明书命中“{hit.name}”无法映射到 Word 坐标，已跳过（local={start_local}:{end_local}）。"
            )
            plan.skipped_unsupported_count += 1
            continue
        cmd_seq[0] += 1
        plan.commands.append(
            WriteCommand(
                cmd_id=f"marker-cmd-{cmd_seq[0]}",
                action_kind="insert_after_name" if status == "insert" else "replace_marker_after_name",
                section="description",
                claim_num=None,
                name=hit.name,
                marker=hit.marker,
                local_start=start_local,
                local_end=end_local,
                word_start=int(word_start),
                word_end=int(word_end),
                expected_old_fragment=str(old_fragment or ""),
                replacement_text=str(replacement or ""),
            )
        )
        if status == "insert":
            plan.inserted_count += 1
        else:
            plan.replaced_count += 1


def _append_commands_for_claim_word(
    doc,
    projections: ProjectionBundle,
    claim: ClaimItem,
    *,
    rows: list[tuple[str, str]],
    plan: MarkerNormalizationWritePlan,
    cmd_seq: list[int],
) -> None:
    text = str(getattr(claim, "text", "") or "")
    if not text:
        return

    hits = _find_non_overlapping_hits(text, rows)
    for hit in hits:
        plan.candidate_claims += 1
        local_status, _local_old_fragment, _local_replacement = _detect_marker_action(
            "claims", text[hit.end :], hit.marker
        )
        if local_status == "correct":
            plan.skipped_correct_count += 1
            continue
        issue_like = _build_issue_like(
            section="claims",
            claim_num=_safe_int(getattr(claim, "num", None), 0),
            span_start=int(hit.start),
            span_end=int(hit.end),
            expected_hit=str(hit.name or ""),
            source_text=text,
        )
        resolved_strict = resolve_issue_range(
            doc,
            issue_like,
            projections,
            strict=True,
            allow_legacy_fallback=False,
            policy=ResolverPolicy(
                strict=True,
                allow_legacy_fallback=False,
                require_com_ready=False,
            ),
        )
        resolved = resolved_strict
        if not bool(getattr(resolved_strict, "ok", False)):
            plan.claim_resolve_strict_failed_count += 1
            resolved_loose = resolve_issue_range(
                doc,
                issue_like,
                projections,
                strict=False,
                allow_legacy_fallback=False,
                policy=ResolverPolicy(
                    strict=False,
                    allow_legacy_fallback=False,
                    require_com_ready=False,
                ),
            )
            if bool(getattr(resolved_loose, "ok", False)):
                loose_actual = _sanitize_word_text(str(getattr(resolved_loose, "actual", "") or ""))
                expected_name = _sanitize_word_text(str(hit.name or ""))
                if loose_actual and expected_name and loose_actual != expected_name:
                    plan.warnings.append(
                        "权利要求"
                        f"{_safe_int(getattr(claim, 'num', None), 0)}命中“{hit.name}”loose定位文本不一致，已跳过"
                        f"（strict:{getattr(resolved_strict, 'reason_code', '')}; actual:{loose_actual}）"
                    )
                    plan.skipped_unsupported_count += 1
                    continue
                resolved = resolved_loose
                plan.claim_resolve_loose_rescued_count += 1
                logger.debug(
                    "[formal_review][marker_plan] claims_locator_rescued claim=%s name=%s strict_reason=%s loose_level=%s",
                    _safe_int(getattr(claim, "num", None), 0),
                    str(hit.name or ""),
                    str(getattr(resolved_strict, "reason_code", "") or ""),
                    str(getattr(resolved_loose, "level", "") or ""),
                )
            else:
                resolved = resolved_loose
        if not bool(getattr(resolved, "ok", False)):
            plan.warnings.append(
                f"权利要求{_safe_int(getattr(claim, 'num', None), 0)}命中“{hit.name}”无法安全定位，已跳过（strict:{getattr(resolved_strict, 'reason_code', '')}; loose:{getattr(resolved, 'reason_code', '')}）。"
            )
            plan.skipped_unsupported_count += 1
            continue
        _bump_claim_resolve_path_counter(plan, str(getattr(resolved, "level", "") or ""))
        name_start = _safe_int(getattr(resolved, "start", None), None)
        name_end = _safe_int(getattr(resolved, "end", None), None)
        if name_start is None or name_end is None or int(name_end) <= int(name_start):
            plan.skipped_unsupported_count += 1
            continue

        if not _word_range_matches_name(doc, int(name_start), int(name_end), str(hit.name or "")):
            plan.claim_name_exact_check_failed_count += 1
            rescued = _rescue_claim_name_word_range(
                doc,
                approx_start=int(name_start),
                approx_end=int(name_end),
                expected_name=str(hit.name or ""),
            )
            if rescued is not None and _word_range_matches_name(
                doc, int(rescued[0]), int(rescued[1]), str(hit.name or "")
            ):
                name_start = int(rescued[0])
                name_end = int(rescued[1])
                plan.claim_name_nearby_rescued_count += 1
            else:
                plan.claim_name_unsafe_continue_count += 1
                plan.skipped_unsupported_count += 1
                plan.warnings.append(
                    "权利要求"
                    f"{_safe_int(getattr(claim, 'num', None), 0)}命中“{hit.name}”名称范围未能恢复到完整匹配，"
                    "已跳过该命令（避免中间插入风险）。"
                )

                continue

        suffix_raw = _read_range_text(doc, int(name_end), 64)
        suffix_text, _start_map, end_map = _sanitize_word_text_with_map(suffix_raw, int(name_end))

        status, old_fragment_sanitized, replacement = _detect_marker_action("claims", suffix_text, hit.marker)
        if status == "correct":
            plan.skipped_correct_count += 1
            continue
        if status != "insert" and _looks_like_revision_applied(
            doc=doc,
            name_end=int(name_end),
            suffix_text=str(suffix_text or ""),
            old_fragment=str(old_fragment_sanitized or ""),
            replacement=str(replacement or ""),
        ):
            plan.skipped_correct_count += 1
            continue

        start_local = int(hit.end)
        end_local = int(hit.end + len(old_fragment_sanitized))
        word_start = int(name_end)
        word_end = int(name_end)
        expected_old_fragment = ""
        if status != "insert":
            frag_len = len(old_fragment_sanitized)
            if frag_len <= 0 or frag_len - 1 >= len(end_map):
                plan.warnings.append(f"权利要求{claim.num}后缀映射失败，已跳过（name={hit.name}）。")
                plan.skipped_unsupported_count += 1
                continue
            word_end = int(end_map[frag_len - 1])
            try:
                expected_old_fragment = str(getattr(doc.Range(int(word_start), int(word_end)), "Text", "") or "")
            except Exception:
                expected_old_fragment = ""

        cmd_seq[0] += 1
        plan.commands.append(
            WriteCommand(
                cmd_id=f"marker-cmd-{cmd_seq[0]}",
                action_kind="insert_after_name" if status == "insert" else "replace_marker_after_name",
                section="claims",
                claim_num=_safe_int(getattr(claim, "num", None), 0),
                name=hit.name,
                marker=hit.marker,
                local_start=start_local,
                local_end=end_local,
                word_start=int(word_start),
                word_end=int(word_end),
                expected_old_fragment=str(expected_old_fragment or ""),
                replacement_text=str(replacement or ""),
            )
        )
        if status == "insert":
            plan.inserted_count += 1
        else:
            plan.replaced_count += 1


def _append_commands_for_description_word(
    doc,
    projections: ProjectionBundle,
    description_text: str,
    *,
    rows: list[tuple[str, str]],
    description_segments: list[object],
    plan: MarkerNormalizationWritePlan,
    cmd_seq: list[int],
) -> None:
    if not description_text:
        return

    scope_start = _description_scope_start(description_segments)
    if scope_start is None:
        plan.description_scope_found = False
        plan.errors.append("说明书未找到“具体实施方式/具体实施例”标题，说明书部分已阻断。")
        return

    hits = _find_non_overlapping_hits(description_text, rows)
    for hit in hits:
        if hit.start < scope_start:
            continue
        plan.candidate_description += 1
        local_status, _local_old_fragment, _local_replacement = _detect_marker_action(
            "description", description_text[hit.end :], hit.marker
        )
        if local_status == "correct":
            plan.skipped_correct_count += 1
            continue
        issue_like = _build_issue_like(
            section="description",
            claim_num=None,
            span_start=int(hit.start),
            span_end=int(hit.end),
            expected_hit=str(hit.name or ""),
            source_text=description_text,
        )
        resolved = resolve_issue_range(
            doc,
            issue_like,
            projections,
            strict=True,
            allow_legacy_fallback=False,
            policy=ResolverPolicy(
                strict=True,
                allow_legacy_fallback=False,
                require_com_ready=False,
            ),
        )
        if not bool(getattr(resolved, "ok", False)):
            plan.warnings.append(
                f"说明书命中“{hit.name}”无法安全定位，已跳过（{getattr(resolved, 'reason_code', '')}）。"
            )
            plan.skipped_unsupported_count += 1
            continue
        name_end = _safe_int(getattr(resolved, "end", None), None)
        if name_end is None:
            plan.skipped_unsupported_count += 1
            continue

        suffix_raw = _read_range_text(doc, int(name_end), 64)
        suffix_text, _start_map, end_map = _sanitize_word_text_with_map(suffix_raw, int(name_end))
        status, old_fragment_sanitized, replacement = _detect_marker_action("description", suffix_text, hit.marker)
        if status == "correct":
            plan.skipped_correct_count += 1
            continue
        if status != "insert" and _looks_like_revision_applied(
            doc=doc,
            name_end=int(name_end),
            suffix_text=str(suffix_text or ""),
            old_fragment=str(old_fragment_sanitized or ""),
            replacement=str(replacement or ""),
        ):
            plan.skipped_correct_count += 1
            continue

        start_local = int(hit.end)
        end_local = int(hit.end + len(old_fragment_sanitized))
        word_start = int(name_end)
        word_end = int(name_end)
        expected_old_fragment = ""
        if status != "insert":
            frag_len = len(old_fragment_sanitized)
            if frag_len <= 0 or frag_len - 1 >= len(end_map):
                plan.warnings.append(f"说明书后缀映射失败，已跳过（name={hit.name}）。")
                plan.skipped_unsupported_count += 1
                continue
            word_end = int(end_map[frag_len - 1])
            try:
                expected_old_fragment = str(getattr(doc.Range(int(word_start), int(word_end)), "Text", "") or "")
            except Exception:
                expected_old_fragment = ""

        cmd_seq[0] += 1
        plan.commands.append(
            WriteCommand(
                cmd_id=f"marker-cmd-{cmd_seq[0]}",
                action_kind="insert_after_name" if status == "insert" else "replace_marker_after_name",
                section="description",
                claim_num=None,
                name=hit.name,
                marker=hit.marker,
                local_start=start_local,
                local_end=end_local,
                word_start=int(word_start),
                word_end=int(word_end),
                expected_old_fragment=str(expected_old_fragment or ""),
                replacement_text=str(replacement or ""),
            )
        )
        if status == "insert":
            plan.inserted_count += 1
        else:
            plan.replaced_count += 1


def build_marker_normalization_write_plan(
    *,
    document: FormalReviewDocument,
    name_to_marker: dict[str, str],
    description_segments: list[object] | None,
    doc: object | None = None,
    projections: ProjectionBundle | None = None,
) -> MarkerNormalizationWritePlan:
    started = time.perf_counter()
    plan = MarkerNormalizationWritePlan()
    rows = _name_priority_rows(name_to_marker)
    if not rows:
        plan.errors.append("标号说明为空或无可用映射。")
        return plan

    cmd_seq = [0]
    use_word = doc is not None and projections is not None
    if use_word:
        logger.debug("[formal_review][marker_plan] build using resolver-based word ranges")
    for claim in list(getattr(document, "claims", []) or []):
        if use_word:
            _append_commands_for_claim_word(doc, projections, claim, rows=rows, plan=plan, cmd_seq=cmd_seq)
        else:
            _append_commands_for_claim(claim, rows=rows, plan=plan, cmd_seq=cmd_seq)

    description_text = str(getattr(document, "description", "") or "")
    if use_word:
        _append_commands_for_description_word(
            doc,
            projections,
            description_text,
            rows=rows,
            description_segments=list(description_segments or []),
            plan=plan,
            cmd_seq=cmd_seq,
        )
    else:
        _append_commands_for_description(
            description_text,
            rows=rows,
            description_segments=list(description_segments or []),
            plan=plan,
            cmd_seq=cmd_seq,
        )

    # Deduplicate commands and block on conflicting replacements for the same Word range.
    if plan.commands:
        seen: set[tuple[str, int | None, int, int, str]] = set()
        repl_by_range: dict[tuple[str, int | None, int, int], str] = {}
        deduped: list[WriteCommand] = []
        dropped = 0
        for cmd in list(plan.commands):
            key = (str(cmd.section), cmd.claim_num, int(cmd.word_start), int(cmd.word_end), str(cmd.replacement_text))
            range_key = (str(cmd.section), cmd.claim_num, int(cmd.word_start), int(cmd.word_end))
            existing_repl = repl_by_range.get(range_key)
            if existing_repl is None:
                repl_by_range[range_key] = str(cmd.replacement_text)
            elif str(cmd.replacement_text) != str(existing_repl):
                plan.errors.append(
                    f"同一位置存在冲突修订：{range_key} -> {existing_repl!r} vs {str(cmd.replacement_text)!r}"
                )
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            deduped.append(cmd)
        if dropped:
            plan.warnings.append(f"已去重重复标号修订命令 {dropped} 条。")
            logger.debug("[formal_review][marker_plan] dedup_commands: dropped=%s kept=%s", int(dropped), int(len(deduped)))
        plan.commands = deduped
        plan.inserted_count = len([c for c in deduped if str(c.action_kind) == "insert_after_name"])
        plan.replaced_count = len([c for c in deduped if str(c.action_kind) != "insert_after_name"])

    plan.commands.sort(key=lambda item: int(item.word_start), reverse=True)
    elapsed_ms = int((time.perf_counter() - float(started)) * 1000)
    logger.info(
        "[formal_review][marker_plan] summary commands=%s claims_candidates=%s desc_candidates=%s strict_failed=%s loose_rescued=%s projection=%s word_find_com=%s word_find_legacy=%s skipped_correct=%s skipped_unsupported=%s warnings_count=%s elapsed_ms=%s",
        int(getattr(plan, "command_count", 0) or 0),
        int(getattr(plan, "candidate_claims", 0) or 0),
        int(getattr(plan, "candidate_description", 0) or 0),
        int(getattr(plan, "claim_resolve_strict_failed_count", 0) or 0),
        int(getattr(plan, "claim_resolve_loose_rescued_count", 0) or 0),
        int(getattr(plan, "claim_resolve_projection_count", 0) or 0),
        int(getattr(plan, "claim_resolve_word_find_com_count", 0) or 0),
        int(getattr(plan, "claim_resolve_word_find_legacy_count", 0) or 0),
        int(getattr(plan, "skipped_correct_count", 0) or 0),
        int(getattr(plan, "skipped_unsupported_count", 0) or 0),
        int(len(list(getattr(plan, "warnings", []) or []))),
        int(elapsed_ms),
    )
    return plan
