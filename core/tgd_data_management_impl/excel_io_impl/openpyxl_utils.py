from __future__ import annotations


def _require_openpyxl():
    try:
        from openpyxl import Workbook, load_workbook

        return Workbook, load_workbook
    except Exception as e:
        raise RuntimeError(f"缺少依赖 openpyxl，无法进行 Excel 导入导出：{e}")
