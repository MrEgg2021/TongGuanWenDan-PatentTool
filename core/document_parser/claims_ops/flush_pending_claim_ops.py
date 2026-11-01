from __future__ import annotations

import re

from lxml import etree

from core.logging_utils import logger


def flush_pending_claim_impl(self, parent_node, force=False, claim_text_break_kind=None):
    if claim_text_break_kind is None:
        claim_text_break_kind = "__claim_text_break__"
    if not self._claims_pending_segments:
        return
    eq_display_ratio = 1.0
    try:
        cfg = getattr(self, "config", {}) or {}
        eq_display_ratio = float(cfg.get("equation_display_scale_ratio", 1.0))
    except Exception:
        eq_display_ratio = 1.0
    if not eq_display_ratio or eq_display_ratio <= 0:
        eq_display_ratio = 1.0
    eq_display_ratio = max(0.4, min(1.0, float(eq_display_ratio)))
    total_text = "".join(
        seg.get("text", "")
        for seg in self._claims_pending_segments
        if seg.get("kind") == "text"
    )
    raw_text = "".join(
        (seg.get("text_plain") if seg.get("text_plain") is not None else seg.get("text", ""))
        for seg in self._claims_pending_segments
        if seg.get("kind") == "text"
    )
    img_files = [
        seg.get("filename")
        for seg in self._claims_pending_segments
        if seg.get("kind") == "img" and seg.get("filename")
    ]
    inline_cnt = sum(
        1
        for seg in self._claims_pending_segments
        if seg.get("kind") == "img" and not seg.get("is_big")
    )
    try:
        logger.debug(
            "[CLAIM_DIAG] text_len=%d raw_len=%d inline_cnt=%d imgs=%s",
            len(total_text),
            len(raw_text),
            inline_cnt,
            img_files[:12],
        )
    except Exception:
        pass
    try:
        need_seg_diag = False
        for seg in self._claims_pending_segments:
            if seg.get("kind") == "img" and (seg.get("is_equation") or seg.get("eq_line_kind") or seg.get("is_eq_number")):
                need_seg_diag = True
                break
            if seg.get("kind") == "text" and seg.get("is_eq_number"):
                need_seg_diag = True
                break
        if need_seg_diag:
            seg_brief = []
            for seg in self._claims_pending_segments:
                kind = seg.get("kind")
                if kind == "text":
                    txt = seg.get("text") or ""
                    seg_brief.append(
                        {
                            "k": "t",
                            "txt": txt[:60],
                            "eq_num": bool(seg.get("is_eq_number")),
                        }
                    )
                elif kind == "img":
                    seg_brief.append(
                        {
                            "k": "i",
                            "file": seg.get("filename"),
                            "eq": bool(seg.get("is_equation")),
                            "big": bool(seg.get("is_big")),
                            "line": seg.get("eq_line_kind"),
                        }
                    )
                else:
                    seg_brief.append({"k": str(kind)})
            logger.debug("[CLAIM_SEGMENTS] count=%d", len(seg_brief))
    except Exception:
        pass
    text_len = len(total_text)
    text_seg_count = 0
    for seg in self._claims_pending_segments:
        if seg.get("kind") == "text":
            text_seg_count += 1
    other_seg_count = len(self._claims_pending_segments) - text_seg_count
    if not force:
        logger.debug(
            "[CLAIM_SKIP_FLUSH] force=%s text_len=%d text_segments=%d other_segments=%d",
            force,
            text_len,
            text_seg_count,
            other_seg_count,
        )
        return
    logger.debug(
        "[CLAIM_FLUSH] force=%s text_len=%d text_segments=%d other_segments=%d",
        force,
        text_len,
        text_seg_count,
        other_seg_count,
    )
    claim_range_start = None
    try:
        for seg in self._claims_pending_segments:
            if isinstance(seg, dict) and seg.get("range_start") is not None:
                try:
                    rs = int(seg.get("range_start"))
                except (TypeError, ValueError):
                    continue
                if claim_range_start is None or rs < claim_range_start:
                    claim_range_start = rs
    except Exception:
        claim_range_start = None
    # 为当前权利要求创建第一个 <claim-text> 段落
    claim_num_attr = None
    try:
        pending_num = getattr(self, "_claims_pending_num", None)
        if pending_num is not None:
            claim_num_attr = str(int(pending_num))
    except Exception:
        claim_num_attr = None
    content_node = self.xml.create_paragraph(parent_node, text=None, num=claim_num_attr, is_claim=True)
    current_text_node = content_node
    claim_node = current_text_node.getparent()
    last_node = None
    pending_new_claim_text = False
    pending_eq_with_num_spaces = 0
    pending_eq_with_num_img_node = None

    def _has_current_content() -> bool:
        return (
            (current_text_node.text is not None and current_text_node.text != "")
            or len(current_text_node) > 0
            or last_node is not None
        )

    def _maybe_break_before_content() -> None:
        nonlocal current_text_node, last_node, pending_new_claim_text
        if not pending_new_claim_text:
            return
        if claim_node is None:
            pending_new_claim_text = False
            return
        if _has_current_content():
            current_text_node = etree.SubElement(claim_node, "claim-text")
            last_node = None
        pending_new_claim_text = False

    try:
        if claim_range_start is not None and claim_node is not None:
            claim_num = claim_node.get("num")
            self._claim_ranges.append({"range_start": claim_range_start, "num": claim_num})
            try:
                claim_id = claim_node.get("id")
            except Exception:
                claim_id = None
            logger.debug(
                "[CLAIM_FLUSH_RESULT] force=%s claim_id=%r claim_num=%r range_start=%r",
                force,
                claim_id,
                claim_num,
                claim_range_start,
            )
    except Exception:
        pass

    for seg_idx, seg in enumerate(self._claims_pending_segments):
        if seg.get("kind") == claim_text_break_kind:
            pending_new_claim_text = True
            continue

        if seg.get("kind") == "text":
            text_value = seg.get("text") or ""

            if "\n" in text_value:
                chunks = text_value.split("\n")
                for ci, chunk in enumerate(chunks):
                    if ci > 0:
                        pending_new_claim_text = True
                    if chunk == "" and ci < len(chunks) - 1:
                        continue
                    if chunk != "":
                        _maybe_break_before_content()
                        last_node = self._append_text_to_node(
                            current_text_node,
                            last_node,
                            chunk,
                            allow_br=False,
                        )
                continue

            if text_value != "":
                _maybe_break_before_content()

            if seg.get("is_eq_number") and claim_node is not None:
                # 公式编号文本：需要保证编号与公式同一行，而编号后的正文（如“其中，...”）单独起一行
                m = re.search(r"[（(]\d+[)）]", text_value)
                if m:
                    prefix = text_value[: m.start()]
                    num_text = text_value[m.start() : m.end()]
                    tail = text_value[m.end() :]

                    if prefix and prefix.strip() != "":
                        last_node = self._append_text_to_node(
                            current_text_node,
                            last_node,
                            prefix,
                            allow_br=False,
                        )

                    if (
                        pending_eq_with_num_spaces
                        and pending_eq_with_num_img_node is not None
                        and last_node is pending_eq_with_num_img_node
                        and getattr(pending_eq_with_num_img_node, "tag", None) == "img"
                        and ((not prefix) or prefix.strip() == "")
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

                    # 编号本身留在当前 <claim-text>，与前面的公式图片同一行
                    last_node = self._append_text_to_node(
                        current_text_node,
                        last_node,
                        num_text,
                        allow_br=False,
                    )

                    # 编号后的内容必须强制另起一行，避免后续正文被排在编号右侧。
                    # - 若 tail 有正文：写入新 <claim-text>
                    # - 若 tail 为空但后续仍有内容段：同样先新起 <claim-text>，让后续段落从新行开始
                    need_newline = False
                    if tail and tail.strip():
                        need_newline = True
                    else:
                        for rest in self._claims_pending_segments[seg_idx + 1 :]:
                            if rest.get("kind") == "img":
                                need_newline = True
                                break
                            if rest.get("kind") == "text":
                                rest_txt = rest.get("text") or ""
                                if rest_txt.strip() != "":
                                    need_newline = True
                                    break

                    if need_newline:
                        current_text_node = etree.SubElement(claim_node, "claim-text")
                        last_node = None

                    if tail and tail.strip():
                        last_node = self._append_text_to_node(
                            current_text_node,
                            last_node,
                            tail.lstrip(),
                            allow_br=False,
                        )
                    continue

            # 普通文本或未命中编号模式的文本，直接追加到当前 <claim-text>
            last_node = self._append_text_to_node(
                current_text_node,
                last_node,
                text_value,
                allow_br=False,
            )
        else:
            _maybe_break_before_content()
            is_eq_with_num = seg.get("eq_line_kind") == "claim_eq_with_num"
            is_big = bool(seg.get("is_big"))
            w_mm = seg.get("width_mm")
            h_mm = seg.get("height_mm")
            if (
                eq_display_ratio != 1.0
                and seg.get("is_equation")
                and not seg.get("_eq_center_padded")
            ):
                try:
                    w_mm = float(w_mm) * eq_display_ratio
                    h_mm = float(h_mm) * eq_display_ratio
                except Exception:
                    w_mm = seg.get("width_mm")
                    h_mm = seg.get("height_mm")
            if is_eq_with_num and claim_node is not None:
                # 公式+编号整行：独立占用一个 <claim-text>，图片保持行内，使编号与公式同一行
                has_content = (
                    (current_text_node.text is not None and current_text_node.text != "")
                    or len(current_text_node) > 0
                    or last_node is not None
                )
                if has_content:
                    current_text_node = etree.SubElement(claim_node, "claim-text")
                    last_node = None

                img_node = self.xml.create_image_node(
                    current_text_node,
                    seg["filename"],
                    w_mm,
                    h_mm,
                    img_type="desc",
                    inline=True,
                )
                last_node = img_node
                pending_eq_with_num_spaces = 3
                pending_eq_with_num_img_node = img_node
            elif is_big and claim_node is not None:
                # 大公式图片：单独放入一个新的 <claim-text> 段落中，块级显示
                has_content = (
                    (current_text_node.text is not None and current_text_node.text != "")
                    or len(current_text_node) > 0
                    or last_node is not None
                )
                if has_content:
                    # 当前位置之前已有文本/节点，先新起一个 <claim-text> 放公式
                    current_text_node = etree.SubElement(claim_node, "claim-text")
                    last_node = None

                img_node = self.xml.create_image_node(
                    current_text_node,
                    seg["filename"],
                    w_mm,
                    h_mm,
                    img_type="desc",
                    inline=False,
                )
                last_node = img_node

                # 公式后续的文字另起一个新的 <claim-text>
                current_text_node = etree.SubElement(claim_node, "claim-text")
                last_node = None
            else:
                # 普通小图仍按原逻辑追加到当前 <claim-text> 中
                inline_flag = not is_big
                img_node = self.xml.create_image_node(
                    current_text_node,
                    seg["filename"],
                    w_mm,
                    h_mm,
                    img_type="desc",
                    inline=inline_flag,
                )
                last_node = img_node

    self._claims_pending_segments = []
    try:
        self._claims_pending_num = None
    except Exception:
        pass
