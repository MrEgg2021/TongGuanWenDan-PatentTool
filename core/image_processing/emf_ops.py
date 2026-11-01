from __future__ import annotations

import os

from PIL import Image

from core import clipboard_utils
from core.image_processing.equation_diag_ops import (
    build_emf_crop_diagnostics,
    resolve_crop_content_threshold,
    save_equation_diag_stage,
    write_equation_diag_json,
)


def save_emf_from_clipboard(
    self,
    output_path,
    crop=True,
    *,
    padding_ratio=None,
    padding_min=None,
    safe_crop_guard: bool = False,
    preserve_detached_equation_marks: bool = False,
):
    """
    优先尝试从剪贴板获取 EMF 矢量数据并渲染为高清 PNG
    return: (width, height) if success, None otherwise
    padding_ratio/padding_min: 传给 _crop_white_borders，None 表示使用配置默认值
    safe_crop_guard: 裁切过度时启用安全回退
    """
    try:
        # 1. 获取 EMF 数据 (带重试，防止剪贴板被占用)
        emf_bytes = None
        import time
        for attempt in range(3):
            emf_bytes = clipboard_utils.get_clipboard_emf_content()
            try:
                blen = len(emf_bytes) if emf_bytes else 0
            except Exception:
                blen = -1
            try:
                self._logger.debug(
                    "[EMF] clipboard_try=%d/%d ok=%r bytes=%r",
                    attempt + 1,
                    3,
                    bool(emf_bytes),
                    blen,
                )
            except Exception:
                pass
            if emf_bytes:
                break
            time.sleep(0.2)

        if not emf_bytes:
            try:
                self._logger.debug("[EMF] clipboard empty after retries, give up")
            except Exception:
                pass
            return None

        # 2. 渲染为 PNG（scale 维持 4x，min_width 允许为 0 表示不强制短边下限）
        scale = self.config.get('scale_factor', 4.0)
        min_width = self.config.get('min_short_edge', 0)
        jpeg_quality = self.config.get('jpeg_quality', 95)
        jpeg_subsampling = self.config.get('jpeg_subsampling', 0)
        try:
            self._logger.debug(
                "[EMF] render params scale=%r min_width=%r crop=%r output=%r jpeg_quality=%r jpeg_subsampling=%r",
                scale,
                min_width,
                crop,
                output_path,
                jpeg_quality,
                jpeg_subsampling,
            )
        except Exception:
            pass
        success = clipboard_utils.render_emf_bytes_to_png(
            emf_bytes, 
            output_path, 
            scale=scale, 
            min_width=min_width
        )

        try:
            fsz = None
            try:
                fsz = os.path.getsize(output_path)
            except Exception:
                fsz = None
            self._logger.debug("[EMF] render saved=%r file_size=%r", bool(success), fsz)
        except Exception:
            pass

        if success:
            # 返回保存后的图片尺寸
            with Image.open(output_path) as img:
                try:
                    save_equation_diag_stage(
                        self.config,
                        output_path,
                        "01_render_raw.png",
                        img,
                    )
                except Exception:
                    pass
                try:
                    self._logger.debug(
                        "[EMF] opened size=%r mode=%r format=%r",
                        getattr(img, "size", None),
                        getattr(img, "mode", None),
                        getattr(img, "format", None),
                    )
                except Exception:
                    pass

                if crop:
                    # EMF 渲染会有较大白底，进行裁剪并记录诊断信息
                    crop_diag_payload = None
                    try:
                        eff_padding_ratio = (
                            self.config.get("crop_padding_ratio", 0.02)
                            if padding_ratio is None
                            else padding_ratio
                        )
                        eff_padding_min = (
                            self.config.get("crop_padding_min", 4)
                            if padding_min is None
                            else padding_min
                        )
                        crop_diag_payload = build_emf_crop_diagnostics(
                            img,
                            threshold=resolve_crop_content_threshold(
                                self.config,
                                preserve_detached_equation_marks=bool(preserve_detached_equation_marks),
                            ),
                            padding_ratio=float(eff_padding_ratio),
                            padding_min=int(eff_padding_min),
                            preserve_detached_equation_marks=bool(preserve_detached_equation_marks),
                        )
                        raw_bbox = crop_diag_payload.get("raw_bbox") or {}
                        final_bbox = crop_diag_payload.get("final_bbox") or {}
                        padding = crop_diag_payload.get("padding") or {}
                        if raw_bbox and final_bbox:
                            self._logger.debug(
                                "[EMF] crop_diag bbox_raw=(%d,%d,%d,%d) img_wh=(%d,%d) pad=(%d,%d) bbox_final=(%d,%d,%d,%d)",
                                int(raw_bbox.get("left", 0)),
                                int(raw_bbox.get("top", 0)),
                                int(raw_bbox.get("width", 0)),
                                int(raw_bbox.get("height", 0)),
                                int(img.size[0]),
                                int(img.size[1]),
                                int(padding.get("pad_x", 0)),
                                int(padding.get("pad_y", 0)),
                                int(final_bbox.get("left", 0)),
                                int(final_bbox.get("top", 0)),
                                int(final_bbox.get("right", 0)),
                                int(final_bbox.get("bottom", 0)),
                            )
                        else:
                            self._logger.debug("[EMF] crop_diag no valid contours")
                    except Exception as diag_e:
                        try:
                            self._logger.debug(f"[EMF] crop_diag failed: {diag_e}")
                        except Exception:
                            pass
                    if padding_ratio is None and padding_min is None:
                        img_cropped = self._crop_white_borders(
                            img,
                            preserve_detached_equation_marks=bool(preserve_detached_equation_marks),
                        )
                    else:
                        img_cropped = self._crop_white_borders(
                            img,
                            padding_ratio=padding_ratio,
                            padding_min=padding_min,
                            preserve_detached_equation_marks=bool(preserve_detached_equation_marks),
                        )
                    if safe_crop_guard and img_cropped is not None:
                        width_ratio = self._get_crop_safe_ratio("crop_safe_width_ratio", 0.85)
                        height_ratio = self._get_crop_safe_ratio("crop_safe_height_ratio", 0.7)
                        if width_ratio is not None or height_ratio is not None:
                            if self._is_crop_too_aggressive(
                                img.size,
                                img_cropped.size,
                                width_ratio=width_ratio,
                                height_ratio=height_ratio,
                            ):
                                try:
                                    self._logger.warning(
                                        "⚠️ 裁切过度，EMF 通路回退原图: src=%s orig=%s cropped=%s",
                                        os.path.basename(output_path),
                                        img.size,
                                        img_cropped.size,
                                    )
                                except Exception:
                                    pass
                                img_cropped = img
                else:
                    crop_diag_payload = {
                        "render_size": [int(img.size[0]), int(img.size[1])],
                    }
                    img_cropped = img

                if crop_diag_payload is None:
                    crop_diag_payload = {}
                crop_diag_payload["crop_requested"] = bool(crop)
                crop_diag_payload["cropped_size"] = [int(img_cropped.size[0]), int(img_cropped.size[1])]
                crop_diag_payload["output_file"] = os.path.basename(str(output_path))
                try:
                    save_equation_diag_stage(
                        self.config,
                        output_path,
                        "02_emf_cropped.png",
                        img_cropped,
                    )
                except Exception:
                    pass
                try:
                    write_equation_diag_json(
                        self.config,
                        output_path,
                        "crop_diag.json",
                        crop_diag_payload,
                    )
                except Exception:
                    pass

                # 覆盖保存
                img_cropped.save(
                    output_path,
                    format="PNG",
                    dpi=(300, 300),
                )
                try:
                    fsz2 = None
                    try:
                        fsz2 = os.path.getsize(output_path)
                    except Exception:
                        fsz2 = None
                    self._logger.debug(
                        "✅ [EMF] render+crop: %s -> %s (crop=%r) file_size=%r",
                        getattr(img, "size", None),
                        getattr(img_cropped, "size", None),
                        crop,
                        fsz2,
                    )
                except Exception:
                    pass
                return img_cropped.size
        return None
    except Exception as e:
        # 降级为 debug，正常用户看不到这类降级信息，避免引起不必要的疑虑
        self._logger.debug(f"⚠️ EMF 渲染尝试失败: {e}")
        return None

