from __future__ import annotations

import os
import time

from PIL import Image

from core.logging_utils import logger
from core.word_engine_impl.com_compat import add_hidden_document

wdInlineShapePicture = 3
wdInlineShapeLinkedPicture = 4
wdInlineShapeEmbeddedOLEObject = 1
wdInlineShapeLinkedOLEObject = 2


def _process_floating_shapes(self, para, parent_node, current_section_key: str) -> bool:
    """处理段落中的浮动 Shape（ShapeRange）。

    现状约束：
    - 段落浮动对象（如“环绕型图片/化学结构式”）不在 InlineShapes 中；
    - 直接忽略会导致内容缺失，但更严重的是 paragraph_mixin 会调用本方法，
      若未实现则会触发 AttributeError 使转换中止。

    当前实现策略（保守，优先不崩溃）：
    - 对非 claims 段落：先按现有逻辑输出段落文本/行内对象；
    - 再尝试将 ShapeRange 中的对象逐个复制为图片并作为 block `<img inline="no">` 追加；
    - 对 claims：暂不处理浮动对象（避免破坏 claim 缓冲/编号逻辑），返回 False 走原有流程。
    """
    if current_section_key == "claims":
        return False

    try:
        rng = para.Range
    except Exception:
        return False

    shape_range = None
    try:
        shape_range = getattr(rng, "ShapeRange", None)
    except Exception:
        shape_range = None
    if shape_range is None:
        return False

    try:
        shape_count = int(getattr(shape_range, "Count", 0) or 0)
    except Exception:
        shape_count = 0
    if shape_count <= 0:
        return False

    # 先按既有流程输出段落文本/行内对象，避免跳过导致文本丢失
    try:
        self.process_paragraph_content(
            para,
            parent_node,
            is_claim=False,
        )
    except Exception:
        # 即使段落处理失败，也不要因为浮动对象导致整个转换中止
        pass

    temp_dir = None
    try:
        temp_dir = os.path.abspath(self.config["paths"]["temp_dir"])
    except Exception:
        temp_dir = None
    if not temp_dir:
        return True

    parent_tag = getattr(parent_node, "tag", "") or ""
    img_type = "draw" if parent_tag == "cn-drawings" else "desc"
    is_drawings_section = (parent_tag == "cn-drawings") or (current_section_key == "drawings")
    drawings_pdf_dpi = 600
    if is_drawings_section:
        try:
            drawings_pdf_dpi = int((self.config.get("table_capture") or {}).get("pdf_dpi", 600) or 600)
        except Exception:
            drawings_pdf_dpi = 600
    if (not drawings_pdf_dpi) or drawings_pdf_dpi <= 0:
        drawings_pdf_dpi = 600

    try:
        rs_int = int(getattr(rng, "Start", 0) or 0)
    except Exception:
        rs_int = None

    shape_objs = []
    for i in range(1, shape_count + 1):
        try:
            obj = shape_range(i)
        except Exception:
            obj = None
        if obj is not None:
            shape_objs.append(obj)

    captured = 0
    for shape_obj in shape_objs:
        try:
            width_point = float(getattr(shape_obj, "Width", 0.0) or 0.0)
        except Exception:
            width_point = 0.0
        if width_point <= 0:
            width_point = 100.0
        drawings_target_width_px = 0
        if is_drawings_section:
            try:
                drawings_target_width_px = self._get_drawings_target_width_px_for_shape(shape_obj)
            except Exception:
                drawings_target_width_px = 0

        import uuid

        filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
        output_path = os.path.join(temp_dir, filename)

        processed_size = None
        pipeline_source = None
        pre_crop_size = None
        img = None
        drawings_frame = None
        ratio_source = "processed_image_fallback"
        direct_dimensions = None

        # Shape.ConvertToInlineShape()/导出后，原浮动 Shape 的 Width/Height 可能立即失效。
        # 必须在任何会改变 COM 对象身份的操作前保存 Word 可见框。
        if is_drawings_section:
            try:
                drawings_frame = self._get_drawings_display_frame(shape_obj)
                ratio_source = str(drawings_frame.get("ratio_source") or ratio_source)
            except Exception:
                drawings_frame = None

        classification = None
        xml_content = None
        try:
            shape_rng = getattr(shape_obj, "Range", None)
            xml_content = getattr(shape_rng, "WordOpenXML", None) if shape_rng is not None else None
        except Exception:
            xml_content = None
        try:
            classification = self._classify_external_object(
                shape_obj,
                section_key=current_section_key,
                xml_content=xml_content,
            )
        except Exception:
            classification = None

        if isinstance(classification, dict):
            try:
                logger.info(
                    "[OBJECT_ROUTE] section=%s classifier=%s kind=%s reason=%s source=%s",
                    str(current_section_key),
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
                extracted = None
                if preview_rid:
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
                        with Image.open(output_path) as _img0:
                            processed_size = tuple(int(v) for v in _img0.size)
                        pre_crop_size = processed_size
                        if is_drawings_section and not isinstance(drawings_frame, dict):
                            drawings_frame = self._get_drawings_display_frame(
                                shape_obj,
                                processed_img_size=processed_size,
                            )
                            ratio_source = str(drawings_frame.get("ratio_source") or "processed_image_fallback")
                            opt_size = self.img_proc.optimize_drawings_image_file(
                                output_path,
                                ratio_num=float(drawings_frame.get("ratio_num") or processed_size[0] or 1),
                                ratio_den=float(drawings_frame.get("ratio_den") or processed_size[1] or 1),
                                allow_edge_crop=False,
                            )
                            if opt_size:
                                processed_size = opt_size
                        pipeline_source = "PREVIEW"
                        self._record_object_fallback_failure(
                            shape_obj=shape_obj,
                            classification=classification,
                            parent_node=parent_node,
                            section_key=current_section_key,
                            resolution_code="preview_extracted",
                        )
                    except Exception:
                        processed_size = None
                if processed_size is None:
                    filename, width_mm, height_mm, _ = self._emit_external_object_placeholder(
                        shape_obj,
                        parent_node=parent_node,
                        section_key=current_section_key,
                        classification=classification,
                    )
                    output_path = os.path.join(temp_dir, filename)
                    direct_dimensions = (float(width_mm), float(height_mm))
                    pipeline_source = "PLACEHOLDER"
                    try:
                        with Image.open(output_path) as _img0:
                            processed_size = tuple(int(v) for v in _img0.size)
                    except Exception:
                        processed_size = (600, 300)
            elif classifier in ("activation_risky", "unsupported"):
                filename, width_mm, height_mm, _ = self._emit_external_object_placeholder(
                    shape_obj,
                    parent_node=parent_node,
                    section_key=current_section_key,
                    classification=classification,
                )
                output_path = os.path.join(temp_dir, filename)
                direct_dimensions = (float(width_mm), float(height_mm))
                pipeline_source = "PLACEHOLDER"
                try:
                    with Image.open(output_path) as _img0:
                        processed_size = tuple(int(v) for v in _img0.size)
                except Exception:
                    processed_size = (600, 300)

        # Drawings 区浮动 Shape：优先使用 SaveAsPicture 导出，避免剪贴板为空导致附图缺失
        if is_drawings_section and processed_size is None:
            exported = False
            try:
                exported = bool(self.word.export_shape_as_picture(shape_obj, output_path))
            except Exception:
                exported = False

            try:
                logger.debug(
                    "[FLOATING_SHAPE_EXPORT] section=%s method=SaveAsPicture ok=%s file=%s",
                    str(current_section_key),
                    bool(exported),
                    filename,
                )
            except Exception:
                pass

            if exported and os.path.exists(output_path):
                try:
                    with Image.open(output_path) as _img0:
                        pre_crop_size = _img0.size
                except Exception:
                    pre_crop_size = None

                if pre_crop_size:
                    try:
                        if not isinstance(drawings_frame, dict):
                            drawings_frame = self._get_drawings_display_frame(
                                shape_obj,
                                processed_img_size=(int(pre_crop_size[0]), int(pre_crop_size[1])),
                            )
                        ratio_source = str(drawings_frame.get("ratio_source") or "processed_image_fallback")
                        opt_size = self.img_proc.optimize_drawings_image_file(
                            output_path,
                            ratio_num=float(drawings_frame.get("ratio_num") or pre_crop_size[0] or 1),
                            ratio_den=float(drawings_frame.get("ratio_den") or pre_crop_size[1] or 1),
                            allow_edge_crop=False,
                        )
                        if opt_size:
                            processed_size = opt_size
                    except Exception:
                        processed_size = None

                if processed_size is None and pre_crop_size:
                    try:
                        processed_size = (int(pre_crop_size[0]), int(pre_crop_size[1]))
                    except Exception:
                        processed_size = None

                pipeline_source = "SAVEAS"

            # SaveAsPicture 不可用/失败时，使用 PDF 导出 + 渲染通路（不依赖剪贴板）
            if processed_size is None:
                try:
                    app = getattr(self.word, "app", None)
                    if app is None:
                        raise RuntimeError("Word app is not available")

                    conv = getattr(shape_obj, "ConvertToInlineShape", None)
                    if not callable(conv):
                        raise RuntimeError("ConvertToInlineShape is not available")

                    inl = conv()
                    base_name, _ = os.path.splitext(os.path.basename(output_path))
                    pdf_path = os.path.join(temp_dir, f"{base_name}_shape.pdf")
                    png_path = os.path.join(temp_dir, f"{base_name}_shape.png")

                    new_doc = None
                    try:
                        new_doc = add_hidden_document(app, logger=logger)
                        new_doc.Range(0, 0).FormattedText = inl.Range
                        wdExportFormatPDF = 17
                        new_doc.ExportAsFixedFormat(OutputFileName=str(pdf_path), ExportFormat=wdExportFormatPDF)
                    finally:
                        if new_doc is not None:
                            try:
                                new_doc.Close(False)
                            except Exception:
                                pass

                    import fitz

                    doc_pdf = fitz.open(pdf_path)
                    try:
                        if doc_pdf.page_count <= 0:
                            raise RuntimeError("exported PDF has no pages")
                        page = doc_pdf[0]
                        zoom = float(drawings_pdf_dpi) / 72.0
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        pix.save(png_path)
                    finally:
                        try:
                            doc_pdf.close()
                        except Exception:
                            pass

                    with Image.open(png_path) as _img_pdf:
                        processed_size = self.img_proc.process_image(
                            _img_pdf.copy(),
                            output_path,
                            is_equation=False,
                            crop=False,
                            apply_enhancement=False,
                            safe_crop_guard=False,
                        )
                    if processed_size:
                        try:
                            if not isinstance(drawings_frame, dict):
                                drawings_frame = self._get_drawings_display_frame(
                                    shape_obj,
                                    processed_img_size=processed_size,
                                )
                            ratio_source = str(drawings_frame.get("ratio_source") or "processed_image_fallback")
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
                        pipeline_source = "PDF"
                        try:
                            pre_crop_size = processed_size
                        except Exception:
                            pass
                        try:
                            logger.debug(
                                "[FLOATING_SHAPE_EXPORT] section=%s method=PDF dpi=%s ok=True file=%s",
                                str(current_section_key),
                                int(drawings_pdf_dpi),
                                filename,
                            )
                        except Exception:
                            pass
                except Exception:
                    processed_size = None

        # Fallback: clipboard bitmap/EMF pipeline
        if processed_size is None:
            copied = False
            try:
                copied = bool(self.word.copy_shape_to_clipboard(shape_obj, use_copy_as_picture=True))
            except Exception:
                copied = False
            if not copied:
                continue

            time.sleep(0.2)

            try:
                img = self.img_proc.get_image_from_clipboard()
            except Exception:
                img = None
        if img is not None:
            try:
                pre_crop_size = img.size
            except Exception:
                pre_crop_size = None
            try:
                processed_size = self.img_proc.process_image(
                    img,
                    output_path,
                    is_equation=False,
                    crop=False,
                    apply_enhancement=not is_drawings_section,
                    safe_crop_guard=False,
                )
                if processed_size and is_drawings_section:
                    try:
                        if not isinstance(drawings_frame, dict):
                            drawings_frame = self._get_drawings_display_frame(
                                shape_obj,
                                processed_img_size=processed_size,
                            )
                        ratio_source = str(drawings_frame.get("ratio_source") or "processed_image_fallback")
                        opt_size = self.img_proc.optimize_drawings_image_file(
                            output_path,
                            ratio_num=float(drawings_frame.get("ratio_num") or processed_size[0] or 1),
                            ratio_den=float(drawings_frame.get("ratio_den") or processed_size[1] or 1),
                            allow_edge_crop=False,
                        )
                        if opt_size:
                            processed_size = opt_size
                    except Exception:
                        pass
                pipeline_source = "BITMAP"
            except Exception:
                processed_size = None

        if processed_size is None and (not is_drawings_section):
            try:
                processed_size = self.img_proc.save_emf_from_clipboard(
                    output_path,
                    crop=True,
                )
                if processed_size:
                    pipeline_source = "EMF"
                    if pre_crop_size is None:
                        try:
                            with Image.open(output_path) as _img0:
                                pre_crop_size = _img0.size
                        except Exception:
                            pre_crop_size = None
            except Exception:
                processed_size = None

        if not processed_size:
            continue

        # 计算 XML 宽高（mm）
        try:
            if direct_dimensions is not None:
                width_mm, height_mm = direct_dimensions
            elif is_drawings_section:
                if not isinstance(drawings_frame, dict):
                    drawings_frame = self._get_drawings_display_frame(
                        shape_obj,
                        processed_img_size=processed_size,
                    )
                ratio_source = str(drawings_frame.get("ratio_source") or ratio_source)
                width_mm, height_mm = self.img_proc.calculate_drawings_dimensions(
                    drawings_frame.get("width_point"),
                    drawings_frame.get("height_point"),
                    processed_img_size=processed_size,
                )
            else:
                width_mm, height_mm = self.img_proc.calculate_xml_dimensions(width_point, processed_size)
        except Exception:
            width_mm, height_mm = 0.0, 0.0

        try:
            block_p = self.xml.create_paragraph(parent_node, text=None, is_claim=False)
            img_node = self.xml.create_image_node(
                block_p,
                filename,
                float(width_mm),
                float(height_mm),
                img_type=img_type,
                inline=False,
            )
            if parent_tag == "cn-drawings" and hasattr(self, "_register_drawings_image_node"):
                try:
                    self._register_drawings_image_node(img_node)
                except Exception:
                    pass
            if parent_tag == "description" and rs_int is not None:
                try:
                    self._desc_p_positions.append({"range_start": int(rs_int), "p": block_p})
                except Exception:
                    pass
        except Exception:
            continue

        captured += 1
        try:
            if pipeline_source and hasattr(self, "_record_image_pipeline"):
                self._record_image_pipeline(str(pipeline_source))  # type: ignore[func-returns-value]
        except Exception:
            pass
        try:
            w_px, h_px = processed_size
            logger.info(
                "IMG_PIPELINE: object=floating source=%s size=%dx%d",
                pipeline_source or "UNKNOWN",
                int(w_px),
                int(h_px),
            )
            if is_drawings_section:
                try:
                    logger.info(
                        "[DRAWINGS_CAPTURE] file=%s source=%s final=%s exact_crop=%s edge_crop=%s ratio_source=%s size=%dx%d",
                        filename,
                        pipeline_source or "UNKNOWN",
                        os.path.splitext(str(filename))[1].lower().lstrip("."),
                        False,
                        bool(getattr(self.img_proc, "_last_drawings_opt_meta", {}).get("edge_cropped")),
                        ratio_source,
                        int(w_px),
                        int(h_px),
                    )
                except Exception:
                    pass
                try:
                    self._log_drawings_size_provenance(
                        object_kind=str((classification or {}).get("object_kind") or "floating_shape"),
                        route=str(pipeline_source or "UNKNOWN"),
                        frame=drawings_frame,
                        captured_size=pre_crop_size,
                        final_size=processed_size,
                        width_mm=float(width_mm),
                        height_mm=float(height_mm),
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # debug-only: 如果需要补白策略统一，可在此引入 px/mm 诊断；当前仅保留最小日志
        try:
            if pre_crop_size and width_mm > 0:
                px_per_mm = float(pre_crop_size[0]) / float(width_mm)
                logger.debug(
                    "[FLOATING_SHAPE_DIM] file=%s pre_w_px=%s width_mm=%.2f px_per_mm=%.2f",
                    filename,
                    int(pre_crop_size[0]),
                    float(width_mm),
                    float(px_per_mm),
                )
        except Exception:
            pass

    try:
        logger.info(
            "[FLOATING_SHAPES] range_start=%s count=%s captured=%s section=%s",
            rs_int,
            int(shape_count),
            int(captured),
            str(current_section_key),
        )
    except Exception:
        pass

    # 已在本方法内处理段落文本，外层应跳过重复处理
    return True

