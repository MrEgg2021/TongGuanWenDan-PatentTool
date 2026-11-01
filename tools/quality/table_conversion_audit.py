from __future__ import annotations

# Direct-script support mutates sys.path before project imports.
# ruff: noqa: E402

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

from lxml import etree

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.config import load_config


PLACEHOLDER_MARKERS = (
    "表格截图失败",
    "未写入 XML",
)
DOC_CODE_TO_SECTION = {
    "100001": "claims",
    "100002": "description",
    "100003": "drawings",
    "100004": "abstract",
}

TRY_RE = re.compile(
    r"\[TABLE_CAPTURE_TRY\] idx=(?P<idx>\d+) section=(?P<section>\S+) "
    r"(?:range=\((?P<range_start>[^,]+),(?P<range_end>[^\)]+)\)|range_start=(?P<range_start_alt>\S+))"
)
RESULT_RE = re.compile(
    r"\[TABLE_CAPTURE_RESULT\] idx=(?P<idx>\d+) section=(?P<section>\S+) "
    r"(?:range=\((?P<range_start>[^,]+),(?P<range_end>[^\)]+)\)|range_start=(?P<range_start_alt>\S+)) "
    r"success=(?P<success>True|False)"
)
CENTER_RE = re.compile(
    r"\[TABLE_CENTER\] file=(?P<file>\S+) section=(?P<section>\S+) target_width_mm=(?P<target>[-0-9.]+) "
    r"before_w_mm=(?P<before_w>[-0-9.]+) before_h_mm=(?P<before_h>[-0-9.]+) "
    r"after_w_mm=(?P<after_w>[-0-9.]+) after_h_mm=(?P<after_h>[-0-9.]+)"
)
PREVIEW_FIT_RE = re.compile(
    r"\[TABLE_PREVIEW_FIT\] section=(?P<section>\S+) file=(?P<file>\S+) "
    r"before_w_mm=(?P<before_w>[-0-9.]+) before_h_mm=(?P<before_h>[-0-9.]+) "
    r"after_w_mm=(?P<after_w>[-0-9.]+) after_h_mm=(?P<after_h>[-0-9.]+)"
)
PDF_FRAGMENT_EMIT_RE = re.compile(
    r"\[TABLE_PDF_FRAGMENT_EMIT\] pages=(?P<pages>\d+) source_method=(?P<source>\S+) hard_table=(?P<hard_table>\S+)"
)
PDF_FRAGMENT_VISUAL_SLICE_RE = re.compile(
    r"\[TABLE_PDF_FRAGMENT_VISUAL_SLICE\] page=(?P<page>\d+) file=(?P<file>\S+) "
    r"original_height_mm=(?P<original_height>[-0-9.]+) max_height_mm=(?P<max_height>[-0-9.]+) "
    r"slices=(?P<slices>\d+) slice_heights_mm=(?P<heights>\S*) cut_modes=(?P<cut_modes>\S*)"
    r"(?: mode=(?P<mode>\S+) total_height_mm=(?P<total_height>[-0-9.]+) "
    r"cuts_px=(?P<cuts_px>\S*) cut_scores=(?P<cut_scores>\S*) boundary_closed=(?P<boundary_closed>\S+))?"
)
EMIT_SUMMARY_RE = re.compile(
    r"\[TABLE_EMIT_SUMMARY\] idx=(?P<idx>\d+) section=(?P<section>\S+) range_start=(?P<range_start>\S+) "
    r"range_end=(?P<range_end>\S+) fragments=(?P<fragments>\d+) files=(?P<files>\S*) "
    r"widths_mm=(?P<widths>\S*) heights_mm=(?P<heights>\S*)"
)
OUTPUT_MAP_RE = re.compile(
    r"\[TABLE_OUTPUT_MAP\] section=(?P<section>\S+) temp=(?P<temp>\S+) final=(?P<final>\S+)"
)


def _pixel_dark_ratio(image, *, threshold: int = 245) -> float:
    try:
        pixels = list(image.getdata())
    except Exception:
        return 0.0
    if not pixels:
        return 0.0
    dark_pixels = sum(1 for pixel in pixels if int(pixel) < int(threshold))
    return float(dark_pixels) / float(len(pixels))


def _analyze_blank_half_fragment(image_path: Path) -> dict | None:
    try:
        from PIL import Image
    except Exception:
        return None

    try:
        with Image.open(image_path) as img:
            gray = img.convert("L")
            width, height = gray.size
            if int(width) < 200 or int(height) < 200:
                return None

            top_height = max(1, int(float(height) * 0.40))
            mid_x = max(1, int(width) // 2)
            left_top = gray.crop((0, 0, mid_x, top_height))
            right_top = gray.crop((mid_x, 0, width, top_height))
            lower_region = gray.crop((0, top_height, width, height))
    except Exception:
        return None

    left_ratio = _pixel_dark_ratio(left_top)
    right_ratio = _pixel_dark_ratio(right_top)
    lower_ratio = _pixel_dark_ratio(lower_region)
    blank_threshold = 0.015
    filled_threshold = 0.03
    contrast_gap = 0.015

    blank_side = ""
    if (
        left_ratio <= blank_threshold
        and right_ratio >= filled_threshold
        and (right_ratio - left_ratio) >= contrast_gap
        and lower_ratio >= 0.02
    ):
        blank_side = "left"
    elif (
        right_ratio <= blank_threshold
        and left_ratio >= filled_threshold
        and (left_ratio - right_ratio) >= contrast_gap
        and lower_ratio >= 0.02
    ):
        blank_side = "right"

    return {
        "blank_side": str(blank_side),
        "left_ratio": float(left_ratio),
        "right_ratio": float(right_ratio),
        "lower_ratio": float(lower_ratio),
    }


def _detect_complementary_blank_half_anomalies(fragments: list[dict]) -> list[str]:
    eligible: list[dict] = []
    for fragment in list(fragments or []):
        try:
            width_mm = float(fragment.get("wi") or 0.0)
            height_mm = float(fragment.get("he") or 0.0)
        except Exception:
            continue
        if width_mm < 150.0 or height_mm < 150.0:
            continue

        image_path = Path(str(fragment.get("image_path") or "")).resolve()
        if not image_path.is_file():
            continue

        analysis = _analyze_blank_half_fragment(image_path)
        if not analysis or not analysis.get("blank_side"):
            continue

        eligible.append(
            {
                "file": str(fragment.get("file") or ""),
                "blank_side": str(analysis.get("blank_side") or ""),
                "left_ratio": float(analysis.get("left_ratio") or 0.0),
                "right_ratio": float(analysis.get("right_ratio") or 0.0),
            }
        )

    failures: list[str] = []
    for prev, curr in zip(eligible, eligible[1:]):
        if str(prev.get("blank_side") or "") == str(curr.get("blank_side") or ""):
            continue
        failures.append(
            "paired complementary blank-half anomaly: "
            f"{prev.get('file')} blank_{prev.get('blank_side')} "
            f"(L={float(prev.get('left_ratio') or 0.0):.3f}, R={float(prev.get('right_ratio') or 0.0):.3f}) vs "
            f"{curr.get('file')} blank_{curr.get('blank_side')} "
            f"(L={float(curr.get('left_ratio') or 0.0):.3f}, R={float(curr.get('right_ratio') or 0.0):.3f})"
        )
    return failures


def _repo_root() -> Path:
    return _REPO_ROOT


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _artifact_root() -> Path:
    return _repo_root() / "artifacts" / "table_conversion_audit"


def _resolve_path(path_value: str | None, *, root: Path) -> Path | None:
    text = str(path_value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _load_config_snapshot(config_path: str | None = None) -> dict:
    cfg = load_config(config_path)
    table_cfg = (cfg.get("table_capture") or {}) if isinstance(cfg, dict) else {}
    preview_cfg = (table_cfg.get("preview_fit") or {}) if isinstance(table_cfg, dict) else {}
    table_split_cfg = (cfg.get("table_splitting") or {}) if isinstance(cfg, dict) else {}
    try:
        max_height_mm = float(table_split_cfg.get("max_height_cm", 24.0) or 24.0) * 10.0
    except Exception:
        max_height_mm = 240.0

    preview_report_path = _resolve_path(preview_cfg.get("calibration_report"), root=_repo_root())
    preview_report = {}
    if preview_report_path and preview_report_path.is_file():
        try:
            preview_report = json.loads(preview_report_path.read_text(encoding="utf-8"))
        except Exception:
            preview_report = {}

    return {
        "config_path": str(config_path or ""),
        "max_height_mm": float(max_height_mm),
        "preview_fit_enabled": bool(preview_cfg.get("enabled")),
        "preview_fit_report_path": str(preview_report_path) if preview_report_path else "",
        "preview_fit_report": preview_report if isinstance(preview_report, dict) else {},
    }


def _discover_target_xml(
    *,
    output_root: Path,
    case_id: str | None = None,
    doc_code: str | None = None,
    xml_path: str | None = None,
) -> Path:
    explicit_xml = _resolve_path(xml_path, root=_repo_root())
    if explicit_xml:
        if not explicit_xml.is_file():
            raise FileNotFoundError(f"XML not found: {explicit_xml}")
        return explicit_xml

    base_root = output_root.resolve()
    if not base_root.exists():
        raise FileNotFoundError(f"output root not found: {base_root}")

    candidates: list[Path] = []
    if case_id and doc_code:
        relative = Path(str(case_id)) / str(doc_code) / f"{doc_code}.xml"
        candidates = [base_root / relative, *(base_root.glob(f".conversion-*/{relative.as_posix()}"))]
        candidates = [item for item in candidates if item.is_file()]
        if candidates:
            return max(candidates, key=lambda item: item.stat().st_mtime).resolve()
        candidate = base_root / relative
        raise FileNotFoundError(f"target XML not found: {candidate}")

    if case_id:
        case_root = base_root / str(case_id)
        case_roots = [case_root, *base_root.glob(f".conversion-*/{case_id}")]
        case_roots = [item for item in case_roots if item.is_dir()]
        if not case_roots:
            raise FileNotFoundError(f"case output dir not found: {case_root}")
        if doc_code:
            candidate = case_root / str(doc_code) / f"{doc_code}.xml"
            if candidate.is_file():
                return candidate.resolve()
        candidates = sorted((xml for item in case_roots for xml in item.rglob("*.xml")), key=lambda item: item.stat().st_mtime, reverse=True)
    else:
        candidates = sorted(base_root.rglob("*.xml"), key=lambda item: item.stat().st_mtime, reverse=True)

    if not candidates:
        raise FileNotFoundError(f"no XML files found under: {base_root}")
    return candidates[0].resolve()


def _safe_float(value, default: float | None = None) -> float | None:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int | None = None) -> int | None:
    try:
        return int(value)
    except Exception:
        return default


def _parse_float_series(raw_value: str | None) -> list[float]:
    values: list[float] = []
    for item in str(raw_value or "").split("|"):
        text = str(item or "").strip()
        if not text:
            continue
        parsed = _safe_float(text)
        if parsed is not None:
            values.append(float(parsed))
    return values


def _parse_int_series(raw_value: str | None) -> list[int]:
    values: list[int] = []
    for item in str(raw_value or "").split("|"):
        text = str(item or "").strip()
        if not text:
            continue
        parsed = _safe_int(text)
        if parsed is not None:
            values.append(int(parsed))
    return values


def _load_xml_fragments(xml_path: Path) -> dict:
    raw_text = xml_path.read_text(encoding="utf-8", errors="replace")
    parser = etree.XMLParser(resolve_entities=False, recover=True, remove_blank_text=False, huge_tree=True)
    root = etree.parse(str(xml_path), parser).getroot()

    images: list[dict] = []
    for order, img in enumerate(root.iter("img"), start=1):
        parent = img.getparent()
        images.append(
            {
                "order": int(order),
                "file": str(img.get("file") or "").strip(),
                "wi": _safe_float(img.get("wi"), 0.0) or 0.0,
                "he": _safe_float(img.get("he"), 0.0) or 0.0,
                "inline": str(img.get("inline") or "").strip().lower(),
                "parent_tag": str(getattr(parent, "tag", "") or ""),
                "parent_num": str(parent.get("num") or "").strip() if parent is not None and hasattr(parent, "get") else "",
            }
        )

    return {
        "xml_path": str(xml_path),
        "raw_text": raw_text,
        "images": images,
        "block_images": [item for item in images if item.get("inline") != "yes"],
    }


def _new_table_block(match: re.Match[str], line: str) -> dict:
    range_start = match.group("range_start") or match.group("range_start_alt") or ""
    range_end = match.group("range_end") or ""
    return {
        "idx": int(match.group("idx")),
        "section": str(match.group("section")),
        "range_start": str(range_start).strip(),
        "range_end": str(range_end).strip(),
        "success": None,
        "fragment_count_log": 0,
        "pdf_fragment_pages": None,
        "emit_summary_fragments": None,
        "emit_summary_files": [],
        "temp_files": [],
        "center_events": [],
        "preview_fit_events": [],
        "visual_slice_events": [],
        "used_split_fallback": False,
        "split_accepts": 0,
        "lines": [line],
        "warnings": [],
        "failures": [],
        "assignment_mode": "",
        "xml_fragments": [],
    }


def _parse_table_blocks(log_path: Path) -> dict:
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    blocks: list[dict] = []
    output_map: dict[str, str] = {}
    current: dict | None = None

    for line in lines:
        map_match = OUTPUT_MAP_RE.search(line)
        if map_match:
            output_map[str(map_match.group("temp")).strip()] = str(map_match.group("final")).strip()

        try_match = TRY_RE.search(line)
        if try_match:
            if current is not None:
                blocks.append(current)
            current = _new_table_block(try_match, line)
            continue

        if current is None:
            continue

        current["lines"].append(line)

        if "[TABLE_SPLIT]" in line or "[TABLE_SPLIT_ACCEPT]" in line or "[TABLE_SPLIT_BACKOFF_FAIL]" in line:
            current["used_split_fallback"] = True
        if "[TABLE_SPLIT_ACCEPT]" in line:
            current["split_accepts"] = int(current.get("split_accepts", 0)) + 1

        center_match = CENTER_RE.search(line)
        if center_match:
            event = {
                "file": str(center_match.group("file")).strip(),
                "before_h_mm": _safe_float(center_match.group("before_h"), 0.0) or 0.0,
                "after_h_mm": _safe_float(center_match.group("after_h"), 0.0) or 0.0,
                "before_w_mm": _safe_float(center_match.group("before_w"), 0.0) or 0.0,
                "after_w_mm": _safe_float(center_match.group("after_w"), 0.0) or 0.0,
                "line": line,
            }
            current["center_events"].append(event)
            current["temp_files"].append(event["file"])

        preview_fit_match = PREVIEW_FIT_RE.search(line)
        if preview_fit_match:
            current["preview_fit_events"].append(
                {
                    "file": str(preview_fit_match.group("file")).strip(),
                    "after_h_mm": _safe_float(preview_fit_match.group("after_h"), 0.0) or 0.0,
                    "line": line,
                }
            )

        pdf_emit_match = PDF_FRAGMENT_EMIT_RE.search(line)
        if pdf_emit_match:
            current["pdf_fragment_pages"] = _safe_int(pdf_emit_match.group("pages"), 0) or 0

        visual_slice_match = PDF_FRAGMENT_VISUAL_SLICE_RE.search(line)
        if visual_slice_match:
            cut_modes_raw = str(visual_slice_match.group("cut_modes") or "").strip()
            boundary_closed_raw = str(visual_slice_match.group("boundary_closed") or "").strip()
            current["visual_slice_events"].append(
                {
                    "page": _safe_int(visual_slice_match.group("page"), 0) or 0,
                    "file": str(visual_slice_match.group("file")).strip(),
                    "original_height_mm": _safe_float(visual_slice_match.group("original_height"), 0.0) or 0.0,
                    "max_height_mm": _safe_float(visual_slice_match.group("max_height"), 0.0) or 0.0,
                    "slices": _safe_int(visual_slice_match.group("slices"), 0) or 0,
                    "slice_heights_mm": _parse_float_series(visual_slice_match.group("heights")),
                    "cut_modes": [item for item in cut_modes_raw.split("|") if item],
                    "mode": str(visual_slice_match.group("mode") or ""),
                    "total_height_mm": _safe_float(visual_slice_match.group("total_height"), 0.0) or 0.0,
                    "cuts_px": _parse_int_series(visual_slice_match.group("cuts_px")),
                    "cut_scores": _parse_float_series(visual_slice_match.group("cut_scores")),
                    "boundary_closed": boundary_closed_raw == "True",
                    "line": line,
                }
            )

        emit_summary_match = EMIT_SUMMARY_RE.search(line)
        if emit_summary_match:
            current["emit_summary_fragments"] = _safe_int(emit_summary_match.group("fragments"), 0) or 0
            files_raw = str(emit_summary_match.group("files") or "").strip()
            if files_raw:
                current["emit_summary_files"] = [item for item in files_raw.split("|") if item]
                current["temp_files"] = list(current["emit_summary_files"])

        result_match = RESULT_RE.search(line)
        if result_match and int(result_match.group("idx")) == int(current.get("idx", -1)):
            current["success"] = str(result_match.group("success")).strip() == "True"
            range_start = result_match.group("range_start") or result_match.group("range_start_alt") or current.get("range_start") or ""
            range_end = result_match.group("range_end") or current.get("range_end") or ""
            current["range_start"] = str(range_start).strip()
            current["range_end"] = str(range_end).strip()
            blocks.append(current)
            current = None

    if current is not None:
        blocks.append(current)

    for block in blocks:
        fragment_count = 0
        if block.get("emit_summary_fragments") is not None:
            fragment_count = int(block.get("emit_summary_fragments") or 0)
        elif block.get("center_events"):
            fragment_count = len(block.get("center_events") or [])
        elif block.get("pdf_fragment_pages"):
            fragment_count = int(block.get("pdf_fragment_pages") or 0)
        elif block.get("visual_slice_events"):
            fragment_count = sum(int(event.get("slices") or 0) for event in list(block.get("visual_slice_events") or []))
        elif block.get("split_accepts") and block.get("success"):
            fragment_count = int(block.get("split_accepts") or 0) + 1
        elif block.get("success"):
            fragment_count = 1
        block["fragment_count_log"] = int(fragment_count)
    return {"blocks": blocks, "output_map": output_map, "lines": lines}


def _assign_xml_fragments_to_tables(blocks: list[dict], xml_block_images: list[dict], output_map: dict[str, str]) -> None:
    images_by_file = {str(item.get("file") or ""): item for item in list(xml_block_images or [])}
    assigned_files: set[str] = set()
    sequential_pool = [item for item in list(xml_block_images or []) if str(item.get("file") or "")]
    cursor = 0

    for block in blocks:
        if not block.get("success"):
            continue

        assigned: list[dict] = []
        temp_files = [str(item) for item in list(block.get("temp_files") or []) if str(item)]
        for temp_name in temp_files:
            final_name = output_map.get(temp_name)
            if not final_name:
                continue
            image_item = images_by_file.get(final_name)
            if image_item and final_name not in assigned_files:
                assigned.append(image_item)
                assigned_files.add(final_name)
        if assigned:
            block["xml_fragments"] = assigned
            block["assignment_mode"] = "output_map"
            continue

        needed = int(block.get("fragment_count_log") or 0)
        if needed <= 0:
            block["xml_fragments"] = []
            block["assignment_mode"] = "none"
            continue

        fallback_assigned: list[dict] = []
        while cursor < len(sequential_pool) and len(fallback_assigned) < needed:
            item = sequential_pool[cursor]
            cursor += 1
            file_name = str(item.get("file") or "")
            if not file_name or file_name in assigned_files:
                continue
            fallback_assigned.append(item)
            assigned_files.add(file_name)

        block["xml_fragments"] = fallback_assigned
        block["assignment_mode"] = "sequential_fallback"


def _build_table_id(block: dict) -> str:
    idx = int(block.get("idx") or 0)
    range_start = str(block.get("range_start") or "").strip() or "na"
    return f"table_{idx}_{range_start}"


def _infer_target_section(xml_path: Path) -> str:
    return str(DOC_CODE_TO_SECTION.get(str(xml_path.stem), "") or "")


def build_audit_report(
    *,
    log_path: Path,
    xml_path: Path,
    config_path: str | None = None,
) -> dict:
    cfg = _load_config_snapshot(config_path)
    log_info = _parse_table_blocks(log_path)
    xml_info = _load_xml_fragments(xml_path)
    blocks = list(log_info.get("blocks") or [])
    target_section = _infer_target_section(xml_path)
    if target_section:
        blocks = [block for block in blocks if str(block.get("section") or "") == target_section]
    output_map = dict(log_info.get("output_map") or {})
    _assign_xml_fragments_to_tables(blocks, xml_info.get("block_images") or [], output_map)

    failures: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []
    placeholder_hits = [marker for marker in PLACEHOLDER_MARKERS if marker and marker in str(xml_info.get("raw_text") or "")]
    if placeholder_hits:
        failures.append(f"xml contains table failure placeholder markers: {', '.join(dict.fromkeys(placeholder_hits))}")

    preview_report = cfg.get("preview_fit_report") or {}
    if (
        isinstance(preview_report, dict)
        and preview_report.get("safe_max_he_mm") is not None
        and preview_report.get("max_excess_mm") is not None
        and not bool(cfg.get("preview_fit_enabled"))
    ):
        infos.append(
            "preview-fit calibration report is available but runtime preview_fit remains disabled"
        )

    tables: list[dict] = []
    for order, block in enumerate(blocks, start=1):
        table_failures: list[str] = []
        table_warnings: list[str] = []

        if not block.get("success"):
            table_failures.append("table capture did not finish with success=True")

        fragment_count_log = int(block.get("fragment_count_log") or 0)
        xml_fragments = list(block.get("xml_fragments") or [])
        if fragment_count_log != len(xml_fragments):
            table_failures.append(
                f"fragment count mismatch: log={fragment_count_log} xml={len(xml_fragments)}"
            )

        for event in list(block.get("center_events") or []):
            before_h = float(event.get("before_h_mm") or 0.0)
            after_h = float(event.get("after_h_mm") or 0.0)
            if abs(before_h - after_h) > 0.01:
                table_failures.append(
                    f"centering changed height for {event.get('file')}: before={before_h:.2f} after={after_h:.2f}"
                )

        max_height_mm = float(cfg.get("max_height_mm") or 240.0)
        visual_slice_events = list(block.get("visual_slice_events") or [])
        for event in visual_slice_events:
            event_max_height = float(event.get("max_height_mm") or max_height_mm)
            slice_count = int(event.get("slices") or 0)
            slice_heights = list(event.get("slice_heights_mm") or [])
            if slice_count < 2:
                table_failures.append(
                    f"visual slice event reports fewer than 2 slices for {event.get('file')}: slices={slice_count}"
                )
            if len(slice_heights) != slice_count:
                table_failures.append(
                    f"visual slice event count mismatch for {event.get('file')}: slices={slice_count} heights={len(slice_heights)}"
                )
            cut_modes = [str(mode) for mode in list(event.get("cut_modes") or [])]
            unsafe_modes = [mode for mode in cut_modes if mode in {"low_density", "balanced", "unsafe"}]
            if unsafe_modes:
                table_failures.append(
                    f"visual slice event reports unsafe cut mode for {event.get('file')}: modes={'|'.join(unsafe_modes)}"
                )
            if str(event.get("mode") or "") == "group":
                cuts_px = list(event.get("cuts_px") or [])
                if len(cuts_px) != max(0, slice_count - 1):
                    table_failures.append(
                        f"group visual slice cut count mismatch for {event.get('file')}: slices={slice_count} cuts={len(cuts_px)}"
                    )
                if not bool(event.get("boundary_closed")):
                    table_failures.append(
                        f"group visual slice did not report closed boundaries for {event.get('file')}"
                    )
            for height in slice_heights:
                if float(height) > event_max_height + 1e-6:
                    table_failures.append(
                        f"visual slice height exceeds max_height_mm for {event.get('file')}: he={float(height):.2f} max={event_max_height:.2f}"
                    )

        for fragment_index, fragment in enumerate(xml_fragments, start=1):
            file_name = str(fragment.get("file") or "").strip()
            image_path = xml_path.parent / file_name
            if not image_path.is_file():
                table_failures.append(f"missing image file: {image_path}")
            height_mm = float(fragment.get("he") or 0.0)
            fragment["image_path"] = str(image_path.resolve())
            if height_mm > max_height_mm + 1e-6:
                table_failures.append(
                    f"fragment height exceeds max_height_mm: {file_name} he={height_mm:.2f} max={max_height_mm:.2f}"
                )
        table_failures.extend(_detect_complementary_blank_half_anomalies(xml_fragments))

        if block.get("used_split_fallback"):
            table_warnings.append("used split fallback")
        if visual_slice_events:
            table_warnings.append("used visual slice fallback")
        if block.get("used_split_fallback") and not block.get("pdf_fragment_pages"):
            table_warnings.append("full-table pdf-first did not directly emit fragments before split fallback")
        if block.get("assignment_mode") == "sequential_fallback":
            table_warnings.append("xml fragments assigned by sequential fallback instead of explicit output mapping")
        if len(xml_fragments) > 1:
            last_fragment = xml_fragments[-1]
            try:
                if float(last_fragment.get("he") or 0.0) < 20.0:
                    table_warnings.append(
                        f"very short tail fragment detected: {last_fragment.get('file')} he={float(last_fragment.get('he') or 0.0):.2f}"
                    )
            except Exception:
                pass

        table_record = {
            "order": int(order),
            "table_id": _build_table_id(block),
            "idx": int(block.get("idx") or 0),
            "section": str(block.get("section") or ""),
            "range_start": str(block.get("range_start") or ""),
            "range_end": str(block.get("range_end") or ""),
            "success": bool(block.get("success")),
            "fragment_count_log": int(fragment_count_log),
            "fragment_count_xml": int(len(xml_fragments)),
            "used_split_fallback": bool(block.get("used_split_fallback")),
            "visual_slice_event_count": int(len(visual_slice_events)),
            "visual_slice_events": visual_slice_events,
            "assignment_mode": str(block.get("assignment_mode") or ""),
            "fragments": [
                {
                    "fragment_index": int(fragment_index),
                    "file": str(fragment.get("file") or ""),
                    "image_path": str((xml_path.parent / str(fragment.get("file") or "")).resolve()),
                    "width_mm": float(fragment.get("wi") or 0.0),
                    "height_mm": float(fragment.get("he") or 0.0),
                    "exists": bool((xml_path.parent / str(fragment.get("file") or "")).is_file()),
                }
                for fragment_index, fragment in enumerate(xml_fragments, start=1)
            ],
            "warnings": table_warnings,
            "failures": table_failures,
            "evidence_lines": list(block.get("lines") or []),
        }
        tables.append(table_record)
        failures.extend(table_failures)
        warnings.extend(table_warnings)

    status = "FAIL" if failures else "PASS"
    replay_entries = []
    for table in tables:
        if table.get("failures"):
            continue
        for fragment in list(table.get("fragments") or []):
            replay_entries.append(
                {
                    "table_id": str(table.get("table_id") or ""),
                    "fragment_index": int(fragment.get("fragment_index") or 0),
                    "image_path": str(fragment.get("image_path") or ""),
                    "width_mm": float(fragment.get("width_mm") or 0.0),
                    "height_mm": float(fragment.get("height_mm") or 0.0),
                }
            )

    return {
        "status": status,
        "failures": failures,
        "warnings": warnings,
        "infos": infos,
        "target": {
            "log_path": str(log_path.resolve()),
            "xml_path": str(xml_path.resolve()),
            "output_doc_dir": str(xml_path.parent.resolve()),
            "target_section": str(target_section),
        },
        "config": cfg,
        "tables": tables,
        "replay_manifest": {
            "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "xml_path": str(xml_path.resolve()),
            "entries": replay_entries,
        },
    }


def _write_audit_outputs(report: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_json = output_dir / "table_conversion_audit_report.json"
    report_md = output_dir / "table_conversion_audit_report.md"
    evidence_log = output_dir / "table_conversion_audit_evidence.log"
    replay_manifest = output_dir / "replay_manifest.json"

    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    replay_manifest.write_text(
        json.dumps(report.get("replay_manifest") or {}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    evidence_lines: list[str] = []
    md_lines = [
        f"# Table Conversion Audit Report ({_timestamp()})",
        "",
        f"- status: **{report.get('status')}**",
        f"- xml: `{report.get('target', {}).get('xml_path', '')}`",
        f"- log: `{report.get('target', {}).get('log_path', '')}`",
        f"- max_height_mm: `{report.get('config', {}).get('max_height_mm')}`",
        "",
    ]

    if report.get("failures"):
        md_lines.append("## Failures")
        for item in list(report.get("failures") or []):
            md_lines.append(f"- {item}")
        md_lines.append("")

    if report.get("warnings"):
        md_lines.append("## Warnings")
        for item in list(report.get("warnings") or []):
            md_lines.append(f"- {item}")
        md_lines.append("")

    if report.get("infos"):
        md_lines.append("## Info")
        for item in list(report.get("infos") or []):
            md_lines.append(f"- {item}")
        md_lines.append("")

    md_lines.append("## Tables")
    for table in list(report.get("tables") or []):
        md_lines.append(
            f"- {table.get('table_id')}: success={table.get('success')} "
            f"log_fragments={table.get('fragment_count_log')} xml_fragments={table.get('fragment_count_xml')} "
            f"assignment={table.get('assignment_mode')}"
        )
        for warn in list(table.get("warnings") or []):
            md_lines.append(f"  - warn: {warn}")
        for fail in list(table.get("failures") or []):
            md_lines.append(f"  - fail: {fail}")
        for fragment in list(table.get("fragments") or []):
            md_lines.append(
                f"  - fragment#{fragment.get('fragment_index')}: {fragment.get('file')} "
                f"wi={fragment.get('width_mm'):.2f} he={fragment.get('height_mm'):.2f} exists={fragment.get('exists')}"
            )
        evidence_lines.append(f"## {table.get('table_id')}")
        evidence_lines.extend(list(table.get("evidence_lines") or []))
        evidence_lines.append("")
    report_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    evidence_log.write_text("\n".join(evidence_lines), encoding="utf-8")

    return {
        "report_json": str(report_json.resolve()),
        "report_md": str(report_md.resolve()),
        "evidence_log": str(evidence_log.resolve()),
        "replay_manifest": str(replay_manifest.resolve()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit table conversion outputs against conversion.log and XML artifacts.")
    parser.add_argument("--log", default="conversion.log", help="Path to conversion.log")
    parser.add_argument("--output-root", default="output", help="Path to output root")
    parser.add_argument("--case-id", default="", help="Optional case id under output root")
    parser.add_argument("--doc-code", default="", help="Optional document code under case id")
    parser.add_argument("--xml", default="", help="Explicit XML path to audit")
    parser.add_argument("--config", default="", help="Optional config.yaml path")
    parser.add_argument("--artifact-dir", default="", help="Optional explicit artifact output directory")
    args = parser.parse_args(argv)

    root = _repo_root()
    log_path = _resolve_path(args.log, root=root)
    output_root = _resolve_path(args.output_root, root=root)
    if log_path is None or not log_path.is_file():
        raise FileNotFoundError(f"log file not found: {log_path}")
    if output_root is None:
        raise FileNotFoundError("output root was not provided")

    xml_path = _discover_target_xml(
        output_root=output_root,
        case_id=str(args.case_id or "").strip() or None,
        doc_code=str(args.doc_code or "").strip() or None,
        xml_path=str(args.xml or "").strip() or None,
    )
    report = build_audit_report(
        log_path=log_path,
        xml_path=xml_path,
        config_path=str(args.config or "").strip() or None,
    )

    artifact_dir = _resolve_path(args.artifact_dir, root=root)
    if artifact_dir is None:
        artifact_dir = _artifact_root() / _timestamp()
    written = _write_audit_outputs(report, artifact_dir)
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "report_json": written["report_json"],
                "report_md": written["report_md"],
                "evidence_log": written["evidence_log"],
                "replay_manifest": written["replay_manifest"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
