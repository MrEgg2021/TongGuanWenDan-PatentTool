from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from core.logging_utils import swallow_exception
from core.request_form_impl.region_infer import _infer_region_from_single_address
from core.request_form_xml_impl.normalize import _normalize_applicant_type_code
from core.tgd_data_management_impl.excel_io_impl.text_utils import _normalize_applicant_id_type_code
from gui.widgets_impl.tgd_fact_record_manager_utils import _make_record_hash, _norm_text


class _SaveFactDialog(Protocol):
    fact_table_left: QTableWidget
    fact_table_right: QTableWidget

    _deleted_fact_ids: list[int]

    def _refresh_fact_table(self) -> None: ...


def _has_any_dirty_flag(dlg: _SaveFactDialog, row: int) -> bool:
    for t in [dlg.fact_table_left, dlg.fact_table_right]:
        for c in range(t.columnCount()):
            it = t.item(row, c)
            if it and it.data(Qt.UserRole + 1):
                return True
    return False


def _t(tbl: QTableWidget, row: int, col: int) -> str:
    it = tbl.item(row, col)
    return _norm_text(it.text()) if it else ""


def _infer_app_address(app_addr_val: str, app_zip_val: str) -> tuple[str, str, str, str]:
    app_prov, app_city, app_addr, app_zip = "", "", "", app_zip_val
    if app_addr_val:
        app_rec = {"province": "", "city": "", "address": app_addr_val}
        try:
            _infer_region_from_single_address(app_rec, "address")
        except Exception:
            swallow_exception("_infer_region_from_single_address_app")
            pass
        app_prov = app_rec.get("province_code", "")
        app_city = app_rec.get("city_code", "")
        app_addr = app_rec.get("address", "")
    return _norm_text(app_prov), _norm_text(app_city), _norm_text(app_addr), _norm_text(app_zip)


def _infer_contact_address(ct_addr_full: str) -> tuple[str, str, str]:
    ct_prov, ct_city, ct_street = "", "", ""
    if ct_addr_full:
        c_rec = {"province": "", "city": "", "street": ct_addr_full}
        try:
            _infer_region_from_single_address(c_rec, "street")
        except Exception:
            swallow_exception("_infer_region_from_single_address_contact")
            pass
        ct_prov = c_rec.get("province_code", "")
        ct_city = c_rec.get("city_code", "")
        ct_street = c_rec.get("street", "")
    return _norm_text(ct_prov), _norm_text(ct_city), _norm_text(ct_street)


def _build_pending_row(dlg: _SaveFactDialog, r: int) -> dict | None:
    item_id = None
    it0 = dlg.fact_table_left.item(r, 1)
    if it0:
        item_id = it0.data(Qt.UserRole)

    is_dirty = False
    if item_id is None:
        is_dirty = True
    else:
        is_dirty = _has_any_dirty_flag(dlg, r)

    if not is_dirty:
        return None

    group_name = _t(dlg.fact_table_left, r, 1)
    app_name = _t(dlg.fact_table_left, r, 2)
    app_type = _t(dlg.fact_table_left, r, 3)
    app_id_type = _t(dlg.fact_table_left, r, 4)
    app_id_no = _t(dlg.fact_table_left, r, 5)
    app_addr_val = _t(dlg.fact_table_left, r, 6)
    app_zip_val = _t(dlg.fact_table_left, r, 7)
    app_phone = _t(dlg.fact_table_left, r, 8)
    app_email = _t(dlg.fact_table_left, r, 9)

    ct_name = _t(dlg.fact_table_left, r, 10)
    ct_phone = _t(dlg.fact_table_left, r, 11)
    ct_email = _t(dlg.fact_table_left, r, 12)
    ct_addr_full = _t(dlg.fact_table_left, r, 13)
    ct_zip = _t(dlg.fact_table_left, r, 14)

    inv_name = _t(dlg.fact_table_right, r, 1)
    inv_id_type = _t(dlg.fact_table_right, r, 2)
    inv_id_no = _t(dlg.fact_table_right, r, 3)
    inv_nat = _t(dlg.fact_table_right, r, 4) or "CN"
    poa = _t(dlg.fact_table_right, r, 5)
    ag_name = _t(dlg.fact_table_right, r, 6)
    ag_code = _t(dlg.fact_table_right, r, 7)

    if not app_name and not inv_name:
        return None

    app_type_code = _normalize_applicant_type_code("", app_type, "")
    app_id_type_code = _normalize_applicant_id_type_code(app_id_type)

    app_prov, app_city, app_addr, app_zip = _infer_app_address(app_addr_val, app_zip_val)
    ct_prov, ct_city, ct_street = _infer_contact_address(ct_addr_full)

    record_hash = _make_record_hash(
        app_name, app_type_code, app_id_type_code, app_id_no,
        app_prov, app_city, app_addr, app_zip, app_phone, app_email,
        inv_name, inv_id_type, inv_id_no, inv_nat,
        ct_name, ct_phone, ct_email, ct_prov, ct_city, ct_street, ct_zip,
        group_name, poa, ag_code
    )

    return {
        "row": int(r),
        "id": item_id,
        "record_hash": record_hash,
        "applicant_name": app_name,
        "inventor_name": inv_name,
        "group_name": group_name,
        "app_type_code": app_type_code,
        "app_id_type_code": app_id_type_code,
        "app_id_no": app_id_no,
        "app_prov": app_prov,
        "app_city": app_city,
        "app_addr": app_addr,
        "app_zip": app_zip,
        "app_phone": app_phone,
        "app_email": app_email,
        "inv_id_type": inv_id_type,
        "inv_id_no": inv_id_no,
        "inv_nat": inv_nat,
        "ct_name": ct_name,
        "ct_phone": ct_phone,
        "ct_email": ct_email,
        "ct_prov": ct_prov,
        "ct_city": ct_city,
        "ct_street": ct_street,
        "ct_zip": ct_zip,
        "poa": poa,
        "ag_name": ag_name,
        "ag_code": ag_code,
    }


def _collect_pending(dlg: _SaveFactDialog) -> list[dict]:
    row_count = dlg.fact_table_left.rowCount()
    pending: list[dict] = []
    for r in range(1, row_count):
        p = _build_pending_row(dlg, r)
        if p is None:
            continue
        pending.append(p)
    return pending
