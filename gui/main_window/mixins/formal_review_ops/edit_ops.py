from __future__ import annotations

from .shared import (
    ClaimItem,
    EditableSegment,
    FormalReviewDocument,
    Issue,
    _SectionSegment,
    _TOKEN_RE,
    _safe_int,
    build_issue_id,
    count_effective_chars,
    extract_figure_markers,
    parse_claim_references,
)

__all__ = [
    "_set_needs_parse",
    "_set_edit_segments",
    "_segment_text",
    "_set_segment_edit_text",
    "_on_formal_review_section_text_edited",
    "_on_formal_review_claim_text_edited",
    "_tokens_intact",
    "_strip_obj_tokens",
    "_build_segment_writeback_payload",
    "_build_document_from_current_views",
    "_clear_document_views",
    "_build_section_segments",
    "_resolve_issue_anchor_base",
    "_issue_scope_bounds",
    "_rebuild_issue_ids",
]

def _set_needs_parse(self, value: bool) -> None:
    self._formal_review_needs_parse = bool(value)
    if value:
        self._set_status_text("形式审查：待解析")

def _set_edit_segments(self, segments: list[EditableSegment] | None) -> None:
    rows = list(segments or [])
    self._formal_review_edit_segments = rows
    self._formal_review_edit_segment_map = {str(item.segment_id): item for item in rows}
    self._formal_review_segment_edits = {str(item.segment_id): str(item.original_display_text or "") for item in rows}
    self._formal_review_writeback_report = {}

def _segment_text(self, segment_id: str, fallback: str = "") -> str:
    edits = dict(getattr(self, "_formal_review_segment_edits", {}) or {})
    if segment_id in edits:
        return str(edits.get(segment_id) or "")
    segment = (getattr(self, "_formal_review_edit_segment_map", {}) or {}).get(str(segment_id or ""))
    if segment is not None:
        return str(segment.original_display_text or "")
    return str(fallback or "")

def _set_segment_edit_text(self, segment_id: str, text: str) -> None:
    segment = (getattr(self, "_formal_review_edit_segment_map", {}) or {}).get(str(segment_id or ""))
    if segment is None:
        return
    current = dict(getattr(self, "_formal_review_segment_edits", {}) or {})
    current[str(segment_id)] = str(text or "")
    self._formal_review_segment_edits = current

def _on_formal_review_section_text_edited(self, section: str) -> None:
    if bool(getattr(self, "_formal_review_syncing_ui", False)):
        return
    editor = {
        "description": getattr(self, "formal_review_description_text", None),
        "abstract": getattr(self, "formal_review_abstract_text", None),
        "drawings": getattr(self, "formal_review_drawings_text", None),
    }.get(str(section or ""))
    if editor is None:
        return
    self._set_segment_edit_text(f"{section}:0", str(editor.toPlainText() or ""))
    if str(section or "") == "abstract":
        self._update_abstract_count_label()

def _on_formal_review_claim_text_edited(self, claim_num: int) -> None:
    if bool(getattr(self, "_formal_review_syncing_ui", False)):
        return
    editor = (getattr(self, "_formal_review_claim_content_views", {}) or {}).get(int(claim_num))
    if editor is None:
        return
    self._set_segment_edit_text(f"claims:{int(claim_num)}", str(editor.toPlainText() or ""))

def _tokens_intact(self, segment: EditableSegment, edited_text: str) -> bool:
    tokens = [str(item.token or "") for item in list(getattr(segment, "token_spans", []) or []) if str(item.token or "")]
    if not tokens:
        return True
    source_text = str(edited_text or "")
    for token in tokens:
        if source_text.count(token) != 1:
            return False
    return True

def _strip_obj_tokens(text: str) -> str:
    source = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return _TOKEN_RE.sub("", source).strip()

def _build_segment_writeback_payload(self) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for segment in list(getattr(self, "_formal_review_edit_segments", []) or []):
        segment_id = str(segment.segment_id or "")
        edited_display_text = self._segment_text(segment_id, fallback=str(segment.original_display_text or ""))
        original_display_text = str(segment.original_display_text or "")
        changed = edited_display_text != original_display_text
        downgrade_reason = ""
        if changed and bool(segment.has_non_text):
            if not self._tokens_intact(segment, edited_display_text):
                downgrade_reason = "Placeholder token changed, cannot write revision safely"
            else:
                downgrade_reason = "Segment contains non-text object, downgraded to comment"

        edited_word_text = self._strip_obj_tokens(edited_display_text)
        original_word_text = self._strip_obj_tokens(str(segment.original_word_text or ""))
        if str(segment.section or "") == "claims":
            prefix_text = str(segment.prefix_text or "")
            edited_word_text = f"{prefix_text}{edited_word_text}" if edited_word_text else prefix_text.strip()
            original_word_text = f"{prefix_text}{original_word_text}" if original_word_text else prefix_text.strip()

        payload.append(
            {
                "segment_id": segment_id,
                "section": str(segment.section or ""),
                "claim_num": segment.claim_num,
                "word_start": int(segment.word_start or 0),
                "word_end": int(segment.word_end or 0),
                "original_display_text": original_display_text,
                "edited_display_text": edited_display_text,
                "original_word_text": original_word_text,
                "edited_word_text": edited_word_text,
                "has_non_text": bool(segment.has_non_text),
                "changed": bool(changed),
                "downgrade_reason": downgrade_reason,
            }
        )
    return payload

def _build_document_from_current_views(self) -> FormalReviewDocument:
    source_document = getattr(self, "_formal_review_document", None)
    source_claims = list(getattr(source_document, "claims", []) or [])
    next_claims: list[ClaimItem] = []
    for claim in source_claims:
        claim_num = int(claim.num)
        editor = (getattr(self, "_formal_review_claim_content_views", {}) or {}).get(claim_num)
        claim_display_text = str(editor.toPlainText() or "") if editor is not None else self._segment_text(
            f"claims:{claim_num}",
            fallback=str(claim.text or ""),
        )
        claim_text = self._strip_obj_tokens(claim_display_text)
        next_claims.append(
            ClaimItem(
                num=claim_num,
                text=claim_text,
                word_count=count_effective_chars(claim_text),
                markers=extract_figure_markers(claim_text),
                refs=parse_claim_references(claim_text).refs,
                anchor_start=getattr(claim, "anchor_start", None),
                anchor_end=getattr(claim, "anchor_end", None),
            )
        )
    next_claims.sort(key=lambda item: int(item.num))

    description_editor = getattr(self, "formal_review_description_text", None)
    abstract_editor = getattr(self, "formal_review_abstract_text", None)
    drawings_editor = getattr(self, "formal_review_drawings_text", None)
    description = self._strip_obj_tokens(str(description_editor.toPlainText() or "")) if description_editor is not None else ""
    abstract = self._strip_obj_tokens(str(abstract_editor.toPlainText() or "")) if abstract_editor is not None else ""
    drawings = self._strip_obj_tokens(str(drawings_editor.toPlainText() or "")) if drawings_editor is not None else ""

    return FormalReviewDocument(
        claims=next_claims,
        description=description,
        abstract=abstract,
        drawings=drawings,
    )

def _clear_document_views(self) -> None:
    for name in ("formal_review_claims_input_text", "formal_review_description_text", "formal_review_abstract_text", "formal_review_drawings_text"):
        editor = getattr(self, name, None)
        if editor is not None:
            editor.clear()
    for name in ("formal_review_issue_preview",):
        preview = getattr(self, name, None)
        if preview is not None:
            preview.setHtml("")
    tree = getattr(self, "formal_review_claims_tree", None)
    if tree is not None:
        tree.clear()
    self._formal_review_claim_content_views = {}
    self._formal_review_claim_marker_labels = {}
    self._formal_review_claim_marker_rows = {}
    table = getattr(self, "formal_review_claims_table", None)
    if table is not None:
        table.setRowCount(0)
    self._set_edit_segments([])
    self._formal_review_projections = None
    self._update_abstract_count_label()

def _build_section_segments(self, anchors: list) -> None:
    document = getattr(self, "_formal_review_document", None)
    claims_map: dict[int, list[_SectionSegment]] = {}
    if document is not None:
        for claim in list(getattr(document, "claims", []) or []):
            claim_num = int(claim.num)
            text = str(claim.text or "")
            claims_map[claim_num] = [
                _SectionSegment("claims", claim_num, 0, len(text), int(claim.anchor_start or 0), raw_text=text)
            ]
    grouped = {"description": [], "abstract": [], "drawings": []}
    for anchor in list(anchors or []):
        section = str(getattr(anchor, "section", "") or "")
        if section in grouped:
            grouped[section].append(anchor)
    result = {"claims": claims_map, "description": [], "abstract": [], "drawings": []}
    for section in ("description", "abstract", "drawings"):
        rows = grouped.get(section, [])
        if not rows:
            text_value = str(getattr(document, section, "") or "") if document is not None else ""
            result[section] = [_SectionSegment(section, None, 0, len(text_value), 0, raw_text=text_value)]
            continue
        segs: list[_SectionSegment] = []
        cursor = 0
        for index, anchor in enumerate(rows):
            raw_text = str(getattr(anchor, "raw_text", "") or "")
            if not raw_text:
                continue
            start = cursor
            end = start + len(raw_text)
            word_start = int(getattr(anchor, "word_range_start", 0) or 0)
            segs.append(_SectionSegment(section, None, start, end, word_start, raw_text=raw_text))
            cursor = end + (1 if index < len(rows) - 1 else 0)
        result[section] = segs
    self._formal_review_section_segments = result

def _resolve_issue_anchor_base(self, issue: Issue) -> int:
    section = str(issue.section or "")
    span_start = _safe_int(issue.span_start, 0) or 0
    if section == "claims":
        mapping = (getattr(self, "_formal_review_section_segments", {}) or {}).get("claims", {})
        rows = mapping.get(int(issue.claim_num or -1), []) if isinstance(mapping, dict) else []
        if rows:
            first = rows[0]
            return int(first.word_range_start - first.local_start)
        return 0
    rows = (getattr(self, "_formal_review_section_segments", {}) or {}).get(section, [])
    if not rows:
        return 0
    for seg in rows:
        if int(seg.local_start) <= span_start <= int(seg.local_end):
            return int(seg.word_range_start - seg.local_start)
    first = rows[0]
    return int(first.word_range_start - first.local_start)

def _issue_scope_bounds(self, issue: Issue) -> tuple[int, int] | None:
    section = str(getattr(issue, "section", "") or "")
    if section == "claims":
        claim_num = _safe_int(getattr(issue, "claim_num", None), None)
        if claim_num is None:
            return None
        document = getattr(self, "_formal_review_document", None)
        if document is None:
            return None
        for claim in list(getattr(document, "claims", []) or []):
            if int(getattr(claim, "num", 0) or 0) != int(claim_num):
                continue
            start = _safe_int(getattr(claim, "anchor_start", None), None)
            end = _safe_int(getattr(claim, "anchor_end", None), None)
            if start is None or end is None or end <= start:
                return None
            return int(start), int(end)
        return None
    rows = list(((getattr(self, "_formal_review_section_segments", {}) or {}).get(section, []) or []))
    if not rows:
        return None
    starts: list[int] = []
    ends: list[int] = []
    for seg in rows:
        start = _safe_int(getattr(seg, "word_range_start", None), None)
        local_start = _safe_int(getattr(seg, "local_start", None), None)
        local_end = _safe_int(getattr(seg, "local_end", None), None)
        if start is None or local_start is None or local_end is None:
            continue
        starts.append(int(start))
        ends.append(int(start + max(0, int(local_end - local_start))))
    if not starts or not ends:
        return None
    return min(starts), max(ends)

def _rebuild_issue_ids(self, issues: list[Issue]) -> None:
    max_expected_hit_len = 120

    def _safe_expected_hit(text: str) -> bool:
        value = str(text or "")
        if not value.strip():
            return False
        if ("\n" in value) or ("\r" in value):
            return False
        return len(value) <= int(max_expected_hit_len)

    def _normalize_expected_hit_candidates(anchor: dict) -> list[str]:
        raw = anchor.get("expected_hit_candidates")
        if not isinstance(raw, (list, tuple)):
            return []
        seen: set[str] = set()
        rows: list[str] = []
        for item in list(raw):
            text = str(item or "").strip()
            if (not text) or (text in seen):
                continue
            seen.add(text)
            rows.append(text)
        return rows

    for issue in issues:
        anchor_base = self._resolve_issue_anchor_base(issue)
        if not isinstance(issue.anchor, dict):
            issue.anchor = {}
        issue.anchor["word_range_start"] = int(anchor_base)
        expected_hit_candidates = _normalize_expected_hit_candidates(issue.anchor)
        if expected_hit_candidates:
            issue.anchor["expected_hit_candidates"] = list(expected_hit_candidates)
        else:
            issue.anchor.pop("expected_hit_candidates", None)
        source = self._section_text_for_issue(issue)
        span_start = _safe_int(getattr(issue, "span_start", None), None)
        span_end = _safe_int(getattr(issue, "span_end", None), None)
        current_expected = str(issue.anchor.get("expected_hit", "") or "")
        if current_expected and (not _safe_expected_hit(current_expected)):
            issue.anchor.pop("expected_hit", None)
            current_expected = ""
        if (not current_expected) and expected_hit_candidates:
            first_candidate = str(expected_hit_candidates[0] or "").strip()
            if _safe_expected_hit(first_candidate):
                issue.anchor["expected_hit"] = first_candidate
                current_expected = first_candidate
        if source and span_start is not None:
            start = max(0, min(int(span_start), len(source)))
            end = start if span_end is None else max(start, min(int(span_end), len(source)))
            if end > start:
                candidate = str(source[start:end] or "")
                if _safe_expected_hit(candidate) and (not expected_hit_candidates):
                    issue.anchor["expected_hit"] = candidate
                    current_expected = candidate
                elif not current_expected:
                    snippet = str(getattr(issue, "snippet", "") or "").strip()
                    if _safe_expected_hit(snippet):
                        issue.anchor["expected_hit"] = snippet
                        current_expected = snippet
                issue.anchor["pre_context"] = str(source[max(0, start - 16) : start])
                issue.anchor["post_context"] = str(source[end : min(len(source), end + 16)])
        bounds = self._issue_scope_bounds(issue)
        if bounds is not None:
            issue.anchor["section_range_start"] = int(bounds[0])
            issue.anchor["section_range_end"] = int(bounds[1])
        issue.issue_id = build_issue_id(issue)


