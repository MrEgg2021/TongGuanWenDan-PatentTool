from __future__ import annotations

import os

from PIL import Image

from core.image_processing.equation_diag_ops import (
    analyze_crop_contours,
    resolve_crop_content_threshold,
)


def pad_equation_for_centering(
    self,
    image_path,
    current_width_mm,
    current_height_mm,
    target_width_mm=None,
    scale_ratio=None,
    px_per_mm_override=None,
    preserve_all_ink=True,
):
    """对图片进行“居中补白”（扩展左右画布宽度）。

    该函数会直接覆盖保存 `image_path` 指向的图片文件，并返回需要写入 XML 的尺寸（mm）。

    适用场景：
    - 公式图片（OMath / OLE）居中：目标宽度通常为 165mm 或 145mm（说明书预留段号/括号等宽度）。
    - 表格转图片居中：表格截图经常来自 EMF 渲染，像素密度（px/mm）明显高于公式；
      若画布宽度固定为 10px/mm，会导致表格因“太宽”而早退无法补白。

    算法要点：
    - 通过 `current_width_mm` 与当前图片像素宽 `w_px` 反推 px/mm，并钳制到 [8, 25]，
      以此计算目标画布像素宽 `canvas_width_px = target_width_mm * px_per_mm`。
    - 补白策略与公式保持一致：统一采用“视觉偏移”补白（左补白 > 右补白）。
      对于表格（EMF）这类高像素密度图片：对偏移量做归一化与限幅，避免剩余补白较小时被推到右侧贴边。

    参数:
    - image_path: 图片文件路径（会被覆盖保存）。
    - current_width_mm/current_height_mm: 当前 XML 宽高（mm），用于反推 px/mm。
    - target_width_mm: 目标行宽（mm），不传则使用配置 `equation_center_text_width_mm`。
    - scale_ratio: 可选缩放比例（0.4~1.0），用于“主体过宽无法补白”时先缩小主体。
    - px_per_mm_override: 可选像素密度基线（px/mm），用于统一公式补白画布尺寸。
    - preserve_all_ink: 公式使用全墨迹边界；表格兼容调用可关闭。

    返回:
    - (new_width_mm, new_height_mm): 需要写回 XML 的宽高（mm）。
    """
    # target_width_mm 为 None 时，使用全局 equation_center_text_width_mm 配置；
    # 否则优先使用调用方指定的目标宽度。
    if target_width_mm is not None:
        try:
            text_width = float(target_width_mm)
        except (TypeError, ValueError):
            text_width = 0.0
    else:
        try:
            text_width = float(self.config.get("equation_center_text_width_mm", 165.0))
        except (TypeError, ValueError):
            text_width = 165.0
    if not text_width or text_width <= 0:
        text_width = 165.0

    if (not image_path or current_width_mm is None or current_height_mm is None):
        return current_width_mm, current_height_mm

    try:
        cw = float(current_width_mm)
        ch = float(current_height_mm)
    except (TypeError, ValueError):
        return current_width_mm, current_height_mm

    if cw <= 0 or ch <= 0:
        return current_width_mm, current_height_mm

    if not os.path.isfile(image_path):
        return current_width_mm, current_height_mm

    try:
        with Image.open(image_path) as img:
            try:
                src_fmt = getattr(img, "format", None)
            except Exception:
                src_fmt = None
            save_as_png = False
            try:
                if str(src_fmt or "").upper() == "PNG":
                    save_as_png = True
            except Exception:
                save_as_png = False
            try:
                if str(image_path).lower().endswith(".png"):
                    save_as_png = True
            except Exception:
                pass
            img = img.convert("RGB")
            w_px, h_px = img.size
            if w_px <= 0 or h_px <= 0:
                return current_width_mm, current_height_mm

            # 计算补白画布宽度（像素）：
            # - 使用 current_width_mm 与当前像素宽 w_px 反推 px/mm（像素密度）。
            # - 对反推出来的 px/mm 进行钳制，避免异常输入导致画布过大/过小。
            #
            # 说明：
            # - 公式（OMath/OLE）通常约 10px/mm；
            # - 表格截图（EMF 渲染）常见 15~17px/mm；
            #   若仍固定 10px/mm，表格会因 w_px 远大于画布而触发早退，导致无法补白。
            px_per_mm_default = 10.0
            if px_per_mm_override is not None:
                try:
                    px_per_mm_default = float(px_per_mm_override)
                except Exception:
                    px_per_mm_default = 10.0
            if (not px_per_mm_default) or px_per_mm_default <= 0:
                px_per_mm_default = 10.0
            px_per_mm_default = max(8.0, min(25.0, float(px_per_mm_default)))

            # NOTE:
            # - current_width_mm/current_height_mm 应代表 Word 中的“真实显示尺寸”（或缩放后的尺寸）
            # - 居中补白只扩展画布宽度，不应改变内容在 PDF 预览中的实际尺寸
            # 因此：优先使用 w_px / current_width_mm 反推 px/mm（与 Word 尺寸保持一致），
            # 仅在无法反推时才回退到 px_per_mm_override / 默认值。
            px_per_mm_raw = None
            try:
                px_per_mm_raw = float(w_px) / float(cw)
            except Exception:
                px_per_mm_raw = None

            if (px_per_mm_raw is None) or (px_per_mm_raw <= 0):
                if px_per_mm_override is not None:
                    try:
                        px_per_mm_raw = float(px_per_mm_override)
                    except Exception:
                        px_per_mm_raw = px_per_mm_default
                else:
                    px_per_mm_raw = px_per_mm_default

            px_per_mm = max(8.0, min(25.0, float(px_per_mm_raw)))
            try:
                canvas_width_px = int(round(float(text_width) * float(px_per_mm)))
            except Exception:
                canvas_width_px = int(round(float(text_width) * px_per_mm_default))
            if canvas_width_px <= 0:
                canvas_width_px = 1650

            scale_mode = "resample"
            try:
                scale_mode_raw = self.config.get("equation_center_scale_mode", "resample")
                scale_mode = str(scale_mode_raw or "resample").strip().lower()
            except Exception:
                scale_mode = "resample"
            if scale_mode not in ("resample", "lossless_canvas"):
                scale_mode = "resample"
            try:
                lossless_max_canvas_px = int(
                    self.config.get("equation_center_lossless_max_canvas_width_px", 10000)
                )
            except Exception:
                lossless_max_canvas_px = 10000
            if lossless_max_canvas_px <= 0:
                lossless_max_canvas_px = 10000

            try:
                crop_analysis = analyze_crop_contours(
                    img,
                    threshold=resolve_crop_content_threshold(
                        self.config,
                        preserve_detached_equation_marks=bool(preserve_all_ink),
                    ),
                    padding_ratio=0.0,
                    padding_min=4,
                    preserve_detached_equation_marks=bool(preserve_all_ink),
                )
                crop_bbox = crop_analysis.get("final_bbox") or {}
                left_crop = int(crop_bbox.get("left", 0))
                right_crop = int(crop_bbox.get("right", 0))
                if right_crop > left_crop and (left_crop > 0 or right_crop < w_px):
                    img = img.crop((left_crop, 0, right_crop, h_px))
                    w_px, h_px = img.size
            except Exception:
                pass

            dpi = 300.0
            target_mm_px = int(round(text_width * dpi / 25.4))

            scaled_changed = False
            ratio_req = None
            if scale_ratio is not None:
                try:
                    ratio_req = float(scale_ratio)
                except Exception:
                    ratio_req = None
            if ratio_req is not None and ratio_req > 0:
                # UI 约束：0.4 ~ 1.0（此处仍做防御性裁剪）
                ratio_req = max(0.4, min(1.0, float(ratio_req)))
                if ratio_req != 1.0:
                    ratio_eff = float(ratio_req)
                    if scale_mode == "lossless_canvas":
                        try:
                            canvas_width_px_lossless = int(
                                round(float(canvas_width_px) / float(ratio_eff))
                            )
                        except Exception:
                            canvas_width_px_lossless = int(canvas_width_px)

                        if canvas_width_px_lossless <= 0:
                            canvas_width_px_lossless = int(canvas_width_px)

                        if canvas_width_px_lossless > int(lossless_max_canvas_px):
                            try:
                                self._logger.warning(
                                    "[EQ_PAD] lossless_canvas fallback to resample: file=%s canvas=%s max=%s ratio=%.4f",
                                    os.path.basename(image_path),
                                    int(canvas_width_px_lossless),
                                    int(lossless_max_canvas_px),
                                    float(ratio_eff),
                                )
                            except Exception:
                                pass
                            scale_mode = "resample"
                        else:
                            canvas_width_px = int(canvas_width_px_lossless)

                    if scale_mode == "resample":
                        # 方案1 + 选项A：
                        # - 缩小主体，但画布宽度仍按目标宽度(165/145)计算（留白变大）
                        # - 若按 ratio 缩小后仍无法放入目标画布宽，则不做兜底处理（由用户在 Word 中调整）
                        try:
                            if w_px > 0 and canvas_width_px > 2:
                                scaled_w_px_f = float(w_px) * float(ratio_eff)
                                new_w = max(1, int(round(float(scaled_w_px_f))))
                                if new_w > int(canvas_width_px):
                                    return current_width_mm, current_height_mm
                        except Exception:
                            pass

                        try:
                            new_w = max(1, int(round(float(w_px) * float(ratio_eff))))
                            new_h = max(1, int(round(float(h_px) * float(ratio_eff))))
                            if (new_w, new_h) != (w_px, h_px):
                                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                                w_px, h_px = img.size
                                scaled_changed = True
                        except Exception:
                            # 缩放失败不应影响后续补白逻辑
                            scaled_changed = False

            if w_px >= canvas_width_px and (not scaled_changed):
                return current_width_mm, current_height_mm

            # 统一采用历史“视觉居中”偏移（左补白 > 右补白），保证项目内补白风格一致。
            # 说明：
            # - 偏移的“基准模型”来源于旧实现（固定 10px/mm，165mm->1650px）结合 300DPI 换算的经验值；
            # - 对于表格（通常 px/mm≈15~17）：若直接按“画布宽度缩放”偏移，会导致偏移过大，
            #   所以做两层保护：
            #   1) 归一化：按 (10px/mm)/px_per_mm 折算，保证偏移量与公式接近；
            #   2) 限幅：偏移不超过 half_pad 的一定比例，避免剩余补白较小时贴边。
            legacy_canvas_px = 1650.0
            half_pad_px_f = max(0.0, (float(canvas_width_px) - float(w_px)) / 2.0)
            diff_px = float(target_mm_px) - float(legacy_canvas_px)
            visual_shift_px_raw = (diff_px / 2.0) * (float(canvas_width_px) / float(legacy_canvas_px))

            try:
                shift_norm_factor = float(px_per_mm_default) / float(px_per_mm)
            except Exception:
                shift_norm_factor = 1.0
            if (not shift_norm_factor) or shift_norm_factor <= 0:
                shift_norm_factor = 1.0
            shift_norm_factor = max(0.1, min(2.0, float(shift_norm_factor)))

            visual_shift_px = float(visual_shift_px_raw) * float(shift_norm_factor)
            if visual_shift_px < 0:
                visual_shift_px = 0.0

            max_shift_px = max(0.0, half_pad_px_f * 0.85)
            if visual_shift_px > max_shift_px:
                visual_shift_px = max_shift_px

            left_pad_px = int(round(float(half_pad_px_f) + float(visual_shift_px)))
            if left_pad_px < 0:
                left_pad_px = 0
            if left_pad_px > canvas_width_px - w_px:
                left_pad_px = max(0, canvas_width_px - w_px)
            right_pad_px = int(canvas_width_px - w_px - left_pad_px)

            if left_pad_px <= 0 and right_pad_px <= 0:
                # 无需补白，但若已发生缩放（主体已缩小），仍需保存图片并回算 XML 尺寸
                if not scaled_changed:
                    return current_width_mm, current_height_mm
                if save_as_png:
                    img.save(
                        image_path,
                        format="PNG",
                        dpi=(300, 300),
                    )
                else:
                    img.save(
                        image_path,
                        quality=self.config.get("jpeg_quality", 95),
                        subsampling=self.config.get("jpeg_subsampling", 0),
                        dpi=(300, 300),
                    )
                # 返回宽度固定为目标文本宽度，高度按最终像素比回算
                try:
                    with Image.open(image_path) as _img:
                        final_w_px, final_h_px = _img.size
                    if final_w_px > 0:
                        new_height_mm = float(text_width) * (float(final_h_px) / float(final_w_px))
                    else:
                        new_height_mm = float(current_height_mm)
                except Exception:
                    new_height_mm = float(current_height_mm)
                return round(float(text_width), 2), round(float(new_height_mm), 2)

            self._logger.debug(
                f"[EQ_PAD] file='{os.path.basename(image_path)}' "
                f"w_px={w_px} h_px={h_px} cw_mm={cw:.2f} target_width_mm={text_width} "
                f"px_per_mm_raw={px_per_mm_raw:.2f} px_per_mm_clamped={px_per_mm:.2f} "
                f"canvas_width_px={canvas_width_px} legacy_shift=True "
                f"shift_norm_factor={shift_norm_factor:.3f} visual_shift_px={visual_shift_px:.2f} max_shift_px={max_shift_px:.2f} "
                f"left_pad_px={left_pad_px} right_pad_px={right_pad_px}"
            )

            bg_color = self.config.get("bg_color", "#FFFFFF")
            new_img = Image.new("RGB", (canvas_width_px, h_px), bg_color)
            new_img.paste(img, (left_pad_px, 0))

            if save_as_png:
                new_img.save(
                    image_path,
                    format="PNG",
                    dpi=(300, 300),
                )
            else:
                new_img.save(
                    image_path,
                    quality=self.config.get("jpeg_quality", 95),
                    subsampling=self.config.get("jpeg_subsampling", 0),
                    dpi=(300, 300),
                )
    except Exception as e:
        self._logger.warning(f"⚠️ 公式补白失败，保留原尺寸: {e}")
        return current_width_mm, current_height_mm

    # 宽度扩展到目标文本宽度后，需要同步回算高度，确保 wi/he 与最终图片宽高比一致，
    # 否则官方 PDF 预览会按 wi/he 强制铺满导致“拉伸畸变”。
    try:
        with Image.open(image_path) as _img:
            final_w_px, final_h_px = _img.size
        if final_w_px > 0:
            new_height_mm = float(text_width) * (float(final_h_px) / float(final_w_px))
        else:
            new_height_mm = float(current_height_mm)
    except Exception:
        new_height_mm = float(current_height_mm)

    return round(float(text_width), 2), round(float(new_height_mm), 2)
