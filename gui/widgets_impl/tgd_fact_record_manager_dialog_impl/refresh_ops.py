from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

from core.tgd_data_management_impl.agency_agent_query import query_agency_agents
from core.tgd_data_management_impl.excel_io_impl.text_utils import (
    _applicant_id_type_text_from_code,
    _applicant_type_text_from_code,
    _format_merged_address,
)
from core.tgd_data_management_impl.fact_record_query import query_fact_records_for_manager
from gui.widgets_impl import GraphicCheckBox
from gui.widgets_impl.tgd_fact_record_manager_item_ops import on_item_changed
from gui.widgets_impl.tgd_fact_record_manager_utils import _norm_text


class _RefreshOpsMixin:
    def _get_fact_group_name_filter_text(self) -> str:
        try:
            for cb in self._fact_filter_widgets.values():
                if getattr(cb, "col", "") == "group_name":
                    return _norm_text(cb.currentText())
        except Exception:
            pass
        return ""

    def _get_filters(self) -> dict:
        filters = {}
        # Fact filters
        for c, cb in self._fact_filter_widgets.items():
            txt = cb.currentText().strip()
            if txt:
                filters[cb.col] = txt
        # Agency filters
        for c, cb in self._agency_filter_widgets.items():
            txt = cb.currentText().strip()
            if txt:
                k = cb.col
                if getattr(cb, "scope", "") == "agency":
                    if k == "agency_name":
                        k = "agency_ref_name"
                    elif k == "agency_code":
                        k = "agency_ref_code"
                filters[k] = txt
        return filters

    def _on_query_clicked(self) -> None:
        self._refresh_current_tab()

    def _on_tab_changed(self, index: int) -> None:
        self._refresh_current_tab()

    def _refresh_current_tab(self) -> None:
        if self.tabs.currentIndex() == 0:
            if self.fact_table_left is not None and self.fact_table_right is not None:
                self._refresh_fact_table()
        else:
            if self.agency_table is not None:
                self._refresh_agency_table()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        on_item_changed(self, item)

    def _refresh_fact_table(self) -> None:
        self._dirty = False
        f = self._get_filters()
        res = query_fact_records_for_manager(
            group_name=f.get("group_name", ""),
            applicant_name=f.get("applicant_name", ""),
            applicant_id_no=f.get("applicant_id_no", ""),
            inventor_name=f.get("inventor_name", ""),
            inventor_id_no=f.get("inventor_id_no", ""),
            agency_ref_name=f.get("agency_ref_name", ""),
            agency_ref_code=f.get("agency_ref_code", ""),
            agent_name=f.get("agent_name", ""),
            limit=500,
        )

        rows = res.records or []

        self.fact_table_left.blockSignals(True)
        self.fact_table_right.blockSignals(True)

        self.fact_table_left.setRowCount(1 + len(rows))
        self.fact_table_right.setRowCount(1 + len(rows))
        self._init_filter_row_lock(
            self.fact_table_left,
            set(getattr(self, "_fact_left_filter_columns", {1, 2, 5})),
        )
        self._init_filter_row_lock(
            self.fact_table_right,
            set(getattr(self, "_fact_right_filter_columns", {1, 3, 5, 6, 7})),
        )

        for i, r in enumerate(rows):
            ridx = i + 1
            rid = r.get("id")

            cb_left = GraphicCheckBox(str(ridx))
            try:
                cb_left.setProperty("class", "TableRowCheck")
            except Exception:
                pass
            try:
                cb_left.setProperty("_tgd_id", rid)
            except Exception:
                pass
            try:
                cb_left.blockSignals(True)
                cb_left.setChecked(bool(rid is not None and int(rid) in self._checked_fact_ids))
                cb_left.blockSignals(False)
            except Exception:
                try:
                    cb_left.blockSignals(False)
                except Exception:
                    pass
            try:
                cb_left.toggled.connect(self._on_fact_row_checkbox_toggled)
            except Exception:
                pass
            try:
                self.fact_table_left.setCellWidget(ridx, 0, cb_left)
            except Exception:
                pass

            cb_right = GraphicCheckBox(str(ridx))
            try:
                cb_right.setProperty("class", "TableRowCheck")
            except Exception:
                pass
            try:
                cb_right.setProperty("_tgd_id", rid)
            except Exception:
                pass
            try:
                cb_right.blockSignals(True)
                cb_right.setChecked(bool(rid is not None and int(rid) in self._checked_fact_ids))
                cb_right.blockSignals(False)
            except Exception:
                try:
                    cb_right.blockSignals(False)
                except Exception:
                    pass
            try:
                cb_right.toggled.connect(self._on_fact_row_checkbox_toggled)
            except Exception:
                pass
            try:
                self.fact_table_right.setCellWidget(ridx, 0, cb_right)
            except Exception:
                pass

            def _item(txt):
                it = QTableWidgetItem(_norm_text(txt))
                it.setData(Qt.UserRole, rid)
                return it

            # Left
            # 0:Name, 1:Type, 2:IDType, 3:IDNo, 4:Phone
            self.fact_table_left.setItem(ridx, 1, _item(r.get("group_name")))
            self.fact_table_left.setItem(ridx, 2, _item(r.get("applicant_name")))
            self.fact_table_left.setItem(
                ridx,
                3,
                _item(_applicant_type_text_from_code(r.get("applicant_type_code"))),
            )
            self.fact_table_left.setItem(
                ridx,
                4,
                _item(_applicant_id_type_text_from_code(r.get("applicant_id_type_code"))),
            )
            self.fact_table_left.setItem(ridx, 5, _item(r.get("applicant_id_no")))

            app_addr_full = _format_merged_address(
                province_code=_norm_text(r.get("applicant_province_code")),
                city_code=_norm_text(r.get("applicant_city_code")),
                detail=_norm_text(r.get("applicant_address")),
                zip_code="",  # Zip is in separate column
                masked=False,
            )
            self.fact_table_left.setItem(ridx, 6, _item(app_addr_full))
            self.fact_table_left.setItem(ridx, 7, _item(r.get("applicant_zip")))
            self.fact_table_left.setItem(ridx, 8, _item(r.get("applicant_phone")))
            self.fact_table_left.setItem(ridx, 9, _item(r.get("applicant_email")))

            self.fact_table_left.setItem(ridx, 10, _item(r.get("contact_name")))
            self.fact_table_left.setItem(ridx, 11, _item(r.get("contact_phone")))
            self.fact_table_left.setItem(ridx, 12, _item(r.get("contact_email")))
            c_addr = _format_merged_address(
                province_code=_norm_text(r.get("contact_province_code")),
                city_code=_norm_text(r.get("contact_city_code")),
                detail=_norm_text(r.get("contact_street")),
                zip_code="",
                masked=False,
            )
            self.fact_table_left.setItem(ridx, 13, _item(c_addr))
            self.fact_table_left.setItem(ridx, 14, _item(r.get("contact_zip")))

            # Right
            # 0:Check, 1:InvName, 2:InvIDType, 3:InvIDNo, 4:Nat, 5:CtName, 6:CtPhone, 7:CtEmail, 8:CtAddr, 9:CtZip, 10:Group, 11:POA, 12:AgName, 13:AgCode
            self.fact_table_right.setItem(ridx, 1, _item(r.get("inventor_name")))
            self.fact_table_right.setItem(ridx, 2, _item(r.get("inventor_id_type")))
            self.fact_table_right.setItem(ridx, 3, _item(r.get("inventor_id_no")))
            self.fact_table_right.setItem(ridx, 4, _item(r.get("inventor_nationality_code")))
            self.fact_table_right.setItem(ridx, 5, _item(r.get("power_of_attorney_no")))
            self.fact_table_right.setItem(ridx, 6, _item(r.get("agency_ref_name")))
            self.fact_table_right.setItem(ridx, 7, _item(r.get("agency_ref_code")))

        self.fact_table_left.blockSignals(False)
        self.fact_table_right.blockSignals(False)

        self._apply_fact_checked_state_to_visible_rows()

    def _refresh_agency_table(self) -> None:
        self._dirty = False
        f = self._get_filters()
        res = query_agency_agents(
            agency_name=f.get("agency_ref_name", ""),
            agency_code=f.get("agency_ref_code", ""),
            agent_name=f.get("agent_name", ""),
            limit=500,
        )

        rows = res.records or []
        self.agency_table.blockSignals(True)
        self.agency_table.setRowCount(1 + len(rows))
        self._init_filter_row_lock(
            self.agency_table,
            set(getattr(self, "_agency_filter_columns", {1, 2, 3})),
        )

        # 0:Check, 1:Name, 2:Code, 3:Agent, 4:Cert, 5:Phone
        for i, r in enumerate(rows):
            ridx = i + 1
            rid = r.get("id")

            cb = GraphicCheckBox(str(ridx))
            try:
                cb.setProperty("class", "TableRowCheck")
            except Exception:
                pass
            try:
                cb.setProperty("_tgd_id", rid)
            except Exception:
                pass
            try:
                cb.blockSignals(True)
                cb.setChecked(bool(rid is not None and int(rid) in self._checked_agency_ids))
                cb.blockSignals(False)
            except Exception:
                try:
                    cb.blockSignals(False)
                except Exception:
                    pass
            try:
                cb.toggled.connect(self._on_agency_row_checkbox_toggled)
            except Exception:
                pass
            try:
                self.agency_table.setCellWidget(ridx, 0, cb)
            except Exception:
                pass

            def _item(txt):
                it = QTableWidgetItem(_norm_text(txt))
                it.setData(Qt.UserRole, rid)
                return it

            self.agency_table.setItem(ridx, 1, _item(r.get("agency_name")))
            self.agency_table.setItem(ridx, 2, _item(r.get("agency_code")))
            self.agency_table.setItem(ridx, 3, _item(r.get("agent_name")))
            self.agency_table.setItem(ridx, 4, _item(r.get("agent_cert_no")))
            self.agency_table.setItem(ridx, 5, _item(r.get("agent_phone")))

        self.agency_table.blockSignals(False)

        self._apply_agency_checked_state_to_visible_rows()
