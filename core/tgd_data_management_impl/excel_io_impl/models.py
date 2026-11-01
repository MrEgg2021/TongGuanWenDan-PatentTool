from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class SheetImportResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class ExcelImportSummary:
    fact_records: SheetImportResult = field(default_factory=SheetImportResult)
    agency_agents: SheetImportResult = field(default_factory=SheetImportResult)
