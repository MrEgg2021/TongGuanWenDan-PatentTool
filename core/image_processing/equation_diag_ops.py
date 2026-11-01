from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any

import cv2
import numpy as np
from PIL import Image

_PRIMARY_MIN_AREA = 20.0
_FALLBACK_MIN_AREA = 4.0
_DEFAULT_CROP_THRESHOLD = 230
_DEFAULT_EQUATION_CROP_THRESHOLD = 245


def _get_image_processing_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    nested = config.get("image_processing")
    if isinstance(nested, dict):
        return nested
    return config


def resolve_crop_content_threshold(
    config: dict[str, Any] | None,
    *,
    preserve_detached_equation_marks: bool,
) -> int:
    if not preserve_detached_equation_marks:
        return _DEFAULT_CROP_THRESHOLD

    img_cfg = _get_image_processing_config(config)
    try:
        threshold = int(img_cfg.get("crop_edge_guard_threshold", _DEFAULT_EQUATION_CROP_THRESHOLD))
    except (TypeError, ValueError):
        threshold = _DEFAULT_EQUATION_CROP_THRESHOLD
    return max(0, min(254, threshold))


def is_equation_diag_enabled(config: dict[str, Any] | None) -> bool:
    img_cfg = _get_image_processing_config(config)
    try:
        return bool(img_cfg.get("equation_diag_enabled", False))
    except Exception:
        return False


def resolve_equation_diag_dir(
    config: dict[str, Any] | None,
    image_path_or_name: str,
    *,
    ensure: bool = False,
) -> str | None:
    if not is_equation_diag_enabled(config):
        return None

    try:
        stem = os.path.splitext(os.path.basename(str(image_path_or_name) or ""))[0]
    except Exception:
        stem = ""
    if not stem:
        return None

    img_cfg = _get_image_processing_config(config)
    try:
        diag_root = str(img_cfg.get("equation_diag_dir") or "").strip()
    except Exception:
        diag_root = ""
    if not diag_root:
        diag_root = os.path.join("temp_processing", "eq_diag")
    diag_root = os.path.abspath(diag_root)
    diag_dir = os.path.join(diag_root, stem)
    if ensure:
        os.makedirs(diag_dir, exist_ok=True)
    return diag_dir


def get_existing_equation_diag_dir(
    config: dict[str, Any] | None,
    image_path_or_name: str,
) -> str | None:
    diag_dir = resolve_equation_diag_dir(config, image_path_or_name, ensure=False)
    if not diag_dir or not os.path.isdir(diag_dir):
        return None
    return diag_dir


def _coerce_image(image: Image.Image | str) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.copy()
    with Image.open(str(image)) as img:
        return img.copy()


def save_equation_diag_stage(
    config: dict[str, Any] | None,
    image_path_or_name: str,
    stage_name: str,
    image: Image.Image | str,
    *,
    require_existing: bool = False,
) -> str | None:
    if not stage_name:
        return None

    diag_dir = (
        get_existing_equation_diag_dir(config, image_path_or_name)
        if require_existing
        else resolve_equation_diag_dir(config, image_path_or_name, ensure=True)
    )
    if not diag_dir:
        return None

    diag_path = os.path.join(diag_dir, str(stage_name))
    img = _coerce_image(image)
    img.save(diag_path, format="PNG", dpi=(300, 300))
    return diag_path


def write_equation_diag_json(
    config: dict[str, Any] | None,
    image_path_or_name: str,
    file_name: str,
    payload: dict[str, Any],
    *,
    require_existing: bool = False,
) -> str | None:
    if not file_name:
        return None

    diag_dir = (
        get_existing_equation_diag_dir(config, image_path_or_name)
        if require_existing
        else resolve_equation_diag_dir(config, image_path_or_name, ensure=True)
    )
    if not diag_dir:
        return None

    diag_path = os.path.join(diag_dir, str(file_name))
    with open(diag_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return diag_path


def write_equation_output_mapping(
    config: dict[str, Any] | None,
    image_path_or_name: str,
    *,
    temp_source: str,
    final_output: str,
    section_key: str | None = None,
) -> str | None:
    diag_dir = get_existing_equation_diag_dir(config, image_path_or_name)
    if not diag_dir:
        return None

    payload = {
        "diagnostic_dir": diag_dir,
        "final_output": str(final_output),
        "section_key": str(section_key or ""),
        "temp_source": str(temp_source),
    }
    return write_equation_diag_json(
        config,
        image_path_or_name,
        "output_mapping.json",
        payload,
        require_existing=True,
    )


def _build_contour_entries(contours: Sequence[np.ndarray]) -> list[dict[str, Any]]:
    contour_entries: list[dict[str, Any]] = []
    for idx, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        contour_entries.append(
            {
                "area": float(cv2.contourArea(contour)),
                "bbox": {
                    "left": int(x),
                    "top": int(y),
                    "right": int(x + w),
                    "bottom": int(y + h),
                    "width": int(w),
                    "height": int(h),
                },
                "index": int(idx),
            }
        )
    return contour_entries


def _select_retained_indices(
    contour_entries: list[dict[str, Any]],
    *,
    primary_min_area: float,
    fallback_min_area: float,
) -> tuple[set[int], float]:
    retained_indices = {
        entry["index"]
        for entry in contour_entries
        if float(entry["area"]) > float(primary_min_area)
    }
    retained_min_area = float(primary_min_area)
    if retained_indices:
        return retained_indices, retained_min_area

    retained_indices = {
        entry["index"]
        for entry in contour_entries
        if float(entry["area"]) > float(fallback_min_area)
    }
    retained_min_area = float(fallback_min_area)
    return retained_indices, retained_min_area


def _build_bbox_from_indices(
    contours: Sequence[np.ndarray],
    indices: set[int],
) -> dict[str, int] | None:
    if not indices:
        return None

    kept_contours = [contours[idx] for idx in sorted(indices)]
    x, y, w, h = cv2.boundingRect(np.concatenate(kept_contours))
    return {
        "left": int(x),
        "top": int(y),
        "right": int(x + w),
        "bottom": int(y + h),
        "width": int(w),
        "height": int(h),
    }


def _build_promoted_micro_record(
    entry: dict[str, Any],
    *,
    raw_bbox: dict[str, int] | None,
) -> dict[str, Any]:
    bbox = entry["bbox"]
    center_x = float(bbox["left"] + bbox["width"] / 2.0)
    is_above = bool(raw_bbox and bbox["bottom"] <= raw_bbox["top"])
    is_below = bool(raw_bbox and bbox["top"] >= raw_bbox["bottom"])
    is_left = bool(raw_bbox and bbox["right"] <= raw_bbox["left"])
    is_right = bool(raw_bbox and bbox["left"] >= raw_bbox["right"])

    if raw_bbox is None:
        relative_position = "unanchored"
        vertical_gap_px = 0
        horizontal_overlap = False
        center_within_horizontal_slack = False
    else:
        positions = []
        if is_above:
            positions.append("above")
            vertical_gap_px = int(raw_bbox["top"] - bbox["bottom"])
        elif is_below:
            positions.append("below")
            vertical_gap_px = int(bbox["top"] - raw_bbox["bottom"])
        else:
            vertical_gap_px = 0
        if is_left:
            positions.append("left")
        elif is_right:
            positions.append("right")
        relative_position = "-".join(positions) if positions else "overlap"
        horizontal_overlap = not (is_left or is_right)
        center_within_horizontal_slack = float(raw_bbox["left"]) <= center_x <= float(raw_bbox["right"])

    return {
        "area": float(entry["area"]),
        "bbox": bbox,
        "center": [
            center_x,
            float(bbox["top"] + bbox["height"] / 2.0),
        ],
        "center_within_horizontal_slack": bool(center_within_horizontal_slack),
        "horizontal_overlap_raw_bbox": bool(horizontal_overlap),
        "is_above_raw_bbox": is_above,
        "is_below_raw_bbox": is_below,
        "is_left_of_raw_bbox": is_left,
        "is_right_of_raw_bbox": is_right,
        "relative_position": relative_position,
        "vertical_gap_px": int(vertical_gap_px),
    }


def _build_discarded_small_record(
    entry: dict[str, Any],
    *,
    final_bbox: dict[str, int] | None,
) -> dict[str, Any]:
    bbox = entry["bbox"]
    return {
        "area": float(entry["area"]),
        "bbox": bbox,
        "center": [
            float(bbox["left"] + bbox["width"] / 2.0),
            float(bbox["top"] + bbox["height"] / 2.0),
        ],
        "is_above_final_bbox": bool(final_bbox and bbox["bottom"] <= final_bbox["top"]),
    }


def _promote_detached_equation_marks(
    contour_entries: list[dict[str, Any]],
    *,
    retained_indices: set[int],
    raw_bbox: dict[str, int] | None,
    preserve_detached_equation_marks: bool,
) -> tuple[set[int], list[dict[str, Any]]]:
    if not preserve_detached_equation_marks:
        return set(), []

    promoted_entries = [
        entry for entry in contour_entries if entry["index"] not in retained_indices
    ]
    promoted_indices = {entry["index"] for entry in promoted_entries}
    promoted_records = [
        _build_promoted_micro_record(entry, raw_bbox=raw_bbox)
        for entry in promoted_entries
    ]

    return promoted_indices, promoted_records


def analyze_crop_contours(
    image: Image.Image | str,
    *,
    threshold: int = 230,
    padding_ratio: float = 0.0,
    padding_min: int = 0,
    primary_min_area: float = _PRIMARY_MIN_AREA,
    fallback_min_area: float = _FALLBACK_MIN_AREA,
    preserve_detached_equation_marks: bool = False,
) -> dict[str, Any]:
    img = _coerce_image(image).convert("RGB")
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, int(threshold), 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    contour_entries = _build_contour_entries(contours)
    retained_indices, retained_min_area = _select_retained_indices(
        contour_entries,
        primary_min_area=float(primary_min_area),
        fallback_min_area=float(fallback_min_area),
    )
    raw_bbox = _build_bbox_from_indices(contours, retained_indices)
    promoted_indices, promoted_micro_contours = _promote_detached_equation_marks(
        contour_entries,
        retained_indices=retained_indices,
        raw_bbox=raw_bbox,
        preserve_detached_equation_marks=bool(preserve_detached_equation_marks),
    )

    combined_indices = set(retained_indices) | set(promoted_indices)
    combined_bbox = _build_bbox_from_indices(contours, combined_indices)

    final_bbox: dict[str, int] | None = None
    pad_x = 0
    pad_y = 0
    if combined_bbox:
        h_img, w_img = gray.shape[:2]
        pad_x = max(int(w_img * float(padding_ratio)), int(padding_min))
        pad_y = max(int(h_img * float(padding_ratio)), int(padding_min))
        left = max(0, int(combined_bbox["left"]) - pad_x)
        right = min(w_img, int(combined_bbox["right"]) + pad_x)
        top = max(0, int(combined_bbox["top"]) - pad_y)
        bottom = min(h_img, int(combined_bbox["bottom"]) + pad_y)
        final_bbox = {
            "left": int(left),
            "top": int(top),
            "right": int(right),
            "bottom": int(bottom),
            "width": int(right - left),
            "height": int(bottom - top),
        }

    discarded_small_contours = [
        _build_discarded_small_record(entry, final_bbox=final_bbox)
        for entry in contour_entries
        if entry["index"] not in retained_indices and entry["index"] not in promoted_indices
    ]
    retained_contour_areas = sorted(
        [
            float(entry["area"])
            for entry in contour_entries
            if entry["index"] in retained_indices
        ],
        reverse=True,
    )
    render_w, render_h = img.size
    return {
        "discarded_small_contours": discarded_small_contours,
        "final_bbox": final_bbox,
        "padding": {
            "pad_x": int(pad_x),
            "pad_y": int(pad_y),
            "padding_min": int(padding_min),
            "padding_ratio": float(padding_ratio),
        },
        "preserve_detached_equation_marks": bool(preserve_detached_equation_marks),
        "promoted_micro_contours": promoted_micro_contours,
        "raw_bbox": raw_bbox,
        "render_size": [int(render_w), int(render_h)],
        "retained_contour_areas": retained_contour_areas,
        "retained_min_area": int(retained_min_area),
        "threshold": int(threshold),
        "total_contours": int(len(contour_entries)),
    }


def build_emf_crop_diagnostics(
    image: Image.Image | str,
    *,
    threshold: int = 230,
    padding_ratio: float = 0.0,
    padding_min: int = 0,
    primary_min_area: float = _PRIMARY_MIN_AREA,
    fallback_min_area: float = _FALLBACK_MIN_AREA,
    preserve_detached_equation_marks: bool = False,
) -> dict[str, Any]:
    return analyze_crop_contours(
        image,
        threshold=threshold,
        padding_ratio=padding_ratio,
        padding_min=padding_min,
        primary_min_area=primary_min_area,
        fallback_min_area=fallback_min_area,
        preserve_detached_equation_marks=preserve_detached_equation_marks,
    )


__all__ = [
    "analyze_crop_contours",
    "build_emf_crop_diagnostics",
    "get_existing_equation_diag_dir",
    "is_equation_diag_enabled",
    "resolve_crop_content_threshold",
    "resolve_equation_diag_dir",
    "save_equation_diag_stage",
    "write_equation_diag_json",
    "write_equation_output_mapping",
]
