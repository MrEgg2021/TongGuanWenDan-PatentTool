from __future__ import annotations

import re

from core.logging_utils import logger

from .preview_fit_ops import apply_preview_fit_if_enabled


DEFAULT_MAX_HEIGHT_MM = 240.0
CLAIMS_FORMULA_NUMBER_RE = re.compile(r"^[\(（]\s*\d+\s*[\)）]$")


def _get_max_height_mm(owner) -> float:
    try:
        return float(owner._get_table_splitting_max_height_cm()) * 10.0
    except Exception:
        return DEFAULT_MAX_HEIGHT_MM


def _safe_remove_temp_image(owner, filename: str | None) -> None:
    if not filename:
        return
    try:
        owner._remove_temp_image_if_exists(filename)
    except Exception:
        return


def _guard_height(owner, filename: str | None, height_mm: float, *, stage: str, section: str, remove_file: bool = False) -> bool:
    helper = getattr(owner, '_guard_table_fragment_height', None)
    if callable(helper):
        try:
            return bool(
                helper(
                    filename,
                    float(height_mm),
                    stage=str(stage),
                    section=str(section),
                    remove_file=bool(remove_file),
                )
            )
        except Exception:
            pass

    max_height_mm = _get_max_height_mm(owner)
    try:
        height_value = float(height_mm)
    except Exception:
        height_value = max_height_mm + 1.0
    if height_value <= max_height_mm + 1e-6:
        return True

    logger.warning(
        '[TABLE_HEIGHT_GUARD] stage=%s section=%s file=%s height_mm=%.2f max_height_mm=%.2f',
        str(stage),
        str(section),
        str(filename),
        height_value,
        max_height_mm,
    )
    if remove_file:
        _safe_remove_temp_image(owner, filename)
    return False


def _table_dimension_count(table_obj, attr_name: str) -> int:
    try:
        return int(getattr(getattr(table_obj, attr_name), "Count"))
    except Exception:
        return 0


def _cell_range(table_obj, row: int, col: int):
    try:
        cell = table_obj.Cell(int(row), int(col))
        return getattr(cell, "Range", None)
    except Exception:
        return None


def _normalized_cell_text(rng) -> str:
    try:
        raw = str(getattr(rng, "Text", "") or "")
    except Exception:
        return ""
    return re.sub(r"[\r\n\x07\t ]+", " ", raw).strip()


def _range_has_formula_object(owner, rng) -> bool:
    detector = getattr(owner, "_table_range_has_ole", None)
    if callable(detector):
        try:
            if bool(detector(rng)):
                return True
        except Exception:
            pass

    for attr_name in ("InlineShapes", "ShapeRange"):
        try:
            collection = getattr(rng, attr_name, None)
            if collection is not None and int(getattr(collection, "Count", 0) or 0) > 0:
                return True
        except Exception:
            continue
    return False


def _is_claims_formula_number_table(owner, table_obj) -> bool:
    if _table_dimension_count(table_obj, "Rows") != 1:
        return False
    if _table_dimension_count(table_obj, "Columns") != 2:
        return False

    right_text = _normalized_cell_text(_cell_range(table_obj, 1, 2))
    if not CLAIMS_FORMULA_NUMBER_RE.match(right_text):
        return False

    return _range_has_formula_object(owner, _cell_range(table_obj, 1, 1))


def _emit_fragments(self, fragments, parent_node, section, table_obj):
    if not fragments:
        return False

    first_fragment_need_num = False
    first_fragment_target_width_mm = None
    subsequent_target_width_mm = None
    claims_formula_table_target_width_mm = None

    if section == 'description':
        split_mode = 'word'
        try:
            split_mode = str(getattr(self, 'description_paragraph_split_mode', 'word') or 'word')
        except Exception:
            split_mode = 'word'

        mode = str(split_mode).lower()
        eq_cfg = {}
        try:
            cfg = getattr(self, 'config', {}) or {}
            eq_cfg = cfg.get('equation_centering', {}) or {}
        except Exception:
            eq_cfg = {}
        precise_cfg = (eq_cfg.get('precise') or {}) if isinstance(eq_cfg, dict) else {}

        try:
            line_width_mm = float(precise_cfg.get('line_width_mm', 165.0))
        except (TypeError, ValueError):
            line_width_mm = 165.0
        try:
            desc_reserved_mm = float(precise_cfg.get('desc_reserved_mm', 20.0))
        except (TypeError, ValueError):
            desc_reserved_mm = 20.0

        subsequent_target_width_mm = line_width_mm
        if mode not in ('period', 'word_period_end'):
            first_fragment_need_num = True
            first_fragment_target_width_mm = line_width_mm - desc_reserved_mm
        else:
            prev_ends_with_period = self._prev_paragraph_ends_with_period(parent_node)
            if prev_ends_with_period:
                first_fragment_need_num = True
                first_fragment_target_width_mm = line_width_mm - desc_reserved_mm
            else:
                first_fragment_need_num = False
                first_fragment_target_width_mm = line_width_mm
    elif section == 'claims' and _is_claims_formula_number_table(self, table_obj):
        try:
            claims_formula_table_target_width_mm = self._get_table_center_target_width_mm("claims")
        except Exception:
            claims_formula_table_target_width_mm = None

    planned_fragments = []
    for idx, (fn, w, h) in enumerate(fragments):
        is_first = idx == 0
        if is_first:
            need_num = first_fragment_need_num
            target_width = first_fragment_target_width_mm
        else:
            need_num = False
            target_width = subsequent_target_width_mm
        if claims_formula_table_target_width_mm is not None:
            target_width = claims_formula_table_target_width_mm

        guard_stage = 'emit_fragments.raw'
        if target_width is not None:
            try:
                before_w, before_h = float(w), float(h)
                w, h = self._apply_table_centering_if_enabled(
                    fn,
                    float(w),
                    float(h),
                    current_section_key=section,
                    target_width_mm=target_width,
                )
                guard_stage = 'emit_fragments.centered'
                if section == "claims":
                    logger.debug(
                        "[TABLE_CLAIMS_FORMULA_TABLE_CENTER] file=%s section=%s target_width_mm=%.2f before_w_mm=%.2f before_h_mm=%.2f after_w_mm=%.2f after_h_mm=%.2f",
                        str(fn),
                        str(section),
                        float(target_width),
                        float(before_w),
                        float(before_h),
                        float(w),
                        float(h),
                    )
            except Exception:
                pass

        try:
            w, h, preview_fit_applied = apply_preview_fit_if_enabled(
                self,
                float(w),
                float(h),
                section=str(section),
                filename=str(fn),
            )
            if preview_fit_applied:
                guard_stage = 'emit_fragments.preview_fit'
        except Exception:
            preview_fit_applied = False

        if not _guard_height(
            self,
            fn,
            h,
            stage=guard_stage,
            section=str(section),
            remove_file=True,
        ):
            set_failure = getattr(self, '_set_table_process_failure_context', None)
            if callable(set_failure):
                set_failure(
                    error_code='final_emit_rejected',
                    stage=guard_stage,
                    error_message=f'fragment height {float(h):.2f}mm exceeds max height',
                    file=str(fn),
                    height_mm=float(h),
                    section=str(section),
                )
            for pending_fn, _, _, _ in planned_fragments:
                _safe_remove_temp_image(self, pending_fn)
            for pending_fn, _, _ in fragments[idx + 1 :]:
                _safe_remove_temp_image(self, pending_fn)
            return False

        planned_fragments.append((fn, w, h, need_num))

    for fn, w, h, need_num in planned_fragments:
        if not self._emit_final_table_image(parent_node, section, fn, w, h, table_obj, need_num):
            return False
    return True
