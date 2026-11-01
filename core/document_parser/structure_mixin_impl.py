from __future__ import annotations

import re

from lxml import etree

from core.patent_type_resolution import get_default_disclosure_heading, is_patent_type_disclosure_heading


class StructureNormalizationMixin:
    def _normalize_description_structure(self):
        """将 <description> 重写为官方推荐结构，便于客户端解析。

        目标结构示例：
        <description>
          <invention-title id="t0001">标题</invention-title>
          <technical-field><heading/>+<p>...</p></technical-field>
          <background-art>...</background-art>
          <disclosure>...</disclosure>
          <description-of-drawings>...</description-of-drawings>
          <mode-for-invention>...</mode-for-invention>
        </description>
        """

        desc_root = self.sections.get("description")
        if desc_root is None:
            return

        # 若已经是分块结构（存在 invention-title 或 technical-field 等），则不再二次重写
        if desc_root.find("invention-title") is not None or desc_root.find("technical-field") is not None:
            return

        # 仅处理直接子节点中的 <p>
        ps = [child for child in list(desc_root) if child.tag == "p"]
        if not ps:
            return

        # 首段视为发明名称
        first_p = ps[0]
        title_text = (first_p.text or "").strip()
        try:
            desc_root.remove(first_p)
        except Exception:
            pass

        invention_title = etree.Element("invention-title")
        invention_title.set("id", "t0001")
        invention_title.text = title_text
        try:
            for child in list(first_p):
                try:
                    first_p.remove(child)
                except Exception:
                    pass
                invention_title.append(child)
        except Exception:
            pass
        try:
            if first_p.text and first_p.text.strip():
                pass
            elif first_p.text:
                invention_title.text = (invention_title.text or "") + first_p.text
        except Exception:
            pass
        try:
            if first_p.tail:
                invention_title.tail = (invention_title.tail or "") + first_p.tail
        except Exception:
            pass
        desc_root.insert(0, invention_title)

        # 将其余段落从根节点中移出，后续按块重新挂载
        remaining_ps = ps[1:]
        for p in remaining_ps:
            try:
                if p.getparent() is desc_root:
                    desc_root.remove(p)
            except Exception:
                continue

        # 小节映射：tag_name -> 关键词列表
        # 这里将“发明内容 / 技术方案 / 有益效果”都映射为 disclosure，小节之间按顺序生成多个 <disclosure> 区块
        section_specs = [
            ("technical-field", ["技术领域"]),
            ("background-art", ["背景技术"]),
            ("disclosure", ["发明内容", "实用新型内容", "技术方案", "有益效果"]),
            ("description-of-drawings", ["附图说明"]),
            ("mode-for-invention", ["具体实施方式", "具体实施例", "实施例"]),
        ]

        blocks: dict[str, etree._Element] = {}
        current_block = None
        heading_index = 1
        mode_block_heading = "具体实施方式"

        default_disclosure_heading = get_default_disclosure_heading(getattr(self, "patent_type", None))

        def _start_block(tag_name, heading_key):
            nonlocal current_block, heading_index
            heading_created = False
            block = blocks.get(tag_name)
            if block is None:
                block = etree.SubElement(desc_root, tag_name)
                blocks[tag_name] = block
                heading_created = True

            if heading_created:
                heading = etree.SubElement(
                    block,
                    "heading",
                    id=f"h{heading_index:04d}",
                    level="2",
                )
                # 默认使用标准关键字作为 heading 文本；
                # 对“具体实施方式”统一采用规范标题，避免带入整段正文。
                if tag_name == "mode-for-invention":
                    heading.text = mode_block_heading
                elif tag_name == "disclosure":
                    if is_patent_type_disclosure_heading(heading_key):
                        heading.text = default_disclosure_heading
                    else:
                        heading.text = heading_key
                else:
                    heading.text = heading_key
                heading_index += 1
            current_block = block
            return heading_created

        def _strip_heading_prefix(text: str) -> str:
            """去掉常见段首编号/序号前缀，保留后续正文。"""
            if not text:
                return text
            # 常见模式示例： [0001]、【0001】、(0001)、0001.、0001、 一、 （一） 1. 1、等
            patterns = [
                r"^[\s\u3000]*[\[\(（【]?\s*[0-9０-９]{1,4}\s*[\]\)）】]?\s*[\.．、]?\s*",
                r"^[\s\u3000]*[一二三四五六七八九十]+[\.．、]\s*",
                r"^[\s\u3000]*（[一二三四五六七八九十]+）\s*",
            ]
            stripped = text
            for pat in patterns:
                new_val = re.sub(pat, "", stripped, count=1)
                if new_val != stripped:
                    stripped = new_val
                    break
            return stripped.lstrip(" \t\u3000")

        def _append_remainder_as_paragraph(block, remainder_text: str):
            """选项B：若标题后还有正文，保留为正文段落。"""
            if not remainder_text or block is None:
                return
            try:
                self.xml.create_paragraph(block, text=remainder_text)
            except Exception:
                # 理论上不会进入此分支，兜底保持兼容
                new_p = etree.SubElement(block, "p")
                new_p.text = remainder_text

        for p in remaining_ps:
            full_text = "".join([t for t in p.itertext() if t])  # 包含子节点文本，避免 p.text 为空导致漏识别
            text_for_match = (full_text or "").strip()
            matched = False
            if text_for_match:
                norm = _strip_heading_prefix(text_for_match)
                for tag_name, keywords in section_specs:
                    for kw in keywords:
                        if norm.startswith(kw):
                            heading_created = _start_block(tag_name, kw)
                            matched = True
                            if heading_created:
                                remainder = norm[len(kw) :].lstrip(" :：-—\t\u3000")
                            else:
                                remainder = text_for_match
                            _append_remainder_as_paragraph(current_block, remainder)
                            break
                    if matched:
                        break
            if matched:
                # 标题段落本身不再作为 <p> 输出
                continue

            if current_block is None:
                # 若在任何标题前就出现正文，默认归入 "disclosure"
                _start_block("disclosure", default_disclosure_heading)
            current_block.append(p)

    def _normalize_drawings_structure(self):
        """将 <cn-drawings> 内部从若干 <p><img/></p> 重写为 <figure><img/></figure> 结构。"""

        draw_root = self.sections.get("drawings")
        if draw_root is None:
            return

        # 若已经存在 figure 结构，则认为已符合 DTD/样例，直接跳过
        if draw_root.find("figure") is not None:
            return

        imgs = [img for img in list(draw_root.iter("img")) if img.get("file")]
        if not imgs:
            return

        # 清空原有子节点（包括 <p> 文本 "图1" 等），这些说明信息已在说明书的 "附图说明" 中体现
        for child in list(draw_root):
            draw_root.remove(child)

        placeholder = "图号缺失"
        labels_map = getattr(self, "_drawings_img_label_by_id", None)
        if not isinstance(labels_map, dict):
            labels_map = {}
        file_labels_map = getattr(self, "_drawings_img_label_by_file", None)
        if not isinstance(file_labels_map, dict):
            file_labels_map = {}

        for idx, img in enumerate(imgs, 1):
            fig = etree.SubElement(
                draw_root,
                "figure",
                id=f"f{idx:04d}",
                num=f"{idx:04d}",
            )
            label_val = None
            try:
                label_val = file_labels_map.get(str(img.get("file") or "").strip())
            except Exception:
                label_val = None
            if not isinstance(label_val, str) or not label_val.strip():
                try:
                    label_val = labels_map.get(id(img))
                except Exception:
                    label_val = None
            if not isinstance(label_val, str) or not label_val.strip():
                label_val = placeholder
            fig.set("figure-labels", str(label_val))
            # 清理 img 尾部残留的文本（例如原段落中的“图1”、“图2”），避免在 figure 内部重复展示
            try:
                img.tail = None
            except Exception:
                pass
            parent = img.getparent()
            if parent is not None:
                try:
                    parent.remove(img)
                except Exception:
                    pass
            fig.append(img)

    def _renumber_description_paragraphs(self):
        """按阅读顺序重新编号 <description> 内所有 <p> 的 num 属性。

        官方样例中：
        - 小节标题使用 <heading id="h0001" level="2">，不带 num；
        - 真正正文段落使用 <p id="p0003" num="0001">，num 从 0001 开始连续递增。

        我们在生成初始 <p> 时用 p 的流水号推导 num（p0003 -> num=0003），
        再经过 _normalize_description_structure 重写结构后，会导致前面的若干 p
        被转换/删除，但 num 不会自动回退，造成首段从 0003 开始的问题。

        这里在结构规范化完成后，统一对 <description> 下的所有 <p> 重新编号，
        确保标题不参与段号计数。
        """
        desc_root = self.sections.get("description")
        if desc_root is None:
            return

        split_mode = getattr(self, "description_paragraph_split_mode", "word")
        mode = None
        try:
            mode = str(split_mode).lower()
        except Exception:
            mode = "word"

        if mode not in ("period", "word_period_end"):
            counter = 0
            for p in desc_root.iter("p"):
                try:
                    if p.get("num") == "XXXX":
                        continue
                    counter += 1
                    p.set("num", f"{counter:04d}")
                except Exception:
                    # 个别异常不影响整体编号流程
                    continue
            return

        def _is_blank_text(val: object) -> bool:
            if val is None:
                return True
            try:
                return not str(val).strip()
            except Exception:
                return True

        def _is_empty_paragraph(p_node: etree._Element) -> bool:
            try:
                if not _is_blank_text(p_node.text):
                    return False
            except Exception:
                return False
            for child in list(p_node):
                if getattr(child, "tag", None) == "img":
                    return False
                try:
                    if not _is_blank_text(child.tail):
                        return False
                except Exception:
                    return False
            return True

        def _contains_block_img(p_node: etree._Element) -> bool:
            try:
                for img in p_node.iter("img"):
                    try:
                        if img.get("inline") != "yes":
                            return True
                    except Exception:
                        return True
            except Exception:
                return False
            return False

        def _is_image_only_block_paragraph(p_node: etree._Element) -> bool:
            try:
                if not _is_blank_text(p_node.text):
                    return False
            except Exception:
                return False

            children = list(p_node)
            if not children:
                return False

            for child in children:
                if getattr(child, "tag", None) != "img":
                    return False
                try:
                    if child.get("inline") == "yes":
                        return False
                except Exception:
                    return False
                try:
                    if not _is_blank_text(child.tail):
                        return False
                except Exception:
                    return False
            return True

        def _extract_tokens(p_node: etree._Element):
            tokens: list[tuple[str, object]] = []
            try:
                if p_node.text:
                    tokens.append(("text", p_node.text))
            except Exception:
                pass
            for child in list(p_node):
                tokens.append(("node", child))
                try:
                    if child.tail:
                        tokens.append(("text", child.tail))
                except Exception:
                    pass
            return tokens

        def _split_tokens_by_period(tokens: list[tuple[str, object]]):
            sentences: list[list[tuple[str, object]]] = []
            current: list[tuple[str, object]] = []

            def _has_content(parts: list[tuple[str, object]]):
                for k, v in parts:
                    if k == "node":
                        return True
                    try:
                        if str(v).strip():
                            return True
                    except Exception:
                        continue
                return False

            for kind, value in tokens:
                if kind == "node":
                    current.append((kind, value))
                    continue

                text_val = "" if value is None else str(value)
                while True:
                    idx = text_val.find("。")
                    if idx < 0:
                        if text_val:
                            current.append(("text", text_val))
                        break
                    before = text_val[: idx + 1]
                    after = text_val[idx + 1 :]
                    if before:
                        current.append(("text", before))
                    if _has_content(current):
                        sentences.append(current)
                    current = []
                    text_val = after

            if _has_content(current):
                sentences.append(current)
            return sentences

        def _reset_p_content(p_node: etree._Element, parts: list[tuple[str, object]]):
            try:
                p_node.text = None
            except Exception:
                pass
            for child in list(p_node):
                try:
                    p_node.remove(child)
                except Exception:
                    continue

            last_child = None
            for kind, value in parts:
                if kind == "text":
                    text_piece = "" if value is None else str(value)
                    if not text_piece:
                        continue
                    if last_child is None:
                        if p_node.text:
                            p_node.text += text_piece
                        else:
                            p_node.text = text_piece
                    else:
                        if last_child.tail:
                            last_child.tail += text_piece
                        else:
                            last_child.tail = text_piece
                    continue

                node = value
                if not isinstance(node, etree._Element):
                    continue
                try:
                    node.tail = None
                except Exception:
                    pass
                try:
                    parent = node.getparent()
                    if parent is not None:
                        parent.remove(node)
                except Exception:
                    pass
                p_node.append(node)
                last_child = node

        def _ensure_last_img_semicolon(p_node: etree._Element, require_inline_yes=None):
            try:
                children = list(p_node)
                if not children:
                    return
                last_child = children[-1]
                if getattr(last_child, "tag", None) != "img":
                    return
                inline_val = last_child.get("inline")
                if require_inline_yes is True and inline_val != "yes":
                    return
                if require_inline_yes is False and inline_val == "yes":
                    return
                tail = last_child.tail
                if tail is None or (isinstance(tail, str) and (not tail.strip())):
                    placeholder = "；"
                    if require_inline_yes is False:
                        placeholder = "\u00A0"
                    last_child.tail = placeholder
            except Exception:
                return

        def _get_last_nonblank_char(p_node: etree._Element) -> str:
            pieces = []
            try:
                if p_node.text:
                    pieces.append(str(p_node.text))
            except Exception:
                pass
            for child in list(p_node):
                try:
                    if child.tail:
                        pieces.append(str(child.tail))
                except Exception:
                    continue
            joined = "".join(pieces)
            if not joined:
                return ""
            try:
                stripped = joined.rstrip()
            except Exception:
                stripped = joined
            if not stripped:
                return ""
            return stripped[-1]

        ps = list(desc_root.iter("p"))
        pre_marked_xxxx_ids = set()
        for p in ps:
            try:
                if p.get("num") == "XXXX":
                    pre_marked_xxxx_ids.add(id(p))
            except Exception:
                continue
        counter = 0
        pending_first_p = None
        i = 0
        while i < len(ps):
            p = ps[i]
            if p is None:
                i += 1
                continue
            if p.getparent() is None:
                i += 1
                continue

            try:
                if id(p) in pre_marked_xxxx_ids and p.get("num") == "XXXX":
                    try:
                        if not (_is_image_only_block_paragraph(p) or _contains_block_img(p)):
                            pending_first_p = None
                    except Exception:
                        pending_first_p = None
                    _ensure_last_img_semicolon(p, require_inline_yes=False)
                    i += 1
                    continue
            except Exception:
                pass

            try:
                if _is_empty_paragraph(p):
                    p.set("num", "XXXX")
                    pending_first_p = None
                    i += 1
                    continue
            except Exception:
                pass

            try:
                if _is_image_only_block_paragraph(p) or _contains_block_img(p):
                    p.set("num", "XXXX")
                    _ensure_last_img_semicolon(p, require_inline_yes=False)
                    i += 1
                    continue
            except Exception:
                pass

            try:
                p.set("num", "XXXX")
            except Exception:
                pass

            if pending_first_p is None:
                pending_first_p = p

            if mode == "period":
                tokens = _extract_tokens(p)
                sentences = _split_tokens_by_period(tokens)
                if len(sentences) > 1:
                    parent = p.getparent()
                    if parent is not None:
                        try:
                            base_index = parent.index(p)
                        except Exception:
                            base_index = None

                        _reset_p_content(p, sentences[0])

                        insert_offset = 1
                        for parts in sentences[1:]:
                            new_p = self.xml.create_paragraph(parent, text=None, is_claim=False)
                            if base_index is not None:
                                try:
                                    parent.remove(new_p)
                                    parent.insert(base_index + insert_offset, new_p)
                                except Exception:
                                    pass
                            _reset_p_content(new_p, parts)
                            try:
                                new_p.set("num", "XXXX")
                            except Exception:
                                pass
                            ps.insert(i + insert_offset, new_p)
                            insert_offset += 1

            if _get_last_nonblank_char(p) == "。":
                if pending_first_p is not None and pending_first_p.getparent() is not None:
                    counter += 1
                    try:
                        pending_first_p.set("num", f"{counter:04d}")
                    except Exception:
                        pass
                pending_first_p = None

            i += 1

        for p in desc_root.iter("p"):
            try:
                children = list(p)
                if not children:
                    continue
                last_child = children[-1]
                if getattr(last_child, "tag", None) != "img":
                    continue
                if last_child.get("inline") != "yes":
                    continue
                tail = last_child.tail
                if tail is None or (isinstance(tail, str) and (not tail.strip())):
                    last_child.tail = "\u00A0"
            except Exception:
                continue
