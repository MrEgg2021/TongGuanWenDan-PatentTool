from __future__ import annotations

from typing import Any, Dict, Tuple

from .constants import _AGENCY_SHEET_NAME, _FACT_SHEET_NAME
from .text_utils import _normalize_text


def _pick_fact_sheet(wb):
    ws = None
    try:
        if _FACT_SHEET_NAME in wb.sheetnames:
            ws = wb[_FACT_SHEET_NAME]
    except Exception:
        ws = None
    if ws is None:
        try:
            sheets = getattr(wb, "worksheets", [])
            if isinstance(sheets, list) and len(sheets) == 1:
                ws = sheets[0]
        except Exception:
            ws = None
    return ws


def _pick_agency_sheet(wb):
    ws = None
    try:
        if _AGENCY_SHEET_NAME in wb.sheetnames:
            ws = wb[_AGENCY_SHEET_NAME]
    except Exception:
        ws = None
    return ws


def _read_header_row(ws):
    header_row = None
    try:
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    except Exception:
        header_row = None
    if not header_row:
        return None
    return header_row


def _build_header_map(header_row) -> Dict[str, int]:
    header_map: Dict[str, int] = {}
    for idx, h in enumerate(list(header_row)):
        key = _normalize_text(h)
        if key:
            header_map[key] = int(idx)
    return header_map


def _make_row_getter(header_map: Dict[str, int]):
    def _get(row_values: Tuple[Any, ...], name: str) -> Any:
        j = header_map.get(name)
        if j is None:
            return None
        if j < 0 or j >= len(row_values):
            return None
        return row_values[j]

    return _get
