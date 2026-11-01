from __future__ import annotations

import os
import time

from PIL import Image

from core import clipboard_utils
from core.logging_utils import logger
from core.word_engine_impl.com_compat import add_hidden_document

wdInlineShapePicture = 3
wdInlineShapeLinkedPicture = 4
wdInlineShapeEmbeddedOLEObject = 1
wdInlineShapeLinkedOLEObject = 2


def _description_visible_export_min_width_px(self, shape_obj) -> int:
    try:
        cfg = getattr(self, "config", {}) or {}
        img_cfg = cfg.get("image_processing") or {}
        min_dpi = float(img_cfg.get("description_visible_export_min_dpi", 180.0) or 0.0)
    except Exception:
        min_dpi = 180.0
    if min_dpi <= 0:
        return 0

    try:
        width_point = float(getattr(shape_obj, "Width", 0.0) or 0.0)
    except Exception:
        width_point = 0.0
    if width_point <= 0:
        return 0

    try:
        width_factor = float((getattr(self, "config", {}) or {}).get("width_factor", 0.3528) or 0.3528)
    except Exception:
        width_factor = 0.3528
    width_mm = width_point * width_factor
    if width_mm <= 0:
        return 0
    try:
        return max(1, int(round(width_mm / 25.4 * min_dpi)))
    except Exception:
        return 0


def _description_visible_export_scale_factor(self, current_width_px: int, min_width_px: int) -> float:
    if min_width_px <= 0 or current_width_px <= 0 or current_width_px >= min_width_px:
        return 1.0
    try:
        cfg = getattr(self, "config", {}) or {}
        img_cfg = cfg.get("image_processing") or {}
        max_scale = float(img_cfg.get("description_visible_export_max_scale", 2.0) or 2.0)
    except Exception:
        max_scale = 2.0
    max_scale = max(1.0, min(float(max_scale), 4.0))
    return max(1.0, min(max_scale, (float(min_width_px) / float(current_width_px)) * 1.05))


def _save_description_clipboard_image(self, shape_obj, output_path: str, *, method: str, low_width_reason: str):
    try:
        img = self.img_proc.get_image_from_clipboard()
    except Exception:
        img = None
    if img is None:
        try:
            logger.info(
                "[DESC_VISIBLE_EXPORT] ok=False accepted=False reason=%s_clipboard_empty file=%s",
                method,
                os.path.basename(output_path),
            )
        except Exception:
            pass
        return None, False

    try:
        size = self.img_proc.process_image(
            img,
            output_path,
            is_equation=False,
            crop=True,
            apply_enhancement=True,
            safe_crop_guard=False,
        )
    except Exception:
        size = None
    if not size:
        return None, False

    min_width_px = _description_visible_export_min_width_px(self, shape_obj)
    if min_width_px > 0 and int(size[0]) < min_width_px:
        try:
            logger.info(
                "[DESC_VISIBLE_EXPORT] ok=True accepted=False reason=%s file=%s size=%dx%d min_width_px=%d",
                low_width_reason,
                os.path.basename(output_path),
                int(size[0]),
                int(size[1]),
                int(min_width_px),
            )
        except Exception:
            pass
        return size, False

    try:
        logger.info(
            "[DESC_VISIBLE_EXPORT] ok=True accepted=True method=%s file=%s size=%dx%d min_width_px=%d",
            method,
            os.path.basename(output_path),
            int(size[0]),
            int(size[1]),
            int(min_width_px),
        )
    except Exception:
        pass
    return size, True


def _try_description_visible_export(self, shape_obj, output_path: str):
    if not output_path:
        return None
    try:
        exported = bool(self.word.export_inline_shape_as_picture(shape_obj, output_path))
    except Exception:
        exported = False
    if not exported:
        try:
            logger.info("[DESC_VISIBLE_EXPORT] ok=False accepted=False reason=export_failed file=%s", os.path.basename(output_path))
        except Exception:
            pass
    else:
        try:
            with Image.open(output_path) as img0:
                size = tuple(int(v) for v in img0.size)
        except Exception:
            try:
                logger.info("[DESC_VISIBLE_EXPORT] ok=True accepted=False reason=invalid_image file=%s", os.path.basename(output_path))
            except Exception:
                pass
            size = None

        if size:
            min_width_px = _description_visible_export_min_width_px(self, shape_obj)
            if min_width_px > 0 and int(size[0]) < min_width_px:
                try:
                    logger.info(
                        "[DESC_VISIBLE_EXPORT] ok=True accepted=False reason=low_width file=%s size=%dx%d min_width_px=%d",
                        os.path.basename(output_path),
                        int(size[0]),
                        int(size[1]),
                        int(min_width_px),
                    )
                except Exception:
                    pass
            else:
                try:
                    logger.info(
                        "[DESC_VISIBLE_EXPORT] ok=True accepted=True method=saveas file=%s size=%dx%d min_width_px=%d",
                        os.path.basename(output_path),
                        int(size[0]),
                        int(size[1]),
                        int(min_width_px),
                    )
                except Exception:
                    pass
                return size

    try:
        copied = bool(self.word.copy_shape_to_clipboard(shape_obj, use_copy_as_picture=True))
    except Exception:
        copied = False
    if not copied:
        try:
            logger.info("[DESC_VISIBLE_EXPORT] ok=False accepted=False reason=copyas_failed file=%s", os.path.basename(output_path))
        except Exception:
            pass
        return None

    size, accepted = _save_description_clipboard_image(
        self,
        shape_obj,
        output_path,
        method="copyas",
        low_width_reason="copyas_low_width",
    )
    if accepted:
        return size

    min_width_px = _description_visible_export_min_width_px(self, shape_obj)
    current_width_px = int(size[0]) if size else 0
    scale_factor = _description_visible_export_scale_factor(self, current_width_px, min_width_px)
    if scale_factor <= 1.01 or not hasattr(self.word, "copy_shape_to_clipboard_scaled"):
        return None

    try:
        copied = bool(
            self.word.copy_shape_to_clipboard_scaled(
                shape_obj,
                scale_factor=scale_factor,
                use_copy_as_picture=True,
            )
        )
    except Exception:
        copied = False
    if not copied:
        try:
            logger.info(
                "[DESC_VISIBLE_EXPORT] ok=False accepted=False reason=scaled_copyas_failed file=%s scale=%.2f",
                os.path.basename(output_path),
                float(scale_factor),
            )
        except Exception:
            pass
        return None

    scaled_size, scaled_accepted = _save_description_clipboard_image(
        self,
        shape_obj,
        output_path,
        method="scaled_copyas",
        low_width_reason="scaled_copyas_low_width",
    )
    if scaled_accepted:
        try:
            logger.info(
                "[DESC_VISIBLE_EXPORT_SCALE] file=%s scale=%.2f before_width=%d after_width=%d min_width_px=%d",
                os.path.basename(output_path),
                float(scale_factor),
                int(current_width_px),
                int(scaled_size[0] if scaled_size else 0),
                int(min_width_px),
            )
        except Exception:
            pass
        return scaled_size
    return None


def handle_shape(self, shape_obj, parent_node=None, section_key: str | None = None):  # type: ignore[override]
    """处理 Shape 对象 (截图、处理、保存)"""
    # 根据配置和对象类型，决定是否走 PDF 矢量渲染通路
    eq_cfg = self.config.get("equation_rendering", {})
    mode = str(eq_cfg.get("mode", "pdf")).lower()

    if mode == "pdf_only":
        raise RuntimeError(
            "检测到配置 equation_rendering.mode=pdf_only，但该模式（方案B）已全局禁用。"
            "请将 equation_rendering.mode 改为 pdf 或 screenshot，并确保安装 Microsoft Word 后重试。"
        )
    is_equation = self._is_equation_shape(shape_obj)
    use_pdf_for_eq = mode in ("pdf", "pdf_only") and is_equation
    skip_emf_for_eq = mode == "pdf_only" and is_equation
    logger.debug(f"[EQ_DEBUG] handle_shape: mode={mode}, use_pdf_for_eq={use_pdf_for_eq}")

    # [FIX-B] 初始化像素密度覆盖变量（方案B修复）
    px_per_mm_for_ole = None
    # 必须先初始化：当公式走 EMF/PDF 通路时也会在后续引用
    pre_crop_size = None

    # [FIX] KingDraw/ChemDraw 等 OLE 对象的原生 EMF 数据可能缺失内容，使用 ClassType 黑名单精准拦截
    is_ole_object = False
    ole_class_type = None
    try:
        t = int(getattr(shape_obj, "Type", 0) or 0)
        if t in (wdInlineShapeEmbeddedOLEObject, wdInlineShapeLinkedOLEObject):
            ole_fmt = getattr(shape_obj, "OLEFormat", None)
            if ole_fmt:
                ole_class_type = str(getattr(ole_fmt, "ClassType", "") or "").lower()
                # 从配置读取黑名单，默认包含 chemdraw 和 kingdraw
                ole_cfg = self.config.get("ole_compatibility", {}) or {}
                BROKEN_OLE_BLACKLIST = ole_cfg.get("broken_ole_classtype_blacklist", ["chemdraw", "kingdraw"]) or ["chemdraw", "kingdraw"]
                if any(keyword in ole_class_type for keyword in BROKEN_OLE_BLACKLIST):
                    is_ole_object = True
                    # 关键策略：对这类对象跳过 EMF（可能丢失线条/内容），优先走 PDF，
                    # 并保持 wi/he 仍按 Word 逻辑宽度计算，避免 PDF 预览中出现“过大”问题。
                    skip_emf_for_eq = True
                    if use_pdf_for_eq:
                        logger.info(f"🚫 检测到已知兼容性差的 OLE 对象: {ole_class_type}，将跳过 EMF，优先使用 PDF 渲染，失败再回退 CopyAsPicture")
                    else:
                        logger.info(f"🚫 检测到已知兼容性差的 OLE 对象: {ole_class_type}，将跳过 EMF，回退 CopyAsPicture")
    except Exception as e:
        logger.debug(f"OLE ClassType 检测异常: {e}")
        is_ole_object = False


    effective_section_key = str(section_key or "").strip()
    if not effective_section_key:
        effective_section_key = self._get_parent_section_key(parent_node)
    section_key = effective_section_key
    is_drawings_section = section_key == "drawings"
    drawings_target_width_px = None
    if is_drawings_section:
        try:
            drawings_target_width_px = self._get_drawings_target_width_px_for_shape(shape_obj)
        except Exception:
            drawings_target_width_px = None

    xml_content = None
    crop_info = None
    try:
        rng = getattr(shape_obj, "Range", None)
        xml_content = getattr(rng, "WordOpenXML", None) if rng is not None else None
        crop_info = self._extract_image_crop_from_openxml(xml_content)
    except Exception:
        crop_info = None

    explicit_pf_crop = None
    try:
        # 对 InlineShape 图片（Type=3/4），PictureFormat 的裁切是“可视裁切”的关键来源。
        # 如果命中，则后续必须禁用二次白边裁切，避免把可视内容再裁掉导致“缺边”。
        if not crop_info:
            explicit_pf_crop = self._extract_image_crop_from_pictureformat(shape_obj)
    except Exception:
        explicit_pf_crop = None

    classification = None
    try:
        classification = self._classify_external_object(
            shape_obj,
            section_key=section_key,
            xml_content=xml_content,
        )
    except Exception:
        classification = None

    if isinstance(classification, dict):
        try:
            logger.info(
                "[OBJECT_ROUTE] section=%s classifier=%s kind=%s reason=%s source=%s",
                section_key,
                classification.get("classifier"),
                classification.get("object_kind"),
                classification.get("reason_code"),
                classification.get("source_hint"),
            )
        except Exception:
            pass

        classifier = str(classification.get("classifier") or "").strip()
        if classifier == "preview_embedded":
            preview_rid = str(classification.get("preview_rid") or "").strip()
            preview_queue_item = None
            if is_drawings_section:
                try:
                    preview_queue_item = self._consume_drawings_inline_package_item(
                        runtime_rid=preview_rid,
                        section_key=section_key,
                    )
                except Exception:
                    preview_queue_item = None
            extracted = None
            if isinstance(preview_queue_item, dict):
                preview_zip_path = str(preview_queue_item.get("zip_path") or "").strip()
                preview_package_rid = str(preview_queue_item.get("rid") or "").strip()
                if preview_zip_path and not self._check_drawings_package_media_integrity(preview_zip_path):
                    raise RuntimeError(
                        "源文件中的说明书附图内嵌图片数据已损坏，无法可靠恢复完整内容；"
                        "为避免生成缺图或黑块，已停止转换。请在 Word 中删除该图片并重新插入原图后再转换。"
                    )
                try:
                    if preview_zip_path:
                        extracted = self._extract_drawings_media_zip_path_to_temp(
                            zip_path=preview_zip_path,
                            filename_prefix="obj_",
                            force_jpg_for_non_tiff=True,
                            target_width_px=drawings_target_width_px,
                        )
                    elif preview_package_rid:
                        extracted = self._extract_drawings_media_to_temp(
                            rid=preview_package_rid,
                            filename_prefix="obj_",
                            force_jpg_for_non_tiff=True,
                            target_width_px=drawings_target_width_px,
                        )
                except Exception:
                    extracted = None
            if not extracted and preview_rid:
                try:
                    extracted = self._extract_drawings_media_to_temp(
                        rid=preview_rid,
                        filename_prefix="obj_",
                        force_jpg_for_non_tiff=True,
                        target_width_px=drawings_target_width_px,
                    )
                except Exception:
                    extracted = None
            if extracted:
                try:
                    filename, output_path = extracted
                except Exception:
                    filename, output_path = None, None
                if filename and output_path and os.path.exists(output_path):
                    try:
                        with Image.open(output_path) as _img0:
                            processed_size = tuple(int(v) for v in _img0.size)
                    except Exception:
                        processed_size = (600, 300)
                    captured_size = processed_size
                    preview_frame = None
                    if is_drawings_section:
                        try:
                            preview_frame = self._get_drawings_display_frame(
                                shape_obj,
                                processed_img_size=processed_size,
                            )
                            opt_size = self.img_proc.optimize_drawings_image_file(
                                output_path,
                                ratio_num=float(preview_frame.get("ratio_num") or processed_size[0] or 1),
                                ratio_den=float(preview_frame.get("ratio_den") or processed_size[1] or 1),
                                allow_edge_crop=False,
                            )
                            if opt_size:
                                processed_size = opt_size
                        except Exception:
                            pass
                    width_mm, height_mm = self._estimate_external_object_dimensions_mm(
                        shape_obj,
                        section_key=section_key,
                        processed_size=processed_size,
                    )
                    if is_drawings_section:
                        try:
                            self._log_drawings_size_provenance(
                                object_kind=str(classification.get("object_kind") or "external_object"),
                                route="PREVIEW",
                                frame=preview_frame,
                                captured_size=captured_size,
                                final_size=processed_size,
                                width_mm=float(width_mm),
                                height_mm=float(height_mm),
                            )
                        except Exception:
                            pass
                    self._record_object_fallback_failure(
                        shape_obj=shape_obj,
                        classification=classification,
                        parent_node=parent_node,
                        section_key=section_key,
                        resolution_code="preview_extracted",
                    )
                    if hasattr(self, "_record_image_pipeline"):
                        self._record_image_pipeline("MEDIA")  # type: ignore[func-returns-value]
                    return filename, float(width_mm), float(height_mm), None
            return self._emit_external_object_placeholder(
                shape_obj,
                parent_node=parent_node,
                section_key=section_key,
                classification=classification,
            )

        if classifier in ("activation_risky", "unsupported"):
            return self._emit_external_object_placeholder(
                shape_obj,
                parent_node=parent_node,
                section_key=section_key,
                classification=classification,
            )

    is_inline_picture = self._is_inline_picture_shape(shape_obj)
    try:
        inline_type_code = int(getattr(shape_obj, "Type", 0) or 0)
    except Exception:
        inline_type_code = 0
    runtime_rid = None
    inline_queue_item = None
    package_crop_info = None
    queue_eligible = bool(is_inline_picture and inline_type_code == wdInlineShapePicture and (not is_ole_object) and (not is_equation))
    try:
        runtime_rid = self._extract_image_rid_from_openxml(xml_content)
    except Exception:
        runtime_rid = None
    if is_drawings_section and queue_eligible:
        try:
            inline_queue_item = self._consume_drawings_inline_package_item(
                runtime_rid=runtime_rid,
                section_key=section_key,
            )
        except Exception:
            inline_queue_item = None
        if isinstance(inline_queue_item, dict):
            maybe_crop = inline_queue_item.get("crop_info")
            if isinstance(maybe_crop, dict):
                package_crop_info = maybe_crop
            try:
                logger.info(
                    "[INLINE_QUEUE_ADVANCE] queue_scope=drawings_inline section=%s rid=%s queue_rid=%s",
                    section_key,
                    str(runtime_rid or ""),
                    str(inline_queue_item.get("rid") or ""),
                )
            except Exception:
                pass

    # 生成文件名
    # 这里有点 Hack，因为 ID 是 XMLBuilder 管理的。
    # 我们先生成一个临时 ID 用于文件名，实际 XML ID 由 XMLBuilder 再次生成
    # 为了保持一致，我们最好让 XMLBuilder 提供下一个 ID，或者...
    # 简单起见：我们用 UUID 或时间戳做文件名，XML 里的 ID 是逻辑 ID。
    # PRD 要求: file="xxx.jpg"。
    # 我们可以先生成图片，文件名无所谓（只要 XML 引用对就行）。
    # 建议：img_{uuid}.jpg
    import uuid

    filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
    output_path = os.path.join(self.config["paths"]["temp_dir"], filename)  # 先存临时

    processed_size = None
    pipeline_source = None
    ratio_source = "processed_image_fallback"
    drawings_frame = None
    if is_drawings_section and (not is_equation):
        self._drawings_media_integrity_failure = None
        extracted = None
        rid_source = None
        media_allowed = False
        media_gate = ""

        media_gate = self._get_drawings_media_gate_reason(
            crop_info=crop_info,
            package_crop_info=package_crop_info,
            explicit_pf_crop=explicit_pf_crop,
        )
        media_allowed = self._should_extract_drawings_from_media(
            crop_info=crop_info,
            package_crop_info=package_crop_info,
            explicit_pf_crop=explicit_pf_crop,
        )

        package_rid = ""
        package_zip_path = ""
        if isinstance(inline_queue_item, dict):
            package_rid = str(inline_queue_item.get("rid") or "")
            package_zip_path = str(inline_queue_item.get("zip_path") or "")

        if package_zip_path and not self._check_drawings_package_media_integrity(package_zip_path):
            raise RuntimeError(
                "源文件中的说明书附图内嵌图片数据已损坏，无法可靠恢复完整内容；"
                "为避免生成缺图或黑块，已停止转换。请在 Word 中删除该图片并重新插入原图后再转换。"
            )

        if media_allowed and (package_zip_path or package_rid):
            try:
                logger.info(
                    "[INLINE_MEDIA_TRY] rid_source=package_queue rid=%s media_gate=%s queue_scope=drawings_inline section=%s",
                    package_rid,
                    media_gate or "open",
                    section_key,
                )
            except Exception:
                pass
            try:
                if package_zip_path:
                    extracted = self._extract_drawings_media_zip_path_to_temp(
                        zip_path=package_zip_path,
                        filename_prefix="img_",
                        force_jpg_for_non_tiff=True,
                        target_width_px=drawings_target_width_px,
                    )
                elif package_rid:
                    extracted = self._extract_drawings_media_to_temp(
                        rid=package_rid,
                        filename_prefix="img_",
                        force_jpg_for_non_tiff=True,
                        target_width_px=drawings_target_width_px,
                    )
                else:
                    extracted = None
                if extracted:
                    rid_source = "package_queue"
                    logger.info(
                        "[INLINE_MEDIA_HIT] rid_source=package_queue rid=%s media_gate=%s queue_scope=drawings_inline section=%s",
                        package_rid,
                        media_gate or "open",
                        section_key,
                    )
                else:
                    logger.info(
                        "[INLINE_MEDIA_MISS] rid_source=package_queue rid=%s media_gate=%s queue_scope=drawings_inline section=%s",
                        package_rid,
                        media_gate or "open",
                        section_key,
                    )
                    self._disable_drawings_inline_package_queue(
                        f"package_media_extract_failed rid={package_rid or 'missing'} zip_path={package_zip_path or 'missing'}",
                        section_key=section_key,
                    )
            except Exception:
                extracted = None

        if media_allowed and (not extracted) and runtime_rid and not (package_zip_path or package_rid):
            try:
                logger.info(
                    "[INLINE_MEDIA_TRY] rid_source=runtime_xml rid=%s media_gate=%s queue_scope=drawings_inline section=%s",
                    runtime_rid,
                    media_gate or "open",
                    section_key,
                )
            except Exception:
                pass
            try:
                extracted = self._extract_drawings_media_to_temp(
                    rid=runtime_rid,
                    filename_prefix="img_",
                    force_jpg_for_non_tiff=True,
                    target_width_px=drawings_target_width_px,
                )
                if extracted:
                    rid_source = "runtime_xml"
                    logger.info(
                        "[INLINE_MEDIA_HIT] rid_source=runtime_xml rid=%s media_gate=%s queue_scope=drawings_inline section=%s",
                        runtime_rid,
                        media_gate or "open",
                        section_key,
                    )
                else:
                    logger.info(
                        "[INLINE_MEDIA_MISS] rid_source=runtime_xml rid=%s media_gate=%s queue_scope=drawings_inline section=%s",
                        runtime_rid,
                        media_gate or "open",
                        section_key,
                    )
            except Exception:
                extracted = None

        if extracted:
            try:
                filename, output_path = extracted
            except Exception:
                filename, output_path = None, None
            if filename and output_path and os.path.exists(output_path):
                explicit_crop_applied = False
                effective_crop_info = crop_info or package_crop_info
                try:
                    with Image.open(output_path) as _img0:
                        base_w_px, base_h_px = _img0.size
                except Exception:
                    base_w_px, base_h_px = 0, 0
                captured_size = (int(base_w_px), int(base_h_px))
                try:
                    cropped_size = self._apply_explicit_crop_to_file(output_path, effective_crop_info)
                    if cropped_size:
                        base_w_px, base_h_px = cropped_size
                        explicit_crop_applied = True
                except Exception:
                    pass
                try:
                    drawings_frame = self._get_drawings_display_frame(
                        shape_obj,
                        processed_img_size=(int(base_w_px), int(base_h_px)),
                    )
                    ratio_source = str(drawings_frame.get("ratio_source") or "processed_image_fallback")
                except Exception:
                    drawings_frame = {
                        "width_point": 100.0,
                        "height_point": None,
                        "ratio_num": float(base_w_px or 1),
                        "ratio_den": float(base_h_px or 1),
                        "ratio_source": "processed_image_fallback",
                    }
                    ratio_source = "processed_image_fallback"
                try:
                    opt_size = self.img_proc.optimize_drawings_image_file(
                        output_path,
                        ratio_num=float(drawings_frame.get("ratio_num") or base_w_px or 1),
                        ratio_den=float(drawings_frame.get("ratio_den") or base_h_px or 1),
                        allow_edge_crop=False,
                    )
                    if opt_size:
                        base_w_px, base_h_px = opt_size
                except Exception:
                    pass
                try:
                    width_mm, height_mm = self.img_proc.calculate_drawings_dimensions(
                        drawings_frame.get("width_point"),
                        drawings_frame.get("height_point"),
                        (int(base_w_px), int(base_h_px)),
                    )
                except Exception:
                    width_mm, height_mm = 0, 0
                try:
                    self._maybe_record_drawings_bitmap_dpi_warning(
                        filename=str(filename),
                        display_width_mm=float(width_mm),
                        pixel_width=int(base_w_px),
                        pixel_height=int(base_h_px),
                    )
                except Exception:
                    pass
                try:
                    logger.info(
                        "[DRAWINGS_CAPTURE] file=%s source=MEDIA rid_source=%s final=%s exact_crop=%s edge_crop=%s ratio_source=%s size=%dx%d",
                        filename,
                        rid_source or "runtime_xml",
                        os.path.splitext(str(filename))[1].lower().lstrip("."),
                        bool(explicit_crop_applied),
                        bool(getattr(self.img_proc, "_last_drawings_opt_meta", {}).get("edge_cropped")),
                        ratio_source,
                        int(base_w_px),
                        int(base_h_px),
                    )
                except Exception:
                    pass
                try:
                    self._log_drawings_size_provenance(
                        object_kind=str((inline_queue_item or {}).get("object_kind") or "inline_picture"),
                        route="MEDIA",
                        frame=drawings_frame,
                        captured_size=captured_size,
                        final_size=(int(base_w_px), int(base_h_px)),
                        width_mm=float(width_mm),
                        height_mm=float(height_mm),
                    )
                except Exception:
                    pass
                if hasattr(self, "_record_image_pipeline"):
                    self._record_image_pipeline("MEDIA")  # type: ignore[func-returns-value]
                return filename, float(width_mm), float(height_mm), px_per_mm_for_ole

        try:
            exported = bool(self.word.export_inline_shape_as_picture(shape_obj, output_path))
        except Exception:
            exported = False
        try:
            logger.info(
                "[INLINE_SAVEAS] ok=%s file=%s queue_scope=drawings_inline section=%s",
                bool(exported),
                filename,
                section_key,
            )
        except Exception:
            pass

        pdf_attempted = False
        pdf_ok = False
        if (not exported) and getattr(self.word, "app", None) is not None:
            try:
                import fitz

                app = self.word.app
                pdf_dpi = 600
                try:
                    pdf_dpi = int((self.config.get("table_capture") or {}).get("pdf_dpi", 600) or 600)
                except Exception:
                    pdf_dpi = 600
                base_name, _ = os.path.splitext(os.path.basename(output_path))
                temp_dir = os.path.abspath(self.config["paths"]["temp_dir"])
                os.makedirs(temp_dir, exist_ok=True)
                pdf_path = os.path.join(temp_dir, f"{base_name}_drawings.pdf")
                png_path = os.path.join(temp_dir, f"{base_name}_drawings.png")
                new_doc = None
                pdf_attempted = True
                try:
                    new_doc = add_hidden_document(app, logger=logger)
                    new_doc.Range(0, 0).FormattedText = shape_obj.Range
                    wdExportFormatPDF = 17
                    new_doc.ExportAsFixedFormat(OutputFileName=str(pdf_path), ExportFormat=wdExportFormatPDF)
                finally:
                    if new_doc is not None:
                        try:
                            new_doc.Close(False)
                        except Exception:
                            pass

                doc_pdf = fitz.open(pdf_path)
                try:
                    if doc_pdf.page_count > 0:
                        page = doc_pdf[0]
                        zoom = float(pdf_dpi) / 72.0
                        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                        pix.save(png_path)
                        with Image.open(png_path) as _img_pdf:
                            processed_size = self.img_proc.process_image(
                                _img_pdf.copy(),
                                output_path,
                                is_equation=False,
                                crop=False,
                                apply_enhancement=False,
                                safe_crop_guard=False,
                            )
                        if processed_size is not None:
                            pipeline_source = "PDF"
                            pdf_ok = True
                finally:
                    try:
                        doc_pdf.close()
                    except Exception:
                        pass
            except Exception:
                processed_size = None
        if pdf_attempted:
            try:
                logger.info(
                    "[INLINE_PDF] ok=%s file=%s queue_scope=drawings_inline section=%s",
                    bool(pdf_ok),
                    filename,
                    section_key,
                )
            except Exception:
                pass

        if exported or processed_size is not None:
            try:
                with Image.open(output_path) as _img0:
                    base_w_px, base_h_px = _img0.size
            except Exception:
                base_w_px, base_h_px = 0, 0
            captured_size = (int(base_w_px), int(base_h_px))
            try:
                drawings_frame = self._get_drawings_display_frame(
                    shape_obj,
                    processed_img_size=(int(base_w_px), int(base_h_px)),
                )
                ratio_source = str(drawings_frame.get("ratio_source") or "processed_image_fallback")
            except Exception:
                drawings_frame = {
                    "width_point": 100.0,
                    "height_point": None,
                    "ratio_num": float(base_w_px or 1),
                    "ratio_den": float(base_h_px or 1),
                    "ratio_source": "processed_image_fallback",
                }
                ratio_source = "processed_image_fallback"
            try:
                opt_size = self.img_proc.optimize_drawings_image_file(
                    output_path,
                    ratio_num=float(drawings_frame.get("ratio_num") or base_w_px or 1),
                    ratio_den=float(drawings_frame.get("ratio_den") or base_h_px or 1),
                    allow_edge_crop=True,
                )
                if opt_size:
                    base_w_px, base_h_px = opt_size
            except Exception:
                pass
            try:
                width_mm, height_mm = self.img_proc.calculate_drawings_dimensions(
                    drawings_frame.get("width_point"),
                    drawings_frame.get("height_point"),
                    (int(base_w_px), int(base_h_px)),
                )
            except Exception:
                width_mm, height_mm = 0, 0
            if pipeline_source is None:
                pipeline_source = "SAVEAS"
            try:
                logger.info(
                    "[DRAWINGS_CAPTURE] file=%s source=%s final=%s exact_crop=%s edge_crop=%s ratio_source=%s size=%dx%d",
                    filename,
                    pipeline_source,
                    os.path.splitext(str(filename))[1].lower().lstrip("."),
                    False,
                    bool(getattr(self.img_proc, "_last_drawings_opt_meta", {}).get("edge_cropped")),
                    ratio_source,
                    int(base_w_px),
                    int(base_h_px),
                )
            except Exception:
                pass
            try:
                self._log_drawings_size_provenance(
                    object_kind="inline_picture",
                    route=str(pipeline_source or "SAVEAS"),
                    frame=drawings_frame,
                    captured_size=captured_size,
                    final_size=(int(base_w_px), int(base_h_px)),
                    width_mm=float(width_mm),
                    height_mm=float(height_mm),
                )
            except Exception:
                pass
            if pipeline_source and hasattr(self, "_record_image_pipeline"):
                self._record_image_pipeline(str(pipeline_source))  # type: ignore[func-returns-value]
            return filename, float(width_mm), float(height_mm), px_per_mm_for_ole


    # 0. 优先尝试 EMF 矢量提取通路 (针对高版本 Word/无 OLE 情况)
    if (
        processed_size is None
        and section_key == "description"
        and (not is_equation)
        and is_inline_picture
        and (not is_ole_object)
    ):
        classifier_key = ""
        try:
            classifier_key = str(classification.get("classifier") or "") if isinstance(classification, dict) else ""
        except Exception:
            classifier_key = ""
        if classifier_key in ("", "word_render_safe", "package_direct"):
            try:
                visible_size = _try_description_visible_export(self, shape_obj, output_path)
            except Exception:
                visible_size = None
            if visible_size:
                processed_size = visible_size
                pre_crop_size = visible_size
                pipeline_source = "SAVEAS"

    # 0. 优先尝试 EMF 矢量提取通路 (针对高版本 Word/无 OLE 情况)
    # 只要被判定为公式，或者配置强制开启
    if is_equation and not skip_emf_for_eq:
        try:
            # 执行标准复制 (保留矢量信息)
            emf_ready = self._copy_range_to_fresh_clipboard(
                lambda: shape_obj.Range.Copy(),
                clipboard_utils.EMF_CLIPBOARD_FORMATS,
                label="shape_emf",
            )
            # 尝试从剪贴板渲染 EMF
            emf_crop = True
            if crop_info:
                emf_crop = False
            eq_img_cfg = self.config.get("image_processing") or {}
            try:
                eq_pad_min = int(eq_img_cfg.get("equation_crop_padding_min", self.config.get("crop_padding_min", 4)) or 0)
            except Exception:
                eq_pad_min = 4
            if emf_ready:
                processed_size = self.img_proc.save_emf_from_clipboard(
                    output_path,
                    crop=emf_crop,
                    padding_ratio=0.0,
                    padding_min=max(0, int(eq_pad_min)),
                    preserve_detached_equation_marks=True,
                )
            if processed_size:
                logger.debug("✅ [EMF通路] 成功通过剪贴板 EMF 渲染高清公式")
                pipeline_source = "EMF"
                try:
                    with Image.open(output_path) as _img0:
                        _img = _img0.copy()
                    try:
                        if pre_crop_size is None:
                            pre_crop_size = _img.size
                    except Exception:
                        pass
                    enhanced_size = self.img_proc.process_image(
                        _img,
                        output_path,
                        is_equation=True,
                        crop=bool(crop_info),
                        apply_enhancement=True,
                    )
                    if enhanced_size:
                        processed_size = enhanced_size
                        try:
                            w_px, h_px = enhanced_size
                            logger.debug(
                                "[EMF_EQ_ENHANCE] object=shape_equation size=%dx%d file=%s",
                                w_px,
                                h_px,
                                os.path.basename(output_path),
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            logger.warning("⚠️ 内部图像渲染通路尝试失败，将回退为其它方式")

    # 优先尝试 PDF 矢量通路（仅对公式）
    if processed_size is None and use_pdf_for_eq:
        processed_size = self._render_equation_via_pdf(shape_obj, output_path)
        if processed_size is None:
            logger.info("ℹ️ PDF 公式渲染失败，回退为截图通路")
        else:
            pipeline_source = pipeline_source or "PDF"

    # 如未启用 PDF 或 PDF 通路失败，则回退为截图通路
    if processed_size is None:
        img = None

        if not is_equation:
            if not self.word.copy_shape_to_clipboard(shape_obj):
                return None, 0, 0, None

            time.sleep(0.3)
            img = self.img_proc.get_image_from_clipboard()

            if img is None:
                logger.debug("ℹ️ 普通图片剪贴板位图读取失败，尝试 Range.CopyAsPicture 兜底")
                if self.word.copy_range_as_picture(shape_obj.Range):
                    time.sleep(0.3)
                    img = self.img_proc.get_image_from_clipboard()

            if img is None:
                logger.warning("⚠️ 普通图片在所有剪贴板通路中均未获取到有效数据")
                return None, 0, 0, None
        else:
            # [FIX] 如果是 OLE 公式，强制使用 CopyAsPicture，避免普通 Copy 拿到残缺数据
            use_cap = is_ole_object
            if use_cap:
                logger.debug("forcing CopyAsPicture for OLE equation fallback")

            bitmap_ready = self._copy_range_to_fresh_clipboard(
                lambda: self.word.copy_range_as_picture(shape_obj.Range, use_copy_as_picture=use_cap),
                clipboard_utils.IMAGE_CLIPBOARD_FORMATS,
                label="shape_equation_bitmap",
            )
            if not bitmap_ready:
                return None, 0, 0, None
            time.sleep(0.3)
            img = self.img_proc.get_image_from_clipboard()
            if img is None:
                logger.warning("⚠️ 公式截图通路未读取到有效位图")
                return None, 0, 0, None

        if processed_size is None and img is not None:
            pre_crop_size = img.size  # 裁剪前像素尺寸
            if is_drawings_section and (not is_equation):
                processed_size = self.img_proc.process_image(
                    img,
                    output_path,
                    is_equation=False,
                    crop=False,
                    apply_enhancement=False,
                    safe_crop_guard=False,
                )
                try:
                    drawings_frame = self._get_drawings_display_frame(
                        shape_obj,
                        processed_img_size=processed_size,
                    )
                    ratio_source = str(drawings_frame.get("ratio_source") or "processed_image_fallback")
                except Exception:
                    drawings_frame = {
                        "width_point": 100.0,
                        "height_point": None,
                        "ratio_num": float(processed_size[0] if processed_size else 1),
                        "ratio_den": float(processed_size[1] if processed_size else 1),
                        "ratio_source": "processed_image_fallback",
                    }
                    ratio_source = "processed_image_fallback"
                if processed_size is not None:
                    try:
                        opt_size = self.img_proc.optimize_drawings_image_file(
                            output_path,
                            ratio_num=float(drawings_frame.get("ratio_num") or processed_size[0] or 1),
                            ratio_den=float(drawings_frame.get("ratio_den") or processed_size[1] or 1),
                            allow_edge_crop=True,
                        )
                        if opt_size:
                            processed_size = opt_size
                    except Exception:
                        pass
            else:
                processed_size = self.img_proc.process_image(
                    img,
                    output_path,
                    is_equation=is_equation,
                    crop=is_equation or (not bool(crop_info) and not bool(explicit_pf_crop)),
                    safe_crop_guard=(bool(crop_info) or bool(explicit_pf_crop)) and (not is_equation),
                )
            if processed_size is not None and pipeline_source is None:
                pipeline_source = "BITMAP"
            if explicit_pf_crop and filename:
                try:
                    logger.debug(
                        "[IMG_CROP_EXPLICIT] file=%s source=PictureFormat raw=%s",
                        filename,
                        explicit_pf_crop.get("_raw"),
                    )
                except Exception:
                    pass


    # 3. 计算尺寸
    # 获取 Word 中的宽度 (Points)
    try:
        width_point = shape_obj.Width
    except Exception:
        width_point = 100  # Fallback

    if is_equation:
        if is_ole_object:
            # [FIX] 黑名单 OLE 对象（如 KingDraw/ChemDraw）使用 Word 逻辑宽度计算，
            # 避免 CopyAsPicture 导致的像素尺寸过大问题
            width_mm, height_mm = self.img_proc.calculate_xml_dimensions(width_point, processed_size)
            logger.debug(f"黑名单 OLE 公式使用 calculate_xml_dimensions: width_point={width_point}, size={processed_size}")

            # [FIX-B] 对于黑名单 OLE，若存在裁剪前尺寸，计算并传递原始像素密度，供后续补白使用
            if pre_crop_size and width_mm > 0:
                try:
                    px_per_mm_for_ole = float(pre_crop_size[0]) / float(width_mm)
                    logger.debug(f"方案B计算像素密度: pre_crop_w={pre_crop_size[0]}, width_mm={width_mm}, px_per_mm={px_per_mm_for_ole}")
                except Exception as e:
                    logger.debug(f"方案B计算像素密度失败: {e}")
                    px_per_mm_for_ole = None
        else:
            width_mm, height_mm = self.img_proc.calculate_equation_dimensions(processed_size)

    elif is_drawings_section:
        if not isinstance(drawings_frame, dict):
            try:
                drawings_frame = self._get_drawings_display_frame(
                    shape_obj,
                    processed_img_size=processed_size,
                )
            except Exception:
                drawings_frame = {
                    "width_point": float(width_point),
                    "height_point": None,
                    "ratio_num": None,
                    "ratio_den": None,
                    "ratio_source": "processed_image_fallback",
                }
        ratio_source = str(drawings_frame.get("ratio_source") or ratio_source)
        width_mm, height_mm = self.img_proc.calculate_drawings_dimensions(
            drawings_frame.get("width_point"),
            drawings_frame.get("height_point"),
            processed_size,
        )

    else:
        width_mm, height_mm = self.img_proc.calculate_xml_dimensions(width_point, processed_size)

    try:
        src = pipeline_source or "UNKNOWN"
        logger.debug(
            "[IMG_CAPTURE_DETAIL] file=%s src=%s pre_crop_size=%s processed=%s crop_info=%s pf_crop=%s ratio_source=%s wp=%.1f wmm=%.2f hmm=%.2f",
            filename,
            src,
            pre_crop_size,
            processed_size,
            bool(crop_info),
            bool(explicit_pf_crop),
            ratio_source,
            float(width_point),
            float(width_mm),
            float(height_mm),
        )
    except Exception:
        pass

    try:
        if processed_size is not None:
            w_px, h_px = processed_size
            obj_kind = "table" if str(filename or "").startswith("tbl_") else "paragraph"
            src = pipeline_source or "BITMAP"
            if src == "EMF":
                logger.info(
                    "IMG_PIPELINE: object=%s source=EMF size=%dx%d",
                    obj_kind,
                    w_px,
                    h_px,
                )
                if hasattr(self, "_record_image_pipeline"):
                    self._record_image_pipeline("EMF")  # type: ignore[func-returns-value]
            elif src == "BITMAP":
                logger.info(
                    "IMG_PIPELINE: object=%s source=BITMAP size=%dx%d",
                    obj_kind,
                    w_px,
                    h_px,
                )
                if hasattr(self, "_record_image_pipeline"):
                    self._record_image_pipeline("BITMAP")  # type: ignore[func-returns-value]
            elif src == "PDF":
                logger.info(
                    "IMG_PIPELINE: object=%s source=PDF size=%dx%d",
                    obj_kind,
                    w_px,
                    h_px,
                )
                if hasattr(self, "_record_image_pipeline"):
                    self._record_image_pipeline("PDF")  # type: ignore[func-returns-value]
            elif src == "SAVEAS":
                logger.info(
                    "IMG_PIPELINE: object=%s source=SAVEAS size=%dx%d",
                    obj_kind,
                    w_px,
                    h_px,
                )
                if hasattr(self, "_record_image_pipeline"):
                    self._record_image_pipeline("SAVEAS")  # type: ignore[func-returns-value]
    except Exception:
        pass

    if is_drawings_section:
        try:
            self._log_drawings_size_provenance(
                object_kind="inline_picture",
                route=str(pipeline_source or "UNKNOWN"),
                frame=drawings_frame,
                captured_size=pre_crop_size,
                final_size=processed_size,
                width_mm=float(width_mm),
                height_mm=float(height_mm),
            )
        except Exception:
            pass

    return filename, width_mm, height_mm, px_per_mm_for_ole

