from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageOps

from core.image_processing.equation_diag_ops import (
    analyze_crop_contours,
    resolve_crop_content_threshold,
)


def _crop_white_borders(
    self,
    image,
    padding_ratio=None,
    padding_min=None,
    preserve_detached_equation_marks=False,
):
    """
    OpenCV 自动裁剪白边
    padding_ratio: 如果为 None，使用 config 中的 crop_padding_ratio
    padding_min: 如果为 None，使用 config 中的 crop_padding_min
    """
    try:
        if padding_ratio is None:
            padding_ratio = self.config.get("crop_padding_ratio", 0.02)
        if padding_min is None:
            padding_min = self.config.get("crop_padding_min", 4)

        preserve_equation_marks = bool(preserve_detached_equation_marks)
        analysis = analyze_crop_contours(
            image,
            threshold=resolve_crop_content_threshold(
                self.config,
                preserve_detached_equation_marks=preserve_equation_marks,
            ),
            padding_ratio=float(padding_ratio),
            padding_min=int(padding_min),
            preserve_detached_equation_marks=preserve_equation_marks,
        )
        final_bbox = analysis.get("final_bbox") or {}
        left = int(final_bbox.get("left", 0))
        right = int(final_bbox.get("right", 0))
        top = int(final_bbox.get("top", 0))
        bottom = int(final_bbox.get("bottom", 0))
        if (right - left) <= 0 or (bottom - top) <= 0:
            return image

        img_rgb = image.convert("RGB")
        cv_img = cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        h_img, w_img = cv_img.shape[:2]

        # 安全裁切：若边缘存在疑似有效像素，则回退到不裁切
        try:
            edge_guard_px = int(self.config.get("crop_edge_guard_px", 2))
        except Exception:
            edge_guard_px = 2
        try:
            edge_guard_thresh = int(self.config.get("crop_edge_guard_threshold", 245))
        except Exception:
            edge_guard_thresh = 245
        edge_guard_px = max(0, min(edge_guard_px, int(min(w_img, h_img) // 4) if min(w_img, h_img) >= 4 else 1))
        if edge_guard_px > 0:
            def _edge_has_content(arr):
                try:
                    return bool((arr < edge_guard_thresh).any())
                except Exception:
                    return False

            risk_sides = []
            if left > 0:
                if _edge_has_content(gray[:, :edge_guard_px]):
                    risk_sides.append("left")
            if right < w_img:
                if _edge_has_content(gray[:, max(0, w_img - edge_guard_px) : w_img]):
                    risk_sides.append("right")
            if top > 0:
                if _edge_has_content(gray[:edge_guard_px, :]):
                    risk_sides.append("top")
            if bottom < h_img:
                if _edge_has_content(gray[max(0, h_img - edge_guard_px) : h_img, :]):
                    risk_sides.append("bottom")
            if risk_sides:
                try:
                    self._logger.warning(
                        "⚠️ 安全裁切触发：边缘存在疑似有效像素，跳过裁切 sides=%s",
                        ",".join(risk_sides),
                    )
                except Exception:
                    pass
                return image

        return image.crop((left, top, right, bottom))
    except Exception as e:
        self._logger.warning(f"⚠️ 裁剪失败，保留原图: {e}")
        return image

def _pad_if_content_touches_edge(self, image):
    """如果内容贴边，则为图像补安全留白，避免 PDF 预览边缘裁切。"""
    if image is None:
        return image

    try:
        min_margin_px = int(self.config.get("crop_output_min_margin_px", self.config.get("crop_edge_guard_px", 2)))
    except Exception:
        min_margin_px = 2
    if min_margin_px <= 0:
        return image

    try:
        edge_guard_thresh = int(self.config.get("crop_edge_guard_threshold", 245))
    except Exception:
        edge_guard_thresh = 245
    edge_guard_thresh = max(0, min(255, int(edge_guard_thresh)))

    try:
        # NOTE:
        # 这里使用像素级 bbox（np.where）而不是 contourArea 过滤。
        # 结构式/细线可能 contour 面积极小，导致 bbox 漏检，补白逻辑不触发。
        img_rgb = image.convert("RGB")
        gray = np.array(img_rgb.convert("L"))
        h_img, w_img = gray.shape[:2]
        if not w_img or not h_img:
            return image

        mask = gray <= edge_guard_thresh
        ys, xs = np.where(mask)
        if xs.size == 0 or ys.size == 0:
            return image

        # 轻微去噪：过少的深色像素通常是 JPEG 噪点或扫描点。
        # 阈值必须足够低，避免误杀“贴边细线”。
        if int(xs.size) < 3:
            return image

        x0 = int(xs.min())
        x1 = int(xs.max())
        y0 = int(ys.min())
        y1 = int(ys.max())

        left_margin = int(x0)
        top_margin = int(y0)
        right_margin = int((w_img - 1) - x1)
        bottom_margin = int((h_img - 1) - y1)

        pad_left = max(0, int(min_margin_px - left_margin))
        pad_top = max(0, int(min_margin_px - top_margin))
        pad_right = max(0, int(min_margin_px - right_margin))
        pad_bottom = max(0, int(min_margin_px - bottom_margin))

        if pad_left or pad_top or pad_right or pad_bottom:
            try:
                self._logger.debug(
                    "[CROP_MARGIN_PAD] pads=(%d,%d,%d,%d) min_margin=%d thresh=%d bbox=(%d,%d,%d,%d) margins=(%d,%d,%d,%d) img_wh=(%d,%d)",
                    pad_left,
                    pad_top,
                    pad_right,
                    pad_bottom,
                    min_margin_px,
                    edge_guard_thresh,
                    x0,
                    y0,
                    x1,
                    y1,
                    left_margin,
                    top_margin,
                    right_margin,
                    bottom_margin,
                    w_img,
                    h_img,
                )
            except Exception:
                pass
            bg = self.config.get("bg_color", "#FFFFFF")
            return ImageOps.expand(img_rgb, border=(pad_left, pad_top, pad_right, pad_bottom), fill=bg)

        return image
    except Exception:
        return image

def _detect_background_color(self, image) -> tuple[int, int, int]:
    try:
        img = image.convert("RGB")
    except Exception:
        return (255, 255, 255)

    try:
        arr = np.array(img)
    except Exception:
        return (255, 255, 255)

    try:
        h, w = arr.shape[:2]
    except Exception:
        return (255, 255, 255)
    if not w or not h:
        return (255, 255, 255)

    margin = 6
    try:
        margin = int(self.config.get("drawings_bg_sample_margin", 6))
    except Exception:
        margin = 6
    margin = max(1, min(int(margin), int(min(w, h) // 4) if min(w, h) >= 4 else 1))

    try:
        top = arr[:margin, :, :].reshape(-1, 3)
        bottom = arr[max(0, h - margin) : h, :, :].reshape(-1, 3)
        left = arr[:, :margin, :].reshape(-1, 3)
        right = arr[:, max(0, w - margin) : w, :].reshape(-1, 3)
        samples = np.concatenate([top, bottom, left, right], axis=0)
    except Exception:
        return (255, 255, 255)
    if samples.size == 0:
        return (255, 255, 255)

    try:
        q = (samples // 8).astype(np.uint8)
        uniq, counts = np.unique(q, axis=0, return_counts=True)
        if uniq.size == 0:
            return (255, 255, 255)
        idx = int(np.argmax(counts))
        target_q = uniq[idx]
        mask = np.all(q == target_q, axis=1)
        picked = samples[mask]
        if picked.size == 0:
            picked = samples
        mean = np.mean(picked, axis=0)
        r, g, b = [int(max(0, min(255, int(round(x))))) for x in mean.tolist()]
        return (r, g, b)
    except Exception:
        try:
            mean = np.mean(samples, axis=0)
            r, g, b = [int(max(0, min(255, int(round(x))))) for x in mean.tolist()]
            return (r, g, b)
        except Exception:
            return (255, 255, 255)

def _crop_solid_background(self, image, bg_rgb: tuple[int, int, int], *, padding_px: int = 2):
    try:
        img = image.convert("RGB")
    except Exception:
        return image

    tol = 28
    try:
        tol = int(self.config.get("drawings_bg_tolerance", 28))
    except Exception:
        tol = 28
    tol = max(2, min(120, int(tol)))

    try:
        pad = int(padding_px)
    except Exception:
        pad = 2
    pad = max(0, min(50, int(pad)))

    try:
        arr = np.array(img)
        h, w = arr.shape[:2]
        if w <= 0 or h <= 0:
            return image
        bg = np.array(bg_rgb, dtype=np.int16).reshape(1, 1, 3)
        diff = np.abs(arr.astype(np.int16) - bg)
        score = diff.sum(axis=2)
        mask = (score > int(tol) * 3).astype(np.uint8) * 255

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image
        valid = [c for c in contours if cv2.contourArea(c) > 20]
        if not valid:
            valid = [c for c in contours if cv2.contourArea(c) > 4]
        if not valid:
            return image

        x, y, cw, ch = cv2.boundingRect(np.concatenate(valid))
        left = max(0, int(x) - pad)
        top = max(0, int(y) - pad)
        right = min(int(w), int(x + cw) + pad)
        bottom = min(int(h), int(y + ch) + pad)
        if right <= left or bottom <= top:
            return image

        return img.crop((left, top, right, bottom))
    except Exception:
        return image

def _pad_to_ratio(self, image, *, ratio_num: int, ratio_den: int, bg_rgb: tuple[int, int, int]):
    if ratio_num <= 0 or ratio_den <= 0:
        return image
    try:
        img = image.convert("RGB")
    except Exception:
        return image

    w, h = img.size
    if w <= 0 or h <= 0:
        return image

    try:
        need_w = (float(w) / float(h)) < (float(ratio_num) / float(ratio_den))
    except Exception:
        need_w = False

    if need_w:
        new_w = int(math.ceil(float(h) * float(ratio_num) / float(ratio_den)))
        new_h = int(h)
    else:
        new_w = int(w)
        new_h = int(math.ceil(float(w) * float(ratio_den) / float(ratio_num)))

    if new_w <= w and new_h <= h:
        return img
    if new_w <= 0 or new_h <= 0:
        return img

    try:
        canvas = Image.new("RGB", (int(new_w), int(new_h)), tuple(bg_rgb))
        left = int((new_w - w) // 2)
        top = int((new_h - h) // 2)
        canvas.paste(img, (left, top))
        return canvas
    except Exception:
        return img

