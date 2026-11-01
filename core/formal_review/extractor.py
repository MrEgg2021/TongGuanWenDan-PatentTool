from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from core.document_parser.sections_mixin import SectionsMixin
from core.logging_utils import logger

from .claim_refs import parse_claim_references
from .edit_model import EditableSegment, TokenSpan
from .models import ClaimItem, FormalReviewDocument
from .text_projection import ParagraphProjection, ProjectionBundle, SectionProjection
from .text_utils import count_effective_chars, extract_figure_markers

_LIST_STRING_DIGIT_RE = re.compile(r"(\d{1,4})")
_INLINE_OBJECT_CHAR = "\x01"
_CLAIM_NUMBER_PRIORITY = ("text_prefix_num", "list_string_num", "list_value_num")
_CLAIM_PREFIX_SEPARATORS = frozenset((".", "\uFF0E", "\u3002", "\u3001", "\uFF0C", ",", ")", "\uFF09"))
_CLAIM_PREFIX_IGNORABLE = frozenset(("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060", "\u200e", "\u200f"))


def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    return "".join(ch for ch in text if (ch in ("\t", "\n") or ord(ch) >= 0x20))


@dataclass(slots=True)
class TextAnchor:
    section: str
    claim_num: int | None
    word_range_start: int
    word_range_end: int | None = None
    raw_text: str = ""
    source: str = "paragraph"
    extra: dict[str, Any] = field(default_factory=dict)


class _SectionPlanProbe(SectionsMixin):
    pass


@dataclass(slots=True)
class _ParagraphChunk:
    plain_text: str
    display_text: str
    token_spans: list[TokenSpan]
    word_start: int
    word_end: int
    paragraph_index: int
    has_non_text: bool = False
    offset_map_start: list[int] = field(default_factory=list)
    offset_map_end: list[int] = field(default_factory=list)


def _safe_count(range_obj, attr_name: str) -> int:
    try:
        attr = getattr(range_obj, attr_name, None)
        return int(getattr(attr, "Count", 0) or 0)
    except Exception:
        return 0


def _is_claim_prefix_leading_ignorable(ch: str) -> bool:
    return bool(ch and (ch.isspace() or ch in _CLAIM_PREFIX_IGNORABLE))


def _normalize_claim_digit(ch: str) -> str | None:
    if not ch:
        return None
    normalized = unicodedata.normalize("NFKC", str(ch))
    if len(normalized) != 1:
        return None
    return normalized if normalized.isdigit() else None


def _parse_claim_prefix(text: str) -> tuple[int | None, int | None]:
    source = str(text or "")
    size = len(source)
    if size <= 0:
        return None, None

    idx = 0
    while idx < size and _is_claim_prefix_leading_ignorable(source[idx]):
        idx += 1
    if idx >= size:
        return None, None

    digits: list[str] = []
    while idx < size:
        digit = _normalize_claim_digit(source[idx])
        if digit is None:
            break
        digits.append(digit)
        idx += 1
        if len(digits) > 4:
            return None, None
    if not digits:
        return None, None

    try:
        claim_num = int("".join(digits))
    except Exception:
        return None, None
    if claim_num <= 0 or claim_num > 9999:
        return None, None

    body_start = idx
    while body_start < size and source[body_start].isspace():
        body_start += 1
    if body_start < size and source[body_start] in _CLAIM_PREFIX_SEPARATORS:
        body_start += 1
        while body_start < size and source[body_start].isspace():
            body_start += 1
    return int(claim_num), int(body_start)


def _looks_like_claim_prefix_hint(text: str) -> bool:
    source = str(text or "")
    if not source:
        return False
    idx = 0
    size = len(source)
    while idx < size and _is_claim_prefix_leading_ignorable(source[idx]):
        idx += 1
    if idx >= size:
        return False
    return _normalize_claim_digit(source[idx]) is not None


def _merge_abs_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    rows = sorted(
        [
            (int(start), int(end))
            for start, end in list(ranges or [])
            if int(end) > int(start)
        ],
        key=lambda item: (item[0], item[1]),
    )
    if not rows:
        return []

    merged: list[tuple[int, int]] = [rows[0]]
    for start, end in rows[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _collect_non_text_ranges(range_obj) -> list[tuple[int, int]]:
    try:
        paragraph_start = int(getattr(range_obj, "Start", 0) or 0)
        paragraph_end = int(getattr(range_obj, "End", paragraph_start) or paragraph_start)
    except Exception:
        return []

    rows: list[tuple[int, int]] = []
    for attr_name in ("InlineShapes", "OMaths"):
        collection = getattr(range_obj, attr_name, None)
        count = _safe_count(range_obj, attr_name)
        if collection is None or count <= 0:
            continue
        for idx in range(1, count + 1):
            try:
                item = collection(idx)
                item_range = getattr(item, "Range", None)
                if item_range is None:
                    continue
                start = int(getattr(item_range, "Start", 0) or 0)
                end = int(getattr(item_range, "End", start) or start)
            except Exception:
                continue
            if end <= start:
                continue
            start = max(start, paragraph_start)
            end = min(end, paragraph_end)
            if end > start:
                rows.append((start, end))
    return _merge_abs_ranges(rows)


def _extract_paragraph_text_and_tokens(
    range_obj,
    *,
    section: str,
    paragraph_index: int,
    paragraph_start: int,
) -> tuple[str, str, list[TokenSpan], bool, list[int], list[int]]:
    source = str(getattr(range_obj, "Text", "") or "")
    non_text_ranges = _collect_non_text_ranges(range_obj)
    plain_chars: list[str] = []
    plain_start_map: list[int] = []
    plain_end_map: list[int] = []

    token_spans: list[TokenSpan] = []
    display_parts: list[str] = []
    cursor = 0
    token_index = 1
    marker_chars = 0
    range_idx = 0
    pending_boundary_break = False
    in_non_text = False
    for index, ch in enumerate(source):
        absolute_pos = int(paragraph_start + index)
        while range_idx < len(non_text_ranges) and absolute_pos >= int(non_text_ranges[range_idx][1]):
            range_idx += 1
        now_non_text = (
            range_idx < len(non_text_ranges)
            and int(non_text_ranges[range_idx][0]) <= absolute_pos < int(non_text_ranges[range_idx][1])
        )
        if now_non_text:
            in_non_text = True
            if ch == _INLINE_OBJECT_CHAR:
                token = f"{{OBJ:{section}:{paragraph_index}:{token_index}}}"
                token_spans.append(
                    TokenSpan(
                        token=token,
                        kind="inline_object",
                        local_start=cursor,
                        local_end=cursor + len(token),
                    )
                )
                display_parts.append(token)
                cursor += len(token)
                token_index += 1
                marker_chars += 1
            continue
        if in_non_text:
            pending_boundary_break = True
            in_non_text = False

        if ch == _INLINE_OBJECT_CHAR:
            token = f"{{OBJ:{section}:{paragraph_index}:{token_index}}}"
            token_spans.append(
                TokenSpan(
                    token=token,
                    kind="inline_object",
                    local_start=cursor,
                    local_end=cursor + len(token),
                )
            )
            display_parts.append(token)
            cursor += len(token)
            token_index += 1
            marker_chars += 1
            continue
        if ch in ("\t", "\n") or ord(ch) >= 0x20:
            if pending_boundary_break and plain_chars and plain_chars[-1] != "\n":
                plain_chars.append("\n")
                plain_start_map.append(absolute_pos)
                plain_end_map.append(absolute_pos)
                display_parts.append("\n")
                cursor += 1
            pending_boundary_break = False

            absolute_start = absolute_pos
            absolute_end = int(absolute_start + 1)
            plain_chars.append(ch)
            plain_start_map.append(absolute_start)
            plain_end_map.append(absolute_end)
            display_parts.append(ch)
            cursor += 1

    plain_raw = "".join(plain_chars)
    left_trim = len(plain_raw) - len(plain_raw.lstrip())
    right_len = len(plain_raw.rstrip())
    if right_len < left_trim:
        right_len = left_trim
    plain_text = plain_raw[left_trim:right_len]
    offset_map_start = plain_start_map[left_trim:right_len]
    offset_map_end = plain_end_map[left_trim:right_len]

    display_text = "".join(display_parts).strip()
    non_text_total = max(marker_chars, _safe_count(range_obj, "InlineShapes"), _safe_count(range_obj, "OMaths"))
    while len(token_spans) < non_text_total:
        token = f"{{OBJ:{section}:{paragraph_index}:{token_index}}}"
        if display_text:
            display_text = f"{display_text} "
        start = len(display_text)
        display_text = f"{display_text}{token}"
        token_spans.append(
            TokenSpan(
                token=token,
                kind="inline_object",
                local_start=start,
                local_end=len(display_text),
            )
        )
        token_index += 1

    return plain_text, display_text, token_spans, non_text_total > 0, offset_map_start, offset_map_end


def _extract_claim_num_from_list_format_sources(range_obj) -> tuple[int | None, int | None]:
    list_format = getattr(range_obj, "ListFormat", None)
    if list_format is None:
        return None, None

    list_value_num: int | None = None
    try:
        list_value = getattr(list_format, "ListValue", None)
        if list_value is not None:
            parsed_value = int(list_value)
            if 1 <= parsed_value <= 9999:
                list_value_num = parsed_value
    except Exception:
        pass

    try:
        list_string = str(getattr(list_format, "ListString", "") or "")
    except Exception:
        list_string = ""
    if not list_string:
        return None, list_value_num

    normalized = unicodedata.normalize("NFKC", list_string)
    match = _LIST_STRING_DIGIT_RE.search(normalized)
    if not match:
        return None, list_value_num
    try:
        parsed_value = int(match.group(1))
    except Exception:
        return None, list_value_num
    if parsed_value <= 0:
        return None, list_value_num
    return parsed_value, list_value_num


def _extract_claim_number_candidates(range_obj, plain_text: str) -> dict[str, int | None]:
    text_prefix_num, text_prefix_body_start = _parse_claim_prefix(str(plain_text or ""))

    list_string_num, list_value_num = _extract_claim_num_from_list_format_sources(range_obj)
    return {
        "text_prefix_num": int(text_prefix_num) if text_prefix_num is not None else None,
        "text_prefix_body_start": int(text_prefix_body_start) if text_prefix_body_start is not None else None,
        "list_string_num": int(list_string_num) if list_string_num is not None else None,
        "list_value_num": int(list_value_num) if list_value_num is not None else None,
    }


def _select_claim_num_candidate(
    candidates: dict[str, int | None],
    current_claim_num: int | None,
) -> tuple[int | None, str | None]:
    if current_claim_num is None:
        for source in _CLAIM_NUMBER_PRIORITY:
            value = candidates.get(source)
            if value is not None:
                return int(value), source
        return None, None

    current = int(current_claim_num)
    for source in _CLAIM_NUMBER_PRIORITY:
        value = candidates.get(source)
        if value is not None and int(value) > current:
            return int(value), source
    return None, None


def _claim_body_and_prefix(
    plain_text: str,
    display_text: str,
    offset_map_start: list[int],
    offset_map_end: list[int],
    *,
    body_start_idx: int | None = None,
) -> tuple[str, str, str, list[int], list[int]]:
    plain = str(plain_text or "")
    display = str(display_text or "")

    parsed_num, parsed_body_start = _parse_claim_prefix(plain)
    if body_start_idx is None:
        if parsed_num is None or parsed_body_start is None:
            return "", plain.strip(), display.strip(), list(offset_map_start or []), list(offset_map_end or [])
        body_start_idx = int(parsed_body_start)

    start_idx = max(0, min(int(body_start_idx), len(plain)))
    body_raw = str(plain[start_idx:] or "")
    body_left_trim = len(body_raw) - len(body_raw.lstrip())
    body_right_len = len(body_raw.rstrip())
    if body_right_len < body_left_trim:
        body_right_len = body_left_trim
    body_start = int(start_idx + body_left_trim)
    body_end = int(start_idx + body_right_len)
    body_plain = str(plain[body_start:body_end] or "")
    if not body_plain:
        body_start = int(start_idx)
        body_end = int(len(plain.rstrip()))
        if body_end < body_start:
            body_end = body_start
        body_plain = str(plain[body_start:body_end] or plain.strip())

    prefix_plain = str(plain[:body_start] if body_plain else plain[:start_idx])
    body_offset_start = list(offset_map_start[body_start:body_end]) if offset_map_start else []
    body_offset_end = list(offset_map_end[body_start:body_end]) if offset_map_end else []
    if not body_offset_start or not body_offset_end:
        body_offset_start = list(offset_map_start or [])
        body_offset_end = list(offset_map_end or [])

    display_num, display_body_start = _parse_claim_prefix(display)
    if display_num is not None and display_body_start is not None:
        display_start_idx = int(display_body_start)
    else:
        display_start_idx = int(min(start_idx, len(display)))
    display_raw = str(display[display_start_idx:] or "")
    display_left_trim = len(display_raw) - len(display_raw.lstrip())
    display_right_len = len(display_raw.rstrip())
    if display_right_len < display_left_trim:
        display_right_len = display_left_trim
    body_display = str(display_raw[display_left_trim:display_right_len] or "")
    if not body_display:
        body_display = display.strip() or body_plain
    return prefix_plain, body_plain, body_display, body_offset_start, body_offset_end


def _join_chunks(chunks: list[_ParagraphChunk]) -> tuple[str, str, list[TokenSpan]]:
    joined_plain = ""
    joined_display = ""
    joined_tokens: list[TokenSpan] = []
    for index, chunk in enumerate(chunks):
        if index > 0:
            joined_plain += "\n"
            joined_display += "\n"
        offset = len(joined_display)
        joined_plain += str(chunk.plain_text or "")
        joined_display += str(chunk.display_text or "")
        for token in list(chunk.token_spans or []):
            joined_tokens.append(
                TokenSpan(
                    token=str(token.token or ""),
                    kind=str(token.kind or "non_text"),
                    local_start=offset + int(token.local_start or 0),
                    local_end=offset + int(token.local_end or 0),
                )
            )
    return joined_plain, joined_display, joined_tokens


def extract_formal_review_document(
    word_engine,
    file_path: str,
) -> tuple[FormalReviewDocument, list[TextAnchor], list[EditableSegment], ProjectionBundle]:
    word_engine.open_doc_for_review(file_path)
    doc = word_engine.doc
    if doc is None:
        raise RuntimeError("Word document is not open")
    return extract_formal_review_document_from_doc(doc)


def extract_formal_review_document_from_doc(
    doc,
) -> tuple[FormalReviewDocument, list[TextAnchor], list[EditableSegment], ProjectionBundle]:
    if doc is None:
        raise RuntimeError("Word document is not open")

    probe = _SectionPlanProbe()
    section_plan = probe._build_section_plan_from_headers(doc)

    claims: list[ClaimItem] = []
    description_parts: list[str] = []
    abstract_parts: list[str] = []
    drawings_parts: list[str] = []
    anchors: list[TextAnchor] = []
    editable_segments: list[EditableSegment] = []
    section_chunks: dict[str, list[_ParagraphChunk]] = {"description": [], "abstract": [], "drawings": []}
    claim_projection_rows: dict[int, list[ParagraphProjection]] = {}
    section_projection_rows: dict[str, list[ParagraphProjection]] = {"description": [], "abstract": [], "drawings": []}

    current_claim_num: int | None = None
    current_claim_parts: list[_ParagraphChunk] = []
    current_claim_prefix: str = ""
    current_claim_start: int | None = None
    current_claim_end: int | None = None
    current_claim_para_index: int = 0

    def _flush_claim() -> None:
        nonlocal current_claim_num, current_claim_parts, current_claim_prefix, current_claim_start, current_claim_end, current_claim_para_index
        if current_claim_num is None:
            return
        text, display_text, token_spans = _join_chunks(current_claim_parts)
        text = str(text or "").strip()
        display_text = str(display_text or "").strip()
        has_non_text = any(bool(chunk.has_non_text) for chunk in current_claim_parts)
        if text or display_text:
            claim_rows: list[ParagraphProjection] = []
            local_cursor = 0
            for idx, chunk in enumerate(current_claim_parts):
                row_text = str(chunk.plain_text or "")
                local_start = int(local_cursor)
                local_end = int(local_start + len(row_text))
                claim_rows.append(
                    ParagraphProjection(
                        section="claims",
                        claim_num=int(current_claim_num),
                        paragraph_index=int(chunk.paragraph_index),
                        local_start=local_start,
                        local_end=local_end,
                        word_start=int(chunk.word_start),
                        word_end=int(chunk.word_end),
                        text=row_text,
                        offset_map_start=list(chunk.offset_map_start or []),
                        offset_map_end=list(chunk.offset_map_end or []),
                    )
                )
                local_cursor = local_end + (1 if idx < len(current_claim_parts) - 1 else 0)
            claim_projection_rows[int(current_claim_num)] = claim_rows
            claims.append(
                ClaimItem(
                    num=current_claim_num,
                    text=text,
                    word_count=count_effective_chars(text),
                    markers=extract_figure_markers(text),
                    refs=parse_claim_references(text).refs,
                    anchor_start=current_claim_start,
                    anchor_end=current_claim_end,
                )
            )
            anchors.append(
                TextAnchor(
                    section="claims",
                    claim_num=current_claim_num,
                    word_range_start=int(current_claim_start or 0),
                    word_range_end=int(current_claim_end or 0),
                    raw_text=text,
                    source="claim",
                )
            )
            editable_segments.append(
                EditableSegment(
                    segment_id=f"claims:{int(current_claim_num)}",
                    section="claims",
                    claim_num=int(current_claim_num),
                    paragraph_index=int(current_claim_para_index),
                    word_start=int(current_claim_start or 0),
                    word_end=int(current_claim_end or 0),
                    original_display_text=display_text,
                    original_word_text=text,
                    token_spans=token_spans,
                    has_non_text=has_non_text,
                    prefix_text=str(current_claim_prefix or ""),
                )
            )
        current_claim_num = None
        current_claim_parts = []
        current_claim_prefix = ""
        current_claim_start = None
        current_claim_end = None
        current_claim_para_index = 0

    for i in range(1, int(doc.Paragraphs.Count) + 1):
        para = doc.Paragraphs(i)
        section_key = probe._get_section_key_for_paragraph(para, section_plan)
        section_key = str(section_key or "").strip()
        if not section_key:
            continue

        token_section = section_key if section_key in {"claims", "description", "abstract", "drawings", "abstract_drawings"} else "unknown"
        plain_text, display_text, token_spans, has_non_text, offset_map_start, offset_map_end = _extract_paragraph_text_and_tokens(
            para.Range,
            section=token_section,
            paragraph_index=int(i),
            paragraph_start=int(para.Range.Start),
        )
        if not plain_text and not has_non_text:
            continue

        range_start = int(para.Range.Start)
        range_end = int(max(range_start, int(para.Range.End) - 1))

        if section_key == "claims":
            candidates = _extract_claim_number_candidates(para.Range, plain_text)
            text_prefix_num = candidates.get("text_prefix_num")
            text_prefix_body_start = candidates.get("text_prefix_body_start")
            list_string_num = candidates.get("list_string_num")
            list_value_num = candidates.get("list_value_num")
            claim_num, claim_num_source = _select_claim_num_candidate(candidates, current_claim_num)
            claim_is_new = bool(
                claim_num is not None
                and (
                    current_claim_num is None
                    or int(claim_num) > int(current_claim_num)
                )
            )
            try:
                logger.debug(
                    "[formal_review][claim_extract] para=%s current=%s text_prefix=%s list_string=%s list_value=%s selected=%s source=%s start_new=%s",
                    int(i),
                    int(current_claim_num) if current_claim_num is not None else None,
                    int(text_prefix_num) if text_prefix_num is not None else None,
                    int(list_string_num) if list_string_num is not None else None,
                    int(list_value_num) if list_value_num is not None else None,
                    int(claim_num) if claim_num is not None else None,
                    str(claim_num_source or ""),
                    bool(claim_is_new),
                )
            except Exception:
                pass

            if text_prefix_num is None and _looks_like_claim_prefix_hint(plain_text):
                try:
                    logger.debug(
                        "[formal_review][claim_extract] para=%s text_prefix_missing",
                        int(i),
                    )
                except Exception:
                    pass

            if claim_num is not None:
                prefix_text = ""
                body_plain = plain_text
                body_display = display_text
                body_offset_start = list(offset_map_start or [])
                body_offset_end = list(offset_map_end or [])
                should_strip_prefix = bool(
                    text_prefix_body_start is not None
                    and (
                        claim_num_source == "text_prefix_num"
                        or (text_prefix_num is not None and int(text_prefix_num) == int(claim_num))
                    )
                )
                if should_strip_prefix:
                    prefix_text, body_plain, body_display, body_offset_start, body_offset_end = _claim_body_and_prefix(
                        plain_text,
                        display_text,
                        offset_map_start,
                        offset_map_end,
                        body_start_idx=int(text_prefix_body_start),
                    )
                body_start = int(body_offset_start[0]) if body_offset_start else int(range_start)
                body_end = int(body_offset_end[-1]) if body_offset_end else int(max(body_start, range_end))
                if current_claim_num is None:
                    current_claim_num = claim_num
                    current_claim_start = body_start
                    current_claim_para_index = int(i)
                    current_claim_prefix = prefix_text
                elif claim_num > int(current_claim_num):
                    _flush_claim()
                    current_claim_num = claim_num
                    current_claim_start = body_start
                    current_claim_para_index = int(i)
                    current_claim_prefix = prefix_text
                current_claim_parts.append(
                    _ParagraphChunk(
                        plain_text=body_plain if body_plain else plain_text,
                        display_text=body_display if body_display else display_text,
                        token_spans=token_spans,
                        # Claim text strips numeric prefix, so projection start must align to body start.
                        word_start=body_start,
                        word_end=body_end,
                        paragraph_index=int(i),
                        has_non_text=has_non_text,
                        offset_map_start=list(body_offset_start or offset_map_start),
                        offset_map_end=list(body_offset_end or offset_map_end),
                    )
                )
            else:
                if current_claim_num is None:
                    continue
                current_claim_parts.append(
                    _ParagraphChunk(
                        plain_text=plain_text,
                        display_text=display_text,
                        token_spans=token_spans,
                        word_start=int(offset_map_start[0]) if offset_map_start else range_start,
                        word_end=int(offset_map_end[-1]) if offset_map_end else range_end,
                        paragraph_index=int(i),
                        has_non_text=has_non_text,
                        offset_map_start=list(offset_map_start or []),
                        offset_map_end=list(offset_map_end or []),
                    )
                )
            current_claim_end = range_end
            continue

        _flush_claim()
        mapped_key = "drawings" if section_key in {"drawings", "abstract_drawings"} else section_key
        if mapped_key not in section_chunks:
            continue

        section_chunks[mapped_key].append(
            _ParagraphChunk(
                plain_text=plain_text,
                display_text=display_text,
                token_spans=token_spans,
                word_start=int(offset_map_start[0]) if offset_map_start else range_start,
                word_end=int(offset_map_end[-1]) if offset_map_end else range_end,
                paragraph_index=int(i),
                has_non_text=has_non_text,
                offset_map_start=list(offset_map_start or []),
                offset_map_end=list(offset_map_end or []),
            )
        )

        if section_key == "description":
            if plain_text:
                description_parts.append(plain_text)
                anchors.append(
                    TextAnchor(
                        section="description",
                        claim_num=None,
                        word_range_start=range_start,
                        word_range_end=range_end,
                        raw_text=plain_text,
                    )
                )
        elif section_key == "abstract":
            if plain_text:
                abstract_parts.append(plain_text)
                anchors.append(
                    TextAnchor(
                        section="abstract",
                        claim_num=None,
                        word_range_start=range_start,
                        word_range_end=range_end,
                        raw_text=plain_text,
                    )
                )
        elif section_key in {"drawings", "abstract_drawings"}:
            if plain_text:
                drawings_parts.append(plain_text)
                anchors.append(
                    TextAnchor(
                        section="drawings",
                        claim_num=None,
                        word_range_start=range_start,
                        word_range_end=range_end,
                        raw_text=plain_text,
                    )
                )

    _flush_claim()
    claims.sort(key=lambda item: int(item.num))
    document = FormalReviewDocument(
        claims=claims,
        description="\n".join(description_parts).strip(),
        abstract="\n".join(abstract_parts).strip(),
        drawings="\n".join(drawings_parts).strip(),
    )

    for section in ("description", "abstract", "drawings"):
        rows = section_chunks.get(section, [])
        if not rows:
            continue
        word_text, display_text, token_spans = _join_chunks(rows)
        editable_segments.append(
            EditableSegment(
                segment_id=f"{section}:0",
                section=section,
                claim_num=None,
                paragraph_index=0,
                word_start=int(rows[0].word_start),
                word_end=int(rows[-1].word_end),
                original_display_text=str(display_text or ""),
                original_word_text=str(word_text or ""),
                token_spans=token_spans,
                has_non_text=any(bool(row.has_non_text) for row in rows),
                prefix_text="",
            )
        )
        local_cursor = 0
        projection_rows: list[ParagraphProjection] = []
        for idx, row in enumerate(rows):
            row_text = str(row.plain_text or "")
            local_start = int(local_cursor)
            local_end = int(local_start + len(row_text))
            projection_rows.append(
                ParagraphProjection(
                    section=section,
                    claim_num=None,
                    paragraph_index=int(row.paragraph_index),
                    local_start=local_start,
                    local_end=local_end,
                    word_start=int(row.word_start),
                    word_end=int(row.word_end),
                    text=row_text,
                    offset_map_start=list(row.offset_map_start or []),
                    offset_map_end=list(row.offset_map_end or []),
                )
            )
            local_cursor = local_end + (1 if idx < len(rows) - 1 else 0)
        section_projection_rows[section] = projection_rows

    projections = ProjectionBundle(
        claims={
            int(claim_num): SectionProjection(section="claims", claim_num=int(claim_num), paragraphs=list(rows or []))
            for claim_num, rows in claim_projection_rows.items()
        },
        sections={
            key: SectionProjection(section=key, claim_num=None, paragraphs=list(rows or []))
            for key, rows in section_projection_rows.items()
        },
    )

    return document, anchors, editable_segments, projections
