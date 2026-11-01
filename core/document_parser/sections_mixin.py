from __future__ import annotations





import re





from core.logging_utils import logger






class SectionsMixin:
    def identify_section(self, text):  # type: ignore[override]
        """根据页眉文本识别章节键。"""
        text = str(text or "").strip()
        if not text:
            return None
        if len(text) > 20:
            return None

        norm = re.sub(r"\s+", "", text)
        if norm == "权利要求书":
            return "claims"
        if norm == "说明书":
            return "description"
        if norm == "说明书附图":
            return "drawings"
        if norm == "摘要附图":
            return "abstract_drawings"
        if norm == "说明书摘要":
            return "abstract"
        return None

    def _build_section_plan_from_headers(self, doc):  # type: ignore[override]


        """基于各 Section 的页眉构建 (RangeStart, RangeEnd, section_key) 列表"""


        plan = []


        sections = doc.Sections


        count = sections.Count





        logger.info(f"🔍 文档共有 {count} 个分节，开始扫描页眉以划分章节...")





        for i in range(1, count + 1):


            sec = sections(i)


            start = sec.Range.Start


            end = sec.Range.End





            found_key = None


            header_debug_info = []





            # 遍历三种类型的页眉：


            # 1: wdHeaderFooterPrimary (主页眉)


            # 2: wdHeaderFooterFirstPage (首页页眉)


            # 3: wdHeaderFooterEvenPages (偶数页页眉)


            for h_idx in [1, 2, 3]:


                try:


                    h = sec.Headers(h_idx)


                    # 注意：即使 LinkToPrevious=True，读取 Range.Text 通常也能拿到显示的内容


                    # 但如果该类型页眉未被激活（exists=False），内容可能为空


                    text = h.Range.Text.strip()


                    if text:


                        header_debug_info.append(f"Type{h_idx}:[{text}]")


                        norm = re.sub(r"\s+", "", text)





                        # 仅接受完全匹配的页眉关键词


                        key = None


                        if norm == "摘要附图":


                            key = 'abstract_drawings'


                        elif norm == "说明书附图":


                            key = 'drawings'


                        elif norm == "权利要求书":


                            key = 'claims'


                        elif norm == "申请信息确认页":


                            key = 'request_meta'


                        elif norm == "说明书摘要":


                            key = 'abstract'


                        elif norm == "说明书":


                            key = 'description'





                        if key:


                            found_key = key


                            # 找到有效 key 后停止遍历当前 Section 的其他页眉


                            # 除非我们认为 FirstPage 和 Primary 可能冲突？通常以出现的为准。


                            break


                except Exception:


                    pass





            if found_key:
                logger.info(


                    "  - Section %s [Range %s-%s]: 识别为 '%s' (页眉数: %s)",
                    i, start, end, found_key, len(header_debug_info),
                )
                plan.append((start, end, found_key))


            else:


                # 如果本节没读到有效关键词，尝试继承上一节的 key


                # (常见于为了排版插入的分节符)


                if plan:


                    prev_key = plan[-1][2]


                    logger.info(


                        "  - Section %s [Range %s-%s]: 未识别到关键词 (页眉数: %s) -> 继承上一节 '%s'",
                        i, start, end, len(header_debug_info), prev_key,
                    )
                    plan.append((start, end, prev_key))


                else:


                    # 首个 Section 且未识别到任何关键词：视为前置 meta（front_matter），


                    # 只用于调试和头部探测，不参与四大正文章节。


                    key = "front_matter"


                    logger.warning(


                        f"  - Section {i} [Range {start}-{end}]: 未识别到关键词且无前序章节 -> 标记为 '{key}'（前置 meta）"


                    )


                    plan.append((start, end, key))





        return plan





    def _get_section_key_for_paragraph(self, para, section_plan):  # type: ignore[override]


        """根据段落起始位置在 section_plan 中查找对应的章节 key（左闭右开区间）"""


        if not section_plan:


            return None


        pos = para.Range.Start


        total = len(section_plan)


        first_start = section_plan[0][0]


        for idx, (start, end, key) in enumerate(section_plan):


            next_start = section_plan[idx + 1][0] if idx + 1 < total else float("inf")


            upper = min(end, next_start)


            if start <= pos < upper:


                return key


        # 若段落起始位置落在第一个 Section 之前，不再强行归入最后一个章节，


        # 以避免首节未识别场景被错误 fallback 到尾部章节。


        if pos < first_start:


            return None


        # 对于确实位于最后一个 Section 之后的段落，仍按旧行为兜底到最后一个章节 key。


        return section_plan[-1][2]





    def _detect_logical_section(self, physical_section, text):  # type: ignore[override]


        """检测是否需要逻辑章节覆盖（仅在必要时启用）"""


        if not text:


            return None





        # 移除空格进行匹配





        # 目前不对说明书段落做附图相关的逻辑覆盖，统一按物理章节处理


        if physical_section == 'description':


            return None





        # 进入真正的 drawings section 时清除覆盖


        if physical_section == 'drawings' and getattr(self, "_logical_section_override", None):


            logger.debug("[SECTION_OVERRIDE_CLEAR] physical=drawings")
            self._logical_section_override = None





        return None


