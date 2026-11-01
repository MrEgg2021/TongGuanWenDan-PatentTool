import re

from core.logging_utils import logger, swallow_exception

from .segment_builder import build_segments
from .eq_centering import apply_eq_centering
from .output_writer import write_segments


def process_paragraph_content(self, para, parent_node, is_claim=False, section_key: str | None = None):
    inline_shapes = para.Range.InlineShapes

    inline_count = 0
    try:
        inline_count = inline_shapes.Count
    except Exception:
        swallow_exception("inline_shapes.Count")
        inline_count = 0

    has_inline = inline_count > 0

    eq_center_cfg = self.config.get("equation_centering") or {}
    enable_eq_center = bool(eq_center_cfg.get("enabled"))

    raw_text_full = ""
    if has_inline:
        raw_text_full = para.Range.Text or ""
        clean_text_full = raw_text_full.replace("\r", "").replace("\x0b", "\n")
        clean_text_full = self._sanitize_text(clean_text_full).strip()

        logger.info(
            "[EQ_INLINE_DBG] idx=%s is_claim=%s inline_cnt=%s",
            getattr(self, "_current_paragraph_index", None),
            is_claim,
            inline_count,
        )

        if any(ch.isdigit() for ch in clean_text_full) and ("(" in clean_text_full or "（" in clean_text_full):
            logger.info(
                "[EQ_NUM_DBG] idx=%s is_claim=%s inline_cnt=%s",
                getattr(self, "_current_paragraph_index", None),
                is_claim,
                inline_count,
            )

    defensive_cfg = self.config.get("defensive", {}) or {}
    enable_wordopenxml_supsub = bool(defensive_cfg.get("enable_wordopenxml_supsub", True))

    segments = build_segments(
        self,
        para,
        parent_node=parent_node,
        is_claim=is_claim,
        section_key=section_key,
        has_inline=has_inline,
        inline_shapes=inline_shapes,
        inline_count=inline_count,
        enable_wordopenxml_supsub=enable_wordopenxml_supsub,
    )

    parent_tag = getattr(parent_node, "tag", "") or ""
    if has_inline:
        try:
            segments, _ = self._merge_visual_eq_line(
                para,
                segments,
                raw_text_full,
                is_claim,
                parent_node=parent_node,
                section_key=section_key,
                allow_merge_with_num=False,
                allow_pure_line=bool(enable_eq_center),
            )
        except Exception:
            swallow_exception("_merge_visual_eq_line")
            pass

    if (not enable_eq_center) and segments:
        try:
            raw_text_full_for_eq = raw_text_full if has_inline else (para.Range.Text or "")
            try:
                raw_text_full_for_eq = (raw_text_full_for_eq or "").replace("\x0b", "\n")
            except Exception:
                swallow_exception("replace_vertical_tab")
                pass
            try:
                clean_text_full_for_eq = self._sanitize_text((raw_text_full_for_eq or "").replace("\r", "")).strip()
            except Exception:
                swallow_exception("_sanitize_text")
                clean_text_full_for_eq = ""
            try:
                eq_lines = self._detect_visual_eq_lines_in_raw(raw_text_full_for_eq)
            except Exception:
                swallow_exception("_detect_visual_eq_lines_in_raw")
                eq_lines = []
            if (not eq_lines) and clean_text_full_for_eq and re.fullmatch(r"[（(]?\s*\d+\s*[)）]?", clean_text_full_for_eq):
                eq_lines = [(0, len(raw_text_full_for_eq or ""))]

            should_detect_eq_with_num = bool(is_claim) or parent_tag == "description" or bool(eq_lines and len(eq_lines) == 1)
            if should_detect_eq_with_num:
                num_pattern = re.compile(r"[（(]\d+[)）]")
                eq_indices = []
                for idx, seg in enumerate(segments):
                    if seg.get("kind") == "img" and seg.get("is_equation"):
                        eq_indices.append(idx)

                if len(eq_indices) == 1:
                    eq_idx = eq_indices[0]
                    for j in range(eq_idx + 1, len(segments)):
                        seg = segments[j]
                        if seg.get("kind") != "text":
                            continue
                        txt = seg.get("text_plain") or seg.get("text") or ""
                        m = num_pattern.search(txt)
                        if not m:
                            continue
                        if is_claim or parent_tag == "description":
                            if not re.fullmatch(r"[（(]\s*\d+\s*[)）]", txt.strip()):
                                continue
                        prefix = txt[: m.start()]
                        if prefix.strip() != "":
                            continue
                        between_ok = True
                        for k in range(eq_idx + 1, j):
                            mid = segments[k]
                            if mid.get("kind") != "text":
                                continue
                            mid_txt = mid.get("text_plain") or mid.get("text") or ""
                            if mid_txt.strip() != "":
                                between_ok = False
                                break
                        if not between_ok:
                            continue

                        kind = "claim_eq_with_num" if is_claim else "desc_eq_with_num"
                        segments[eq_idx]["eq_line_kind"] = kind
                        seg["is_eq_number"] = True
                        break
        except Exception:
            swallow_exception("detect_eq_with_num")
            pass

    if not segments:
        return

    if is_claim:
        defensive_cfg = self.config.get("defensive", {}) or {}
        try:
            big_eq_width_mm = float(defensive_cfg.get("claim_big_eq_width_mm", 120.0))
        except (TypeError, ValueError):
            big_eq_width_mm = 120.0

        for seg in segments:
            if seg.get("kind") == "img" and seg.get("is_equation") and seg.get("width_mm") is not None:
                try:
                    w = float(seg.get("width_mm"))
                except (TypeError, ValueError):
                    continue
                if w >= big_eq_width_mm:
                    seg["is_big"] = True

    if enable_eq_center:
        segments = apply_eq_centering(
            self,
            para,
            segments,
            raw_text_full=raw_text_full,
            has_inline=has_inline,
            is_claim=is_claim,
            parent_tag=parent_tag,
            eq_center_cfg=eq_center_cfg,
        )

    write_segments(self, para, parent_node, segments, is_claim=is_claim)


__all__ = ["process_paragraph_content"]
