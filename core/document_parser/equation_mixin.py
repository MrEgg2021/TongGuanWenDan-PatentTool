from __future__ import annotations

import os
import time

import fitz
from PIL import Image

from core import clipboard_utils
from core.logging_utils import logger

# Word 常量（与原 ImageEquationMixin 中保持一致）
wdInlineShapeEmbeddedOLEObject = 1


class EquationRenderingMixin:
    def _copy_range_to_fresh_clipboard(self, copy_action, formats, *, label: str) -> bool:
        for attempt in range(1, 3):
            before_sequence = clipboard_utils.get_clipboard_sequence_number()
            try:
                copy_result = copy_action()
                copied = copy_result is not False
            except Exception as e:
                logger.debug("[CLIPBOARD_TXN] label=%s attempt=%d copy_failed=%s", label, attempt, e)
                copied = False

            if not copied:
                continue

            is_fresh = clipboard_utils.wait_for_clipboard_fresh_content(
                before_sequence,
                formats,
                timeout_s=1.0,
                poll_s=0.05,
            )
            logger.debug(
                "[CLIPBOARD_TXN] label=%s attempt=%d before_seq=%r fresh=%r",
                label,
                attempt,
                before_sequence,
                is_fresh,
            )
            if is_fresh:
                return True
        return False

    def _is_equation_shape(self, shape_obj):  # type: ignore[override]
        """判断 InlineShape 是否为公式对象 (Equation.KSEE3 等)"""
        try:
            type_code = getattr(shape_obj, "Type", None)
            # 优先尝试读取 OLEFormat.ClassType（在部分环境中可能不可用）
            ole = getattr(shape_obj, "OLEFormat", None)
            class_type = ""
            if ole is not None:
                try:
                    class_type = getattr(ole, "ClassType", "") or ""
                except Exception:
                    class_type = ""

            if not isinstance(class_type, str):
                class_type = str(class_type)

            is_type_ole = type_code == wdInlineShapeEmbeddedOLEObject
            class_type_lower = class_type.lower()
            is_ole_equation = ("equation" in class_type_lower) if class_type else False
            is_visio_ole = ("visio" in class_type_lower) if class_type else False
            # 部分旧公式对象无法读取 ClassType，仍保留 Type=1 的兼容判定；
            # 但真实 Visio 附图同样是 Type=1，不能误走公式尺寸路径。
            is_equation = bool(is_ole_equation or (is_type_ole and not is_visio_ole))

            logger.debug(
                f"[EQ_DEBUG] InlineShape Type={type_code}, OLE ClassType={class_type}, "
                f"is_type_ole={is_type_ole}, is_ole_equation={is_ole_equation}, "
                f"is_visio_ole={is_visio_ole}, is_equation={is_equation}"
            )
            return is_equation
        except Exception as e:
            logger.debug(f"[EQ_DEBUG] _is_equation_shape 异常: {e}")
            return False

    def _render_equation_via_pdf(self, shape_obj, output_path):  # type: ignore[override]
        """通过 ExportAsFixedFormat + PyMuPDF 将公式矢量渲染为高 DPI 位图，并交给 ImageProcessor 处理

        返回值: processed_size (width_px, height_px) 或 None (失败时)
        """
        eq_cfg = self.config.get("equation_rendering", {})
        pdf_dpi = eq_cfg.get("pdf_dpi", 600) or 600
        try:
            pdf_dpi = int(pdf_dpi)
        except (TypeError, ValueError):
            pdf_dpi = 600

        temp_dir = os.path.abspath(self.config["paths"]["temp_dir"])
        base_name, _ = os.path.splitext(os.path.basename(output_path))
        pdf_path = os.path.join(temp_dir, f"{base_name}_eq.pdf")
        png_path = os.path.join(temp_dir, f"{base_name}_eq.png")
        try:
            os.makedirs(temp_dir, exist_ok=True)
        except Exception as ensure_err:
            raise OSError(f"公式临时输出目录不存在且无法创建: {temp_dir}") from ensure_err

        app = self.word.app
        if app is None:
            logger.warning("⚠️ Word 应用未启动，无法走 PDF 公式渲染通路，回退为截图")
            return None

        new_doc = None
        try:
            new_doc = app.Documents.Add()
            new_doc.Range(0, 0).FormattedText = shape_obj.Range
            wdExportFormatPDF = 17
            new_doc.ExportAsFixedFormat(OutputFileName=pdf_path, ExportFormat=wdExportFormatPDF)
        except Exception as e:
            logger.warning(f"⚠️ 公式 PDF 导出失败，将回退为截图: {e}")
            return None
        finally:
            if new_doc is not None:
                try:
                    # False/0 = 不保存更改，避免退出时弹出“是否保存 文档1”
                    new_doc.Close(False)
                except Exception:
                    # 关闭失败不影响后续降级逻辑
                    pass

        try:
            doc_pdf = fitz.open(pdf_path)
            if doc_pdf.page_count == 0:
                logger.warning("⚠️ 公式 PDF 页数为 0，将回退为截图")
                return None
            page = doc_pdf[0]
            zoom = pdf_dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pix.save(png_path)
            doc_pdf.close()

            img = Image.open(png_path)
            processed_size = self.img_proc.process_image(img, output_path, is_equation=True)

            try:
                w_px, h_px = processed_size
                logger.info(
                    "IMG_PIPELINE: object=%s source=PDF dpi=%d size=%dx%d",
                    "omath" if getattr(shape_obj, "__class__", None).__name__ == "OMath" else "shape_equation",
                    pdf_dpi,
                    w_px,
                    h_px,
                )
                if hasattr(self, "_record_image_pipeline"):
                    self._record_image_pipeline("PDF")  # type: ignore[func-returns-value]
            except Exception:
                pass

            return processed_size
        except Exception as e:
            logger.warning(f"⚠️ 公式 PDF 渲染失败，将回退为截图: {e}")
            return None

    def handle_omath(self, omath_obj):  # type: ignore[override]
        import uuid

        filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
        output_path = os.path.join(self.config["paths"]["temp_dir"], filename)

        eq_cfg = self.config.get("equation_rendering", {})
        mode = str(eq_cfg.get("mode", "pdf")).lower()

        if mode == "pdf_only":
            raise RuntimeError(
                "检测到配置 equation_rendering.mode=pdf_only，但该模式（方案B）已全局禁用。"
                "请将 equation_rendering.mode 改为 pdf 或 screenshot，并确保安装 Microsoft Word 后重试。"
            )
        use_pdf_for_eq = mode in ("pdf", "pdf_only")
        skip_emf_for_eq = mode == "pdf_only"

        processed_size = None
        pipeline_source = None

        if not skip_emf_for_eq:
            try:
                eq_img_cfg = self.config.get("image_processing", {}) if isinstance(self.config, dict) else {}
                eq_pad_min = int(eq_img_cfg.get("equation_crop_padding_min", eq_img_cfg.get("crop_padding_min", 4)) or 0)
                emf_ready = self._copy_range_to_fresh_clipboard(
                    lambda: omath_obj.Range.Copy(),
                    clipboard_utils.EMF_CLIPBOARD_FORMATS,
                    label="omath_emf",
                )
                if emf_ready:
                    processed_size = self.img_proc.save_emf_from_clipboard(
                        output_path,
                        padding_ratio=0.0,
                        padding_min=max(eq_pad_min, 0),
                        preserve_detached_equation_marks=True,
                    )
                if processed_size:
                    pipeline_source = "EMF"
                    try:
                        with Image.open(output_path) as _img0:
                            _img = _img0.copy()
                        enhanced_size = self.img_proc.process_image(
                            _img,
                            output_path,
                            is_equation=True,
                            crop=False,
                            apply_enhancement=True,
                        )
                        if enhanced_size:
                            processed_size = enhanced_size
                            try:
                                w_px, h_px = enhanced_size
                                logger.debug(
                                    "[EMF_EQ_ENHANCE] object=omath size=%dx%d file=%s",
                                    w_px,
                                    h_px,
                                    os.path.basename(output_path),
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                processed_size = None

        if processed_size is None and use_pdf_for_eq:
            processed_size = self._render_equation_via_pdf(omath_obj, output_path)
            if processed_size is not None and pipeline_source is None:
                # PDF 通路的日志与计数在 _render_equation_via_pdf 内部完成，这里只标记来源避免误判
                pipeline_source = "PDF"

        if processed_size is None:
            bitmap_ready = self._copy_range_to_fresh_clipboard(
                lambda: self.word.copy_range_as_picture(omath_obj.Range),
                clipboard_utils.IMAGE_CLIPBOARD_FORMATS,
                label="omath_bitmap",
            )
            if not bitmap_ready:
                return None, 0, 0

            img = None
            # 为兼容 Word 2007 这类旧环境，复制后需要等待剪贴板刷新
            # 使用 0.3s * 4 次重试窗口，避免读取到上一次的图片内容
            for _ in range(4):
                img = self.img_proc.get_image_from_clipboard()
                if img is not None:
                    break
                time.sleep(0.3)

            if not img:
                return None, 0, 0

            processed_size = self.img_proc.process_image(img, output_path, is_equation=True)
            if processed_size is not None and pipeline_source is None:
                pipeline_source = "BITMAP"

        if not processed_size:
            return None, 0, 0

        try:
            w_px, h_px = processed_size
        except Exception:
            return None, 0, 0

        try:
            src = pipeline_source or "BITMAP"
            if src == "EMF":
                logger.info(
                    "IMG_PIPELINE: object=omath source=EMF size=%dx%d",
                    w_px,
                    h_px,
                )
                if hasattr(self, "_record_image_pipeline"):
                    self._record_image_pipeline("EMF")  # type: ignore[func-returns-value]
            elif src == "BITMAP":
                logger.info(
                    "IMG_PIPELINE: object=omath source=BITMAP size=%dx%d",
                    w_px,
                    h_px,
                )
                if hasattr(self, "_record_image_pipeline"):
                    self._record_image_pipeline("BITMAP")  # type: ignore[func-returns-value]
            # 对于 PDF 通路，_render_equation_via_pdf 已输出 IMG_PIPELINE 日志并计数，这里无需重复记录
        except Exception:
            pass

        width_mm, height_mm = self.img_proc.calculate_equation_dimensions(processed_size)
        return filename, width_mm, height_mm
