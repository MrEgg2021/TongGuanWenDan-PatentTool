from __future__ import annotations

# Compatibility layer: keep legacy import path stable while delegating to V3.
from .excel_report_v3 import build_default_excel_name, build_dynamic_keys, write_excel_report

__all__ = ["build_default_excel_name", "build_dynamic_keys", "write_excel_report"]
