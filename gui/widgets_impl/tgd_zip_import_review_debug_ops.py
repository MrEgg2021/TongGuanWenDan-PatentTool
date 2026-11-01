from __future__ import annotations

import os
import sys


def _zip_debug_enabled() -> bool:
    v = ""
    try:
        v = str(os.environ.get("TGD_DEBUG_ZIP_IMPORT") or "").strip().lower()
    except Exception:
        v = ""
    return bool(v) and v not in {"0", "false", "no", "off"}


def zip_dbg(msg: str) -> None:
    if not _zip_debug_enabled():
        return
    try:
        print(f"[TGD_ZIP_IMPORT] {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass
