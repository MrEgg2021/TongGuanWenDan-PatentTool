from __future__ import annotations

from .text_formatting import extract_text_with_formatting
from .process import process_paragraph_content
from .eq_line import detect_visual_eq_lines_in_raw, merge_visual_eq_line


class ParagraphInlineObjectMixin:
    _extract_text_with_formatting = extract_text_with_formatting
    process_paragraph_content = process_paragraph_content
    _detect_visual_eq_lines_in_raw = detect_visual_eq_lines_in_raw
    _merge_visual_eq_line = merge_visual_eq_line


__all__ = ["ParagraphInlineObjectMixin"]
