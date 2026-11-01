import re

from core.logging_utils import logger

def write_segments(self, para, parent_node, segments, *, is_claim: bool):
    if not segments:
        return

    if is_claim:
        detected_claim_num = None
        detected_from_text = False

        # 1) 优先用 Word 的 ListString（如果存在）
        list_marker = ""
        try:
            if hasattr(self, "_get_list_marker"):
                list_marker = str(self._get_list_marker(para) or "")
        except Exception:
            list_marker = ""
        if list_marker:
            m = re.search(r"\d+", list_marker)
            if m:
                try:
                    detected_claim_num = int(m.group())
                except Exception:
                    detected_claim_num = None

        # 2) ListString 不可用则回退到文本前缀（兼容“13、…”/“12.” 等）
        first_text_seg = None
        for seg in segments:
            if seg.get("kind") == "text":
                first_text_seg = seg
                break
        # claims-only 前缀识别：编号分隔符后不能紧跟数字，避免将 3.5% 误判为 "3."
        common_prefix_re = r"^[\s\ufeff\u200b\u200c\u200d\u2060\u200e\u200f]*(\d+)\s*[\.．、\)）](?!\s*\d)"
        if first_text_seg is not None and detected_claim_num is None:
            original_text = first_text_seg.get("text_plain") or first_text_seg.get("text") or ""
            m = re.match(common_prefix_re, original_text)
            if m:
                try:
                    detected_claim_num = int(m.group(1))
                    detected_from_text = True
                except Exception:
                    detected_claim_num = None
                    detected_from_text = False

        # 3) 单调递增判定：仅当 claim_num 大于当前 pending_num 才认为是新 claim
        pending_num = getattr(self, "_claims_pending_num", None)
        try:
            pending_num_int = int(pending_num) if pending_num is not None else None
        except Exception:
            pending_num_int = None

        is_new_numbered_start = False
        if detected_claim_num is not None:
            if pending_num_int is None or detected_claim_num > pending_num_int:
                is_new_numbered_start = True

        # 4) 来自文本前缀时，按规则决定是否从正文中移除编号前缀：
        #    - 新 claim 起始（保持既有行为）
        #    - 与 pending_num 相等且当前无待刷新的 claim 缓冲（回归场景）
        should_strip_prefix = False
        strip_reason = None
        try:
            has_pending_segments = bool(getattr(self, "_claims_pending_segments", None))
        except Exception:
            has_pending_segments = False
        if detected_from_text and first_text_seg is not None:
            if is_new_numbered_start:
                should_strip_prefix = True
                strip_reason = "new_start"
            elif (
                detected_claim_num is not None
                and pending_num_int is not None
                and int(detected_claim_num) == int(pending_num_int)
                and not has_pending_segments
            ):
                should_strip_prefix = True
                strip_reason = "equal_pending_without_buffer"
            elif (
                detected_claim_num is not None
                and pending_num_int is not None
                and int(detected_claim_num) < int(pending_num_int)
                and not has_pending_segments
            ):
                should_strip_prefix = True
                strip_reason = "lt_pending_without_buffer"

        if should_strip_prefix and first_text_seg is not None:
            original_text = first_text_seg.get("text_plain") or first_text_seg.get("text") or ""
            prefix_re = (
                rf"^[\s\ufeff\u200b\u200c\u200d\u2060\u200e\u200f]*"
                rf"{re.escape(str(detected_claim_num))}\s*[\.．、\)）](?!\s*\d)\s*"
            )
            first_text_seg["text_plain"] = re.sub(prefix_re, "", original_text)
            try:
                first_text_seg["text"] = re.sub(prefix_re, "", first_text_seg.get("text") or "")
            except Exception:
                first_text_seg["text"] = first_text_seg.get("text") or ""
            try:
                logger.debug(
                    "[CLAIM_PREFIX_STRIP] reason=%s detected=%r pending=%r",
                    strip_reason,
                    detected_claim_num,
                    pending_num_int,
                )
            except Exception:
                pass

        self._append_claim_segments(
            parent_node,
            segments,
            is_new_start=is_new_numbered_start,
            claim_num=detected_claim_num,
        )
        return

    current_p = None
    last_node = None
    pending_eq_with_num_spaces = 0
    pending_eq_with_num_img_node = None
    eq_display_ratio = 1.0
    try:
        cfg = getattr(self, "config", {}) or {}
        eq_display_ratio = float(cfg.get("equation_display_scale_ratio", 1.0))
    except Exception:
        eq_display_ratio = 1.0
    if not eq_display_ratio or eq_display_ratio <= 0:
        eq_display_ratio = 1.0
    # UI 约束：0.4 ~ 1.0；这里做一次防御性裁剪
    eq_display_ratio = max(0.4, min(1.0, float(eq_display_ratio)))

    def _ensure_paragraph(seg=None):
        nonlocal current_p, last_node
        if current_p is None:
            current_p = self.xml.create_paragraph(parent_node, text=None, is_claim=False)
            last_node = None
            parent_tag_inner = getattr(parent_node, "tag", "") or ""
            if parent_tag_inner == "description":
                try:
                    rs = None
                    if isinstance(seg, dict):
                        rs = seg.get("range_start")
                    if rs is None:
                        rs = para.Range.Start
                    rs_int = int(rs)
                    self._desc_p_positions.append({"range_start": rs_int, "p": current_p})
                except Exception:
                    pass

    parent_tag_inner = getattr(parent_node, "tag", "") or ""
    is_drawings = (parent_tag_inner == "cn-drawings")

    for seg in segments:
        if seg.get("kind") == "text":
            if is_drawings:
                if hasattr(self, "_register_drawings_label_text"):
                    try:
                        self._register_drawings_label_text(seg.get("text_plain") or seg.get("text") or "")
                    except Exception:
                        pass
                continue
            _ensure_paragraph(seg)
            if (
                parent_tag_inner in ("description", "cn-abstract")
                and seg.get("is_eq_number")
                and pending_eq_with_num_spaces
                and pending_eq_with_num_img_node is not None
                and last_node is pending_eq_with_num_img_node
                and getattr(pending_eq_with_num_img_node, "tag", None) == "img"
            ):
                try:
                    existing_tail = pending_eq_with_num_img_node.tail or ""
                    if existing_tail.strip() == "":
                        pending_eq_with_num_img_node.tail = "\u3000" * int(pending_eq_with_num_spaces)
                    else:
                        pending_eq_with_num_img_node.tail = existing_tail + ("\u3000" * int(pending_eq_with_num_spaces))
                except Exception:
                    pass

                pending_eq_with_num_spaces = 0
                pending_eq_with_num_img_node = None

                text_value = (seg.get("text") or "").lstrip()
            else:
                text_value = seg.get("text") or ""

            last_node = self._append_text_to_node(current_p, last_node, text_value)
            continue

        img_type = "draw" if is_drawings else "desc"
        if seg.get("is_big"):
            w_mm = seg["width_mm"]
            h_mm = seg["height_mm"]
            if (
                eq_display_ratio != 1.0
                and seg.get("is_equation")
                and not seg.get("_eq_center_padded")
            ):
                try:
                    w_mm = float(w_mm) * eq_display_ratio
                    h_mm = float(h_mm) * eq_display_ratio
                except Exception:
                    w_mm = seg["width_mm"]
                    h_mm = seg["height_mm"]
            block_p = self.xml.create_paragraph(parent_node, text=None, is_claim=False)
            img_node = self.xml.create_image_node(
                block_p,
                seg["filename"],
                w_mm,
                h_mm,
                img_type=img_type,
                inline=False,
            )
            if is_drawings and hasattr(self, "_register_drawings_image_node"):
                try:
                    self._register_drawings_image_node(img_node)
                except Exception:
                    pass
            if parent_tag_inner == "description":
                try:
                    rs = seg.get("range_start")
                    if rs is None:
                        rs = para.Range.Start
                    rs_int = int(rs)
                    self._desc_p_positions.append({"range_start": rs_int, "p": block_p})
                except Exception:
                    pass
            current_p = None
            last_node = None
        else:
            _ensure_paragraph(seg)
            w_mm = seg["width_mm"]
            h_mm = seg["height_mm"]
            if (
                eq_display_ratio != 1.0
                and seg.get("is_equation")
                and not seg.get("_eq_center_padded")
            ):
                try:
                    w_mm = float(w_mm) * eq_display_ratio
                    h_mm = float(h_mm) * eq_display_ratio
                except Exception:
                    w_mm = seg["width_mm"]
                    h_mm = seg["height_mm"]
            img_node = self.xml.create_image_node(
                current_p,
                seg["filename"],
                w_mm,
                h_mm,
                img_type=img_type,
                inline=True,
            )
            if is_drawings and hasattr(self, "_register_drawings_image_node"):
                try:
                    self._register_drawings_image_node(img_node)
                except Exception:
                    pass
            last_node = img_node
            if (
                parent_tag_inner in ("description", "cn-abstract")
                and seg.get("is_equation")
                and seg.get("eq_line_kind") == "desc_eq_with_num"
            ):
                pending_eq_with_num_spaces = 1 if parent_tag_inner == "description" else 3
                pending_eq_with_num_img_node = img_node


__all__ = ["write_segments"]
