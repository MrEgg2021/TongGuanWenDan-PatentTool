from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from gui.widgets_impl.tgd_fact_record_manager_utils import _validate_china_id, _validate_social_credit_code


class _ItemOpsDialog(Protocol):
    fact_table_left: QTableWidget | None
    fact_table_right: QTableWidget | None

    _dirty: bool


def _trigger_revalidation_if_needed(dlg: _ItemOpsDialog, tbl: QTableWidget, row: int, col: int) -> bool:
    # 1. Trigger re-validation of ID No if ID Type changes
    if tbl == dlg.fact_table_left and col == 4:
        it_no = tbl.item(row, 5)
        if it_no:
            on_item_changed(dlg, it_no)
        return True
    if tbl == dlg.fact_table_right and col == 2:
        it_no = tbl.item(row, 3)
        if it_no:
            on_item_changed(dlg, it_no)
        return True
    return False


def _validate_id_no_if_target_column(
    dlg: _ItemOpsDialog,
    tbl: QTableWidget,
    row: int,
    col: int,
    text: str,
) -> tuple[bool, str, int]:
    # 2. Extract context for validation
    target_id_col = -1
    id_type = ""
    is_valid = True
    error_msg = ""

    if tbl == dlg.fact_table_left and col == 5:
        target_id_col = 5
        it_type = tbl.item(row, 4)
        if it_type:
            id_type = it_type.text().strip()
        if "社会信用代码" in id_type:
            if not _validate_social_credit_code(text):
                is_valid = False
                error_msg = "统一社会信用代码格式不正确（应为18位）"
        elif "身份证" in id_type:
            if not _validate_china_id(text):
                is_valid = False
                error_msg = "身份证号格式不正确（应为18位）"

    elif tbl == dlg.fact_table_right and col == 3:
        target_id_col = 3
        it_type = tbl.item(row, 2)
        if it_type:
            id_type = it_type.text().strip()
        if "身份证" in id_type:
            if not _validate_china_id(text):
                is_valid = False
                error_msg = "身份证号格式不正确（应为18位）"

    return bool(is_valid), str(error_msg), int(target_id_col)


def _check_internal_duplicate_id_no(tbl: QTableWidget, row: int, target_id_col: int, text: str) -> tuple[bool, str]:
    # 3. Real-time Internal Duplicate Check for ID No
    is_duplicate = False
    error_msg = ""

    if text and target_id_col != -1:
        for r in range(1, tbl.rowCount()):
            if r == row:
                continue
            it_other = tbl.item(r, target_id_col)
            if it_other and it_other.text().strip() == text:
                is_duplicate = True
                error_msg = f"该证件号与第 {r} 行重复"
                break

    return bool(is_duplicate), str(error_msg)


def _apply_visual_feedback(
    tbl: QTableWidget,
    item: QTableWidgetItem,
    *,
    is_valid: bool,
    is_duplicate: bool,
    error_msg: str,
) -> None:
    # 4. Apply Visual Feedback
    tbl.blockSignals(True)
    if not is_valid:
        item.setBackground(QBrush(QColor("#fee2e2"))) # light red
        item.setToolTip(error_msg)
    elif is_duplicate:
        item.setBackground(QBrush(QColor("#ffedd5"))) # light orange (duplicate hint)
        item.setToolTip(error_msg)
    else:
        item.setBackground(QBrush(QColor("#fef9c3"))) # light yellow (dirty hint)
        item.setToolTip("")

    item.setForeground(QBrush(QColor("#000000")))
    item.setData(Qt.UserRole + 1, True) # Set Dirty flag
    tbl.blockSignals(False)


def on_item_changed(dlg: _ItemOpsDialog, item: QTableWidgetItem) -> None:
    if item.row() == 0: # Filter row
        return

    tbl = item.tableWidget()
    if tbl is None:
        return
    row = item.row()
    col = item.column()
    text = item.text().strip()

    # Validation and Duplicate Check
    is_valid = True
    error_msg = ""
    is_duplicate = False

    if _trigger_revalidation_if_needed(dlg, tbl, row, col):
        return

    is_valid, error_msg, target_id_col = _validate_id_no_if_target_column(dlg, tbl, row, col, text)

    if is_valid:
        is_duplicate, dup_msg = _check_internal_duplicate_id_no(tbl, row, target_id_col, text)
        if is_duplicate:
            error_msg = dup_msg

    _apply_visual_feedback(tbl, item, is_valid=is_valid, is_duplicate=is_duplicate, error_msg=error_msg)

    dlg._dirty = True
