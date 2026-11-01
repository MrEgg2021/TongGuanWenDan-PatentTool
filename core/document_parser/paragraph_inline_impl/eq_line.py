import re


def detect_visual_eq_lines_in_raw(self, raw_text_full):
    if not raw_text_full:
        return []

    lines = []
    start = 0
    n = len(raw_text_full)
    for i, ch in enumerate(raw_text_full):
        if ch in ("\x0b", "\r"):
            if i > start:
                lines.append((start, i))
            start = i + 1
    if start < n:
        lines.append((start, n))

    result = []
    for ls, le in lines:
        snippet = raw_text_full[ls:le]
        if "\x01" not in snippet:
            continue
        tmp = snippet.replace("\x01", " ")
        visible = self._sanitize_text(tmp).strip()
        if visible == "":
            result.append((ls, le))
            continue
        if re.fullmatch(r"[（(]?\s*\d+\s*[)）]?", visible):
            result.append((ls, le))
    return result


def merge_visual_eq_line(
    self,
    para,
    segments,
    raw_text_full,
    is_claim,
    parent_node=None,
    section_key: str | None = None,
    allow_merge_with_num=True,
    allow_pure_line=False,
):
    if not raw_text_full or not segments:
        return segments, False

    eq_lines = self._detect_visual_eq_lines_in_raw(raw_text_full)
    if len(eq_lines) != 1:
        return segments, False

    eq_idx = None
    for i, seg in enumerate(segments):
        if seg.get("kind") == "img" and seg.get("is_equation"):
            eq_idx = i
            break

    if eq_idx is None:
        return segments, False

    eq_seg_orig = segments[eq_idx]
    eq_start = eq_seg_orig.get("range_start")
    eq_end = eq_seg_orig.get("range_end")
    if eq_start is None or eq_end is None:
        return segments, False

    num_idx = None
    num_start_abs = None
    num_end_abs = None

    num_pattern = re.compile(r"[（(]\d+[)）]")

    for j in range(eq_idx + 1, len(segments)):
        seg = segments[j]
        if seg.get("kind") != "text":
            continue

        txt = seg.get("text_plain") or seg.get("text") or ""
        m = num_pattern.search(txt)
        if not m:
            continue

        prefix = txt[: m.start()]
        if prefix.strip() != "":
            continue

        rs = seg.get("range_start")
        re_ = seg.get("range_end")
        if rs is None or re_ is None:
            continue

        num_rng_full = self.word.doc.Range(rs, re_)
        raw_text = num_rng_full.Text or ""
        if not raw_text:
            continue

        rel = raw_text.find(txt)
        if rel < 0:
            continue

        num_start_abs = rs + rel + m.start()
        num_end_abs = rs + rel + m.end()
        num_idx = j
        break

    if num_idx is None or num_start_abs is None or num_end_abs is None:
        if allow_pure_line:
            eq_seg_orig["is_big"] = True
            return segments, True
        return segments, False

    if not allow_merge_with_num:
        eq_candidates = []
        for idx, seg in enumerate(segments):
            if seg.get("kind") == "img" and seg.get("is_equation"):
                rs = seg.get("range_start")
                re_ = seg.get("range_end")
                if rs is None or re_ is None:
                    continue
                if num_start_abs is not None and rs >= num_start_abs:
                    continue
                if num_start_abs is not None and re_ > num_start_abs:
                    continue
                eq_candidates.append((idx, rs, re_))

        if len(eq_candidates) >= 2:
            eq_candidates.sort(key=lambda x: x[1])
            eq_start_abs = eq_candidates[0][1]
            eq_end_abs = max(item[2] for item in eq_candidates)

            try:
                eq_rng = self.word.doc.Range(eq_start_abs, eq_end_abs)
            except Exception:
                return segments, False

            filename, width_mm, height_mm = self._screenshot_range(
                eq_rng,
                parent_node=parent_node,
                is_equation=True,
            )
            if not filename:
                return segments, False

            eq_seg = {
                "kind": "img",
                "filename": filename,
                "width_mm": width_mm,
                "height_mm": height_mm,
                "is_equation": True,
                "is_big": False,
                "range_start": eq_start_abs,
                "range_end": eq_end_abs,
            }

            new_segments = []
            inserted = False
            eq_indices = {idx for idx, _, _ in eq_candidates}
            for idx, seg in enumerate(segments):
                if idx in eq_indices:
                    if not inserted:
                        new_segments.append(eq_seg)
                        inserted = True
                    continue
                new_segments.append(seg)

            return new_segments, True

        return segments, False

    try:
        line_rng = self.word.doc.Range(min(eq_start, num_start_abs), max(eq_end, num_end_abs))
    except Exception:
        return segments, False

    filename, width_mm, height_mm = self._screenshot_range(
        line_rng,
        parent_node=parent_node,
        is_equation=True,
    )
    if not filename:
        return segments, False

    line_start_abs = line_rng.Start
    line_end_abs = line_rng.End

    pre_segments = []
    post_segments = []

    for idx, seg in enumerate(segments):
        if idx < eq_idx:
            pre_segments.append(seg)
        elif idx > num_idx:
            post_segments.append(seg)
        elif idx == num_idx:
            rs = seg.get("range_start")
            re_ = seg.get("range_end")
            if rs is None or re_ is None:
                continue

            try:
                tail_rng = self.word.doc.Range(num_end_abs, re_)
                tail_text = tail_rng.Text.replace("\r", "").replace("\x0b", "\n")
                tail_text = self._sanitize_text(tail_text)
            except Exception:
                tail_text = ""

            if tail_text:
                post_segments.append(
                    {
                        "kind": "text",
                        "text": tail_text,
                        "range_start": tail_rng.Start,
                        "range_end": tail_rng.End,
                    }
                )

    eq_seg = {
        "kind": "img",
        "filename": filename,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "is_equation": True,
        "is_big": True,
        "range_start": line_start_abs,
        "range_end": line_end_abs,
    }

    new_segments = pre_segments + [eq_seg] + post_segments
    return new_segments, True


__all__ = ["detect_visual_eq_lines_in_raw", "merge_visual_eq_line"]
