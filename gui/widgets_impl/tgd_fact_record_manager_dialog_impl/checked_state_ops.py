from __future__ import annotations

from PySide6.QtCore import Qt

from gui.widgets_impl import GraphicCheckBox


class _CheckedStateOpsMixin:
    def _get_fact_row_id(self, row: int) -> int | None:
        if self.fact_table_left is None:
            return None
        try:
            it = self.fact_table_left.item(row, 1)
            if it is None:
                it = self.fact_table_left.item(row, 0)
            if it is None:
                return None
            rid = it.data(Qt.UserRole)
            if rid is None:
                return None
            return int(rid)
        except Exception:
            return None

    def _get_agency_row_id(self, row: int) -> int | None:
        if self.agency_table is None:
            return None
        try:
            it = self.agency_table.item(row, 1)
            if it is None:
                it = self.agency_table.item(row, 0)
            if it is None:
                return None
            rid = it.data(Qt.UserRole)
            if rid is None:
                return None
            return int(rid)
        except Exception:
            return None

    def _get_checked_fact_row_indices(self) -> list[int]:
        rows: list[int] = []
        if self.fact_table_left is None:
            return rows
        try:
            rc = int(self.fact_table_left.rowCount())
            for r in range(1, rc):
                w = self.fact_table_left.cellWidget(r, 0)
                if isinstance(w, GraphicCheckBox) and w.isChecked():
                    rows.append(int(r))
        except Exception:
            pass
        return rows

    def _get_checked_agency_row_indices(self) -> list[int]:
        rows: list[int] = []
        if self.agency_table is None:
            return rows
        try:
            rc = int(self.agency_table.rowCount())
            for r in range(1, rc):
                w = self.agency_table.cellWidget(r, 0)
                if isinstance(w, GraphicCheckBox) and w.isChecked():
                    rows.append(int(r))
        except Exception:
            pass
        return rows

    def _apply_fact_checked_state_to_visible_rows(self) -> None:
        if self.fact_table_left is None or self.fact_table_right is None:
            return
        try:
            rc = int(self.fact_table_left.rowCount())
            for r in range(1, rc):
                rid = self._get_fact_row_id(r)
                checked = rid in self._checked_fact_ids if rid is not None else False
                for tbl in [self.fact_table_left, self.fact_table_right]:
                    w = tbl.cellWidget(r, 0)
                    if isinstance(w, GraphicCheckBox):
                        w.blockSignals(True)
                        w.setChecked(checked)
                        w.blockSignals(False)
        except Exception:
            pass

    def _apply_agency_checked_state_to_visible_rows(self) -> None:
        if self.agency_table is None:
            return
        try:
            rc = int(self.agency_table.rowCount())
            for r in range(1, rc):
                rid = self._get_agency_row_id(r)
                checked = rid in self._checked_agency_ids if rid is not None else False
                w = self.agency_table.cellWidget(r, 0)
                if isinstance(w, GraphicCheckBox):
                    w.blockSignals(True)
                    w.setChecked(checked)
                    w.blockSignals(False)
        except Exception:
            pass

    def _on_fact_row_checkbox_toggled(self, checked: bool) -> None:
        rid = self.sender().property("_tgd_id")
        if rid is None:
            return
        try:
            rid_int = int(rid)
            if checked:
                self._checked_fact_ids.add(rid_int)
            else:
                self._checked_fact_ids.discard(rid_int)
            self._apply_fact_checked_state_to_visible_rows()
        except Exception:
            pass

    def _on_agency_row_checkbox_toggled(self, checked: bool) -> None:
        rid = self.sender().property("_tgd_id")
        if rid is None:
            return
        try:
            rid_int = int(rid)
            if checked:
                self._checked_agency_ids.add(rid_int)
            else:
                self._checked_agency_ids.discard(rid_int)
            self._apply_agency_checked_state_to_visible_rows()
        except Exception:
            pass

    def _select_all_fact_rows(self) -> None:
        if self.fact_table_left is None:
            return
        try:
            rc = self.fact_table_left.rowCount()
            for r in range(1, rc):
                rid = self._get_fact_row_id(r)
                if rid is not None:
                    self._checked_fact_ids.add(int(rid))
            self._apply_fact_checked_state_to_visible_rows()
        except Exception:
            pass

    def _deselect_all_fact_rows(self) -> None:
        if self.fact_table_left is None:
            return
        try:
            rc = self.fact_table_left.rowCount()
            for r in range(1, rc):
                rid = self._get_fact_row_id(r)
                if rid is not None:
                    self._checked_fact_ids.discard(int(rid))
            self._apply_fact_checked_state_to_visible_rows()
        except Exception:
            pass

    def _select_all_agency_rows(self) -> None:
        if self.agency_table is None:
            return
        try:
            rc = self.agency_table.rowCount()
            for r in range(1, rc):
                rid = self._get_agency_row_id(r)
                if rid is not None:
                    self._checked_agency_ids.add(int(rid))
            self._apply_agency_checked_state_to_visible_rows()
        except Exception:
            pass

    def _deselect_all_agency_rows(self) -> None:
        if self.agency_table is None:
            return
        try:
            rc = self.agency_table.rowCount()
            for r in range(1, rc):
                rid = self._get_agency_row_id(r)
                if rid is not None:
                    self._checked_agency_ids.discard(int(rid))
            self._apply_agency_checked_state_to_visible_rows()
        except Exception:
            pass

    def _update_fact_row_numbers(self) -> None:
        if self.fact_table_left is None or self.fact_table_right is None:
            return
        rc = self.fact_table_left.rowCount()
        for r in range(1, rc):
            for tbl in [self.fact_table_left, self.fact_table_right]:
                w = tbl.cellWidget(r, 0)
                if isinstance(w, GraphicCheckBox):
                    w.setText(str(r))

    def _update_agency_row_numbers(self) -> None:
        if self.agency_table is None:
            return
        rc = self.agency_table.rowCount()
        for r in range(1, rc):
            w = self.agency_table.cellWidget(r, 0)
            if isinstance(w, GraphicCheckBox):
                w.setText(str(r))
