from __future__ import annotations

# Direct-script support mutates sys.path before project imports.
# ruff: noqa: E402

import argparse
import json
import os
import re
import sys
from typing import Dict, Iterable, List, Tuple
import hashlib
import cv2
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from PIL import Image

from core.config import load_config
from core.img_processor import ImageProcessor


def _read_lines(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().splitlines()
    except Exception:
        return []


def _parse_img_copy_map(lines: Iterable[str]) -> Dict[str, str]:
    # [IMG_COPY] ... src=... dst=...
    mapping: Dict[str, str] = {}
    pattern = re.compile(r"\[IMG_COPY\].*?src=(.*?)\s+dst=(.*)$")
    for line in lines:
        m = pattern.search(line)
        if not m:
            continue
        src = m.group(1).strip()
        dst = m.group(2).strip()
        src_base = os.path.basename(src)
        dst_base = os.path.basename(dst)
        if src_base and dst_base:
            mapping[dst_base] = src_base
    return mapping


def _build_temp_size_index(temp_dir: str) -> Dict[int, List[str]]:
    index: Dict[int, List[str]] = {}
    try:
        for entry in os.scandir(temp_dir):
            if not entry.is_file():
                continue
            name = entry.name.lower()
            if not (
                name.endswith(".jpg")
                or name.endswith(".jpeg")
                or name.endswith(".png")
                or name.endswith(".tif")
                or name.endswith(".tiff")
            ):
                continue
            try:
                size = int(entry.stat().st_size)
            except Exception:
                continue
            index.setdefault(size, []).append(entry.path)
    except Exception:
        pass
    return index


def _file_hash(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _map_by_hash(
    target_path: str,
    temp_size_index: Dict[int, List[str]],
    hash_cache: Dict[str, str],
) -> str | None:
    try:
        size = int(os.path.getsize(target_path))
    except Exception:
        return None
    candidates = temp_size_index.get(size) or []
    if not candidates:
        return None
    target_hash = _file_hash(target_path)
    if not target_hash:
        return None
    for cand in candidates:
        ch = hash_cache.get(cand)
        if not ch:
            ch = _file_hash(cand)
            if ch:
                hash_cache[cand] = ch
        if ch and ch == target_hash:
            return os.path.basename(cand)
    return None


def _parse_table_trim_modes(lines: Iterable[str]) -> Dict[str, str]:
    # TABLE_TRIM_SKIP -> skip
    # TABLE_TRIM_SAFE -> conservative
    modes: Dict[str, str] = {}
    skip_re = re.compile(r"\[TABLE_TRIM_SKIP\].*?file=([^\s]+)")
    safe_re = re.compile(r"\[TABLE_TRIM_SAFE\].*?file=([^\s]+)")
    for line in lines:
        m = skip_re.search(line)
        if m:
            modes[m.group(1).strip()] = "skip"
            continue
        m = safe_re.search(line)
        if m:
            modes[m.group(1).strip()] = "conservative"
    return modes


def _parse_explicit_crop_images(lines: Iterable[str]) -> Dict[str, bool]:
    # [IMG_CROP_EXPLICIT] file=...
    flags: Dict[str, bool] = {}
    exp_re = re.compile(r"\[IMG_CROP_EXPLICIT\].*?file=([^\s]+)")
    for line in lines:
        m = exp_re.search(line)
        if m:
            flags[m.group(1).strip()] = True
    return flags


def _load_targets_from_file(path: str) -> List[str]:
    targets: List[str] = []
    for raw in _read_lines(path):
        line = (raw or "").strip()
        if not line or line.startswith("#"):
            continue
        targets.append(line)
    return targets


def _save_image(image: Image.Image, path: str, cfg: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        quality = int(cfg.get("jpeg_quality", 95))
    except Exception:
        quality = 95
    try:
        subsampling = int(cfg.get("jpeg_subsampling", 0))
    except Exception:
        subsampling = 0
    image.save(path, quality=quality, subsampling=subsampling, dpi=(300, 300))


def _crop_with_guard(
    img_proc: ImageProcessor,
    image: Image.Image,
    padding_ratio: float | None,
    padding_min: int | None,
    *,
    disable_safe_ratio: bool = False,
) -> Image.Image:
    base = image
    try:
        cropped = img_proc._crop_white_borders(base, padding_ratio=padding_ratio, padding_min=padding_min)
    except Exception:
        cropped = base

    try:
        width_ratio = img_proc._get_crop_safe_ratio("crop_safe_width_ratio", 0.85)
    except Exception:
        width_ratio = None
    try:
        height_ratio = img_proc._get_crop_safe_ratio("crop_safe_height_ratio", 0.7)
    except Exception:
        height_ratio = None

    if not disable_safe_ratio:
        try:
            if (width_ratio is not None) or (height_ratio is not None):
                if img_proc._is_crop_too_aggressive(
                    base.size,
                    cropped.size,
                    width_ratio=width_ratio,
                    height_ratio=height_ratio,
                ):
                    return base
        except Exception:
            return base
    return cropped


def _analyze_crop_decision(
    img_proc: ImageProcessor,
    image: Image.Image,
    *,
    padding_ratio: float | None,
    padding_min: int | None,
    disable_safe_ratio: bool = False,
) -> Dict[str, object]:
    info: Dict[str, object] = {
        "status": "unknown",
        "contours": 0,
        "valid_contours": 0,
        "edge_guard": [],
        "candidate_box": None,
        "candidate_size": None,
        "safe_ratio_triggered": False,
        "safe_ratio_disabled": bool(disable_safe_ratio),
    }
    try:
        cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)
        found = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = found[0] if len(found) == 2 else found[1]
        info["contours"] = int(len(contours))
        if not contours:
            info["status"] = "no_contours"
            return info

        valid_contours = [c for c in contours if cv2.contourArea(c) > 20]
        if not valid_contours:
            valid_contours = [c for c in contours if cv2.contourArea(c) > 4]
        info["valid_contours"] = int(len(valid_contours))
        if not valid_contours:
            info["status"] = "no_valid_contours"
            return info

        x, y, w, h = cv2.boundingRect(np.concatenate(valid_contours))
        h_img, w_img = cv_img.shape[:2]

        if padding_ratio is None:
            padding_ratio = img_proc.config.get("crop_padding_ratio", 0.02)
        if padding_min is None:
            padding_min = img_proc.config.get("crop_padding_min", 4)

        pad_x = max(int(w_img * float(padding_ratio)), int(padding_min))
        pad_y = max(int(h_img * float(padding_ratio)), int(padding_min))
        left = max(0, x - pad_x)
        right = min(w_img, x + w + pad_x)
        top = max(0, y - pad_y)
        bottom = min(h_img, y + h + pad_y)
        info["candidate_box"] = [int(left), int(top), int(right), int(bottom)]
        info["candidate_size"] = [int(right - left), int(bottom - top)]

        try:
            edge_guard_px = int(img_proc.config.get("crop_edge_guard_px", 2))
        except Exception:
            edge_guard_px = 2
        try:
            edge_guard_thresh = int(img_proc.config.get("crop_edge_guard_threshold", 245))
        except Exception:
            edge_guard_thresh = 245
        edge_guard_px = max(
            0,
            min(
                int(edge_guard_px),
                int(min(w_img, h_img) // 4) if min(w_img, h_img) >= 4 else 1,
            ),
        )
        risk_sides = []
        if edge_guard_px > 0:
            def _edge_has_content(arr):
                try:
                    return bool((arr < edge_guard_thresh).any())
                except Exception:
                    return False

            if left > 0 and _edge_has_content(gray[:, :edge_guard_px]):
                risk_sides.append("left")
            if right < w_img and _edge_has_content(gray[:, max(0, w_img - edge_guard_px) : w_img]):
                risk_sides.append("right")
            if top > 0 and _edge_has_content(gray[:edge_guard_px, :]):
                risk_sides.append("top")
            if bottom < h_img and _edge_has_content(gray[max(0, h_img - edge_guard_px) : h_img, :]):
                risk_sides.append("bottom")

        if risk_sides:
            info["edge_guard"] = risk_sides
            info["status"] = "edge_guard"
            return info

        info["status"] = "ok"

        try:
            width_ratio = img_proc._get_crop_safe_ratio("crop_safe_width_ratio", 0.85)
        except Exception:
            width_ratio = None
        try:
            height_ratio = img_proc._get_crop_safe_ratio("crop_safe_height_ratio", 0.7)
        except Exception:
            height_ratio = None
        if not disable_safe_ratio:
            if (width_ratio is not None) or (height_ratio is not None):
                if img_proc._is_crop_too_aggressive(
                    image.size,
                    (int(right - left), int(bottom - top)),
                    width_ratio=width_ratio,
                    height_ratio=height_ratio,
                ):
                    info["safe_ratio_triggered"] = True
                    info["status"] = "safe_ratio"
        return info
    except Exception as exc:
        info["status"] = "exception"
        info["error"] = str(exc)
        return info


def _process_table(
    img_proc: ImageProcessor,
    src_path: str,
    dst_path: str,
    mode: str,
    cfg: dict,
    *,
    disable_safe_ratio: bool = False,
) -> Tuple[str, Dict[str, object]]:
    with Image.open(src_path) as im:
        base = im.convert("RGB")

    if mode == "skip":
        diag = {"status": "skip"}
    elif mode == "conservative":
        diag = _analyze_crop_decision(
            img_proc,
            base,
            padding_ratio=None,
            padding_min=None,
            disable_safe_ratio=disable_safe_ratio,
        )
    else:
        diag = _analyze_crop_decision(
            img_proc,
            base,
            padding_ratio=0.0,
            padding_min=4,
            disable_safe_ratio=disable_safe_ratio,
        )

    if mode == "skip":
        result = base
    elif mode == "conservative":
        result = _crop_with_guard(
            img_proc,
            base,
            padding_ratio=None,
            padding_min=None,
            disable_safe_ratio=disable_safe_ratio,
        )
    else:
        result = _crop_with_guard(
            img_proc,
            base,
            padding_ratio=0.0,
            padding_min=4,
            disable_safe_ratio=disable_safe_ratio,
        )

    _save_image(result, dst_path, cfg)
    diag["size_before"] = list(base.size)
    diag["size_after"] = list(result.size)
    diag["applied"] = bool(base.size != result.size)
    return mode, diag


def _process_normal(
    img_proc: ImageProcessor,
    src_path: str,
    dst_path: str,
    explicit_crop: bool,
    cfg: dict,
) -> Tuple[str, Dict[str, object]]:
    with Image.open(src_path) as im:
        base = im.convert("RGB")

    if explicit_crop:
        result = base
        mode = "skip_explicit"
        diag = {"status": "skip_explicit", "size_before": list(base.size), "size_after": list(base.size), "applied": False}
    else:
        # Use the same processing path as normal images: crop=True + enhancement enabled
        result = base
        img_proc.process_image(result, dst_path, is_equation=False, crop=True, apply_enhancement=True)
        try:
            with Image.open(dst_path) as out_im:
                out_size = list(out_im.size)
        except Exception:
            out_size = list(base.size)
        diag = {"status": "normal", "size_before": list(base.size), "size_after": out_size, "applied": bool(base.size != tuple(out_size))}
        return "normal", diag

    _save_image(result, dst_path, cfg)
    return mode, diag


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch crop test for temp_processing images.")
    parser.add_argument("--log", default="conversion.log", help="Path to conversion.log")
    parser.add_argument("--config", default=None, help="Path to config.yaml (optional)")
    parser.add_argument("--temp-dir", default=None, help="temp_processing directory (optional)")
    parser.add_argument("--out-dir", default=None, help="Output directory (optional)")
    parser.add_argument("--targets-file", default=None, help="Text file with output image paths (one per line)")
    parser.add_argument("--targets", nargs="*", default=None, help="Output image paths (space-separated)")
    parser.add_argument("--report", default=None, help="Write JSON report to this path (optional)")
    parser.add_argument(
        "--disable-safe-ratio",
        action="store_true",
        help="Disable safe_ratio guard (test only)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    img_proc = ImageProcessor(cfg)

    temp_dir = args.temp_dir or os.path.abspath(cfg.get("paths", {}).get("temp_dir", "temp_processing"))
    out_dir = args.out_dir or os.path.join(temp_dir, "crop_test")
    os.makedirs(out_dir, exist_ok=True)

    targets: List[str] = []
    if args.targets_file:
        targets.extend(_load_targets_from_file(args.targets_file))
    if args.targets:
        targets.extend(args.targets)

    if not targets:
        print("No targets provided. Use --targets-file or --targets.")
        return 1

    log_lines = _read_lines(args.log)
    copy_map = _parse_img_copy_map(log_lines)
    temp_size_index = _build_temp_size_index(temp_dir)
    hash_cache: Dict[str, str] = {}
    table_modes = _parse_table_trim_modes(log_lines)
    explicit_crop_flags = _parse_explicit_crop_images(log_lines)

    results = []
    missing_map = 0
    mapped_by_hash = 0
    missing_src = 0

    for target in targets:
        target = target.strip().strip('"')
        base_out = os.path.basename(target)
        src_base = copy_map.get(base_out)
        if not src_base:
            src_base = _map_by_hash(target, temp_size_index, hash_cache)
            if src_base:
                mapped_by_hash += 1
            else:
                missing_map += 1
                results.append({"target": base_out, "status": "no_mapping"})
                continue

        src_path = os.path.join(temp_dir, src_base)
        if not os.path.exists(src_path):
            missing_src += 1
            results.append({"target": base_out, "src": src_base, "status": "missing_temp"})
            continue

        dst_path = os.path.join(out_dir, base_out)
        is_table = src_base.lower().startswith("tbl_")

        if is_table:
            mode = table_modes.get(src_base, "tight")
            applied, diag = _process_table(
                img_proc,
                src_path,
                dst_path,
                mode,
                cfg,
                disable_safe_ratio=args.disable_safe_ratio,
            )
            results.append(
                {
                    "target": base_out,
                    "src": src_base,
                    "kind": "table",
                    "mode": applied,
                    "out": dst_path,
                    "diag": diag,
                }
            )
        else:
            explicit_crop = bool(explicit_crop_flags.get(src_base))
            applied, diag = _process_normal(img_proc, src_path, dst_path, explicit_crop, cfg)
            results.append(
                {
                    "target": base_out,
                    "src": src_base,
                    "kind": "normal",
                    "mode": applied,
                    "out": dst_path,
                    "diag": diag,
                }
            )

    summary = {
        "total_targets": len(targets),
        "mapped": len(targets) - missing_map,
        "mapped_by_hash": mapped_by_hash,
        "missing_map": missing_map,
        "missing_temp": missing_src,
        "output_dir": out_dir,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.report:
        try:
            with open(args.report, "w", encoding="utf-8") as f:
                json.dump({"summary": summary, "items": results}, f, ensure_ascii=False, indent=2)
        except Exception:
            print("Failed to write report:", args.report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
