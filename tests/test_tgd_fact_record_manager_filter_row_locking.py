from __future__ import annotations

import types
import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QTableWidgetItem

    _PYSIDE6_AVAILABLE = True
except Exception:
    QApplication = None  # type: ignore[assignment]
    QTableWidgetItem = object  # type: ignore[assignment]
    Qt = None  # type: ignore[assignment]
    _PYSIDE6_AVAILABLE = False


@unittest.skipUnless(_PYSIDE6_AVAILABLE, "PySide6 not installed; UI runtime tests skipped.")
class TgdFactManagerFilterRowLockingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _assert_filter_row_state(self, table, filter_columns: set[int]) -> None:
        self.assertIsNotNone(table)
        self.assertGreaterEqual(int(table.rowCount()), 1)
        self.assertGreater(int(table.columnCount()), 0)

        item0 = table.item(0, 0)
        self.assertIsNotNone(item0)
        self.assertFalse(bool(item0.flags() & Qt.ItemIsEditable))

        for col in range(1, int(table.columnCount())):
            widget = table.cellWidget(0, col)
            item = table.item(0, col)
            if col in filter_columns:
                self.assertIsNotNone(widget, f"expected filter widget at col={col}")
            else:
                self.assertIsNone(widget, f"non-filter col should not have widget, col={col}")
                self.assertIsNotNone(item, f"non-filter col should have placeholder item, col={col}")
                self.assertFalse(bool(item.flags() & Qt.ItemIsEditable), f"non-filter col must be read-only, col={col}")

    def test_filter_row_non_filter_columns_are_locked_on_init(self) -> None:
        from gui.widgets_impl.tgd_fact_record_manager_dialog import TgdFactRecordManagerDialog

        dlg = TgdFactRecordManagerDialog(embedded=True)
        try:
            self._assert_filter_row_state(dlg.fact_table_left, {1, 2, 5})
            self._assert_filter_row_state(dlg.fact_table_right, {1, 3, 5, 6, 7})
            self._assert_filter_row_state(dlg.agency_table, {1, 2, 3})
        finally:
            dlg.close()
            dlg.deleteLater()

    def test_refresh_clears_non_filter_row_residue(self) -> None:
        from gui.widgets_impl.tgd_fact_record_manager_dialog import TgdFactRecordManagerDialog

        dlg = TgdFactRecordManagerDialog(embedded=True)
        try:
            # Simulate stale values in non-filter cells on row 0
            for table, col in ((dlg.fact_table_left, 6), (dlg.fact_table_right, 2), (dlg.agency_table, 4)):
                item = table.item(0, col)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(0, col, item)
                item.setText("stale-value")

            with (
                patch(
                    "gui.widgets_impl.tgd_fact_record_manager_dialog_impl.refresh_ops.query_fact_records_for_manager",
                    return_value=types.SimpleNamespace(records=[]),
                ),
                patch(
                    "gui.widgets_impl.tgd_fact_record_manager_dialog_impl.refresh_ops.query_agency_agents",
                    return_value=types.SimpleNamespace(records=[]),
                ),
            ):
                dlg._refresh_fact_table()
                dlg._refresh_agency_table()

            self.assertEqual((dlg.fact_table_left.item(0, 6).text() if dlg.fact_table_left.item(0, 6) else ""), "")
            self.assertEqual((dlg.fact_table_right.item(0, 2).text() if dlg.fact_table_right.item(0, 2) else ""), "")
            self.assertEqual((dlg.agency_table.item(0, 4).text() if dlg.agency_table.item(0, 4) else ""), "")

            self._assert_filter_row_state(dlg.fact_table_left, {1, 2, 5})
            self._assert_filter_row_state(dlg.fact_table_right, {1, 3, 5, 6, 7})
            self._assert_filter_row_state(dlg.agency_table, {1, 2, 3})
        finally:
            dlg.close()
            dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()

