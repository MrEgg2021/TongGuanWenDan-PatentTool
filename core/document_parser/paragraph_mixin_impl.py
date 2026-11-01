from __future__ import annotations

import os
import re
from collections import Counter

from core.logging_utils import logger
from core.conversion import ConversionCancelled

# Word 常量（仅用于段落遍历中的 Information 调用）
wdWithInTable = 12
TABLE_FAILURE_PLACEHOLDER_TEXT = "表格截图失败，未写入 XML，请人工核对原文。"
DRAWINGS_LABEL_PATTERN = re.compile(
    r"^(图\s*[0-9０-９]+(?:\s*[-－—]\s*[0-9０-９]+)?(?:\s*[A-Za-zＡ-Ｚａ-ｚ]|\s*[（(]\s*[A-Za-zＡ-Ｚａ-ｚ]\s*[）)])?)(?:$|[^0-9０-９A-Za-zＡ-Ｚａ-ｚ])"
)


class ParagraphTraversalMixin:
    def _init_drawings_label_state(self) -> None:
        try:
            self._drawings_img_nodes = []
        except Exception:
            pass
        try:
            self._drawings_label_lines = []
        except Exception:
            pass
        try:
            self._drawings_img_label_by_id = {}
        except Exception:
            pass
        try:
            self._drawings_img_label_by_file = {}
        except Exception:
            pass
        try:
            self._drawings_img_total = 0
        except Exception:
            pass
        try:
            self._drawings_label_report = None
        except Exception:
            pass

    def _emit_table_failure_placeholder(self, parent_node, section_key: str, failure_record: dict | None = None) -> bool:
        text = TABLE_FAILURE_PLACEHOLDER_TEXT
        if str(section_key) == "claims":
            try:
                self._append_claim_segments(
                    parent_node,
                    [{"kind": "text", "text": text, "text_plain": text}],
                    is_new_start=False,
                    claim_num=None,
                )
                if isinstance(failure_record, dict):
                    try:
                        pending_num = getattr(self, "_claims_pending_num", None)
                        if pending_num is not None:
                            failure_record.setdefault("claim_num", str(int(pending_num)))
                    except Exception:
                        pass
                return True
            except Exception as exc:
                logger.warning(
                    "[TABLE_PLACEHOLDER_FAIL] section=%s stage=claims_append error_type=%s error=%s",
                    str(section_key),
                    type(exc).__name__,
                    str(exc),
                )

        try:
            p_node = self.xml.create_paragraph(
                parent_node,
                text=text,
                is_claim=(str(section_key) == "claims"),
            )
            if isinstance(failure_record, dict) and str(section_key) == "description" and p_node is not None:
                try:
                    desc_positions = getattr(self, "_desc_p_positions", None)
                    if not isinstance(desc_positions, list):
                        desc_positions = []
                        self._desc_p_positions = desc_positions
                    desc_positions.append(
                        {
                            "p": p_node,
                            "range_start": failure_record.get("range_start"),
                        }
                    )
                except Exception:
                    pass
            return True
        except Exception as exc:
            logger.warning(
                "[TABLE_PLACEHOLDER_FAIL] section=%s stage=create_paragraph error_type=%s error=%s",
                str(section_key),
                type(exc).__name__,
                str(exc),
            )
            return False

    def _register_drawings_image_node(self, img_node) -> None:
        if img_node is None:
            return
        try:
            img_nodes = getattr(self, "_drawings_img_nodes", None)
            if not isinstance(img_nodes, list):
                img_nodes = []
                self._drawings_img_nodes = img_nodes
            img_nodes.append(img_node)
        except Exception:
            pass
        try:
            self._drawings_img_total = int(getattr(self, "_drawings_img_total", 0) or 0) + 1
        except Exception:
            self._drawings_img_total = 1

    def _normalize_drawings_label_line(self, label_text: object) -> str:
        try:
            txt = str(label_text or "").strip()
        except Exception:
            return ""
        if not txt:
            return ""
        match = DRAWINGS_LABEL_PATTERN.match(txt)
        if not match:
            return ""
        try:
            return re.sub(r"\s+", "", str(match.group(1) or "").strip())
        except Exception:
            return ""

    def _register_drawings_label_text(self, label_text: object) -> None:
        try:
            txt = str(label_text or "")
        except Exception:
            return
        lines: list[str] = []
        try:
            lines = [ln.strip() for ln in str(txt).splitlines()]
        except Exception:
            lines = []
        if not lines:
            return

        try:
            label_lines = getattr(self, "_drawings_label_lines", None)
            if not isinstance(label_lines, list):
                label_lines = []
                self._drawings_label_lines = label_lines
            for ln in lines:
                label = self._normalize_drawings_label_line(ln)
                if label:
                    label_lines.append(label)
                elif ln:
                    logger.debug("[DRAWINGS_LABEL_SKIP] length=%d", len(ln))
        except Exception:
            pass

    def _resolve_drawings_image_path(self, file_name: str) -> str:
        candidates: list[str] = []
        try:
            config = getattr(self, "config", {}) or {}
            paths = config.get("paths", {}) if isinstance(config, dict) else {}
            if isinstance(paths, dict):
                temp_dir = str(paths.get("temp_dir") or "").strip()
                if temp_dir:
                    candidates.append(os.path.join(temp_dir, file_name))
            temp_dir = str(config.get("temp_dir") or "").strip() if isinstance(config, dict) else ""
            if temp_dir:
                candidates.append(os.path.join(temp_dir, file_name))
        except Exception:
            pass
        candidates.append(file_name)
        for path in candidates:
            try:
                if path and os.path.isfile(path):
                    return path
            except Exception:
                continue
        return ""

    def _is_near_blank_drawings_image(self, file_name: str) -> bool:
        path = self._resolve_drawings_image_path(file_name)
        if not path:
            return False
        try:
            from PIL import Image

            with Image.open(path) as img:
                gray = img.convert("L")
                width, height = gray.size
                total = max(1, int(width) * int(height))
                non_white_mask = gray.point(lambda px: 255 if px < 245 else 0, mode="L")
                bbox = non_white_mask.getbbox()
                if bbox is None:
                    return True
                non_white_pixels = int(non_white_mask.histogram()[255])
                return total >= 10000 and (non_white_pixels / total) <= 0.0015
        except Exception as exc:
            logger.debug("[DRAWINGS_BLANK_IMAGE_CHECK_FAIL] file=%s error=%s", file_name, exc)
            return False

    def _remove_drawings_image_node(self, img_node) -> None:
        parent = img_node.getparent()
        if parent is None:
            return
        grandparent = parent.getparent()
        if str(parent.tag) == "p" and grandparent is not None and len(parent) <= 1:
            parent_text = "".join(parent.itertext()).strip()
            if not parent_text:
                grandparent.remove(parent)
                return
        parent.remove(img_node)

    def _filter_blank_drawings_images(self, imgs: list) -> list:
        kept: list = []
        for img in imgs:
            file_name = str(img.get("file") or "").strip()
            if file_name and self._is_near_blank_drawings_image(file_name):
                try:
                    self._remove_drawings_image_node(img)
                    logger.info("[DRAWINGS_BLANK_IMAGE_SKIP] file=%s", file_name)
                except Exception as exc:
                    logger.warning("[DRAWINGS_BLANK_IMAGE_SKIP_FAIL] file=%s error=%s", file_name, exc)
                    kept.append(img)
                continue
            kept.append(img)
        return kept

    def _finalize_drawings_labels(self) -> None:
        placeholder = "图号缺失"
        try:
            m = getattr(self, "_drawings_img_label_by_id", None)
        except Exception:
            m = None
        if not isinstance(m, dict):
            m = {}
            try:
                self._drawings_img_label_by_id = m
            except Exception:
                pass
        try:
            file_label_map = getattr(self, "_drawings_img_label_by_file", None)
        except Exception:
            file_label_map = None
        if not isinstance(file_label_map, dict):
            file_label_map = {}
            try:
                self._drawings_img_label_by_file = file_label_map
            except Exception:
                pass

        labels_in_order: list[str] = []
        label_lines: list[str] = []
        try:
            raw_lines = getattr(self, "_drawings_label_lines", None)
            if isinstance(raw_lines, list):
                label_lines = [
                    label
                    for label in (self._normalize_drawings_label_line(x) for x in raw_lines)
                    if label
                ]
        except Exception:
            label_lines = []

        imgs: list = []
        try:
            draw_root = (getattr(self, "sections", {}) or {}).get("drawings")
            if draw_root is not None:
                imgs = [img for img in list(draw_root.iter("img")) if img.get("file")]
        except Exception:
            imgs = []
        imgs = self._filter_blank_drawings_images(imgs)

        for idx, img in enumerate(imgs):
            label = placeholder
            try:
                if idx < len(label_lines):
                    label = label_lines[idx] or placeholder
            except Exception:
                label = placeholder
            try:
                m[id(img)] = label
            except Exception:
                pass
            try:
                file_name = str(img.get("file") or "").strip()
                if file_name:
                    file_label_map[file_name] = label
            except Exception:
                pass
            labels_in_order.append(label)

        missing_count = 0
        try:
            missing_count = sum(1 for v in labels_in_order if v == placeholder)
        except Exception:
            missing_count = 0

        duplicate_labels: list[str] = []
        try:
            counts = Counter([v for v in labels_in_order if v and v != placeholder])
            duplicate_labels = [k for k, c in counts.items() if c and c > 1]
        except Exception:
            duplicate_labels = []

        img_count = 0
        try:
            img_count = len(imgs)
        except Exception:
            img_count = 0

        label_line_count = 0
        try:
            label_line_count = len(label_lines)
        except Exception:
            label_line_count = 0

        unused_labels: list[str] = []
        try:
            if label_line_count > img_count:
                unused_labels = label_lines[img_count:]
        except Exception:
            unused_labels = []

        count_mismatch = False
        try:
            count_mismatch = (img_count != label_line_count)
        except Exception:
            count_mismatch = False

        report = {
            "img_count": img_count,
            "label_line_count": label_line_count,
            "count_mismatch": count_mismatch,
            "missing_count": missing_count,
            "duplicate_labels": duplicate_labels,
            "unused_labels": unused_labels,
            "labels_sample": labels_in_order[:20],
        }
        try:
            self._drawings_label_report = report
        except Exception:
            pass

    def _emit_progress(self, stage, **payload):  # type: ignore[override]
        cb = getattr(self, "progress_callback", None)
        if cb is not None:
            try:
                cb(stage, payload)
            except ConversionCancelled:
                raise
            except Exception:
                # GUI 侧问题不能影响核心处理
                pass

    def run(self, input_file, case_id=None, patent_type=None, request_info=None):  # type: ignore[override]
        """主处理流程：打开文档、按章节遍历段落并生成 XML 与图片"""
        self.patent_type = patent_type
        self.request_info = request_info
        try:
            self.input_file_path = input_file
        except Exception:
            pass
        logger.info(f"🚀 开始处理文档: {input_file}")
        forced_section_key = ""
        try:
            forced_section_key = str(getattr(self, "forced_section_key", "") or "").strip()
        except Exception:
            forced_section_key = ""
        if forced_section_key:
            try:
                root_tags = getattr(self, "output_body_root_tags", None)
            except Exception:
                root_tags = None
            if isinstance(root_tags, dict):
                root_tag = str(root_tags.get(forced_section_key) or "").strip()
                if root_tag:
                    from lxml import etree

                    attrs = {"lang": "zh", "country": "CN"} if root_tag == "cn-other-file" else {}
                    self.sections[forced_section_key] = etree.Element(root_tag, **attrs)

        # 根据 enabled_sections 构建允许处理的章节集合（未提供时默认全开）
        enabled = getattr(self, "enabled_sections", None)
        if not isinstance(enabled, dict):
            enabled = {
                "claims": True,
                "description": True,
                "drawings": True,
                "abstract": True,
                "request_form": True,
            }
        allowed_sections = {k for k, v in enabled.items() if v}
        if not allowed_sections:
            # 兜底：若全部被禁用，则默认视为全开，避免后续逻辑全部跳过
            allowed_sections = {"claims", "description", "drawings", "abstract", "request_form"}
        logger.info(f"[ENABLED_SECTIONS] {sorted(allowed_sections)}")
        self._emit_progress("start", message="正在加载文档和配置...")
        self.word.open_doc(input_file)
        doc = self.word.doc
        try:
            queue_state = self._rebuild_drawings_inline_package_queue_state()
        except Exception:
            queue_state = {"items": []}
        legacy_inventory = getattr(self.word, "_legacy_drawings_inventory", None)
        if isinstance(legacy_inventory, dict):
            self._legacy_drawings_inventory = dict(legacy_inventory)
            self._legacy_drawings_inventory["package_drawings"] = len(queue_state.get("items") or [])

        if forced_section_key:
            section_plan = [(0, float("inf"), forced_section_key)]
            logger.info("[FORCED_SECTION] 将整份文档按章节 %s 处理", forced_section_key)
        else:
            # 基于页眉构建章节计划
            section_plan = self._build_section_plan_from_headers(doc)
        logger.info(f"[SECTION_PLAN] {section_plan}")
        self._emit_progress("section_plan_ready", message="章节结构识别完成，准备遍历段落...")

        # 处理过的表格起始位置
        self.processed_tables.clear()
        # 记录每个表格 Range.Start 对应的截图是否成功
        try:
            self._table_capture_success.clear()
        except Exception:
            # 兼容旧版本实例上不存在该字段的情况
            self._table_capture_success = {}
        try:
            self._clear_table_process_failure_context()
        except Exception:
            self._table_process_failure_context = None
        try:
            self._table_placeholder_inserted.clear()
        except Exception:
            self._table_placeholder_inserted = set()
        self.table_screenshot_failures = []
        self.object_fallback_failures = []
        self._drawings_quality_warnings = []
        self._drawings_media_quality_meta_by_file = {}
        self._desc_p_positions = []
        self._claim_ranges = []

        try:
            self._init_drawings_label_state()
        except Exception:
            pass

        paragraphs = doc.Paragraphs
        total = 0
        try:
            total = int(paragraphs.Count)
        except Exception:
            total = 0
        
        logger.info(f"🧾 文档共有 {total} 个段落，开始遍历...")
        self._emit_progress(
            "scan_ready",
            message="文档预扫描完成，开始逐段处理...",
            total_paragraphs=total,
        )

        prev_section_key = None
        unknown_parent_count = 0
        unknown_parent_samples = []
        
        # [Performance] Use iterator instead of index access to avoid O(N^2) complexity in COM
        for idx, para in enumerate(paragraphs, start=1):
            try:
                in_table = bool(para.Range.Information(wdWithInTable))
            except Exception:
                in_table = False
            try:
                tables_count = para.Range.Tables.Count
            except Exception:
                tables_count = 0

            raw_text = ""
            text = ""
            if not in_table:
                raw_text = para.Range.Text
                raw_text = (raw_text or "").replace("\x0b", "\n")
                text = self._sanitize_text(raw_text).strip()

            # [Performance] Guard logging calls that access COM properties
            if (
                idx <= 40
                and section_plan
                and logger.isEnabledFor(10)  # logging.DEBUG
            ):
                if self._get_section_key_for_paragraph(para, section_plan) == "claims":
                    logger.debug(
                        "[CLAIM_DIAG_PRE] idx=%s range_start=%s inline_shapes=%s",
                        idx,
                        para.Range.Start,
                        getattr(para.Range.InlineShapes, "Count", 0),
                    )

            # 根据当前位置获取章节 key
            current_section_key = forced_section_key or self._get_section_key_for_paragraph(para, section_plan)
            override_key = None if forced_section_key else self._detect_logical_section(current_section_key, text)
            if override_key:
                if logger.isEnabledFor(10):
                    logger.debug(
                        "[SECTION_OVERRIDE_APPLY] idx=%s physical=%s override=%s",
                        idx,
                        current_section_key,
                        override_key,
                    )
                current_section_key = override_key
            if not current_section_key:
                continue
            if current_section_key not in allowed_sections:
                continue
            
            if idx <= 40 and logger.isEnabledFor(10):
                logger.debug(
                    "[CLAIM_DIAG_SECTION] idx=%s range_start=%s section=%s",
                    idx,
                    para.Range.Start,
                    current_section_key,
                )
            
            if current_section_key != prev_section_key:
                if logger.isEnabledFor(10):
                    logger.debug(
                        "[SECTION_SWITCH] idx=%s range_start=%s prev=%s -> current=%s",
                        idx,
                        para.Range.Start,
                        prev_section_key,
                        current_section_key,
                    )
                prev_section_key = current_section_key

            parent_node = self.sections.get(current_section_key)
            if parent_node is None:
                unknown_parent_count += 1
                rng_start = None
                if logger.isEnabledFor(30): # logging.WARNING
                    try:
                        rng_start = int(para.Range.Start)
                    except Exception:
                        rng_start = None
                text_preview = text[:50]
                if len(unknown_parent_samples) < 20:
                    unknown_parent_samples.append(
                        {
                            "index": idx,
                            "section": current_section_key,
                            "range_start": rng_start,
                            "text_preview": text_preview,
                        }
                    )
                if logger.isEnabledFor(30):
                    logger.warning(
                        "[UNKNOWN_SECTION_PARENT] idx=%s range_start=%s section=%s",
                        idx,
                        rng_start,
                        current_section_key,
                    )
                continue

            if not in_table and logger.isEnabledFor(10):
                logger.debug("[PARA_DEBUG] idx=%s section=%s", idx, current_section_key)

            # 段落级进度上报（粗粒度），供 GUI 做百分比换算
            self._emit_progress(
                "paragraph",
                index=idx,
                total=total,
                section=current_section_key,
            )

            # 1. 表格处理（整体截图），同一表格仅处理一次
            try:
                shapes_count = para.Range.ShapeRange.Count
            except Exception:
                shapes_count = 0
            
            if idx <= 40 and current_section_key == "claims" and logger.isEnabledFor(10):
                logger.debug(
                    "[CLAIM_DIAG_STEP] idx=%s in_table=%s tables=%s shapes=%s",
                    idx,
                    in_table,
                    tables_count,
                    shapes_count,
                )

            if tables_count > 0 and not in_table and logger.isEnabledFor(10):
                try:
                    diag_table = para.Range.Tables(1)
                    logger.debug(
                        "[TABLE_DIAG_OUTSIDE] idx=%s section=%s in_table=%s tables=%s "
                        "range=(%s,%s) rows=%s cols=%s shapes=%s",
                        idx,
                        current_section_key,
                        in_table,
                        tables_count,
                        int(diag_table.Range.Start),
                        int(diag_table.Range.End),
                        diag_table.Rows.Count,
                        diag_table.Columns.Count,
                        shapes_count,
                    )
                except Exception:
                    logger.debug(
                        "[TABLE_DIAG_OUTSIDE] idx=%s section=%s in_table=%s tables=%s (detail unavailable)",
                        idx,
                        current_section_key,
                        in_table,
                        tables_count,
                    )

            if in_table and tables_count > 0:
                table_status = getattr(self, "_table_capture_success", None)
                if not isinstance(table_status, dict):
                    table_status = {}
                    self._table_capture_success = table_status

                table = None
                t_start = None
                t_end = None
                table_rows = None
                table_cols = None
                try:
                    table = para.Range.Tables(1)
                    try:
                        t_start = int(table.Range.Start)
                    except Exception:
                        t_start = None
                    try:
                        t_end = int(table.Range.End)
                    except Exception:
                        t_end = None
                    try:
                        table_rows = int(table.Rows.Count)
                    except Exception:
                        table_rows = None
                    try:
                        table_cols = int(table.Columns.Count)
                    except Exception:
                        table_cols = None
                except Exception as table_exc:
                    logger.warning(
                        "[TABLE_CAPTURE_EXCEPTION] idx=%s section=%s stage=get_table error_type=%s error=%s",
                        idx,
                        current_section_key,
                        type(table_exc).__name__,
                        str(table_exc),
                    )
                    try:
                        self.table_screenshot_failures.append(
                            {
                                "section": current_section_key,
                                "paragraph_index": idx,
                                "range_start": None,
                                "range_end": None,
                                "error_code": "TABLE_COM_ERROR",
                                "error_type": type(table_exc).__name__,
                                "error_message": str(table_exc)[:300],
                                "stage": "get_table",
                            }
                        )
                    except Exception:
                        pass
                    continue

                table_key = t_start if t_start is not None else ("idx", int(idx))
                success = table_status.get(table_key)
                process_error = None
                if success is None:
                    success = True
                    if table_key not in self.processed_tables:
                        try:
                            logger.info(
                                "[TABLE_CAPTURE_TRY] idx=%s section=%s range=(%s,%s) rows=%s cols=%s",
                                idx,
                                current_section_key,
                                t_start,
                                t_end,
                                table_rows,
                                table_cols,
                            )
                        except Exception:
                            logger.info(
                                "[TABLE_CAPTURE_TRY] idx=%s section=%s range_start=%s (detail unavailable)",
                                idx,
                                current_section_key,
                                t_start,
                            )
                        try:
                            success = bool(self.process_table(table, parent_node, current_section_key))
                        except Exception as proc_exc:
                            process_error = proc_exc
                            success = False
                            logger.warning(
                                "[TABLE_CAPTURE_EXCEPTION] idx=%s section=%s stage=process_table range_start=%s error_type=%s error=%s",
                                idx,
                                current_section_key,
                                t_start,
                                type(proc_exc).__name__,
                                str(proc_exc),
                            )
                        # 无论成功与否，都标记为已尝试，避免后续段落重复处理同一张表
                        self.processed_tables.add(table_key)

                        try:
                            logger.info(
                                "[TABLE_CAPTURE_RESULT] idx=%s section=%s range=(%s,%s) success=%s",
                                idx,
                                current_section_key,
                                t_start,
                                t_end,
                                success,
                            )
                        except Exception:
                            logger.info(
                                "[TABLE_CAPTURE_RESULT] idx=%s section=%s range_start=%s success=%s",
                                idx,
                                current_section_key,
                                t_start,
                                success,
                            )

                        emit_summary = []
                        try:
                            consume_emit_summary = getattr(self, "_consume_table_emit_summary_context", None)
                            if callable(consume_emit_summary):
                                emit_summary = consume_emit_summary() or []
                        except Exception:
                            emit_summary = []

                        if success:
                            summary_files = []
                            summary_widths = []
                            summary_heights = []
                            for item in list(emit_summary or []):
                                if not isinstance(item, dict):
                                    continue
                                file_name = str(item.get("file") or "").strip()
                                if file_name:
                                    summary_files.append(file_name)
                                try:
                                    summary_widths.append(f"{float(item.get('width_mm')):.2f}")
                                except Exception:
                                    pass
                                try:
                                    summary_heights.append(f"{float(item.get('height_mm')):.2f}")
                                except Exception:
                                    pass
                            logger.info(
                                "[TABLE_EMIT_SUMMARY] idx=%s section=%s range_start=%s range_end=%s fragments=%s files=%s widths_mm=%s heights_mm=%s",
                                idx,
                                current_section_key,
                                t_start,
                                t_end,
                                len(summary_files) if summary_files else len(list(emit_summary or [])),
                                "|".join(summary_files),
                                "|".join(summary_widths),
                                "|".join(summary_heights),
                            )

                        if not success:
                            failure_meta = None
                            try:
                                consume_failure = getattr(self, "_consume_table_process_failure_context", None)
                                if callable(consume_failure):
                                    failure_meta = consume_failure()
                            except Exception:
                                failure_meta = None
                            failure_record = {
                                "section": current_section_key,
                                "paragraph_index": idx,
                                "range_start": t_start,
                                "range_end": t_end,
                                "error_code": "TABLE_COM_ERROR",
                                "error_type": type(process_error).__name__ if process_error else "",
                                "error_message": (str(process_error)[:300] if process_error else ""),
                                "stage": "process_table",
                            }
                            if isinstance(failure_meta, dict):
                                for key in (
                                    "error_code",
                                    "error_type",
                                    "error_message",
                                    "stage",
                                    "requested_row",
                                    "safe_row",
                                    "height_mm",
                                    "rows",
                                    "rows_before",
                                    "rows_after",
                                ):
                                    value = failure_meta.get(key)
                                    if value is not None and value != "":
                                        failure_record[key] = value
                            try:
                                self.table_screenshot_failures.append(failure_record)
                            except Exception:
                                pass

                    table_status[table_key] = bool(success)

                # 仅当整表截图成功写入 XML 时，才跳过表内段落；
                # 若截图失败（success=False），则退回为单元格文本输出，避免内容丢失。
                if idx <= 40 and current_section_key == "claims":
                    if success:
                        logger.debug("[CLAIM_DIAG_SKIP] idx=%s reason=table", idx)
                    else:
                        logger.debug("[CLAIM_DIAG_SKIP] idx=%s reason=table_failed", idx)
                if success:
                    continue

                placeholder_tables = getattr(self, "_table_placeholder_inserted", None)
                if not isinstance(placeholder_tables, set):
                    placeholder_tables = set()
                    self._table_placeholder_inserted = placeholder_tables
                if table_key not in placeholder_tables:
                    failure_record = None
                    try:
                        if self.table_screenshot_failures:
                            failure_record = self.table_screenshot_failures[-1]
                    except Exception:
                        failure_record = None

                    inserted = self._emit_table_failure_placeholder(parent_node, current_section_key, failure_record)
                    if inserted:
                        placeholder_tables.add(table_key)
                        if isinstance(failure_record, dict):
                            failure_record["resolution_code"] = "placeholder_inserted"
                        logger.warning(
                            "[TABLE_PLACEHOLDER] section=%s range_start=%s range_end=%s table_key=%s inserted=true",
                            str(current_section_key),
                            t_start,
                            t_end,
                            str(table_key),
                        )
                    else:
                        if isinstance(failure_record, dict):
                            failure_record["resolution_code"] = "placeholder_insert_failed"
                        logger.warning(
                            "[TABLE_PLACEHOLDER] section=%s range_start=%s range_end=%s table_key=%s inserted=false",
                            str(current_section_key),
                            t_start,
                            t_end,
                            str(table_key),
                        )
                continue

            # 2. 过滤完全空的段落
            if (
                not text
                and para.Range.InlineShapes.Count == 0
                and para.Range.ShapeRange.Count == 0
            ):
                continue

            # 3. 处理浮动元素 (ShapeRange)
            if para.Range.ShapeRange.Count > 0:
                handled = self._process_floating_shapes(para, parent_node, current_section_key)
                if handled:
                    if idx <= 40 and current_section_key == "claims":
                        logger.debug("[CLAIM_DIAG_SKIP] idx=%s reason=shape_range", idx)
                    continue

            # 4. 普通内容段落：文本 + 行内图片
            self._current_paragraph_index = idx
            self.process_paragraph_content(
                para,
                parent_node,
                is_claim=(current_section_key == "claims"),
                section_key=current_section_key,
            )

        if unknown_parent_count > 0:
            logger.warning(
                "[UNKNOWN_SECTION_PARENT_SUMMARY] total=%s positions=%r",
                unknown_parent_count,
                [(item["index"], item["range_start"]) for item in unknown_parent_samples],
            )

        # 确保所有待合并的权利要求片段在章节遍历结束后被刷新为最终 <claim>
        claims_root = self.sections.get("claims")
        if claims_root is not None:
            try:
                self._flush_pending_claim(claims_root, force=True)
            except Exception:
                pass

        # 5. 生成文件
        self._emit_progress("before_generate", message="段落处理完成，正在生成 XML 和案卷包...")

        try:
            self._finalize_drawings_labels()
        except Exception:
            pass

        legacy_inventory = getattr(self, "_legacy_drawings_inventory", None)
        if isinstance(legacy_inventory, dict):
            label_report = getattr(self, "_drawings_label_report", None)
            captured_drawings = int((label_report or {}).get("img_count") or 0) if isinstance(label_report, dict) else 0
            package_drawings = int(legacy_inventory.get("package_drawings") or 0)
            legacy_inventory["captured_drawings"] = captured_drawings
            logger.info(
                "[LEGACY_DRAWINGS_COUNTS] source=%s reopened=%s package_drawings=%d captured_drawings=%d",
                legacy_inventory.get("source"),
                legacy_inventory.get("reopened"),
                package_drawings,
                captured_drawings,
            )
            if captured_drawings < package_drawings:
                logger.warning(
                    "[LEGACY_DRAWINGS_CAPTURE_INCOMPLETE] package_drawings=%d captured_drawings=%d",
                    package_drawings,
                    captured_drawings,
                )

        result = self.generate_output_files(case_id=case_id)
        # 输出一次图像处理通路的统计摘要，便于在日志中评估 EMF/PDF/截图使用情况
        try:
            stats = getattr(self, "_img_pipeline_stats", None)
            if isinstance(stats, dict):
                emf = int(stats.get("EMF", 0))
                pdf = int(stats.get("PDF", 0))
                bmp = int(stats.get("BITMAP", 0))
                media = int(stats.get("MEDIA", 0))
                saveas = int(stats.get("SAVEAS", 0))
                logger.info(
                    "IMG_PIPELINE_SUMMARY: EMF=%d PDF=%d BITMAP=%d MEDIA=%d SAVEAS=%d",
                    emf,
                    pdf,
                    bmp,
                    media,
                    saveas,
                )
        except Exception:
            pass

        self._emit_progress("done", message="转换完成", result_summary=result)
        return result
