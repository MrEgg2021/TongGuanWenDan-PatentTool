from __future__ import annotations

import re

from .edit_model import EditableSegment
from .claim_refs import parse_claim_references
from .extractor import TextAnchor
from .models import ClaimItem, FormalReviewDocument
from .text_utils import count_effective_chars, extract_figure_markers

_CLAIM_PREFIX_RE = re.compile(r"^\s*(\d{1,4})\s*[\.。、，,\)）]?\s*(.*)$")


def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    return "".join(ch for ch in text if (ch in ("\t", "\n") or ord(ch) >= 0x20))


def _normalize_claim_text(text: str) -> list[tuple[int | None, str]]:
    source = _sanitize_text(text).replace("\r\n", "\n").replace("\r", "\n")
    pieces = [part.strip() for part in source.split("。") if part and part.strip()]
    rows: list[tuple[int | None, str]] = []
    for part in pieces:
        match = _CLAIM_PREFIX_RE.match(part)
        if match:
            claim_num = int(match.group(1))
            body = str(match.group(2) or "").strip()
            normalized = body or part.strip()
            rows.append((claim_num, normalized))
            continue
        rows.append((None, part.strip()))
    return rows


def parse_plain_text_sections(
    claims_text: str,
    description_text: str,
    abstract_text: str,
    drawings_text: str,
) -> tuple[FormalReviewDocument, list[TextAnchor], list[EditableSegment]]:
    claims_rows = _normalize_claim_text(claims_text)

    claims: list[ClaimItem] = []
    anchors: list[TextAnchor] = []
    editable_segments: list[EditableSegment] = []
    cursor = 0
    next_num = 1
    for claim_num_raw, claim_body in claims_rows:
        normalized_body = str(claim_body or "").strip()
        if not normalized_body:
            continue
        if not normalized_body.endswith("。"):
            normalized_body = f"{normalized_body}。"

        claim_num = int(claim_num_raw) if claim_num_raw is not None else int(next_num)
        next_num = max(int(next_num) + 1, claim_num + 1)

        claim_item = ClaimItem(
            num=claim_num,
            text=normalized_body,
            word_count=count_effective_chars(normalized_body),
            markers=extract_figure_markers(normalized_body),
            refs=parse_claim_references(normalized_body).refs,
            anchor_start=cursor,
            anchor_end=cursor + len(normalized_body),
        )
        claims.append(claim_item)
        anchors.append(
            TextAnchor(
                section="claims",
                claim_num=claim_num,
                word_range_start=cursor,
                word_range_end=cursor + len(normalized_body),
                raw_text=normalized_body,
                source="plain_text",
            )
        )
        editable_segments.append(
            EditableSegment(
                segment_id=f"claims:{claim_num}",
                section="claims",
                claim_num=claim_num,
                paragraph_index=0,
                word_start=cursor,
                word_end=cursor + len(normalized_body),
                original_display_text=normalized_body,
                original_word_text=normalized_body,
                token_spans=[],
                has_non_text=False,
                prefix_text="",
            )
        )
        cursor += len(normalized_body) + 1

    claims.sort(key=lambda item: int(item.num))
    description = _sanitize_text(description_text).strip()
    abstract = _sanitize_text(abstract_text).strip()
    drawings = _sanitize_text(drawings_text).strip()

    if description:
        anchors.append(
            TextAnchor(
                section="description",
                claim_num=None,
                word_range_start=0,
                word_range_end=len(description),
                raw_text=description,
                source="plain_text",
            )
        )
        editable_segments.append(
            EditableSegment(
                segment_id="description:0",
                section="description",
                claim_num=None,
                paragraph_index=0,
                word_start=0,
                word_end=len(description),
                original_display_text=description,
                original_word_text=description,
                token_spans=[],
                has_non_text=False,
                prefix_text="",
            )
        )
    if abstract:
        anchors.append(
            TextAnchor(
                section="abstract",
                claim_num=None,
                word_range_start=0,
                word_range_end=len(abstract),
                raw_text=abstract,
                source="plain_text",
            )
        )
        editable_segments.append(
            EditableSegment(
                segment_id="abstract:0",
                section="abstract",
                claim_num=None,
                paragraph_index=0,
                word_start=0,
                word_end=len(abstract),
                original_display_text=abstract,
                original_word_text=abstract,
                token_spans=[],
                has_non_text=False,
                prefix_text="",
            )
        )
    if drawings:
        anchors.append(
            TextAnchor(
                section="drawings",
                claim_num=None,
                word_range_start=0,
                word_range_end=len(drawings),
                raw_text=drawings,
                source="plain_text",
            )
        )
        editable_segments.append(
            EditableSegment(
                segment_id="drawings:0",
                section="drawings",
                claim_num=None,
                paragraph_index=0,
                word_start=0,
                word_end=len(drawings),
                original_display_text=drawings,
                original_word_text=drawings,
                token_spans=[],
                has_non_text=False,
                prefix_text="",
            )
        )

    return (
        FormalReviewDocument(
            claims=claims,
            description=description,
            abstract=abstract,
            drawings=drawings,
        ),
        anchors,
        editable_segments,
    )
