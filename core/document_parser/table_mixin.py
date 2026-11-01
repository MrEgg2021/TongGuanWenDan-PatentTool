from __future__ import annotations

import os

from core.logging_utils import logger

from .table_ops.emit_fragment_ops import _emit_fragments
from .table_ops.process_ops import process_table
from .table_ops.render_pdf_ops import _capture_table_pdf_first_result
from .table_ops.process_steps.types import TableCaptureResult


class TableProcessingMixin:
    def _clear_table_emit_summary_context(self) -> None:
        try:
            self._table_emit_summary_context = []
        except Exception:
            pass

    def _append_table_emit_summary_context(
        self,
        *,
        filename: str,
        width_mm: float,
        height_mm: float,
        section: str,
    ) -> None:
        payload = {
            "file": str(filename or "").strip(),
            "width_mm": float(width_mm),
            "height_mm": float(height_mm),
            "section": str(section or "").strip(),
        }
        try:
            items = getattr(self, "_table_emit_summary_context", None)
        except Exception:
            items = None
        if not isinstance(items, list):
            items = []
            try:
                self._table_emit_summary_context = items
            except Exception:
                pass
        items.append(payload)

    def _consume_table_emit_summary_context(self) -> list[dict]:
        try:
            items = getattr(self, "_table_emit_summary_context", None)
        except Exception:
            items = None
        output = [dict(item) for item in items] if isinstance(items, list) else []
        self._clear_table_emit_summary_context()
        return output

    def _get_table_splitting_max_height_cm(self) -> float:
        cfg = getattr(self, "config", {}) or {}
        try:
            ts = cfg.get("table_splitting", {}) or {}
        except Exception:
            ts = {}
        try:
            v = float((ts or {}).get("max_height_cm", 24.0))
        except (TypeError, ValueError):
            v = 24.0
        if not v or v <= 0:
            v = 24.0
        return float(v)

    def _get_table_splitting_max_height_mm(self) -> float:
        return float(self._get_table_splitting_max_height_cm()) * 10.0

    def _guard_table_fragment_height(
        self,
        filename: str | None,
        height_mm: float,
        *,
        stage: str,
        section: str,
        remove_file: bool = False,
    ) -> bool:
        try:
            height_value = float(height_mm)
        except Exception:
            height_value = self._get_table_splitting_max_height_mm() + 1.0

        max_height_mm = self._get_table_splitting_max_height_mm()
        if height_value <= max_height_mm + 1e-6:
            return True

        logger.warning(
            "[TABLE_HEIGHT_GUARD] stage=%s section=%s file=%s height_mm=%.2f max_height_mm=%.2f",
            str(stage),
            str(section),
            str(filename),
            height_value,
            max_height_mm,
        )
        if remove_file:
            self._remove_temp_image_if_exists(filename)
        return False

    def _clear_table_process_failure_context(self) -> None:
        try:
            self._table_process_failure_context = None
        except Exception:
            pass

    def _set_table_process_failure_context(
        self,
        *,
        error_code: str,
        stage: str,
        error_message: str | None = None,
        error_type: str | None = None,
        **extra,
    ) -> None:
        payload = {
            "error_code": str(error_code or "").strip(),
            "stage": str(stage or "").strip(),
            "error_message": str(error_message or "").strip(),
            "error_type": str(error_type or "").strip(),
        }
        for key, value in (extra or {}).items():
            if value is None:
                continue
            payload[str(key)] = value
        try:
            self._table_process_failure_context = payload
        except Exception:
            pass

    def _peek_table_process_failure_context(self) -> dict | None:
        try:
            payload = getattr(self, "_table_process_failure_context", None)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            return dict(payload)
        return None

    def _consume_table_process_failure_context(self) -> dict | None:
        payload = self._peek_table_process_failure_context()
        self._clear_table_process_failure_context()
        return payload

    def _table_range_has_ole(self, rng) -> bool:
        """Best-effort: detect OLE/embedded objects within a table range."""
        if rng is None:
            return False
        try:
            inline_shapes = getattr(rng, "InlineShapes", None)
            if inline_shapes is not None:
                try:
                    count = int(inline_shapes.Count)
                except Exception:
                    count = 0
                for i in range(1, count + 1):
                    try:
                        shape = inline_shapes(i)
                    except Exception:
                        continue
                    try:
                        type_code = getattr(shape, "Type", None)
                        if int(type_code) == 1:
                            return True
                    except Exception:
                        pass
                    try:
                        ole = getattr(shape, "OLEFormat", None)
                        if ole is not None:
                            class_type = getattr(ole, "ClassType", "") or ""
                            if class_type:
                                return True
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            xml_content = getattr(rng, "WordOpenXML", None)
            if xml_content:
                xml_text = str(xml_content)
                if ("<o:OLEObject" in xml_text) or ("<w:object" in xml_text):
                    return True
        except Exception:
            pass
        return False

    def _table_range_has_drawings(self, rng) -> bool:
        """Detect drawings/inline shapes inside table range (non-OLE)."""
        if rng is None:
            return False
        try:
            inline_shapes = getattr(rng, "InlineShapes", None)
            if inline_shapes is not None:
                try:
                    count = int(inline_shapes.Count)
                except Exception:
                    count = 0
                if count > 0:
                    return True
        except Exception:
            pass
        try:
            shape_range = getattr(rng, "ShapeRange", None)
            if shape_range is not None:
                try:
                    count = int(shape_range.Count)
                except Exception:
                    count = 0
                if count > 0:
                    return True
        except Exception:
            pass
        try:
            xml_content = getattr(rng, "WordOpenXML", None)
            if xml_content:
                xml_text = str(xml_content)
                if ("<w:drawing" in xml_text) or ("<wp:inline" in xml_text) or ("<wp:anchor" in xml_text):
                    return True
        except Exception:
            pass
        return False

    def _table_range_has_explicit_crop(self, rng) -> bool:
        """Detect explicit crop (srcRect / PictureFormat) inside table range to avoid over-trimming."""
        if rng is None:
            return False
        try:
            xml_content = getattr(rng, "WordOpenXML", None)
            if xml_content:
                xml_text = str(xml_content)
                if ("<a:srcRect" in xml_text) or ("srcRect" in xml_text):
                    return True
        except Exception:
            pass

        def _shape_has_picture_crop(shape) -> bool:
            if shape is None:
                return False
            try:
                fn = getattr(self, "_extract_image_crop_from_picture_format", None)
                if callable(fn):
                    crop_info = fn(shape)
                    if crop_info:
                        return True
            except Exception:
                pass
            try:
                pic = getattr(shape, "PictureFormat", None)
            except Exception:
                pic = None
            if pic is None:
                return False
            try:
                crop_left = float(getattr(pic, "CropLeft", 0.0) or 0.0)
                crop_top = float(getattr(pic, "CropTop", 0.0) or 0.0)
                crop_right = float(getattr(pic, "CropRight", 0.0) or 0.0)
                crop_bottom = float(getattr(pic, "CropBottom", 0.0) or 0.0)
            except Exception:
                return False
            return any(abs(v) > 0.01 for v in (crop_left, crop_top, crop_right, crop_bottom))

        try:
            inline_shapes = getattr(rng, "InlineShapes", None)
            if inline_shapes is not None:
                try:
                    count = int(inline_shapes.Count)
                except Exception:
                    count = 0
                for i in range(1, count + 1):
                    try:
                        shape = inline_shapes(i)
                    except Exception:
                        continue
                    if _shape_has_picture_crop(shape):
                        return True
        except Exception:
            pass

        try:
            shape_range = getattr(rng, "ShapeRange", None)
            if shape_range is not None:
                try:
                    count = int(shape_range.Count)
                except Exception:
                    count = 0
                for i in range(1, count + 1):
                    try:
                        shape = shape_range(i)
                    except Exception:
                        continue
                    if _shape_has_picture_crop(shape):
                        return True
        except Exception:
            pass
        return False

    def _collect_table_external_object_fallbacks(self, rng, *, section_key: str) -> list[dict]:
        if rng is None:
            return []

        hits: list[dict] = []
        seen: set[tuple[int | None, str, str]] = set()

        def _append_hit(shape_obj) -> None:
            if shape_obj is None:
                return
            try:
                classification = self._classify_external_object(shape_obj, section_key=section_key)
            except Exception:
                classification = None
            if not isinstance(classification, dict):
                return
            classifier = str(classification.get("classifier") or "").strip()
            if classifier not in ("preview_embedded", "activation_risky", "unsupported"):
                return
            try:
                range_start = self._safe_get_shape_range_start(shape_obj)
            except Exception:
                range_start = None
            key = (
                range_start,
                str(classification.get("classifier") or "").strip(),
                str(classification.get("object_kind") or "").strip(),
            )
            if key in seen:
                return
            seen.add(key)
            hits.append(
                {
                    "shape_obj": shape_obj,
                    "classification": classification,
                    "range_start": range_start,
                }
            )

        try:
            inline_shapes = getattr(rng, "InlineShapes", None)
            if inline_shapes is not None:
                try:
                    count = int(inline_shapes.Count)
                except Exception:
                    count = 0
                for idx in range(1, count + 1):
                    try:
                        _append_hit(inline_shapes(idx))
                    except Exception:
                        continue
        except Exception:
            pass

        try:
            shape_range = getattr(rng, "ShapeRange", None)
            if shape_range is not None:
                try:
                    count = int(shape_range.Count)
                except Exception:
                    count = 0
                for idx in range(1, count + 1):
                    try:
                        _append_hit(shape_range(idx))
                    except Exception:
                        continue
        except Exception:
            pass
        return hits


    def _get_table_center_target_width_mm(self, current_section_key: str) -> float | None:
        table_center_cfg = {}
        try:
            cfg = getattr(self, "config", {}) or {}
            table_center_cfg = cfg.get("table_image_centering", {}) or {}
        except Exception:
            table_center_cfg = {}

        if not bool(table_center_cfg.get("enabled")):
            return None

        eq_cfg = {}
        try:
            cfg = getattr(self, "config", {}) or {}
            eq_cfg = cfg.get("equation_centering", {}) or {}
        except Exception:
            eq_cfg = {}

        precise_cfg = (eq_cfg.get("precise") or {}) if isinstance(eq_cfg, dict) else {}
        try:
            line_width_mm = float(precise_cfg.get("line_width_mm", 165.0))
        except (TypeError, ValueError):
            line_width_mm = 165.0
        try:
            claim_visual_offset_mm = float(precise_cfg.get("claim_visual_offset_mm", 0.0))
        except (TypeError, ValueError):
            claim_visual_offset_mm = 0.0

        claim_line_target_width_mm = line_width_mm + claim_visual_offset_mm

        if current_section_key == "claims":
            return float(claim_line_target_width_mm)
        if current_section_key == "abstract":
            return float(line_width_mm)
        if current_section_key == "description":
            return float(line_width_mm)
        return None

    def _prev_paragraph_ends_with_period(self, parent_node) -> bool:
        """Return True when the previous paragraph should be treated as sentence-terminated."""
        if parent_node is None:
            return True  # No parent paragraph is available; use a permissive default.

        try:
            all_ps = list(parent_node.iter("p"))
            if not all_ps:
                return True  # No paragraph nodes found; do not block table placement.

            last_p = all_ps[-1]
            pieces = []
            try:
                if last_p.text:
                    pieces.append(str(last_p.text))
            except Exception:
                pass
            for child in list(last_p):
                try:
                    if child.tail:
                        pieces.append(str(child.tail))
                except Exception:
                    continue

            joined = "".join(pieces)
            if not joined:
                return True  # The paragraph is effectively empty.

            try:
                stripped = joined.rstrip()
            except Exception:
                stripped = joined

            if not stripped:
                return True

            last_char = stripped[-1]
            return last_char in (".", "。")
        except Exception:
            return True  # Fall back conservatively if the XML paragraph cannot be inspected.

    def _get_table_width_point(self, table) -> float | None:
        if table is None:
            return None
        width_point = None
        total = 0.0
        cols = None
        cols_count = 0
        try:
            cols = table.Columns
            cols_count = int(cols.Count)
        except Exception:
            cols = None
            cols_count = 0

        if cols is not None and cols_count > 0:
            for idx in range(1, cols_count + 1):
                try:
                    col = cols(idx)
                except Exception:
                    col = None
                if col is None:
                    continue
                try:
                    w = float(getattr(col, "Width", 0) or 0)
                except Exception:
                    w = 0.0
                if w > 0:
                    total += w
            if total > 0:
                width_point = float(total)

        if width_point is None:
            try:
                pref = float(getattr(table, "PreferredWidth", 0) or 0)
            except Exception:
                pref = 0.0
            if pref > 0:
                pref_type = None
                try:
                    pref_type = getattr(table, "PreferredWidthType", None)
                except Exception:
                    pref_type = None

                if pref_type is None:
                    width_point = float(pref)
                else:
                    # Word COM constant wdPreferredWidthPoints is 3.
                    try:
                        if int(pref_type) == 3:
                            width_point = float(pref)
                    except Exception:
                        pass

        return width_point

    def _apply_table_centering_if_enabled(
        self,
        filename: str,
        width_mm: float,
        height_mm: float,
        *,
        current_section_key: str,
        target_width_mm: float | None = None,
    ) -> tuple[float, float]:
        target_w = float(target_width_mm) if target_width_mm is not None else self._get_table_center_target_width_mm(current_section_key)
        if target_w is None:
            return width_mm, height_mm

        temp_dir = None
        try:
            temp_dir = os.path.abspath(self.config["paths"]["temp_dir"])
        except Exception:
            temp_dir = None
        if not temp_dir:
            return width_mm, height_mm

        try:
            image_path = os.path.join(temp_dir, filename)
            new_w, new_h = self.img_proc.pad_table_for_centering_keep_height(
                image_path,
                width_mm,
                height_mm,
                target_width_mm=float(target_w),
            )
            if logger.isEnabledFor(10):
                logger.debug(
                    "[TABLE_CENTER] file=%s section=%s target_width_mm=%.2f before_w_mm=%.2f before_h_mm=%.2f after_w_mm=%.2f after_h_mm=%.2f",
                    str(filename),
                    str(current_section_key),
                    float(target_w),
                    float(width_mm),
                    float(height_mm),
                    float(new_w),
                    float(new_h),
                )
            return float(new_w), float(new_h)
        except Exception:
            return width_mm, height_mm

    def _remove_temp_image_if_exists(self, filename: str | None) -> None:
        if not filename:
            return
        temp_dir = None
        try:
            temp_dir = os.path.abspath(self.config["paths"]["temp_dir"])
        except Exception:
            temp_dir = None
        if not temp_dir:
            return
        try:
            path = os.path.join(temp_dir, filename)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            return



    def _capture_table_in_canvas_payload(
        self,
        table,
        *,
        parent_node,
        current_section_key: str,
        width_point: float | None,
    ) -> dict:
        """Capture table fragments from the split canvas while preserving pdf-first multi-page output."""
        try:
            clear_failure = getattr(self, "_clear_table_process_failure_context", None)
            if callable(clear_failure):
                clear_failure()
        except Exception:
            pass

        capture = getattr(self, "_capture_table_pdf_first_result", None)
        if callable(capture):
            try:
                result = capture(
                    table.Range,
                    current_section_key=str(current_section_key),
                    width_point=width_point,
                )
            except Exception as exc:
                self._set_table_process_failure_context(
                    error_code="render_export_failed",
                    stage="probe.capture_fragment",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                return {"ok": False, "fragments": []}

            if isinstance(result, TableCaptureResult):
                fragments = [
                    (str(fragment.file), float(fragment.width_mm), float(fragment.height_mm))
                    for fragment in list(result.fragments or [])
                ]
                if fragments and not str(result.failure_code or "").strip():
                    return {
                        "ok": True,
                        "fragments": fragments,
                        "fragment_count": len(fragments),
                        "hard_table": bool(result.hard_table),
                        "used_blank_doc_fallback": bool(result.used_blank_doc_fallback),
                        "diagnostic_code": str(result.diagnostic_code or "") or None,
                    }

                failure_code = str(result.failure_code or "render_export_failed")
                diagnostic_code = str(result.diagnostic_code or "") or None
                error_message = "pdf-first probe capture did not yield legal fragments"
                if fragments:
                    error_message = (
                        f"pdf-first probe capture yielded {len(fragments)} fragment(s) "
                        f"but returned failure_code={failure_code}"
                    )
                self._set_table_process_failure_context(
                    error_code=failure_code,
                    stage="probe.capture_fragment",
                    error_message=error_message,
                    diagnostic_code=diagnostic_code,
                    hard_table=bool(result.hard_table),
                    used_blank_doc_fallback=bool(result.used_blank_doc_fallback),
                    fragment_count=len(fragments),
                )
                return {"ok": False, "fragments": []}

        return {"ok": False, "fragments": []}

    def _capture_table_in_canvas(
        self,
        table,
        *,
        parent_node,
        current_section_key: str,
        width_point: float | None,
    ):
        """Capture the current table fragment from the split canvas."""
        payload = dict(
            self._capture_table_in_canvas_payload(
                table,
                parent_node=parent_node,
                current_section_key=current_section_key,
                width_point=width_point,
            )
            or {}
        )
        if not payload.get("ok"):
            return None, 0.0, 0.0

        fragments = list(payload.get("fragments") or [])
        if len(fragments) == 1:
            fn, w, h = fragments[0]
            return str(fn), float(w), float(h)

        for fn, _, _ in fragments:
            self._remove_temp_image_if_exists(fn)

        logger.warning(
            "[TABLE_PROBE_DIAGNOSTIC] classification=%s section=%s fragment_count=%s",
            "probe_contract_rejected_multi_fragment",
            str(current_section_key),
            len(fragments),
        )
        self._set_table_process_failure_context(
            error_code="probe_contract_rejected_multi_fragment",
            stage="probe.capture_fragment",
            error_message=f"pdf-first probe capture yielded {len(fragments)} fragments instead of one",
            classification="probe_contract_rejected_multi_fragment",
            diagnostic_code=payload.get("diagnostic_code"),
            hard_table=bool(payload.get("hard_table")),
            used_blank_doc_fallback=bool(payload.get("used_blank_doc_fallback")),
            fragment_count=len(fragments),
        )
        return None, 0.0, 0.0

    def _emit_final_table_image(self, parent_node, section, fn, w, h, table_obj, need_num):
        """Emit the final table image only when the fragment height is within limit."""
        if not self._guard_table_fragment_height(
            fn,
            h,
            stage="emit_final",
            section=str(section),
            remove_file=True,
        ):
            self._set_table_process_failure_context(
                error_code="final_emit_rejected",
                stage="emit_final",
                error_message=f"table fragment height {float(h):.2f}mm exceeds max height",
            )
            return False

        if section == "claims":
            seg = {
                "kind": "img",
                "filename": str(fn),
                "width_mm": float(w),
                "height_mm": float(h),
                "is_equation": False,
                "is_big": True,
            }
            try:
                self._append_claim_segments(parent_node, [seg], is_new_start=False, claim_num=None)
            except Exception:
                content_node = self.xml.create_paragraph(parent_node, text=None, is_claim=True)
                self.xml.create_image_node(content_node, fn, w, h, img_type="desc", inline=False)
        else:
            p_num = "XXXX" if (section == "description" and not need_num) else None
            p_node = self.xml.create_paragraph(parent_node, text=None, num=p_num, is_claim=False)
            self.xml.create_image_node(p_node, fn, w, h, img_type="desc", inline=False)
        try:
            self._append_table_emit_summary_context(
                filename=str(fn),
                width_mm=float(w),
                height_mm=float(h),
                section=str(section),
            )
        except Exception:
            pass
        return True

# Attach extracted heavy methods for compatibility.
TableProcessingMixin._capture_table_pdf_first_result = _capture_table_pdf_first_result
TableProcessingMixin.process_table = process_table
TableProcessingMixin._emit_fragments = _emit_fragments

__all__ = ["TableProcessingMixin"]
