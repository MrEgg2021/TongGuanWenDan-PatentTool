from __future__ import annotations

import os

import cv2
import numpy as np
from PIL import Image

from core.image_processing.equation_diag_ops import save_equation_diag_stage


def optimize_drawings_image_file(
    self,
    image_path: str,
    *,
    ratio_num: int,
    ratio_den: int,
    allow_edge_crop: bool = True,
) -> tuple[int, int] | None:
    if not image_path:
        return None
    if ratio_num <= 0 or ratio_den <= 0:
        return None

    try:
        with Image.open(image_path) as img0:
            info = getattr(img0, "info", {}) or {}
            dpi = info.get("dpi")
            img0 = img0.convert("RGB")
            original_size = tuple(img0.size)
            bg_rgb = self._detect_background_color(img0)
            if allow_edge_crop:
                cropped = self._crop_solid_background(img0, bg_rgb, padding_px=2)
            else:
                cropped = img0
            edge_cropped = tuple(cropped.size) != original_size
            padded = self._pad_to_ratio(cropped, ratio_num=ratio_num, ratio_den=ratio_den, bg_rgb=bg_rgb)
            final_size = tuple(padded.size)
    except Exception:
        return None

    try:
        ext = ""
        try:
            ext = os.path.splitext(str(image_path))[1].lower()
        except Exception:
            ext = ""

        output_format = "JPEG"
        if ext in (".tif", ".tiff"):
            output_format = "TIFF"
            padded.save(image_path, format="TIFF", compression="tiff_deflate")
        else:
            save_kwargs = {
                "quality": int(self.config.get("jpeg_quality", 100)),
                "subsampling": int(self.config.get("jpeg_subsampling", 0)),
            }
            try:
                if isinstance(dpi, tuple) and len(dpi) == 2:
                    save_kwargs["dpi"] = dpi
            except Exception:
                pass
            padded.save(image_path, format="JPEG", **save_kwargs)
        try:
            self._last_drawings_opt_meta = {
                "edge_cropped": bool(edge_cropped),
                "edge_crop_skipped": bool(not allow_edge_crop),
                "original_size": original_size,
                "final_size": final_size,
                "output_format": output_format,
            }
        except Exception:
            pass
        return final_size
    except Exception:
        return None

def process_image(
    self,
    image,
    output_path,
    is_equation=False,
    crop=True,
    apply_enhancement=True,
    safe_crop_guard: bool = False,
):
    """
    处理图片流程：
    1. 格式转换 (JPG)
    2. 白底处理
    3. 放大 (如果不够大)
    4. OpenCV 自动裁剪（可通过 crop 开关禁用）
    5. 锐化/降噪（可由 apply_enhancement 控制）
    6. 保存文件
    return: (processed_width_px, processed_height_px)
    safe_crop_guard: 裁切过度时启用安全回退
    """
    try:
        # 1. & 2. 转 RGB 并处理白底
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            bg = Image.new('RGB', image.size, self.config.get('bg_color', '#FFFFFF'))
            # 3.6.x 以上 Pillow 支持直接 convert 带背景，这里用 paste 兼容性更好
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            bg.paste(image, mask=image.split()[3])
            image = bg
        else:
            image = image.convert('RGB')

        # 3. 放大处理 (确保短边至少 min_short_edge)
        min_short = self.config.get('min_short_edge', 1000)
        w, h = image.size
        short_edge = min(w, h)

        if short_edge < min_short:
            scale = min_short / short_edge
            # 限制最大放大倍数，防止过度模糊
            scale = min(scale, self.config.get('scale_factor', 4.0)) 
            new_size = (int(w * scale), int(h * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            self._logger.debug(f"🔍 图片已放大: {w}x{h} -> {new_size}")

        # 4. OpenCV 自动裁剪
        original_size = image.size
        if crop:
            base_image = image
            if is_equation:
                # 公式图片统一采用 0 padding 的紧致裁剪，避免多余白边导致视觉字号偏小
                try:
                    eq_pad_min = int(self.config.get("equation_crop_padding_min", self.config.get("crop_padding_min", 4)))
                except Exception:
                    eq_pad_min = 4
                eq_pad_min = max(0, int(eq_pad_min))
                image = self._crop_white_borders(
                    image,
                    padding_ratio=0.0,
                    padding_min=eq_pad_min,
                    preserve_detached_equation_marks=True,
                )
            else:
                image = self._crop_white_borders(image)
            if safe_crop_guard and image is not None:
                width_ratio = self._get_crop_safe_ratio("crop_safe_width_ratio", 0.85)
                height_ratio = self._get_crop_safe_ratio("crop_safe_height_ratio", 0.7)
                if width_ratio is not None or height_ratio is not None:
                    if self._is_crop_too_aggressive(
                        original_size,
                        image.size,
                        width_ratio=width_ratio,
                        height_ratio=height_ratio,
                    ):
                        try:
                            self._logger.warning(
                                "⚠️ 裁切过度，已回退原图: orig=%s cropped=%s",
                                original_size,
                                image.size,
                            )
                        except Exception:
                            pass
                        image = base_image
            if image.size != original_size:
                self._logger.debug(f"✂️ 图片已裁剪: {image.size[0]}x{image.size[1]}")
            else:
                self._logger.debug("✂️ 无需裁剪或裁剪未生效")
        else:
            self._logger.debug("✂️ 跳过裁剪 (crop=False)")

        if apply_enhancement and self.config.get('sharpen_enabled', False):
            cv_img_sharp = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            radius = float(self.config.get('sharpen_radius', 1.0))
            amount = float(self.config.get('sharpen_amount', 1.5))
            if radius > 0 and amount > 0:
                if self.config.get('binarize_enabled', False):
                    gray = cv2.cvtColor(cv_img_sharp, cv2.COLOR_BGR2GRAY)
                    blur = cv2.GaussianBlur(gray, (0, 0), radius)
                    sharp = cv2.addWeighted(gray, 1.0 + amount, blur, -amount, 0)
                    clip = float(self.config.get('contrast_clip', 0.0))
                    if clip > 0:
                        lo, hi = np.percentile(sharp, (clip, 100.0 - clip))
                        if hi > lo:
                            sharp = np.clip((sharp - lo) * 255.0 / (hi - lo), 0, 255).astype('uint8')
                    method = str(self.config.get('binarize_method', 'otsu')).lower()
                    if method == 'otsu':
                        _, sharp = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    else:
                        _, sharp = cv2.threshold(sharp, 200, 255, cv2.THRESH_BINARY)
                    cv_img_sharp = cv2.cvtColor(sharp, cv2.COLOR_GRAY2BGR)
                else:
                    blur = cv2.GaussianBlur(cv_img_sharp, (0, 0), radius)
                    sharp = cv2.addWeighted(cv_img_sharp, 1.0 + amount, blur, -amount, 0)
                    clip = float(self.config.get('contrast_clip', 0.0))
                    if clip > 0:
                        lo, hi = np.percentile(sharp, (clip, 100.0 - clip))
                        if hi > lo:
                            scale = 255.0 / (hi - lo)
                            sharp = np.clip((sharp - lo) * scale, 0, 255).astype('uint8')
                    cv_img_sharp = sharp
                image = Image.fromarray(cv2.cvtColor(cv_img_sharp, cv2.COLOR_BGR2RGB))

        # 5. 安全留白：内容贴边时补白，避免 PDF 预览边缘裁切
        try:
            image = self._pad_if_content_touches_edge(image)
        except Exception:
            pass

        if is_equation:
            try:
                save_equation_diag_stage(
                    self.config,
                    output_path,
                    "03_enhanced.png",
                    image,
                    require_existing=True,
                )
            except Exception:
                pass

        save_as_png = False
        save_as_tiff = False
        try:
            if os.path.isfile(output_path):
                try:
                    with Image.open(output_path) as _probe:
                        fmt = str(getattr(_probe, "format", "") or "").upper()
                        if fmt == "PNG":
                            save_as_png = True
                        elif fmt in ("TIFF", "TIF"):
                            save_as_tiff = True
                except Exception:
                    save_as_png = False
        except Exception:
            save_as_png = False
        try:
            output_lower = str(output_path).lower()
            if output_lower.endswith(".png"):
                save_as_png = True
            elif output_lower.endswith(".tif") or output_lower.endswith(".tiff"):
                save_as_tiff = True
        except Exception:
            pass

        try:
            parent_dir = os.path.dirname(os.path.abspath(str(output_path)))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
        except Exception as ensure_err:
            raise OSError(f"图片输出目录不存在且无法创建: {output_path}") from ensure_err

        if save_as_tiff:
            image.save(
                output_path,
                format="TIFF",
                compression="tiff_deflate",
                dpi=(300, 300),
            )
        elif save_as_png:
            image.save(
                output_path,
                format="PNG",
                dpi=(300, 300),
            )
        else:
            # 5. 保存（高质量 + 禁用色度子采样，减少边缘模糊）
            image.save(
                output_path,
                quality=self.config.get('jpeg_quality', 95),
                subsampling=self.config.get('jpeg_subsampling', 0),
                dpi=(300, 300),
            )
        return image.size

    except Exception as e:
        self._logger.error(f"❌ 图片处理失败: {e}")
        raise

