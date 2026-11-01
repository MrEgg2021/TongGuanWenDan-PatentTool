from core.logging_utils import logger


def _ranges_overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    if start == other_start and end == other_end:
        return True
    return start < other_end and other_start < end


def _dedupe_overlapping_formula_objects(self, objects):
    omath_ranges = [(start, end) for obj_type, start, end, _obj in objects if obj_type == "omath"]
    if not omath_ranges:
        return objects

    deduped = []
    for obj_type, start, end, obj in objects:
        if obj_type == "shape":
            try:
                is_equation = self._is_equation_shape(obj)
            except Exception:
                is_equation = False
            if is_equation and any(_ranges_overlap(start, end, om_start, om_end) for om_start, om_end in omath_ranges):
                logger.debug("[EQ_DEDUPE] skip overlapping equation shape range=%s-%s", start, end)
                continue
        deduped.append((obj_type, start, end, obj))
    return deduped


def build_segments(
    self,
    para,
    *,
    parent_node=None,
    section_key: str | None = None,
    is_claim: bool,
    has_inline: bool,
    inline_shapes,
    inline_count: int,
    enable_wordopenxml_supsub: bool,
):
    segments = []

    try:
        omaths = para.Range.OMaths
        omath_count = getattr(omaths, "Count", 0)
    except Exception:
        omaths = None
        omath_count = 0

    has_any_object = has_inline or (omath_count > 0)

    if not has_any_object:
        rng = para.Range
        raw_text = rng.Text
        try:
            raw_text = (raw_text or "").replace("\x0b", "\n")
        except Exception:
            raw_text = rng.Text
        text_plain = self._sanitize_text(raw_text).strip()
        text_value = text_plain
        if enable_wordopenxml_supsub:
            text_formatted = self._extract_text_with_formatting(rng)
            text_value = self._sanitize_text(text_formatted).strip()
        text = text_value
        if text:
            segments.append(
                {
                    "kind": "text",
                    "text": text,
                    "text_plain": text_plain,
                    "range_start": rng.Start,
                    "range_end": rng.End,
                }
            )
        logger.debug(
            "[CLAIM_RAW] idx=%s is_claim=%s",
            getattr(self, "_current_paragraph_index", None),
            is_claim,
        )
        return segments

    shapes = []
    if inline_count > 0:
        for i in range(1, inline_count + 1):
            try:
                ishp = inline_shapes(i)
                shapes.append((ishp.Range.Start, ishp.Range.End, ishp))
            except Exception:
                continue

    objects = []
    for start, end, shape in shapes:
        objects.append(("shape", start, end, shape))

    if omath_count > 0 and omaths is not None:
        for i in range(1, omath_count + 1):
            try:
                om = omaths(i)
                objects.append(("omath", om.Range.Start, om.Range.End, om))
            except Exception:
                continue

    objects = _dedupe_overlapping_formula_objects(self, objects)

    if not objects:
        rng = para.Range
        raw_text = rng.Text
        text_plain = self._sanitize_text(raw_text).strip()
        text_value = text_plain
        if enable_wordopenxml_supsub:
            text_formatted = self._extract_text_with_formatting(rng)
            text_value = self._sanitize_text(text_formatted).strip()
        text = text_value
        if text:
            segments.append(
                {
                    "kind": "text",
                    "text": text,
                    "text_plain": text_plain,
                    "range_start": rng.Start,
                    "range_end": rng.End,
                }
            )
        return segments

    objects.sort(key=lambda x: x[1])

    defensive_cfg = self.config.get("defensive", {}) or {}
    large_img_height_mm = float(defensive_cfg.get("large_img_height_mm", 40.0))

    current_pos = para.Range.Start

    for obj_type, start, end, obj in objects:
        if start > current_pos:
            rng = self.word.doc.Range(current_pos, start)
            text_part_plain = rng.Text.replace("\r", "").replace("\x0b", "\n")
            text_part_plain = self._sanitize_text(text_part_plain)
            text_part = text_part_plain
            if enable_wordopenxml_supsub:
                text_part_formatted = self._extract_text_with_formatting(rng)
                text_part_formatted = text_part_formatted.replace("\r", "").replace("\x0b", "\n")
                text_part = self._sanitize_text(text_part_formatted)
            if text_part:
                segments.append(
                    {
                        "kind": "text",
                        "text": text_part,
                        "text_plain": text_part_plain,
                        "range_start": rng.Start,
                        "range_end": rng.End,
                    }
                )

        if obj_type == "shape":
            img_filename, width_mm, height_mm, px_per_mm_for_ole = self.handle_shape(
                obj,
                parent_node=parent_node,
                section_key=section_key,
            )
            if img_filename:
                is_equation = self._is_equation_shape(obj)
                is_big = (not is_claim) and (not is_equation) and (height_mm >= large_img_height_mm)
                segments.append(
                    {
                        "kind": "img",
                        "filename": img_filename,
                        "width_mm": width_mm,
                        "height_mm": height_mm,
                        "is_equation": is_equation,
                        "is_big": is_big,
                        "range_start": start,
                        "range_end": end,
                        "px_per_mm_for_ole": px_per_mm_for_ole,
                    }
                )

        else:
            img_filename, width_mm, height_mm = self.handle_omath(obj)
            if img_filename:
                segments.append(
                    {
                        "kind": "img",
                        "filename": img_filename,
                        "width_mm": width_mm,
                        "height_mm": height_mm,
                        "is_equation": True,
                        "is_big": False,
                        "range_start": start,
                        "range_end": end,
                    }
                )

        current_pos = end

    if current_pos < para.Range.End:
        rng = self.word.doc.Range(current_pos, para.Range.End)
        text_part_plain = rng.Text.replace("\r", "").replace("\x0b", "\n")
        text_part_plain = self._sanitize_text(text_part_plain)
        text_part = text_part_plain
        if enable_wordopenxml_supsub:
            text_part_formatted = self._extract_text_with_formatting(rng)
            text_part_formatted = text_part_formatted.replace("\r", "").replace("\x0b", "\n")
            text_part = self._sanitize_text(text_part_formatted)
        if text_part:
            segments.append(
                {
                    "kind": "text",
                    "text": text_part,
                    "text_plain": text_part_plain,
                    "range_start": rng.Start,
                    "range_end": rng.End,
                }
            )

    return segments


__all__ = ["build_segments"]
