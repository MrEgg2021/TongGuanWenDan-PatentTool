from __future__ import annotations

import json
import os
import sys
from typing import Any, Protocol

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QTableWidget

from gui.widgets_impl.tgd_fact_record_manager_utils import _norm_text


def _layout_debug_enabled() -> bool:
    v = _norm_text(os.environ.get("TGD_DEBUG_LAYOUT"))
    if not v:
        return False
    return v.lower() not in {"0", "false", "no", "off"}


def _layout_dbg(msg: str) -> None:
    if not _layout_debug_enabled():
        return
    try:
        print(f"[TGD_LAYOUT] {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass


def _header_snapshot(h) -> dict:
    try:
        count = int(h.count())
    except Exception:
        count = 0
    hidden_cnt = 0
    widths: list[int] = []
    try:
        for i in range(int(count)):
            try:
                if bool(h.isSectionHidden(int(i))):
                    hidden_cnt += 1
            except Exception:
                pass
            try:
                widths.append(int(h.sectionSize(int(i))))
            except Exception:
                widths.append(-1)
    except Exception:
        pass
    return {
        "count": int(count),
        "hidden": int(hidden_cnt),
        "widths_head": widths[: min(6, len(widths))],
    }


class _LayoutStateDialog(Protocol):
    fact_table_left: QTableWidget | None
    fact_table_right: QTableWidget | None
    agency_table: QTableWidget | None

    splitter: Any

    def _get_layout_config_path(self) -> str: ...

    def _get_table_layout_signature(self, tbl: QTableWidget) -> dict: ...

    def _save_layout_state(self, *, force: bool = False) -> None: ...

    def _ensure_fact_tables_last_visible_stretch(self) -> None: ...


def _apply_hidden_state(tbl: QTableWidget, hidden) -> bool:
    restore_failed = False
    try:
        count = int(tbl.columnCount())
    except Exception:
        count = 0
    if isinstance(hidden, list) and len(hidden) == int(count):
        for i, is_h in enumerate(hidden):
            try:
                if int(i) < int(count):
                    tbl.setColumnHidden(int(i), bool(is_h))
            except Exception:
                restore_failed = True
    else:
        if hidden is not None:
            restore_failed = True
    return bool(restore_failed)


def _apply_order_state(h, order) -> bool:
    restore_failed = False
    if isinstance(order, list) and len(order) == h.count():
        try:
            desired = [int(x) for x in order]
            if sorted(desired) != list(range(int(h.count()))):
                raise ValueError("invalid order")
            for target_visual, logical in enumerate(desired):
                cur_visual = int(h.visualIndex(int(logical)))
                if cur_visual >= 0 and int(cur_visual) != int(target_visual):
                    h.moveSection(int(cur_visual), int(target_visual))
        except Exception:
            restore_failed = True
    else:
        if order is not None:
            restore_failed = True
    return bool(restore_failed)


def _apply_widths_state(tbl: QTableWidget, widths) -> bool:
    restore_failed = False
    try:
        count = int(tbl.columnCount())
    except Exception:
        count = 0
    if isinstance(widths, list) and len(widths) == int(count):
        for i, w in enumerate(widths):
            try:
                if int(i) < int(count):
                    if int(w) <= 0:
                        continue
                    tbl.setColumnWidth(int(i), max(1, int(w)))
            except Exception:
                restore_failed = True
    else:
        if widths is not None:
            restore_failed = True
    return bool(restore_failed)


def _restore_header_state(h, state_hex: str | None) -> bool:
    if not state_hex:
        return True
    try:
        return bool(h.restoreState(QByteArray.fromHex(_norm_text(state_hex).encode())))
    except Exception:
        return False


def _apply_single_table_state(dlg: _LayoutStateDialog, name: str, tbl: QTableWidget, config: dict) -> tuple[bool, bool]:
    structural_mismatch = False
    restore_failed = False

    if not isinstance(config.get(name), dict):
        return True, False

    h = tbl.horizontalHeader()

    try:
        _layout_dbg(f"apply table={name} before={_header_snapshot(h)}")
    except Exception:
        pass

    stored_sig = config[name].get("signature")
    cur_sig = dlg._get_table_layout_signature(tbl)
    try:
        stored_count = int(stored_sig.get("count")) if isinstance(stored_sig, dict) else None
    except Exception:
        stored_count = None
    try:
        cur_count = int(cur_sig.get("count")) if isinstance(cur_sig, dict) else None
    except Exception:
        cur_count = None
    if (stored_count is None) or (cur_count is None) or (int(stored_count) != int(cur_count)):
        try:
            _layout_dbg(f"table={name} signature mismatch stored_count={stored_count} cur_count={cur_count}")
        except Exception:
            pass
        return True, False

    try:
        hidden_cfg = config[name].get("hidden")
        widths_cfg = config[name].get("widths")
        order_cfg = config[name].get("order")
        _layout_dbg(
            f"table={name} cfg hidden_len={len(hidden_cfg) if isinstance(hidden_cfg, list) else None} "
            f"widths_len={len(widths_cfg) if isinstance(widths_cfg, list) else None} "
            f"order_len={len(order_cfg) if isinstance(order_cfg, list) else None}"
        )
    except Exception:
        pass

    if "hidden" in config[name]:
        restore_failed = bool(restore_failed) or bool(_apply_hidden_state(tbl, config[name].get("hidden") or []))

    if "order" in config[name]:
        restore_failed = bool(restore_failed) or bool(_apply_order_state(h, config[name].get("order")))

    if "widths" in config[name]:
        restore_failed = bool(restore_failed) or bool(_apply_widths_state(tbl, config[name].get("widths")))

    has_explicit_layout = any(k in config[name] for k in ("hidden", "order", "widths"))
    if (not bool(has_explicit_layout)) and ("state" in config[name]):
        restored_ok = _restore_header_state(h, config[name].get("state"))
        if not bool(restored_ok):
            restore_failed = True
        try:
            _layout_dbg(f"table={name} restoreState ok={bool(restored_ok)}")
        except Exception:
            pass

    try:
        _layout_dbg(f"apply table={name} after={_header_snapshot(h)} restore_failed={bool(restore_failed)}")
    except Exception:
        pass

    return bool(structural_mismatch), bool(restore_failed)


def _apply_splitter_state(dlg: _LayoutStateDialog, config: dict) -> tuple[bool, bool]:
    structural_mismatch = False
    restore_failed = False

    if "splitter" in config and hasattr(dlg, "splitter") and dlg.splitter:
        try:
            sizes = config.get("splitter")
            if isinstance(sizes, list) and len(sizes) == 2:
                dlg.splitter.setSizes([int(sizes[0]), int(sizes[1])])
            else:
                structural_mismatch = True
        except Exception:
            restore_failed = True

    return bool(structural_mismatch), bool(restore_failed)


def load_layout_state(dlg: _LayoutStateDialog) -> tuple[bool, bool]:
    try:
        path = dlg._get_layout_config_path()
        try:
            _layout_dbg(f"load path={path} exists={bool(os.path.exists(path))} embedded={getattr(dlg, '_embedded', None)}")
        except Exception:
            pass
        if not os.path.exists(path):
            return False, False
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)

        try:
            _layout_dbg(f"load keys={list(config.keys()) if isinstance(config, dict) else type(config)}")
        except Exception:
            pass

        structural_mismatch = False
        restore_failed = False

        for name, tbl in [("fact_left", dlg.fact_table_left), ("fact_right", dlg.fact_table_right), ("agency", dlg.agency_table)]:
            if not tbl or name not in config:
                continue

            if not isinstance(config.get(name), dict):
                structural_mismatch = True
                continue

            sm, rf = _apply_single_table_state(dlg, name, tbl, config)
            structural_mismatch = bool(structural_mismatch) or bool(sm)
            restore_failed = bool(restore_failed) or bool(rf)

        sm2, rf2 = _apply_splitter_state(dlg, config)
        structural_mismatch = bool(structural_mismatch) or bool(sm2)
        restore_failed = bool(restore_failed) or bool(rf2)

        if structural_mismatch:
            try:
                dlg._save_layout_state(force=True)
            except Exception:
                pass

        try:
            dlg._ensure_fact_tables_last_visible_stretch()
        except Exception:
            pass

        try:
            if getattr(dlg, 'fact_table_left', None) is not None:
                _layout_dbg(f"final fact_left={_header_snapshot(dlg.fact_table_left.horizontalHeader())}")
            if getattr(dlg, 'fact_table_right', None) is not None:
                _layout_dbg(f"final fact_right={_header_snapshot(dlg.fact_table_right.horizontalHeader())}")
            if getattr(dlg, 'agency_table', None) is not None:
                _layout_dbg(f"final agency={_header_snapshot(dlg.agency_table.horizontalHeader())}")
            _layout_dbg(f"done structural_mismatch={bool(structural_mismatch)} restore_failed={bool(restore_failed)}")
        except Exception:
            pass

        return bool(structural_mismatch), bool(restore_failed)
    except Exception:
        return False, True
