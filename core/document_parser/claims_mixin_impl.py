from __future__ import annotations

import re

from lxml import etree

from core.logging_utils import logger

from .claims_ops.flush_pending_claim_ops import flush_pending_claim_impl


_SUBSCRIPT_CHAR_MAP = {
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "₃": "3",
    "₄": "4",
    "₅": "5",
    "₆": "6",
    "₇": "7",
    "₈": "8",
    "₉": "9",
    "₊": "+",
    "₋": "-",
    "₌": "=",
    "₍": "(",
    "₎": ")",
    "ₐ": "a",
    "ₑ": "e",
    "ₕ": "h",
    "ᵢ": "i",
    "ⱼ": "j",
    "ₖ": "k",
    "ₗ": "l",
    "ₘ": "m",
    "ₙ": "n",
    "ₒ": "o",
    "ₚ": "p",
    "ᵣ": "r",
    "ₛ": "s",
    "ₜ": "t",
    "ᵤ": "u",
    "ᵥ": "v",
    "ₓ": "x",
}


_CLAIM_TEXT_BREAK_KIND = "__claim_text_break__"
_CLAIM_PERIOD = "\u3002"

_SUPERSCRIPT_CHAR_MAP = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
    "⁺": "+",
    "⁻": "-",
    "⁼": "=",
    "⁽": "(",
    "⁾": ")",
    "ⁿ": "n",
    "ⁱ": "i",
}


class ClaimsMixin:
    def _sanitize_text(self, text):
        """清洗文本，移除 XML 不允许的控制字符"""
        if not text:
            return ""
        # 保留常规可见字符和制表/换行，剔除 0x20 以下的控制符
        return "".join(ch for ch in text if (ch in ('\t', '\n') or ord(ch) >= 0x20))

    def _convert_unicode_supsub_to_tags(self, text: str) -> str:
        if not text:
            return text

        has_any = False
        for ch in text:
            if ch in _SUBSCRIPT_CHAR_MAP or ch in _SUPERSCRIPT_CHAR_MAP:
                has_any = True
                break
        if not has_any:
            return text

        out_parts: list[str] = []
        buf: list[str] = []
        mode: str | None = None

        def _flush() -> None:
            nonlocal buf, mode
            if not buf:
                return
            content = "".join(buf)
            if mode == "sub":
                out_parts.append(f"<sub>{content}</sub>")
            elif mode == "sup":
                out_parts.append(f"<sup>{content}</sup>")
            else:
                out_parts.append(content)
            buf = []
            mode = None

        for ch in text:
            if ch in _SUBSCRIPT_CHAR_MAP:
                if mode != "sub":
                    _flush()
                    mode = "sub"
                buf.append(_SUBSCRIPT_CHAR_MAP[ch])
                continue
            if ch in _SUPERSCRIPT_CHAR_MAP:
                if mode != "sup":
                    _flush()
                    mode = "sup"
                buf.append(_SUPERSCRIPT_CHAR_MAP[ch])
                continue

            _flush()
            out_parts.append(ch)

        _flush()
        return "".join(out_parts)

    def _append_text_to_node(self, container, last_node_ref, text_value, allow_br: bool = True):
        if not text_value:
            return last_node_ref

        # 预处理：将 "*" 替换为 "×" 的逻辑移到片段处理中，或者全局处理（只要不破坏标签）
        # 但由于 text_value 现在可能包含 html 标签，为了安全，还是在拆分后处理内容部分
        
        # 使用正则拆分文本和标签
        # 匹配 <sub>...</sub> 或 <sup>...</sup>
        # 使用捕获组 () 使得 split 保留分隔符（即标签本身）
        parts = re.split(r'(<(?:sub|sup)>.*?</(?:sub|sup)>)', text_value)
        expanded_parts = []
        for part in parts:
            if not part:
                continue
            if re.match(r'<(sub|sup)>.*?</\1>', part):
                expanded_parts.append(part)
                continue
            converted = self._convert_unicode_supsub_to_tags(part)
            if converted != part:
                expanded_parts.extend(
                    p
                    for p in re.split(r'(<(?:sub|sup)>.*?</(?:sub|sup)>)', converted)
                    if p
                )
            else:
                expanded_parts.append(part)
        parts = expanded_parts
        
        current_last_node = last_node_ref

        def _append_plain_with_breaks(target_container, target_last_node, plain_text: str | None):
            if plain_text is None:
                return target_last_node
            # 仅处理段内手工换行：外层调用方已将 \x0b / w:br 归一为 \n。
            # 这里将 \n 映射为 DTD 支持的 <br/>。
            if not allow_br:
                chunks = [plain_text]
            else:
                chunks = plain_text.split("\n")
            last = target_last_node
            for idx, chunk in enumerate(chunks):
                if chunk:
                    if last is None:
                        if target_container.text:
                            target_container.text += chunk
                        else:
                            target_container.text = chunk
                    else:
                        if last.tail:
                            last.tail += chunk
                        else:
                            last.tail = chunk
                if allow_br and idx < len(chunks) - 1:
                    br_node = etree.SubElement(target_container, "br")
                    last = br_node
            return last

        for part in parts:
            if not part:
                continue

            # 检查是否为标签片段
            tag_match = re.match(r'<(sub|sup)>(.*?)</\1>', part)
            
            if tag_match:
                tag_name = tag_match.group(1)
                content = tag_match.group(2)
                
                # 对标签内部文本进行清洗处理（如乘号替换）
                content = re.sub(r'(?<=\S)\s*\*\s*(?=\S)', '×', content)
                
                # 创建子节点 <sub> 或 <sup>
                # 注意：SubElement 会自动追加到 container 的末尾
                # 但我们需要确保逻辑上的顺序。如果 current_last_node 存在，
                # 说明前面有文本或节点。SubElement 总是 append 到 children list。
                # 由于我们在遍历 segments 也是顺序的，这里直接 append 是安全的。
                
                # 这里有一个细节：如果之前的 text 是加在 last_node.tail 上的，
                # 那么 SubElement 添加的新节点会在 last_node 之后（同级）。
                # 符合预期：<p>text<last/>text<sub>...</sub></p>
                
                new_node = etree.SubElement(container, tag_name)
                _append_plain_with_breaks(new_node, None, content)
                
                # 更新 last_node 指针，后续文本将追加到这个新节点的 tail
                current_last_node = new_node
                
            else:
                # 普通文本片段
                # 处理乘号替换
                part_text = re.sub(r'(?<=\S)\s*\*\s*(?=\S)', '×', part)

                current_last_node = _append_plain_with_breaks(container, current_last_node, part_text)
                        
        return current_last_node

    def _append_claim_segments(self, parent_node, segments, is_new_start=False, claim_num: int | None = None):
        if not segments:
            return

        # 结合显式 claim_num 做“单调递增”的新起始判定，避免把正文里的内部编号误识别为新 claim
        pending_num = getattr(self, "_claims_pending_num", None)
        try:
            pending_num_int = int(pending_num) if pending_num is not None else None
        except Exception:
            pending_num_int = None

        claim_num_int = None
        if claim_num is not None:
            try:
                claim_num_int = int(claim_num)
            except Exception:
                claim_num_int = None

        effective_new_start = bool(is_new_start)
        if claim_num_int is not None and pending_num_int is not None:
            # 新 claim 号码应当单调递增；小于等于当前号码视为正文内部编号，禁止触发 flush
            if claim_num_int > pending_num_int:
                effective_new_start = True
            else:
                effective_new_start = False

        # 遇到新的编号起始段且已有未刷新的缓存，说明上一条权利要求已结束，
        # 需要先将其强制刷新为一个 <claim>。
        if effective_new_start and self._claims_pending_segments:
            logger.debug(
                "[CLAIM_FLUSH_PRE] reason=new_start pending_segments=%d",
                len(self._claims_pending_segments),
            )
            self._flush_pending_claim(parent_node, force=True)

        # 建立/更新当前 pending 的 claim 号码（用于 create_paragraph(num=...)）
        if claim_num_int is not None:
            try:
                if effective_new_start or getattr(self, "_claims_pending_num", None) is None:
                    self._claims_pending_num = claim_num_int
            except Exception:
                pass

        def _split_segments_by_period(parts):
            period = _CLAIM_PERIOD
            groups = []
            current = []
            for seg in parts:
                if seg.get("kind") != "text":
                    current.append(seg)
                    continue
                text_val = seg.get("text") or ""
                plain_val = seg.get("text_plain")
                if period not in text_val:
                    current.append(seg)
                    continue
                text_chunks = text_val.split(period)
                plain_chunks = plain_val.split(period) if isinstance(plain_val, str) else None
                for idx, chunk in enumerate(text_chunks):
                    is_last = idx == (len(text_chunks) - 1)
                    if not is_last:
                        new_seg = dict(seg)
                        new_seg["text"] = f"{chunk}{period}"
                        if plain_chunks is not None:
                            try:
                                plain_piece = plain_chunks[idx]
                            except Exception:
                                plain_piece = chunk
                            new_seg["text_plain"] = f"{plain_piece}{period}"
                        current.append(new_seg)
                        groups.append((current, True))
                        current = []
                    else:
                        if chunk:
                            new_seg = dict(seg)
                            new_seg["text"] = chunk
                            if plain_chunks is not None:
                                try:
                                    plain_piece = plain_chunks[idx]
                                except Exception:
                                    plain_piece = chunk
                                new_seg["text_plain"] = plain_piece
                            current.append(new_seg)
            if current:
                groups.append((current, False))
            return groups

        segment_groups = _split_segments_by_period(segments)
        for group_idx, (group, ends_with_period) in enumerate(segment_groups):
            if not group:
                if ends_with_period:
                    logger.debug("[CLAIM_FLUSH_PRE] reason=period empty_group=%s", group_idx)
                    self._flush_pending_claim(parent_node, force=True)
                continue
            if self._claims_pending_segments:
                self._claims_pending_segments.append({"kind": _CLAIM_TEXT_BREAK_KIND})
            self._claims_pending_segments.extend(group)

            logger.debug(
                "[CLAIM_BUFFER] pending_segments=%d is_new_start=%s",
                len(self._claims_pending_segments),
                effective_new_start,
            )

            if ends_with_period:
                logger.debug("[CLAIM_FLUSH_PRE] reason=period pending_segments=%d", len(self._claims_pending_segments))
                next_claim_num_base = None
                try:
                    cur_num = getattr(self, "_claims_pending_num", None)
                    if cur_num is not None:
                        next_claim_num_base = int(cur_num)
                except Exception:
                    next_claim_num_base = None
                self._flush_pending_claim(parent_node, force=True)
                if next_claim_num_base is not None:
                    try:
                        self._claims_pending_num = int(next_claim_num_base) + 1
                        logger.debug(
                            "[CLAIM_NUM_INC] reason=period from=%s to=%s",
                            int(next_claim_num_base),
                            int(next_claim_num_base) + 1,
                        )
                    except Exception:
                        pass

    def _flush_pending_claim(self, parent_node, force=False):
        return flush_pending_claim_impl(
            self,
            parent_node,
            force=force,
            claim_text_break_kind=_CLAIM_TEXT_BREAK_KIND,
        )
