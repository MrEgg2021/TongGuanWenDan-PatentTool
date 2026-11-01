from PIL import Image, ImageGrab
import logging

from core.image_processing.crop_ops import (
    _crop_solid_background,
    _crop_white_borders,
    _detect_background_color,
    _pad_if_content_touches_edge,
    _pad_to_ratio,
)
from core.image_processing.emf_ops import save_emf_from_clipboard
from core.image_processing.equation_ops import pad_equation_for_centering
from core.image_processing.process_ops import optimize_drawings_image_file, process_image
from core.image_processing.table_center_ops import pad_table_for_centering_keep_height


class ImageProcessor:
    """
    图像处理器
    负责剪贴板图片、裁边、增强、XML 尺寸计算等图像相关操作。
    """

    def __init__(self, config):
        self.config = config
        self._logger = logging.getLogger(__name__)

    def _get_crop_safe_ratio(self, key: str, default: float) -> float | None:
        try:
            val = float(self.config.get(key, default))
        except Exception:
            val = default
        if val <= 0:
            return None
        if val > 1:
            val = 1.0
        return float(val)

    def _is_crop_too_aggressive(
        self,
        original_size,
        cropped_size,
        *,
        width_ratio: float | None,
        height_ratio: float | None,
    ) -> bool:
        try:
            ow, oh = original_size
            cw, ch = cropped_size
        except Exception:
            return False
        if ow <= 0 or oh <= 0 or cw <= 0 or ch <= 0:
            return False
        if width_ratio is not None and float(cw) < float(ow) * float(width_ratio):
            return True
        if height_ratio is not None and float(ch) < float(oh) * float(height_ratio):
            return True
        return False

    def get_image_from_clipboard(self):
        """从剪贴板获取图片。"""
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                return img
            if isinstance(img, list) and len(img) > 0:
                return Image.open(img[0])
            self._logger.warning('Clipboard did not contain a usable image.')
            return None
        except Exception as e:
            self._logger.error(f'Failed to read clipboard image: {e}')
            return None

    def calculate_equation_dimensions(self, processed_img_size):
        w_px, h_px = processed_img_size

        try:
            mm_per_px = float(self.config.get('omath_mm_per_px', 0.1))
        except (TypeError, ValueError):
            mm_per_px = 0.1

        width_mm = w_px * mm_per_px
        height_mm = h_px * mm_per_px

        max_width = self.config.get('max_width_mm', 165.0)
        try:
            max_width = float(max_width)
        except (TypeError, ValueError):
            max_width = 165.0

        if width_mm > max_width:
            ratio = max_width / width_mm
            width_mm = max_width
            height_mm = height_mm * ratio

        return round(width_mm, 2), round(height_mm, 2)

    def calculate_xml_dimensions(self, original_width_point, processed_img_size):
        """
        计算 XML 中图片节点的 wi/he。
        return: (width_mm, height_mm)
        """
        w_px, h_px = processed_img_size
        factor = self.config.get('width_factor', 0.3528)
        width_mm = original_width_point * factor

        if w_px > 0:
            height_mm = width_mm * (h_px / w_px)
        else:
            height_mm = 0

        max_width = self.config.get('max_width_mm', 165.00)
        if width_mm > max_width:
            ratio = max_width / width_mm
            width_mm = max_width
            height_mm = height_mm * ratio

        return round(width_mm, 2), round(height_mm, 2)

    def calculate_drawings_dimensions(self, original_width_point, original_height_point, processed_img_size):
        """
        计算说明书附图的 XML wi/he。

        优先使用 Word 显示框的宽高点值；若高度不可用，再回退到处理后图片自身比例。
        """
        try:
            width_point = float(original_width_point or 0.0)
        except Exception:
            width_point = 0.0
        if width_point <= 0:
            width_point = 100.0

        factor = self.config.get('width_factor', 0.3528)
        width_mm = width_point * factor

        height_mm = 0.0
        try:
            height_point = float(original_height_point or 0.0)
        except Exception:
            height_point = 0.0

        if height_point > 0:
            height_mm = height_point * factor
        else:
            try:
                w_px, h_px = processed_img_size
            except Exception:
                w_px, h_px = 0, 0
            if w_px > 0:
                height_mm = width_mm * (float(h_px) / float(w_px))

        max_width = self.config.get('max_width_mm', 165.00)
        if width_mm > max_width:
            ratio = max_width / width_mm
            width_mm = max_width
            height_mm = height_mm * ratio

        return round(width_mm, 2), round(height_mm, 2)


ImageProcessor.save_emf_from_clipboard = save_emf_from_clipboard
ImageProcessor._crop_white_borders = _crop_white_borders
ImageProcessor._pad_if_content_touches_edge = _pad_if_content_touches_edge
ImageProcessor._detect_background_color = _detect_background_color
ImageProcessor._crop_solid_background = _crop_solid_background
ImageProcessor._pad_to_ratio = _pad_to_ratio
ImageProcessor.optimize_drawings_image_file = optimize_drawings_image_file
ImageProcessor.process_image = process_image
ImageProcessor.pad_equation_for_centering = pad_equation_for_centering
ImageProcessor.pad_table_for_centering_keep_height = pad_table_for_centering_keep_height

__all__ = ['ImageProcessor']
