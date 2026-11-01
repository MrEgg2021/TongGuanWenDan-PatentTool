from __future__ import annotations

import time
from typing import Iterable

from core.logging_utils import logger
from core.word_engine_impl.com_compat import add_hidden_document
from ...table_topology import CanvasSplitter, TableTopologyScanner


DEFAULT_MAX_HEIGHT_MM = 240.0
DEFAULT_PAGE_HEIGHT_PT = 29.7 * 72.0 / 2.54
CUT_BORDER_POLICY_CLOSED = "closed"


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
    helper = getattr(owner, "_guard_table_fragment_height", None)
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
        "[TABLE_HEIGHT_GUARD] stage=%s section=%s file=%s height_mm=%.2f max_height_mm=%.2f",
        str(stage),
        str(section),
        str(filename),
        height_value,
        max_height_mm,
    )
    if remove_file:
        _safe_remove_temp_image(owner, filename)
    return False


def _normalize_capture_fragments(payload: dict | None) -> list[tuple[str, float, float]]:
    normalized: list[tuple[str, float, float]] = []
    for item in list((payload or {}).get("fragments") or []):
        try:
            filename, width_mm, height_mm = item
        except Exception:
            continue
        filename_text = str(filename or "").strip()
        if not filename_text:
            continue
        normalized.append((filename_text, float(width_mm), float(height_mm)))
    return normalized


def _capture_table_fragments_in_canvas(owner, table, *, parent_node, current_section_key: str, width_point: float | None) -> dict:
    capture_payload = getattr(owner, "_capture_table_in_canvas_payload", None)
    if callable(capture_payload):
        payload = dict(
            capture_payload(
                table,
                parent_node=parent_node,
                current_section_key=str(current_section_key),
                width_point=width_point,
            )
            or {}
        )
        fragments = _normalize_capture_fragments(payload)
        payload["fragments"] = fragments
        payload["fragment_count"] = len(fragments)
        payload["max_fragment_height_mm"] = max((float(item[2]) for item in fragments), default=0.0)
        if len(fragments) == 1:
            payload["file"], payload["width_mm"], payload["height_mm"] = fragments[0]
        return payload

    fn, w, h = owner._capture_table_in_canvas(
        table,
        parent_node=parent_node,
        current_section_key=current_section_key,
        width_point=width_point,
    )
    if not fn:
        return {"ok": False, "fragments": [], "fragment_count": 0, "max_fragment_height_mm": 0.0}
    return {
        "ok": True,
        "fragments": [(str(fn), float(w), float(h))],
        "fragment_count": 1,
        "max_fragment_height_mm": float(h),
        "file": str(fn),
        "width_mm": float(w),
        "height_mm": float(h),
    }


def _collect_row_heights(table) -> list[float]:
    heights: list[float] = []
    rows_cnt = 0
    try:
        rows_cnt = int(table.Rows.Count)
    except Exception:
        return heights

    for idx in range(1, rows_cnt + 1):
        height_value = 20.0
        try:
            raw_height = float(table.Rows(idx).Height)
            if raw_height <= 0 or raw_height > 999999:
                raw_height = 20.0
            height_value = float(raw_height)
        except Exception:
            height_value = 20.0
        heights.append(height_value)
    return heights


def _build_row_top_map(table) -> dict[int, float]:
    row_top_map: dict[int, float] = {}
    rows_cnt = 0
    try:
        rows_cnt = int(table.Rows.Count)
    except Exception:
        return row_top_map

    try:
        doc = table.Range.Document
        page_height_pt = float(doc.PageSetup.PageHeight)
        if page_height_pt <= 0:
            page_height_pt = DEFAULT_PAGE_HEIGHT_PT
    except Exception:
        page_height_pt = DEFAULT_PAGE_HEIGHT_PT

    try:
        cells = table.Range.Cells
        cell_count = int(cells.Count)
    except Exception:
        cells = None
        cell_count = 0

    for cell_idx in range(1, cell_count + 1):
        try:
            cell = cells(cell_idx)
        except Exception:
            continue
        try:
            row_idx = int(getattr(cell, "RowIndex", 0) or 0)
        except Exception:
            row_idx = 0
        if row_idx <= 0:
            continue
        try:
            vertical_merge = int(getattr(cell, "VerticalMerge", 0) or 0)
        except Exception:
            vertical_merge = 0
        if vertical_merge == 1:
            continue
        try:
            top_in_page = float(cell.Range.Information(6))
            page_no = int(cell.Range.Information(3) or 1)
            if page_no <= 0:
                page_no = 1
        except Exception:
            continue
        top_global = (float(page_no - 1) * page_height_pt) + top_in_page
        if row_idx not in row_top_map or top_global < row_top_map[row_idx]:
            row_top_map[row_idx] = top_global

    if row_top_map:
        return row_top_map

    for row_idx in range(1, rows_cnt + 1):
        try:
            row_obj = table.Rows(row_idx)
            top_in_page = float(row_obj.Range.Information(6))
            page_no = int(row_obj.Range.Information(3) or 1)
            if page_no <= 0:
                page_no = 1
            row_top_map[row_idx] = (float(page_no - 1) * page_height_pt) + top_in_page
        except Exception:
            continue
    return row_top_map


def _choose_cut_row(row_top_map: dict[int, float], row_heights: Iterable[float], target_slice_pt: float) -> tuple[int, str]:
    ordered_row_tops = [(int(row_idx), float(top_pt)) for row_idx, top_pt in sorted((row_top_map or {}).items())]
    if ordered_row_tops:
        _base_row, base_top = ordered_row_tops[0]
        for row_idx, top_pt in ordered_row_tops[1:]:
            if (float(top_pt) - float(base_top)) > float(target_slice_pt):
                return int(row_idx), "coords"

    accum_h = 0.0
    for row_idx, row_height in enumerate(list(row_heights), start=1):
        try:
            accum_h += float(row_height)
        except Exception:
            accum_h += 20.0
        if accum_h > float(target_slice_pt):
            return int(row_idx), "row_height"
    return -1, "none"


def _refresh_first_canvas_table(canvas):
    try:
        if canvas is not None and int(canvas.Tables.Count) >= 1:
            return canvas.Tables(1)
    except Exception:
        return None
    return None


def _cleanup_fragment_files(owner, fragments) -> None:
    for item in list(fragments or []):
        try:
            filename = item[0]
        except Exception:
            filename = None
        _safe_remove_temp_image(owner, filename)


def _disable_heading_rows(table) -> None:
    try:
        heading_rows_to_check = min(5, int(table.Rows.Count))
    except Exception:
        heading_rows_to_check = 0
    for hdr_idx in range(1, heading_rows_to_check + 1):
        try:
            row_obj = table.Rows(hdr_idx)
            if getattr(row_obj, "HeadingFormat", False):
                row_obj.HeadingFormat = False
        except Exception:
            continue


def _copy_range_to_target(source_range, target_range) -> str | None:
    try:
        source_range.Copy()
        target_range.Paste()
        return "copy_paste"
    except Exception:
        pass
    try:
        target_range.FormattedText = source_range
        return "formatted_text"
    except Exception:
        return None


def _copy_table_to_canvas_with_method(source_table, canvas):
    try:
        canvas.Content.Delete()
    except Exception:
        pass
    try:
        target_range = canvas.Range(0, 0)
    except Exception:
        return None, None
    copy_method = _copy_range_to_target(source_table.Range, target_range)
    if not copy_method:
        return None, None
    return _refresh_first_canvas_table(canvas), str(copy_method)


def _copy_table_to_canvas(source_table, canvas):
    table, _copy_method = _copy_table_to_canvas_with_method(source_table, canvas)
    return table


def _close_doc_quietly(doc) -> None:
    if doc is None:
        return
    try:
        doc.Close(SaveChanges=0)
    except Exception:
        pass


def _iter_doc_tables(doc):
    try:
        table_count = int(doc.Tables.Count)
    except Exception:
        table_count = 0
    for idx in range(1, table_count + 1):
        try:
            yield idx, doc.Tables(idx)
        except Exception:
            continue


def _resolve_appended_probe_table(doc, *, tables_before: int, insertion_start: int):
    candidates = []
    for idx, table in _iter_doc_tables(doc):
        try:
            table_start = int(table.Range.Start)
        except Exception:
            table_start = -1
        if idx > int(tables_before) or table_start >= int(insertion_start):
            candidates.append((table_start, idx, table))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (int(item[0]), int(item[1])))
    return candidates[-1][2]


def _cleanup_same_canvas_probe(doc, insertion_start: int) -> None:
    try:
        content_end = int(doc.Content.End) - 1
    except Exception:
        content_end = int(insertion_start)
    if content_end < int(insertion_start):
        return
    try:
        doc.Range(int(insertion_start), int(content_end)).Delete()
    except Exception:
        pass


def _create_scratch_probe_context(app, source_table):
    scratch = None
    try:
        scratch = add_hidden_document(app, logger=logger)
    except Exception as exc:
        return {
            "ok": False,
            "error_code": "render_export_failed",
            "stage": "probe.create_canvas",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "probe_source": "scratch",
            "copy_success": False,
        }

    scratch_table, copy_method = _copy_table_to_canvas_with_method(source_table, scratch)
    if scratch_table is None:
        _close_doc_quietly(scratch)
        return {
            "ok": False,
            "error_code": "split_stalled",
            "stage": "probe.copy_table",
            "error_message": "failed to copy current table into probe canvas",
            "probe_source": "scratch",
            "copy_success": False,
        }

    return {
        "ok": True,
        "canvas": scratch,
        "table": scratch_table,
        "cleanup": lambda: _close_doc_quietly(scratch),
        "probe_source": "scratch",
        "copy_method": str(copy_method or ""),
        "copy_success": True,
    }


def _create_same_canvas_probe_context(source_table):
    try:
        doc = source_table.Range.Document
        insertion_start = max(0, int(doc.Content.End) - 1)
        tables_before = int(doc.Tables.Count)
        target_range = doc.Range(int(insertion_start), int(insertion_start))
    except Exception as exc:
        return {
            "ok": False,
            "error_code": "render_export_failed",
            "stage": "probe.create_canvas",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "probe_source": "same_canvas",
            "copy_success": False,
        }

    copy_method = _copy_range_to_target(source_table.Range, target_range)
    if not copy_method:
        _cleanup_same_canvas_probe(doc, int(insertion_start))
        return {
            "ok": False,
            "error_code": "split_stalled",
            "stage": "probe.copy_table",
            "error_message": "failed to clone current table on shared canvas",
            "probe_source": "same_canvas",
            "copy_success": False,
        }

    probe_table = _resolve_appended_probe_table(doc, tables_before=int(tables_before), insertion_start=int(insertion_start))
    if probe_table is None:
        _cleanup_same_canvas_probe(doc, int(insertion_start))
        return {
            "ok": False,
            "error_code": "split_stalled",
            "stage": "probe.copy_table",
            "error_message": "shared canvas probe clone did not materialize a table",
            "probe_source": "same_canvas",
            "copy_method": str(copy_method),
            "copy_success": False,
        }

    return {
        "ok": True,
        "canvas": doc,
        "table": probe_table,
        "cleanup": lambda: _cleanup_same_canvas_probe(doc, int(insertion_start)),
        "probe_source": "same_canvas",
        "copy_method": str(copy_method),
        "copy_success": True,
        "split_anchor_start": int(insertion_start),
    }


def _materialize_probe_context(owner, source_table, *, prefer_same_canvas: bool, current_section_key: str | None = None, safe_row: int | None = None):
    word_engine = getattr(owner, "word", None)
    app = getattr(word_engine, "app", None)
    if app is None:
        return {
            "ok": False,
            "error_code": "render_export_failed",
            "stage": "probe.missing_word_app",
            "error_message": "word application is unavailable during split probe",
        }

    attempts = []
    scratch_context = dict(_create_scratch_probe_context(app, source_table) or {})
    if scratch_context.get("ok"):
        return scratch_context

    attempts.append(
        {
            "probe_source": str(scratch_context.get("probe_source") or ""),
            "stage": str(scratch_context.get("stage") or ""),
            "error_code": str(scratch_context.get("error_code") or ""),
            "error_message": str(scratch_context.get("error_message") or ""),
            "copy_success": bool(scratch_context.get("copy_success", False)),
        }
    )

    should_try_same_canvas = (
        str(scratch_context.get("probe_source") or "") == "scratch"
        and str(scratch_context.get("stage") or "") == "probe.copy_table"
    )
    if not should_try_same_canvas:
        scratch_context["copy_attempts"] = list(attempts)
        return scratch_context

    section_label = str(current_section_key or "")
    safe_row_value = int(safe_row) if safe_row is not None else -1
    started = time.perf_counter()
    logger.warning(
        "[TABLE_PROBE_FALLBACK] section=%s safe_row=%s hint_same_canvas=%s from_source=scratch stage=%s -> same_canvas_start",
        section_label,
        safe_row_value,
        bool(prefer_same_canvas),
        str(scratch_context.get("stage") or ""),
    )
    same_canvas_context = dict(_create_same_canvas_probe_context(source_table) or {})
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    logger.warning(
        "[TABLE_PROBE_FALLBACK] section=%s safe_row=%s source=same_canvas ok=%s stage=%s error_code=%s elapsed_ms=%.1f",
        section_label,
        safe_row_value,
        bool(same_canvas_context.get("ok")),
        str(same_canvas_context.get("stage") or ""),
        str(same_canvas_context.get("error_code") or ""),
        float(elapsed_ms),
    )
    if same_canvas_context.get("ok"):
        same_canvas_context["copy_attempts"] = list(attempts)
        return same_canvas_context

    attempts.append(
        {
            "probe_source": str(same_canvas_context.get("probe_source") or ""),
            "stage": str(same_canvas_context.get("stage") or ""),
            "error_code": str(same_canvas_context.get("error_code") or ""),
            "error_message": str(same_canvas_context.get("error_message") or ""),
            "copy_success": bool(same_canvas_context.get("copy_success", False)),
        }
    )
    same_canvas_context["copy_attempts"] = list(attempts)
    return same_canvas_context


def _resolve_split_pair_after_anchor(doc, anchor_start: int):
    candidates = []
    for idx, table in _iter_doc_tables(doc):
        try:
            table_start = int(table.Range.Start)
        except Exception:
            continue
        if table_start >= int(anchor_start):
            candidates.append((table_start, idx, table))
    if len(candidates) < 2:
        return None, None
    candidates.sort(key=lambda item: (int(item[0]), int(item[1])))
    return candidates[0][2], candidates[1][2]


def _split_probe_table(splitter, table, row_idx: int, *, split_anchor_start: int | None = None):
    if split_anchor_start is None:
        return splitter.split_row_at(table, int(row_idx))

    try:
        doc = table.Range.Document
    except Exception:
        return None, None

    if int(row_idx) <= 1:
        return None, table

    try:
        if int(row_idx) > int(table.Rows.Count):
            return table, None
    except Exception:
        pass

    selected = False
    try:
        cols_count = int(table.Columns.Count)
    except Exception:
        cols_count = 0
    if cols_count > 0:
        for col_idx in range(1, cols_count + 1):
            try:
                cell = table.Cell(int(row_idx), int(col_idx))
                row_index = int(getattr(cell, "RowIndex", row_idx) or row_idx)
                vertical_merge = int(getattr(cell, "VerticalMerge", 0) or 0)
                if row_index != int(row_idx) or vertical_merge == 1:
                    continue
                cell.Range.Select()
                selected = True
                break
            except Exception:
                continue
    if not selected:
        return None, None

    try:
        splitter.engine.app.Selection.SplitTable()
    except Exception:
        return None, None
    return _resolve_split_pair_after_anchor(doc, int(split_anchor_start))


def _iter_candidate_rows(scanner, current_table, start_row: int):
    seen_rows: set[int] = set()
    requested_row = int(start_row)
    while requested_row > 1:
        try:
            safe_row = int(scanner.find_safe_cut_row(requested_row, working_table=current_table))
        except Exception:
            safe_row = -1
        if safe_row == -1:
            safe_row = int(requested_row)
        safe_row = min(int(safe_row), int(requested_row))
        if safe_row <= 1:
            break
        if safe_row in seen_rows:
            requested_row -= 1
            continue
        seen_rows.add(safe_row)
        yield int(requested_row), int(safe_row)
        requested_row = int(safe_row) - 1


def _probe_split_candidate(
    owner,
    source_table,
    safe_row: int,
    *,
    parent_node,
    current_section_key: str,
    width_point: float | None,
    prefer_same_canvas: bool = False,
):
    word_engine = getattr(owner, "word", None)
    if getattr(word_engine, "app", None) is None:
        return {
            "ok": False,
            "error_code": "render_export_failed",
            "stage": "probe.missing_word_app",
            "error_message": "word application is unavailable during split probe",
        }

    def _run_single_probe(*, force_cell_split: bool) -> dict:
        probe_context = dict(
            _materialize_probe_context(
                owner,
                source_table,
                prefer_same_canvas=bool(prefer_same_canvas),
                current_section_key=str(current_section_key),
                safe_row=int(safe_row),
            )
            or {}
        )
        if not probe_context.get("ok"):
            probe_context["forced_cell_split"] = bool(force_cell_split)
            return probe_context

        scratch_table = probe_context.get("table")
        cleanup = probe_context.get("cleanup")
        probe_source = str(probe_context.get("probe_source") or ("same_canvas" if prefer_same_canvas else "scratch"))
        copy_method = str(probe_context.get("copy_method") or "")
        copy_attempts = list(probe_context.get("copy_attempts") or [])
        split_anchor_start = probe_context.get("split_anchor_start")

        try:
            _disable_heading_rows(scratch_table)

            if logger.isEnabledFor(10):
                logger.debug(
                    "[TABLE_PROBE_CONTEXT] section=%s safe_row=%s prefer_same_canvas=%s probe_source=%s copy_method=%s prior_failures=%s",
                    str(current_section_key),
                    int(safe_row),
                    bool(prefer_same_canvas),
                    probe_source,
                    copy_method or "unknown",
                    len(copy_attempts),
                )

            probe_scanner = TableTopologyScanner(scratch_table)
            probe_splitter = CanvasSplitter(word_engine)

            try:
                actual_safe_row = int(probe_scanner.find_safe_cut_row(int(safe_row), working_table=scratch_table))
            except Exception:
                actual_safe_row = -1
            should_force_split = bool(force_cell_split)
            if actual_safe_row == -1:
                should_force_split = True
                actual_safe_row = int(safe_row)

            boundary_inspection = {}
            inspect_boundary = getattr(probe_scanner, "inspect_cut_boundary", None)
            if callable(inspect_boundary):
                try:
                    boundary_inspection = dict(inspect_boundary(int(actual_safe_row), table=scratch_table) or {})
                except Exception:
                    boundary_inspection = {}
            if not boundary_inspection:
                describe_boundary = getattr(probe_scanner, "describe_boundary_merge_origins", None)
                if callable(describe_boundary):
                    try:
                        boundary_merge_origins = list(describe_boundary(int(actual_safe_row), table=scratch_table) or [])
                    except Exception:
                        boundary_merge_origins = []
                    boundary_inspection = {
                        "blocked_by_continue": bool(boundary_merge_origins),
                        "ambiguous_access": False,
                        "merge_origins": boundary_merge_origins,
                        "access_errors": [],
                    }

            ambiguous_access = bool(boundary_inspection.get("ambiguous_access"))
            blocked_by_continue = bool(boundary_inspection.get("blocked_by_continue"))
            boundary_merge_origins = list(boundary_inspection.get("merge_origins") or [])
            access_errors = list(boundary_inspection.get("access_errors") or [])
            boundary_blocked_by_vmerge = bool(blocked_by_continue) and bool(should_force_split)
            if boundary_blocked_by_vmerge or ambiguous_access:
                logger.warning(
                    "[TABLE_PROBE_DIAGNOSTIC] classification=%s section=%s safe_row=%s origin_count=%s origins=%s",
                    "ambiguous_cut_boundary" if ambiguous_access else "boundary_blocked_by_vmerge",
                    str(current_section_key),
                    int(actual_safe_row),
                    len(boundary_merge_origins),
                    boundary_merge_origins,
                )

            if should_force_split:
                try:
                    probe_splitter.force_split_cells_at_row(scratch_table, int(actual_safe_row))
                except Exception:
                    pass

            upper, lower = _split_probe_table(
                probe_splitter,
                scratch_table,
                int(actual_safe_row),
                split_anchor_start=int(split_anchor_start) if split_anchor_start is not None else None,
            )
            if upper is None:
                return {
                    "ok": False,
                    "error_code": "split_stalled",
                    "stage": "probe.split_row",
                    "error_message": f"failed to split table at row {int(actual_safe_row)}",
                    "safe_row": int(actual_safe_row),
                    "probe_source": probe_source,
                    "copy_method": copy_method or None,
                    "copy_attempts": copy_attempts,
                    "forced_cell_split": bool(should_force_split),
                    "ambiguous_access": bool(ambiguous_access),
                    "blocked_by_continue": bool(blocked_by_continue),
                    "access_errors": access_errors,
                    "boundary_blocked_by_vmerge": bool(boundary_blocked_by_vmerge),
                    "boundary_merge_origins": boundary_merge_origins,
                }

            try:
                if logger.isEnabledFor(10):
                    logger.debug(
                        "[TABLE_BORDER_POLICY] section=%s stage=probe strategy=%s safe_row=%s",
                        str(current_section_key),
                        CUT_BORDER_POLICY_CLOSED,
                        int(actual_safe_row),
                    )
                probe_splitter.apply_cut_border_policy(
                    upper,
                    lower,
                    strategy=CUT_BORDER_POLICY_CLOSED,
                    stage="probe",
                )
            except Exception:
                pass

            clear_failure = getattr(owner, "_clear_table_process_failure_context", None)
            if callable(clear_failure):
                try:
                    clear_failure()
                except Exception:
                    pass

            capture_payload = _capture_table_fragments_in_canvas(
                owner,
                upper,
                parent_node=parent_node,
                current_section_key=current_section_key,
                width_point=width_point,
            )
            if not capture_payload.get("ok"):
                failure_ctx = None
                consume_failure = getattr(owner, "_consume_table_process_failure_context", None)
                if callable(consume_failure):
                    try:
                        failure_ctx = consume_failure()
                    except Exception:
                        failure_ctx = None
                if not failure_ctx:
                    peek_failure = getattr(owner, "_peek_table_process_failure_context", None)
                    if callable(peek_failure):
                        try:
                            failure_ctx = peek_failure()
                        except Exception:
                            failure_ctx = None
                failure_ctx = dict(failure_ctx or {})
                failure_code = str(failure_ctx.get("error_code") or "render_export_failed")
                failure_stage = str(failure_ctx.get("stage") or "probe.capture_fragment")
                error_message = str(failure_ctx.get("error_message") or f"failed to capture probe fragment at row {int(actual_safe_row)}")
                result = {
                    "ok": False,
                    "error_code": failure_code,
                    "stage": failure_stage,
                    "error_message": error_message,
                    "safe_row": int(actual_safe_row),
                    "probe_source": probe_source,
                    "copy_method": copy_method or None,
                    "copy_attempts": copy_attempts,
                    "forced_cell_split": bool(should_force_split),
                    "ambiguous_access": bool(ambiguous_access),
                    "blocked_by_continue": bool(blocked_by_continue),
                    "access_errors": access_errors,
                    "boundary_blocked_by_vmerge": bool(boundary_blocked_by_vmerge),
                    "boundary_merge_origins": boundary_merge_origins,
                }
                for key in (
                    "error_type",
                    "diagnostic_code",
                    "used_blank_doc_fallback",
                    "hard_table",
                    "fragment_count",
                    "classification",
                ):
                    if failure_ctx.get(key) is not None:
                        result[key] = failure_ctx.get(key)
                return result
            fragments = _normalize_capture_fragments(capture_payload)
            fragment_count = len(fragments)
            max_fragment_height_mm = max((float(item[2]) for item in fragments), default=0.0)
            top_fragment_inherently_multi_page = bool(fragment_count > 1 and int(actual_safe_row) <= 2)
            if top_fragment_inherently_multi_page:
                logger.warning(
                    "[TABLE_PROBE_DIAGNOSTIC] classification=%s section=%s safe_row=%s fragment_count=%s max_fragment_height_mm=%.2f",
                    "top_fragment_inherently_multi_page",
                    str(current_section_key),
                    int(actual_safe_row),
                    int(fragment_count),
                    float(max_fragment_height_mm),
                )
            result = {
                "ok": True,
                "fragments": fragments,
                "fragment_count": int(fragment_count),
                "max_fragment_height_mm": float(max_fragment_height_mm),
                "safe_row": int(actual_safe_row),
                "probe_source": probe_source,
                "copy_method": copy_method or None,
                "copy_attempts": copy_attempts,
                "forced_cell_split": bool(should_force_split),
                "ambiguous_access": bool(ambiguous_access),
                "blocked_by_continue": bool(blocked_by_continue),
                "access_errors": access_errors,
                "boundary_blocked_by_vmerge": bool(boundary_blocked_by_vmerge),
                "boundary_merge_origins": boundary_merge_origins,
                "top_fragment_inherently_multi_page": bool(top_fragment_inherently_multi_page),
            }
            if fragment_count == 1:
                fn, w, h = fragments[0]
                result["file"] = str(fn)
                result["width_mm"] = float(w)
                result["height_mm"] = float(h)
            elif fragments:
                result["height_mm"] = float(max_fragment_height_mm)
            return result
        finally:
            if callable(cleanup):
                try:
                    cleanup()
                except Exception:
                    pass

    result = _run_single_probe(force_cell_split=False)
    if result.get("ok"):
        return result

    should_retry_with_force_split = (
        str(result.get("stage") or "") == "probe.capture_fragment"
        and str(result.get("error_code") or "") in {"fragment_still_over_limit", "fragment_measured_over_limit"}
        and not bool(result.get("forced_cell_split"))
        and int(result.get("safe_row") or safe_row) > 1
    )
    if not should_retry_with_force_split:
        return result

    logger.warning(
        "[TABLE_PROBE_RETRY] section=%s safe_row=%s action=force_split_cells_at_row reason=%s",
        str(current_section_key),
        int(result.get("safe_row") or safe_row),
        str(result.get("error_code") or ""),
    )
    retry_result = _run_single_probe(force_cell_split=True)
    retry_result["retry_reason"] = "force_split_cells_at_row"
    return retry_result


RECOVERABLE_PROBE_FAILURE_CODES = {
    "fragment_still_over_limit",
    "fragment_measured_over_limit",
    "selection_export_failed",
    "blank_doc_export_failed",
    "pdf_page_invalid",
    "render_export_failed",
}

STRUCTURAL_PROBE_FAILURE_STAGES = {
    "probe.missing_word_app",
    "probe.create_canvas",
    "probe.copy_table",
    "probe.split_row",
}


def _is_recoverable_probe_failure(probe: dict | None) -> bool:
    payload = dict(probe or {})
    stage = str(payload.get("stage") or "").strip()
    error_code = str(payload.get("error_code") or "").strip()
    if stage in STRUCTURAL_PROBE_FAILURE_STAGES:
        return False
    if stage == "probe.capture_fragment":
        return True
    return error_code in RECOVERABLE_PROBE_FAILURE_CODES


def _probe_has_ambiguous_boundary(probe: dict | None) -> bool:
    payload = dict(probe or {})
    if bool(payload.get("ambiguous_access")):
        return True
    if bool(payload.get("blocked_by_continue")):
        return True
    if bool(payload.get("boundary_blocked_by_vmerge")):
        return True
    return bool(payload.get("boundary_merge_origins"))


def _pick_split_candidate(
    owner,
    scanner,
    current_table,
    start_row: int,
    *,
    parent_node,
    current_section_key: str,
    width_point: float | None,
    max_height_mm: float,
    prefer_same_canvas: bool = False,
):
    oversize_attempts = []
    final_failure = None
    prefer_same_canvas = bool(prefer_same_canvas)
    for requested_row, safe_row in _iter_candidate_rows(scanner, current_table, int(start_row)):
        probe = _probe_split_candidate(
            owner,
            current_table,
            int(safe_row),
            parent_node=parent_node,
            current_section_key=current_section_key,
            width_point=width_point,
            prefer_same_canvas=bool(prefer_same_canvas),
        )
        if not probe.get("ok"):
            probe["requested_row"] = int(requested_row)
            probe["safe_row"] = int(probe.get("safe_row", safe_row) or safe_row)
            if _is_recoverable_probe_failure(probe):
                final_failure = dict(probe)
                logger.warning(
                    "[TABLE_SPLIT_BACKOFF_FAIL] section=%s requested_row=%s safe_row=%s error_code=%s stage=%s probe_source=%s",
                    str(current_section_key),
                    int(requested_row),
                    int(probe.get("safe_row", safe_row) or safe_row),
                    str(probe.get("error_code") or "render_export_failed"),
                    str(probe.get("stage") or "probe.capture_fragment"),
                    str(probe.get("probe_source") or ""),
                )
                continue
            return None, probe

        if _probe_has_ambiguous_boundary(probe):
            probe["requested_row"] = int(requested_row)
            probe["safe_row"] = int(probe.get("safe_row", safe_row) or safe_row)
            probe["ok"] = False
            probe["error_code"] = str(probe.get("error_code") or "ambiguous_cut_boundary")
            probe["stage"] = str(probe.get("stage") or "split.backoff_ambiguous_boundary")
            probe["error_message"] = str(
                probe.get("error_message")
                or f"probe at safe_row={int(probe.get('safe_row', safe_row) or safe_row)} produced an ambiguous cut boundary"
            )
            probe["classification"] = str(probe.get("classification") or "ambiguous_cut_boundary")
            final_failure = dict(probe)
            logger.warning(
                "[TABLE_SPLIT_BACKOFF_AMBIGUOUS] section=%s requested_row=%s safe_row=%s ambiguous_access=%s origin_count=%s",
                str(current_section_key),
                int(requested_row),
                int(probe.get("safe_row", safe_row) or safe_row),
                bool(probe.get("ambiguous_access")),
                len(list(probe.get("boundary_merge_origins") or [])),
            )
            _cleanup_fragment_files(owner, probe.get("fragments"))
            _safe_remove_temp_image(owner, probe.get("file"))
            continue

        height_mm = float(probe.get("max_fragment_height_mm") or probe.get("height_mm") or 0.0)
        if height_mm <= float(max_height_mm) + 1e-6:
            probe["requested_row"] = int(requested_row)
            return probe, None

        oversize_attempts.append(
            {
                "requested_row": int(requested_row),
                "safe_row": int(probe.get("safe_row", safe_row) or safe_row),
                "height_mm": float(height_mm),
            }
        )
        final_failure = {
            "ok": False,
            "error_code": "fragment_measured_over_limit",
            "stage": "split.backoff_exhausted",
            "error_message": (
                f"all candidate fragments exceeded max height; "
                f"last safe_row={int(probe.get('safe_row', safe_row) or safe_row)} height_mm={float(height_mm):.2f}"
            ),
            "requested_row": int(requested_row),
            "safe_row": int(probe.get("safe_row", safe_row) or safe_row),
            "height_mm": float(height_mm),
            "probe_source": probe.get("probe_source"),
            "copy_method": probe.get("copy_method"),
        }
        logger.warning(
            "[TABLE_SPLIT_BACKOFF] section=%s requested_row=%s safe_row=%s height_mm=%.2f max_height_mm=%.2f",
            str(current_section_key),
            int(requested_row),
            int(probe.get("safe_row", safe_row) or safe_row),
            float(height_mm),
            float(max_height_mm),
        )
        _cleanup_fragment_files(owner, probe.get("fragments"))
        _safe_remove_temp_image(owner, probe.get("file"))

    if final_failure is not None:
        return None, final_failure

    return None, {
        "ok": False,
        "error_code": "split_stalled",
        "stage": "split.backoff_unavailable",
        "error_message": "no earlier candidate row was available for split backoff",
    }


def _apply_split_to_current_table(scanner, splitter, current_table, safe_row: int, *, current_section_key: str):
    try:
        actual_safe_row = int(scanner.find_safe_cut_row(int(safe_row), working_table=current_table))
    except Exception:
        actual_safe_row = -1
    if actual_safe_row == -1:
        logger.info("[CELL_SPLIT] section=%s requested_row=%s", str(current_section_key), int(safe_row))
        try:
            splitter.force_split_cells_at_row(current_table, int(safe_row))
        except Exception:
            pass
        actual_safe_row = int(safe_row)

    upper, lower = splitter.split_row_at(current_table, int(actual_safe_row))
    if upper is None:
        return None, None, int(actual_safe_row)

    try:
        if logger.isEnabledFor(10):
            logger.debug(
                "[TABLE_BORDER_POLICY] section=%s stage=apply strategy=%s safe_row=%s",
                str(current_section_key),
                CUT_BORDER_POLICY_CLOSED,
                int(actual_safe_row),
            )
        splitter.apply_cut_border_policy(
            upper,
            lower,
            strategy=CUT_BORDER_POLICY_CLOSED,
            stage="apply",
        )
    except Exception:
        pass
    return upper, lower, int(actual_safe_row)


def process_table_split_flow(self, table, parent_node, current_section_key):  # type: ignore[override]
    max_height_mm = _get_max_height_mm(self)
    try:
        max_height_cm = float(max_height_mm) / 10.0
    except Exception:
        max_height_cm = 24.0

    row_count = 0
    try:
        row_count = int(table.Rows.Count)
    except Exception:
        row_count = 0
    try:
        col_count = int(table.Columns.Count)
    except Exception:
        col_count = 0
    try:
        rng_start = int(table.Range.Start)
        rng_end = int(table.Range.End)
    except Exception:
        rng_start, rng_end = None, None

    logger.info(
        "[TABLE_PROCESS] section=%s rows=%s cols=%s range_start=%s range_end=%s",
        str(current_section_key),
        row_count,
        col_count,
        rng_start,
        rng_end,
    )

    try:
        target_slice_pt = float(max_height_cm) * 72.0 / 2.54
    except Exception:
        target_slice_pt = 24.0 * 72.0 / 2.54

    table_width_point = None
    try:
        table_width_point = self._get_table_width_point(table)
    except Exception:
        table_width_point = None

    logger.info("[TABLE_SPLIT] section=%s rows=%s", str(current_section_key), row_count)

    word_engine = getattr(self, "word", None)
    if word_engine is None:
        logger.warning("[TABLE_SPLIT_UNAVAILABLE] section=%s reason=missing_word_engine", str(current_section_key))
        self._set_table_process_failure_context(
            error_code="render_export_failed",
            stage="split.missing_word_engine",
            error_message="word engine is unavailable for table split flow",
            rows=row_count,
        )
        return False

    scanner = TableTopologyScanner(table)
    splitter = CanvasSplitter(word_engine)

    canvas = None
    canvas_owned = False
    try:
        canvas = add_hidden_document(word_engine.app, logger=logger)
        canvas_owned = True
    except Exception:
        try:
            canvas = word_engine.get_canvas_doc()
        except Exception:
            canvas = None
        canvas_owned = False
    if canvas is None:
        logger.warning("[TABLE_SPLIT_UNAVAILABLE] section=%s reason=missing_canvas_doc", str(current_section_key))
        self._set_table_process_failure_context(
            error_code="render_export_failed",
            stage="split.missing_canvas_doc",
            error_message="unable to allocate split canvas document",
            rows=row_count,
        )
        return False

    original_table = table
    max_retries = 2
    retry_count = 0

    try:
        while retry_count <= max_retries:
            try:
                working_table = _copy_table_to_canvas(original_table, canvas)
                if working_table is None:
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.warning("[TABLE_RECOVERY] section=%s retry=%s/%s stage=paste", str(current_section_key), retry_count, max_retries)
                        time.sleep(0.2)
                        continue
                    return False

                _disable_heading_rows(working_table)

                fragments = []
                current_table = working_table
                loop_guard = 0
                max_loops = 100

                while loop_guard < max_loops:
                    loop_guard += 1
                    try:
                        rows_cnt = int(current_table.Rows.Count)
                    except Exception:
                        rows_cnt = 0
                    if rows_cnt <= 0:
                        logger.warning("[TABLE_LOOP_ERROR] section=%s stage=rows_empty", str(current_section_key))
                        self._set_table_process_failure_context(
                            error_code="split_stalled",
                            stage="split.rows_empty",
                            error_message="current working table has no rows",
                        )
                        break

                    row_top_map = _build_row_top_map(current_table)
                    row_heights = _collect_row_heights(current_table)
                    cut_row, cut_method = _choose_cut_row(row_top_map, row_heights, target_slice_pt)

                    if logger.isEnabledFor(10):
                        logger.debug(
                            "[TABLE_SPLIT_DECISION] loop=%s rows=%s cut_row=%s method=%s mapped_rows=%s",
                            loop_guard,
                            rows_cnt,
                            cut_row,
                            cut_method,
                            len(row_top_map),
                        )

                    if cut_row == -1:
                        capture_payload = _capture_table_fragments_in_canvas(
                            self,
                            current_table,
                            parent_node=parent_node,
                            current_section_key=current_section_key,
                            width_point=table_width_point,
                        )
                        final_fragments = _normalize_capture_fragments(capture_payload)
                        max_fragment_height_mm = max((float(item[2]) for item in final_fragments), default=0.0)
                        if not capture_payload.get("ok"):
                            logger.warning("[TABLE_SPLIT_CAPTURE_FAIL] section=%s stage=final_capture", str(current_section_key))
                            self._set_table_process_failure_context(
                                error_code="render_export_failed",
                                stage="split.capture_final",
                                error_message="failed to capture final table fragment",
                                rows=rows_cnt,
                            )
                            _cleanup_fragment_files(self, fragments)
                            break
                        if float(max_fragment_height_mm) <= float(max_height_mm) + 1e-6:
                            fragments.extend(final_fragments)
                            break
                        _cleanup_fragment_files(self, final_fragments)
                        if rows_cnt <= 1:
                            self._set_table_process_failure_context(
                                error_code="fragment_measured_over_limit",
                                stage="split.capture_final",
                                error_message=f"single-row final fragment height {float(max_fragment_height_mm):.2f}mm exceeds max height",
                                rows=rows_cnt,
                                height_mm=float(max_fragment_height_mm),
                                fragment_count=len(final_fragments),
                            )
                            _cleanup_fragment_files(self, fragments)
                            return False
                        logger.warning(
                            "[TABLE_FINAL_BACKOFF] section=%s rows=%s height_mm=%.2f max_height_mm=%.2f",
                            str(current_section_key),
                            rows_cnt,
                            float(max_fragment_height_mm),
                            float(max_height_mm),
                        )
                        candidate_start_row = rows_cnt
                    else:
                        candidate_start_row = cut_row

                    prefer_same_canvas_probe = False
                    if logger.isEnabledFor(10):
                        logger.debug(
                            "[TABLE_SPLIT_PROBE_PLAN] section=%s loop=%s rows_before=%s candidate_start_row=%s prefer_same_canvas=%s",
                            str(current_section_key),
                            loop_guard,
                            rows_cnt,
                            int(candidate_start_row),
                            prefer_same_canvas_probe,
                        )

                    candidate, candidate_failure = _pick_split_candidate(
                        self,
                        scanner,
                        current_table,
                        int(candidate_start_row),
                        parent_node=parent_node,
                        current_section_key=str(current_section_key),
                        width_point=table_width_point,
                        max_height_mm=float(max_height_mm),
                        prefer_same_canvas=prefer_same_canvas_probe,
                    )
                    if candidate is None:
                        logger.warning(
                            "[TABLE_SPLIT_BACKOFF_FAIL] section=%s loop=%s cut_row=%s stage=%s error_code=%s probe_source=%s rows_before=%s",
                            str(current_section_key),
                            loop_guard,
                            cut_row,
                            str((candidate_failure or {}).get("stage", "")),
                            str((candidate_failure or {}).get("error_code", "")),
                            str((candidate_failure or {}).get("probe_source", "")),
                            rows_cnt,
                        )
                        if candidate_failure:
                            self._set_table_process_failure_context(
                                error_code=str(candidate_failure.get("error_code") or "render_export_failed"),
                                stage=str(candidate_failure.get("stage") or "split.backoff"),
                                error_message=str(candidate_failure.get("error_message") or ""),
                                requested_row=candidate_failure.get("requested_row"),
                                safe_row=candidate_failure.get("safe_row"),
                                height_mm=candidate_failure.get("height_mm"),
                                max_fragment_height_mm=candidate_failure.get("max_fragment_height_mm"),
                                probe_source=candidate_failure.get("probe_source"),
                                copy_method=candidate_failure.get("copy_method"),
                                copy_attempts=candidate_failure.get("copy_attempts"),
                                classification=candidate_failure.get("classification"),
                                fragment_count=candidate_failure.get("fragment_count"),
                                ambiguous_access=candidate_failure.get("ambiguous_access"),
                                blocked_by_continue=candidate_failure.get("blocked_by_continue"),
                                access_errors=candidate_failure.get("access_errors"),
                                boundary_blocked_by_vmerge=candidate_failure.get("boundary_blocked_by_vmerge"),
                                boundary_merge_origins=candidate_failure.get("boundary_merge_origins"),
                                top_fragment_inherently_multi_page=candidate_failure.get("top_fragment_inherently_multi_page"),
                                rows=rows_cnt,
                                rows_before=rows_cnt,
                            )
                        _cleanup_fragment_files(self, fragments)
                        return False

                    accepted_safe_row = int(candidate.get("safe_row") or 0)
                    upper, lower, applied_safe_row = _apply_split_to_current_table(
                        scanner,
                        splitter,
                        current_table,
                        accepted_safe_row,
                        current_section_key=str(current_section_key),
                    )
                    if upper is None:
                        self._set_table_process_failure_context(
                            error_code="split_stalled",
                            stage="split.apply",
                            error_message=f"failed to apply split at safe_row={int(accepted_safe_row)}",
                            safe_row=int(accepted_safe_row),
                            rows=rows_cnt,
                        )
                        _cleanup_fragment_files(self, candidate.get("fragments"))
                        _safe_remove_temp_image(self, candidate.get("file"))
                        _cleanup_fragment_files(self, fragments)
                        return False

                    candidate_fragments = _normalize_capture_fragments(candidate)
                    if not candidate_fragments and candidate.get("file"):
                        candidate_fragments = [
                            (
                                str(candidate.get("file")),
                                float(candidate.get("width_mm") or 0.0),
                                float(candidate.get("height_mm") or 0.0),
                            )
                        ]
                    fragments.extend(candidate_fragments)
                    logger.info(
                        "[TABLE_SPLIT_ACCEPT] section=%s loop=%s requested_row=%s safe_row=%s applied_safe_row=%s height_mm=%.2f fragment_count=%s probe_source=%s rows_before=%s",
                        str(current_section_key),
                        loop_guard,
                        int(candidate.get("requested_row") or candidate_start_row),
                        int(accepted_safe_row),
                        int(applied_safe_row),
                        float(candidate.get("max_fragment_height_mm") or candidate.get("height_mm") or 0.0),
                        int(len(candidate_fragments)),
                        str(candidate.get("probe_source") or ""),
                        rows_cnt,
                    )

                    try:
                        upper.Delete()
                    except Exception:
                        pass

                    refreshed_table = None
                    for _ in range(3):
                        refreshed_table = _refresh_first_canvas_table(canvas)
                        if refreshed_table is not None:
                            break
                        time.sleep(0.05)
                    current_table = refreshed_table or lower
                    if current_table is None:
                        logger.warning("[TABLE_LOOP_ERROR] section=%s stage=missing_lower_fragment", str(current_section_key))
                        self._set_table_process_failure_context(
                            error_code="split_stalled",
                            stage="split.missing_lower_fragment",
                            error_message="lower fragment is missing after split",
                            safe_row=int(applied_safe_row),
                            rows_before=rows_cnt,
                        )
                        _cleanup_fragment_files(self, fragments)
                        break

                    try:
                        new_rows_cnt = int(current_table.Rows.Count)
                    except Exception:
                        new_rows_cnt = 0
                    try:
                        lower_range_start = int(current_table.Range.Start)
                        lower_range_end = int(current_table.Range.End)
                    except Exception:
                        lower_range_start, lower_range_end = None, None
                    logger.info(
                        "[TABLE_SPLIT_CONTINUE] section=%s loop=%s rows_before=%s rows_after=%s lower_range_start=%s lower_range_end=%s",
                        str(current_section_key),
                        loop_guard,
                        rows_cnt,
                        new_rows_cnt,
                        lower_range_start,
                        lower_range_end,
                    )
                    if new_rows_cnt <= 0:
                        logger.warning("[TABLE_LOOP_ERROR] section=%s stage=rows_after_split_empty", str(current_section_key))
                        self._set_table_process_failure_context(
                            error_code="split_stalled",
                            stage="split.rows_after_split_empty",
                            error_message="lower fragment became empty after split",
                            safe_row=int(applied_safe_row),
                            rows_before=rows_cnt,
                            rows_after=new_rows_cnt,
                            lower_range_start=lower_range_start,
                            lower_range_end=lower_range_end,
                        )
                        _cleanup_fragment_files(self, fragments)
                        break
                    if new_rows_cnt >= rows_cnt:
                        logger.warning(
                            "[TABLE_SPLIT_STALL] section=%s rows_before=%s rows_after=%s safe_row=%s",
                            str(current_section_key),
                            rows_cnt,
                            new_rows_cnt,
                            applied_safe_row,
                        )
                        self._set_table_process_failure_context(
                            error_code="split_stalled",
                            stage="split.rows_stalled",
                            error_message="row count did not decrease after split",
                            safe_row=int(applied_safe_row),
                            rows_before=rows_cnt,
                            rows_after=new_rows_cnt,
                            lower_range_start=lower_range_start,
                            lower_range_end=lower_range_end,
                        )
                        _cleanup_fragment_files(self, fragments)
                        return False

                if fragments:
                    try:
                        canvas.Content.Delete()
                    except Exception:
                        pass
                    return self._emit_fragments(fragments, parent_node, current_section_key, original_table)

                logger.warning("[TABLE_FALLBACK] section=%s stage=topology_empty", str(current_section_key))
                break
            except Exception as exc:
                logger.error(
                    "[TABLE_PROCESS_ERROR] section=%s retry=%s/%s error_type=%s error=%s",
                    str(current_section_key),
                    retry_count + 1,
                    max_retries + 1,
                    type(exc).__name__,
                    str(exc),
                )
                retry_count += 1
                try:
                    canvas.Content.Delete()
                except Exception:
                    pass
                if retry_count <= max_retries:
                    time.sleep(0.3)
                    continue
                break
    finally:
        if canvas_owned and canvas is not None:
            try:
                canvas.Close(SaveChanges=0)
            except Exception:
                pass
        elif canvas is not None:
            try:
                canvas.Content.Delete()
            except Exception:
                pass

    peek_failure = getattr(self, "_peek_table_process_failure_context", None)
    failure_context = peek_failure() if callable(peek_failure) else None
    if not failure_context:
        self._set_table_process_failure_context(
            error_code="render_export_failed",
            stage="split.pdf_exhausted",
            error_message="PDF-backed table split flow did not produce legal fragments",
            rows=row_count,
        )
    return False
