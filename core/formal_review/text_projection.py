from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ParagraphProjection:
    section: str
    claim_num: int | None
    paragraph_index: int
    local_start: int
    local_end: int
    word_start: int
    word_end: int
    text: str = ""
    # Optional exact character boundary mapping from review text offsets to Word offsets.
    # If present and length matches text length, this mapping is preferred over linear offset.
    offset_map_start: list[int] | None = None
    offset_map_end: list[int] | None = None


@dataclass(slots=True)
class SectionProjection:
    section: str
    claim_num: int | None
    paragraphs: list[ParagraphProjection] = field(default_factory=list)


@dataclass(slots=True)
class ProjectionBundle:
    claims: dict[int, SectionProjection] = field(default_factory=dict)
    sections: dict[str, SectionProjection] = field(default_factory=dict)

    def paragraphs_for(self, section: str, claim_num: int | None = None) -> list[ParagraphProjection]:
        section_key = str(section or "")
        if section_key == "claims":
            if claim_num is None:
                return []
            row = self.claims.get(int(claim_num))
            return list(getattr(row, "paragraphs", []) or [])
        row = self.sections.get(section_key)
        return list(getattr(row, "paragraphs", []) or [])


def projection_text(paragraphs: list[ParagraphProjection]) -> str:
    if not paragraphs:
        return ""
    chunks: list[str] = []
    for idx, row in enumerate(paragraphs):
        chunks.append(str(getattr(row, "text", "") or ""))
        if idx < len(paragraphs) - 1:
            chunks.append("\n")
    return "".join(chunks)


def _map_offset(
    paragraphs: list[ParagraphProjection],
    offset: int,
    *,
    prefer_end: bool,
) -> tuple[ParagraphProjection, int] | None:
    for row in paragraphs:
        start = int(getattr(row, "local_start", 0) or 0)
        end = int(getattr(row, "local_end", 0) or 0)
        word_start = int(getattr(row, "word_start", 0) or 0)
        local_len = max(0, end - start)
        start_map = list(getattr(row, "offset_map_start", None) or [])
        end_map = list(getattr(row, "offset_map_end", None) or [])
        has_exact_map = bool(local_len > 0 and len(start_map) == local_len and len(end_map) == local_len)
        if start <= offset < end:
            rel = int(offset - start)
            if has_exact_map:
                if prefer_end:
                    boundary_idx = max(0, rel - 1)
                    return row, int(end_map[boundary_idx])
                return row, int(start_map[rel])
            return row, int(word_start + rel)
        if prefer_end and offset == end:
            if has_exact_map:
                return row, int(end_map[-1])
            return row, int(word_start + (end - start))
    return None


def map_span_to_word_range(
    paragraphs: list[ParagraphProjection],
    span_start: int,
    span_end: int,
) -> tuple[int, int] | None:
    if not paragraphs:
        return None
    start = int(span_start)
    end = int(span_end)
    if end <= start:
        return None
    mapped_start = _map_offset(paragraphs, start, prefer_end=False)
    mapped_end = _map_offset(paragraphs, end, prefer_end=True)
    if mapped_start is None or mapped_end is None:
        return None
    start_row, abs_start = mapped_start
    end_row, abs_end = mapped_end
    if start_row is not end_row:
        return None
    if abs_end <= abs_start:
        return None
    return int(abs_start), int(abs_end)


def all_occurrences(text: str, needle: str) -> list[int]:
    source = str(text or "")
    target = str(needle or "")
    if not source or not target:
        return []
    rows: list[int] = []
    cursor = 0
    while True:
        idx = source.find(target, cursor)
        if idx < 0:
            break
        rows.append(int(idx))
        cursor = idx + 1
    return rows


def count_occurrences_before(text: str, needle: str, pos: int) -> int:
    source = str(text or "")
    target = str(needle or "")
    if not source or not target:
        return 0
    limit = max(0, min(int(pos), len(source)))
    return len(all_occurrences(source[:limit], target))


def locate_occurrence_in_projection(
    paragraphs: list[ParagraphProjection],
    needle: str,
    occurrence_index: int,
) -> tuple[int, int] | None:
    target = str(needle or "")
    if not target:
        return None
    source = projection_text(paragraphs)
    matches = all_occurrences(source, target)
    if not matches:
        return None
    idx = int(occurrence_index or 0)
    if idx < 0 or idx >= len(matches):
        return None
    return map_span_to_word_range(paragraphs, int(matches[idx]), int(matches[idx] + len(target)))


__all__ = [
    "ParagraphProjection",
    "SectionProjection",
    "ProjectionBundle",
    "projection_text",
    "map_span_to_word_range",
    "all_occurrences",
    "count_occurrences_before",
    "locate_occurrence_in_projection",
]
