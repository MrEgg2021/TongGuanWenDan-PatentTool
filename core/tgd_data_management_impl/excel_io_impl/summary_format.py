from __future__ import annotations

from .constants import _AGENCY_SHEET_NAME, _FACT_SHEET_NAME
from .models import ExcelImportSummary, SheetImportResult


def format_import_summary_text(summary: ExcelImportSummary, *, max_errors: int = 30) -> str:
    def _fmt_one(title: str, r: SheetImportResult) -> str:
        lines = [
            f"{title}：新增 {r.inserted}，更新 {r.updated}，跳过 {r.skipped}",
        ]
        if r.errors:
            lines.append("错误/警告：")
            for msg in r.errors[: max(0, int(max_errors))]:
                lines.append(f"- {msg}")
            if len(r.errors) > max_errors:
                lines.append(f"- ……（共 {len(r.errors)} 条，仅显示前 {max_errors} 条）")
        return "\n".join(lines)

    parts = [_fmt_one(_FACT_SHEET_NAME, summary.fact_records), _fmt_one(_AGENCY_SHEET_NAME, summary.agency_agents)]
    return "\n".join(parts).strip()
