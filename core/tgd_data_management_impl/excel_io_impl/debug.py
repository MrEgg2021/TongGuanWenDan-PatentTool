from __future__ import annotations

import os
import sys


def _excel_debug_enabled() -> bool:
    v = ""
    try:
        v = str(os.environ.get("TGD_DEBUG_EXCEL_IO") or "").strip().lower()
    except Exception:
        v = ""
    return bool(v) and v not in {"0", "false", "no", "off"}


def excel_dbg(msg: str) -> None:
    if not _excel_debug_enabled():
        return
    try:
        print(f"[TGD_EXCEL_IO] {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass
