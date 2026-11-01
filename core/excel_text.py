from __future__ import annotations

from collections.abc import Iterable


def append_text_row(worksheet, values: Iterable[object]) -> None:
    """Append business text without letting openpyxl reinterpret '=...' as a formula."""
    worksheet.append(list(values))
    for cell in worksheet[worksheet.max_row]:
        if isinstance(cell.value, str):
            cell.data_type = "s"
