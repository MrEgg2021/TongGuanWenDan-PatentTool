from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TablePdfFragment:
    file: str
    page_index: int
    width_px: int
    height_px: int
    width_mm: float
    height_mm: float
    source_method: str


@dataclass(frozen=True)
class TableCaptureResult:
    fragments: list[TablePdfFragment] = field(default_factory=list)
    used_blank_doc_fallback: bool = False
    hard_table: bool = False
    failure_code: str | None = None
    diagnostic_code: str | None = None


@dataclass(frozen=True)
class TableProcessContext:
    owner: Any
    table: Any
    parent_node: Any
    current_section_key: str