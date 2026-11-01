from __future__ import annotations

import os
import re
import shutil
import tempfile
from datetime import datetime

from PIL import Image

from core.archive_safety import safe_member_path
from core.image_processing.equation_diag_ops import (
    get_existing_equation_diag_dir,
    write_equation_output_mapping,
)
from core.logging_utils import logger
from core.runtime import register_output_workspace
from core.request_form_xml import create_110101_xml, create_120101_xml
from core.data_bus_xml import create_data_bus


def _assert_unique_poa_in_request_info(req_info) -> None:
    if not isinstance(req_info, dict):
        return
    agency_enabled = False
    try:
        if "agency_enabled" in req_info:
            agency_enabled = bool(req_info.get("agency_enabled"))
    except Exception:
        agency_enabled = False
    if not agency_enabled:
        return

    apps = []
    try:
        apps = req_info.get("applicants") or []
    except Exception:
        apps = []
    if not isinstance(apps, list) or not apps:
        return

    seen = set()
    dup = set()
    for a in apps:
        if not isinstance(a, dict):
            continue
        try:
            v = str(a.get("power_of_attorney_no") or "").strip()
        except Exception:
            v = ""
        if not v:
            continue
        if v in seen:
            dup.add(v)
        else:
            seen.add(v)
    if dup:
        raise ValueError(
            "发现重复的总委托书编号(POA)，同一申请内不可重复，已阻止生成请求书 XML：\n"
            + "\n".join([f"- {d}" for d in sorted(dup)])
        )


class OutputGenerationMixin:
    def _postprocess_description_period_equations(self):  # type: ignore[override]
        try:
            split_mode = getattr(self, "description_paragraph_split_mode", "word")
        except Exception:
            split_mode = "word"
        if str(split_mode).lower() not in ("period", "word_period_end"):
            return

        try:
            eq_cfg = self.config.get("equation_centering") or {}
        except Exception:
            eq_cfg = {}
        if not isinstance(eq_cfg, dict) or not eq_cfg.get("enabled"):
            return

        desc_root = self.sections.get("description")
        if desc_root is None:
            return

        eq_meta_by_file = getattr(self, "_eq_centering_desc_equation_images", None)
        if not isinstance(eq_meta_by_file, dict) or not eq_meta_by_file:
            return

        precise_cfg = (eq_cfg.get("precise") or {}) if isinstance(eq_cfg, dict) else {}
        try:
            line_width_mm = float(precise_cfg.get("line_width_mm", 165.0))
        except (TypeError, ValueError):
            line_width_mm = 165.0
        try:
            claim_visual_offset_mm = float(precise_cfg.get("claim_visual_offset_mm", 0.0))
        except (TypeError, ValueError):
            claim_visual_offset_mm = 0.0

        claim_body_target_width_mm = line_width_mm + claim_visual_offset_mm
        claim_line_target_width_mm = line_width_mm + claim_visual_offset_mm

        try:
            temp_dir = os.path.abspath(self.config["paths"]["temp_dir"])
        except Exception:
            temp_dir = None
        if not temp_dir:
            return

        num_pat = re.compile(r"[（(]\s*\d+\s*[)）]")

        eq_display_ratio = 1.0
        try:
            eq_display_ratio = float(self.config.get("equation_display_scale_ratio", 1.0))
        except Exception:
            eq_display_ratio = 1.0
        if not eq_display_ratio or eq_display_ratio <= 0:
            eq_display_ratio = 1.0
        eq_display_ratio = max(0.4, min(1.0, float(eq_display_ratio)))

        px_per_mm_override = None
        try:
            mm_per_px = float(self.config.get("omath_mm_per_px", 0.1))
            if mm_per_px > 0:
                px_per_mm_override = 1.0 / float(mm_per_px)
        except Exception:
            px_per_mm_override = None

        for p in desc_root.iter("p"):
            try:
                if p.get("num") != "XXXX":
                    continue
            except Exception:
                continue

            try:
                imgs = [child for child in list(p) if getattr(child, "tag", None) == "img"]
            except Exception:
                imgs = []
            if len(imgs) != 1:
                continue

            img = imgs[0]
            try:
                fn = img.get("file")
            except Exception:
                fn = None
            if not isinstance(fn, str) or not fn:
                continue

            meta = eq_meta_by_file.get(fn)
            if not isinstance(meta, dict):
                continue

            with_num = bool(meta.get("with_num"))
            target_w = claim_body_target_width_mm if with_num else claim_line_target_width_mm
            already_padded = bool(meta.get("padded"))

            try:
                wi = float(img.get("wi"))
                he = float(img.get("he"))
            except Exception:
                wi = None
                he = None

            # period 模式下，description 里的公式行 num="XXXX" 需要按“无段号”的宽度处理（165）。
            # 但早期（段号尚未最终确定）有些公式会先按 desc_line_target_width_mm(≈145) 做过一次补白，
            # 并把 meta["padded"]=True 标记为“已补白”，导致这里无法再纠正到 165，最终出现：
            # - 图片宽=1450px，但 wi=145（PDF 视觉上更窄 / 不符合预期）
            # 因此：即使已经 padded，只要 wi != target_w，也允许再次补白以纠正目标宽度。
            need_pad = (not already_padded)
            try:
                if wi is not None and abs(float(wi) - float(target_w)) > 0.05:
                    need_pad = True
            except Exception:
                pass

            if need_pad:
                try:
                    image_path = os.path.join(temp_dir, fn)
                    # 若之前已经按错误目标宽度补白过（比如 145->165），这里仅需要“扩展画布”纠正宽度，
                    # 不应再次套用 equation_display_scale_ratio（否则会二次缩小主体）。
                    sr = eq_display_ratio if (not already_padded) else None
                    new_w, new_h = self.img_proc.pad_equation_for_centering(
                        image_path,
                        wi,
                        he,
                        target_width_mm=target_w,
                        scale_ratio=sr,
                        px_per_mm_override=px_per_mm_override,
                    )
                    try:
                        img.set("wi", f"{float(new_w):.2f}")
                    except Exception:
                        pass
                    try:
                        img.set("he", f"{float(new_h):.2f}")
                    except Exception:
                        pass
                    try:
                        meta["padded"] = True
                    except Exception:
                        pass
                except Exception:
                    pass

            if with_num:
                try:
                    tail = img.tail or ""
                    m = num_pat.search(tail)
                    if m:
                        prefix = tail[: m.start()]
                        if prefix.strip(" \t\r\n\u3000") == "":
                            rest = tail[m.start() :]
                            rest = rest.lstrip(" \t\r\n\u3000")
                            img.tail = ("\u3000" * 3) + rest
                except Exception:
                    pass

    def _postprocess_description_period_tables(self):  # type: ignore[override]
        """period/word_period_end 模式下：纠正说明书表格图片的目标宽度。

        背景：
        - structure_mixin 在 period/word_period_end 下会把含 block 图片（表格/整段截图等）的段落标记为 num="XXXX"。
        - 表格截图阶段可能仍按“预留段号宽度(≈145mm)”做过一次居中补白，导致最终出现：num=XXXX 但 wi=145。
        - 这里在段号最终确定后，将表格图片纠正为“无段号”的满行宽（默认 165mm）。
        """
        try:
            split_mode = getattr(self, "description_paragraph_split_mode", "word")
        except Exception:
            split_mode = "word"
        if str(split_mode).lower() not in ("period", "word_period_end"):
            return

        try:
            table_cfg = self.config.get("table_image_centering") or {}
        except Exception:
            table_cfg = {}
        if not isinstance(table_cfg, dict) or not table_cfg.get("enabled"):
            return

        desc_root = self.sections.get("description")
        if desc_root is None:
            return

        eq_cfg = {}
        try:
            eq_cfg = self.config.get("equation_centering") or {}
        except Exception:
            eq_cfg = {}
        precise_cfg = (eq_cfg.get("precise") or {}) if isinstance(eq_cfg, dict) else {}
        try:
            line_width_mm = float(precise_cfg.get("line_width_mm", 165.0))
        except (TypeError, ValueError):
            line_width_mm = 165.0
        if not line_width_mm or line_width_mm <= 0:
            line_width_mm = 165.0

        try:
            temp_dir = os.path.abspath(self.config["paths"]["temp_dir"])
        except Exception:
            temp_dir = None
        if not temp_dir:
            return

        for p in desc_root.iter("p"):
            try:
                if p.get("num") != "XXXX":
                    continue
            except Exception:
                continue

            try:
                imgs = [child for child in list(p) if getattr(child, "tag", None) == "img"]
            except Exception:
                imgs = []
            if len(imgs) != 1:
                continue

            img = imgs[0]
            try:
                if img.get("inline") == "yes":
                    continue
            except Exception:
                continue

            try:
                fn = img.get("file")
            except Exception:
                fn = None
            if not isinstance(fn, str) or not fn:
                continue
            # 表格截图的临时文件名统一为 tbl_ 前缀。
            if not fn.startswith("tbl_"):
                continue

            try:
                wi = float(img.get("wi"))
                he = float(img.get("he"))
            except Exception:
                continue

            target_w = float(line_width_mm)
            try:
                if abs(float(wi) - float(target_w)) <= 0.05:
                    continue
            except Exception:
                pass

            try:
                image_path = os.path.join(temp_dir, fn)
                new_w, new_h = self.img_proc.pad_equation_for_centering(
                    image_path,
                    wi,
                    he,
                    target_width_mm=target_w,
                    preserve_all_ink=False,
                )
                try:
                    img.set("wi", f"{float(new_w):.2f}")
                except Exception:
                    pass
                try:
                    img.set("he", f"{float(new_h):.2f}")
                except Exception:
                    pass
            except Exception:
                continue

    def _postprocess_table_failure_positions(self):  # type: ignore[override]
        failures = getattr(self, "table_screenshot_failures", None)
        if not failures:
            return

        desc_positions = []
        try:
            for item in getattr(self, "_desc_p_positions", []):
                p_node = item.get("p")
                if p_node is None or p_node.getparent() is None:
                    continue
                rs = item.get("range_start")
                if rs is None:
                    continue
                try:
                    rs_int = int(rs)
                except (TypeError, ValueError):
                    continue
                num = p_node.get("num")
                if not num:
                    continue
                desc_positions.append((rs_int, num))
            desc_positions.sort(key=lambda x: x[0])
        except Exception:
            desc_positions = []

        claim_ranges = []
        try:
            for item in getattr(self, "_claim_ranges", []):
                rs = item.get("range_start")
                if rs is None:
                    continue
                try:
                    rs_int = int(rs)
                except (TypeError, ValueError):
                    continue
                num = item.get("num")
                if not num:
                    continue
                claim_ranges.append((rs_int, num))
            claim_ranges.sort(key=lambda x: x[0])
        except Exception:
            claim_ranges = []

        for f in failures:
            section_key = f.get("section")
            rs_val = f.get("range_start")
            if rs_val is None:
                continue
            try:
                rs_int = int(rs_val)
            except (TypeError, ValueError):
                continue

            if section_key == "description" and desc_positions:
                best_num = None
                for pos_rs, num in desc_positions:
                    if pos_rs <= rs_int:
                        best_num = num
                    else:
                        break
                if best_num is not None:
                    f["desc_para_num"] = best_num
            elif section_key == "claims" and claim_ranges:
                best_num = None
                for pos_rs, num in claim_ranges:
                    if pos_rs <= rs_int:
                        best_num = num
                    else:
                        break
                if best_num is not None:
                    f["claim_num"] = best_num

    def generate_output_files(self, case_id=None):  # type: ignore[override]
        """在独立工作目录生成 ZIP；失败不会删除或覆盖已有输出。"""
        output_root = self.config['paths']['output_dir']
        output_root_abs = os.path.abspath(output_root)
        if case_id is None:
            bus_cfg = self.config.get('bus', {}) or {}
            case_id = str(bus_cfg.get('case_id', "") or "").strip() or "00000000"
        case_id = str(case_id)
        if len(safe_member_path(case_id).parts) != 1 or re.search(r'[\\/:\x00-\x1f<>"|?*]', case_id):
            raise ValueError("案件编号必须是单个有效目录名")
        os.makedirs(output_root_abs, exist_ok=True)
        workspace = tempfile.mkdtemp(prefix=".conversion-", dir=output_root_abs)
        try:
            result = self._generate_output_files_in_workspace(workspace, case_id)
            register_output_workspace(workspace)
            return result
        except BaseException:
            shutil.rmtree(workspace, ignore_errors=True)
            raise

    def _generate_output_files_in_workspace(self, output_root_abs, case_id):
        case_root = os.path.join(output_root_abs, case_id)
        os.makedirs(case_root, exist_ok=True)
        # 在生成各 XML 和图片前，先规范化说明书与附图的内部结构，贴合 DTD 与客户端期望
        self._normalize_description_structure()
        self._normalize_drawings_structure()
        # 规范化结构完成后，重新整理说明书段落编号，使标题不占用段号
        self._renumber_description_paragraphs()
        self._postprocess_description_period_equations()
        self._postprocess_description_period_tables()
        self._postprocess_table_failure_positions()

        # 定义目录映射
        mapping = {
            'claims': '100001',
            'description': '100002',
            'drawings': '100003',
            'abstract': '100004',
        }

        temp_img_dir = self.config['paths']['temp_dir']
        generated_files_info = []

        enabled = getattr(self, "enabled_sections", None)
        if not isinstance(enabled, dict):
            enabled = {
                'claims': True,
                'description': True,
                'drawings': True,
                'abstract': True,
                'request_form': True,
            }

        moved_desc_img = None
        desc_root = self.sections.get('description')

        # 图片命名前缀：按文种区分
        prefix_by_section = {
            'claims': 'qlyqs',      # 权利要求书图片前缀
            'description': 'sms',   # 说明书图片前缀
            'drawings': 'ft',       # 说明书附图前缀
            # abstract 暂无样本前缀约定，通常也不包含图片
        }
        try:
            prefix_overrides = getattr(self, "image_prefix_overrides", None)
        except Exception:
            prefix_overrides = None
        if isinstance(prefix_overrides, dict):
            for section_key, prefix in prefix_overrides.items():
                section_key = str(section_key or "").strip()
                prefix = str(prefix or "").strip()
                if section_key and prefix:
                    prefix_by_section[section_key] = prefix
        # 每个章节的图片计数器（从 1 开始）
        img_counters = {k: 0 for k in prefix_by_section.keys()}
        # 记录图片移动计划：(section_key, old_filename, new_filename)
        img_move_plan = []
        # 记录各章节对应的输出目录路径
        section_folder_paths = {}

        # 尝试从说明书 XML 中提取发明名称，供 list.xml 和 110101.xml 使用
        invention_title = None
        if desc_root is not None:
            try:
                title_node = next(desc_root.iter('invention-title'))
            except (StopIteration, TypeError):
                title_node = None
            if title_node is not None and (title_node.text or "").strip():
                invention_title = title_node.text.strip()

        # 若说明书未解析到发明名称，则尝试从请求书信息中获取；再退回到输入文件名；最后 case_id；再无则 "output"
        if not invention_title:
            req_info = getattr(self, "request_info", None)
            if isinstance(req_info, dict):
                title_override = req_info.get("title")
                if isinstance(title_override, str) and title_override.strip():
                    invention_title = title_override.strip()

        if not invention_title:
            try:
                input_path = getattr(self, "input_file_path", None)
                if input_path:
                    invention_title = os.path.splitext(os.path.basename(str(input_path)))[0]
            except Exception:
                invention_title = None

        if not invention_title:
            invention_title = getattr(self, "case_id", None) or "output"

        for key, folder_name in mapping.items():
            if not enabled.get(key, True):
                continue
            content_root = self.sections[key]
            if content_root is None or len(content_root) == 0:
                continue

            # 在写入 XML 之前，先根据章节前缀重写图片文件名，并生成移动计划
            prefix = prefix_by_section.get(key)
            if prefix:
                # 根据章节类型确定本次要处理的图片顺序
                if key == 'drawings' and moved_desc_img is not None:
                    all_imgs = list(content_root.iter('img'))
                    if moved_desc_img in all_imgs:
                        imgs = [moved_desc_img] + [img for img in all_imgs if img is not moved_desc_img]
                    else:
                        imgs = all_imgs
                else:
                    imgs = list(content_root.iter('img'))

                for img in imgs:
                    old_file = img.get('file')
                    if not old_file:
                        continue
                    img_counters[key] = img_counters.get(key, 0) + 1
                    ext = ""
                    try:
                        ext = os.path.splitext(str(old_file))[1].lower()
                    except Exception:
                        ext = ""
                    if ext == ".jpeg":
                        ext = ".jpg"
                    elif ext == ".tiff":
                        ext = ".tif"
                    if not ext:
                        ext = ".jpg"

                    new_file = f"{prefix}_{img_counters[key]}{ext}"
                    img.set('file', new_file)
                    img_move_plan.append((key, old_file, new_file))
                    if key == "drawings":
                        try:
                            for item in getattr(self, "_drawings_quality_warnings", []) or []:
                                if isinstance(item, dict) and item.get("temp_file") == old_file:
                                    item["final_file"] = new_file
                        except Exception:
                            pass
                    try:
                        logger.debug(
                            "[IMG_RENAME] section=%s old=%s new=%s",
                            key,
                            old_file,
                            new_file,
                        )
                    except Exception:
                        pass
            else:
                # 无前缀章节（如摘要），保持原文件名，仅记录移动计划
                for img in content_root.iter('img'):
                    old_file = img.get('file')
                    if not old_file:
                        continue
                    img_move_plan.append((key, old_file, old_file))

            # 创建子目录
            folder_path = os.path.join(case_root, folder_name)
            os.makedirs(folder_path)
            section_folder_paths[key] = folder_path

            # 构建完整的 XML 树
            full_root = self.xml.init_xml()
            full_root.append(content_root)

            # 保存 XML
            xml_filename = f"{folder_name}.xml"
            xml_full_path = os.path.join(folder_path, xml_filename)
            self.xml.save(xml_full_path)

            # 估算页数 (PRD: 字符数/1000 + 图片数/2)
            # 简单统计
            text_len = 0
            img_count = 0
            for p in content_root.iter('p'):
                if p.text:
                    text_len += len(p.text)
            for claim_text in content_root.iter('claim-text'):
                if claim_text.text:
                    text_len += len(claim_text.text)
            img_count = len(list(content_root.iter('img')))

            pages = max(1, int(text_len / 1000 + img_count / 2))
            generated_files_info.append((folder_name, xml_filename, pages))

        # 生成请求书 XML（发明 110101 / 实用新型 120101）并记录到清单
        patent_type = getattr(self, "patent_type", None)
        req_info = getattr(self, "request_info", None)
        # 根据附图章节是否存在图片，判断本案是否实际包含说明书附图
        has_drawings = img_counters.get('drawings', 0) > 0
        if enabled.get('request_form', True):
            if patent_type == "utility_model":
                try:
                    self._emit_progress("generate_120101", message="正在生成实用新型专利请求书（120101.xml）...")
                except Exception:
                    pass
                _assert_unique_poa_in_request_info(req_info)
                create_120101_xml(case_root, invention_title, self.config, req_info, has_drawings=has_drawings)
                generated_files_info.append(("120101", "120101.xml", 1))
            else:
                try:
                    self._emit_progress("generate_110101", message="正在生成发明专利请求书（110101.xml）...")
                except Exception:
                    pass
                _assert_unique_poa_in_request_info(req_info)
                create_110101_xml(case_root, invention_title, self.config, req_info, has_drawings=has_drawings)
                generated_files_info.append(("110101", "110101.xml", 1))

        # 根据移动计划，将图片从临时目录拷贝到各章节目录，并使用新的文件名
        for section_key, old_name, new_name in img_move_plan:
            folder_path = section_folder_paths.get(section_key)
            if not folder_path:
                continue
            src = os.path.join(temp_img_dir, old_name)
            dst = os.path.join(folder_path, new_name)
            if os.path.exists(src):
                try:
                    logger.debug(
                        "[IMG_COPY] section=%s src=%s dst=%s",
                        section_key,
                        src,
                        dst,
                    )
                except Exception:
                    pass
                try:
                    copied = False
                    dst_ext = ""
                    try:
                        dst_ext = os.path.splitext(str(dst))[1].lower()
                    except Exception:
                        dst_ext = ""

                    if dst_ext in (".jpg", ".jpeg"):
                        with Image.open(src) as im0:
                            src_fmt = str(getattr(im0, "format", "") or "").upper()
                            if src_fmt == "PNG":
                                im = im0.convert("RGB")
                                img_cfg = self.config.get("image_processing") or {}
                                try:
                                    jpeg_quality = int(img_cfg.get("jpeg_quality", 95))
                                except Exception:
                                    jpeg_quality = 95
                                try:
                                    jpeg_subsampling = int(img_cfg.get("jpeg_subsampling", 0))
                                except Exception:
                                    jpeg_subsampling = 0
                                im.save(
                                    dst,
                                    quality=jpeg_quality,
                                    subsampling=jpeg_subsampling,
                                    dpi=(300, 300),
                                )
                                copied = True

                    if not copied:
                        shutil.copy(src, dst)
                        copied = True
                except Exception:
                    shutil.copy(src, dst)
                    copied = True
                if copied:
                    try:
                        if str(old_name or "").startswith("tbl_"):
                            logger.info(
                                "[TABLE_OUTPUT_MAP] section=%s temp=%s final=%s",
                                section_key,
                                old_name,
                                new_name,
                            )
                    except Exception:
                        pass
                    try:
                        diag_dir = get_existing_equation_diag_dir(self.config, old_name)
                        mapping_path = write_equation_output_mapping(
                            self.config,
                            old_name,
                            temp_source=src,
                            final_output=dst,
                            section_key=section_key,
                        )
                        if diag_dir and mapping_path:
                            logger.info(
                                "[EQ_DIAG_MAP] section=%s temp=%s final=%s diag_dir=%s mapping=%s",
                                section_key,
                                src,
                                dst,
                                diag_dir,
                                mapping_path,
                            )
                    except Exception:
                        pass
            else:
                try:
                    logger.warning("[IMG_COPY_MISS] section=%s missing=%s", section_key, src)
                except Exception:
                    pass

        # 仅当本次实际生成了请求书 XML（110101/120101）时，才生成 list.xml
        has_request_form_entry = any(
            isinstance(item, (list, tuple)) and item and item[0] in ("110101", "120101")
            for item in generated_files_info
        )
        if has_request_form_entry:
            create_data_bus(
                case_root,
                generated_files_info,
                invention_title,
                self.config,
                case_id=case_id,
                patent_type=getattr(self, "patent_type", None),
            )

        # 打包内层案件 ZIP（<case_id>.zip）
        inner_base = os.path.join(output_root_abs, case_id)
        if has_request_form_entry:
            # 有请求书时保持原有结构：ZIP 顶层为 <case_id> 目录
            shutil.make_archive(inner_base, 'zip', root_dir=output_root_abs, base_dir=case_id)
        else:
            # 无请求书时，ZIP 顶层直接为 100001/100002/... 等文书目录，避免多一层 <case_id>
            shutil.make_archive(inner_base, 'zip', root_dir=case_root, base_dir='.')
        inner_zip_path = inner_base + ".zip"

        # 兼容保留 output_package.zip，内容与内层案件 ZIP 一致
        final_zip_path = os.path.join(output_root_abs, "output_package.zip")
        if os.path.exists(final_zip_path):
            os.remove(final_zip_path)
        shutil.copy(inner_zip_path, final_zip_path)

        # 外层时间戳 ZIP，仅包含 <case_id>.zip 一个文件
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        outer_base = os.path.join(output_root_abs, timestamp)
        # 为便于第三方工具直接解压后看到纯数字案件目录，这里的时间戳 ZIP
        # 采用与 inner_zip_path 相同的目录结构，仅更换文件名。
        if has_request_form_entry:
            shutil.make_archive(outer_base, 'zip', root_dir=output_root_abs, base_dir=case_id)
        else:
            shutil.make_archive(outer_base, 'zip', root_dir=case_root, base_dir='.')
        outer_zip_path = outer_base + ".zip"

        logger.info(f"📦 内层案件 ZIP 已生成: {inner_zip_path}")
        logger.info(f"📦 外层时间戳 ZIP 已生成: {outer_zip_path}")

        return {
            "case_id": case_id,
            "case_root": case_root,
            "inner_zip_path": inner_zip_path,
            "final_zip_path": final_zip_path,
            "outer_zip_path": outer_zip_path,
            "invention_title": invention_title,
            "table_screenshot_failures": getattr(self, "table_screenshot_failures", []),
            "object_fallback_failures": getattr(self, "object_fallback_failures", []),
            "drawings_label_report": getattr(self, "_drawings_label_report", None),
            "drawings_quality_warnings": list(getattr(self, "_drawings_quality_warnings", []) or []),
        }
