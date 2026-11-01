from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QTableWidgetItem

from core.request_form_impl.region_infer import _infer_region_from_single_address
from core.request_form_xml_impl.normalize import _normalize_applicant_type_code
from core.tgd_data_management_impl.excel_io_impl.text_utils import (
    _applicant_id_type_text_from_code,
    _applicant_type_text_from_code,
    _extract_zip_and_remove,
    _format_merged_address,
    _normalize_applicant_id_type_code,
)
from gui.dialog_utils import show_blocking_alert_modal
from gui.widgets_impl.request_form import dialog as request_form_dialog
from gui.widgets_impl.tgd_zip_import_review_debug_ops import zip_dbg
from gui.widgets_impl.tgd_zip_import_review_utils import _infer_applicant_id_type_code_from_id_no, _norm_text


def load_from_request_info(dlg) -> None:
    base_name = ""
    try:
        base_name = os.path.basename(dlg._source_file_path)
    except Exception:
        base_name = ""
    if base_name:
        dlg.file_label.setText(f"当前文件：{base_name}")
    else:
        dlg.file_label.setText("")

    rows, pre_errors = request_form_dialog._build_fact_records_from_request_info(dlg, dlg._initial_request_info)
    if pre_errors:
        show_blocking_alert_modal(dlg, "提示", "\n".join(pre_errors), primary_text="关闭", secondary_text="关闭")

    dlg._fact_rows = list(rows or [])
    for item in dlg._fact_rows:
        if not isinstance(item, dict):
            continue
        app = item.get("app") if isinstance(item.get("app"), dict) else None
        if not isinstance(app, dict):
            continue
        if not _norm_text(app.get("type_code")):
            t_code = _normalize_applicant_type_code("", _norm_text(app.get("type")), "")
            if _norm_text(t_code):
                app["type_code"] = _norm_text(t_code)
        if not _norm_text(app.get("id_type_code")):
            id_code = _normalize_applicant_id_type_code(_norm_text(app.get("id_type")))
            if not _norm_text(id_code):
                id_code = _infer_applicant_id_type_code_from_id_no(_norm_text(app.get("id_no")))
            if _norm_text(id_code):
                app["id_type_code"] = _norm_text(id_code)
        item["app"] = app

        inv = item.get("inv") if isinstance(item.get("inv"), dict) else None
        if isinstance(inv, dict):
            inv_nat = _norm_text(inv.get("nationality_code")) or "CN"
            if inv_nat:
                inv["nationality_code"] = inv_nat

            if (not _norm_text(inv.get("id_type"))) and inv_nat == "CN":
                inv["id_type"] = "居民身份证"
            item["inv"] = inv

    refresh_fact_table(dlg)

    try:
        update_fact_tab_layout(dlg)
    except Exception:
        pass

    try:
        ensure_fact_editor_prefilled(dlg)
    except Exception:
        pass

    dlg._dirty = False
    prefill_agency_table(dlg)

    try:
        zip_dbg(f"load_from_request_info rows={len(dlg._fact_rows or [])} pre_errors={len(pre_errors or [])}")
    except Exception:
        pass


def prefill_agency_table(dlg) -> None:
    agency_info = None
    try:
        agency_info = dlg._initial_request_info.get("agency_info")
    except Exception:
        agency_info = None

    if not isinstance(agency_info, dict):
        dlg.agency_table.setRowCount(0)
        return

    name = _norm_text(agency_info.get("name"))
    code = _norm_text(agency_info.get("code"))
    if not name and not code:
        dlg.agency_table.setRowCount(0)
        return

    agents: list[dict] = []
    raw_agents = None
    try:
        raw_agents = agency_info.get("agents")
    except Exception:
        raw_agents = None
    if isinstance(raw_agents, list):
        for a in raw_agents:
            if not isinstance(a, dict):
                continue
            an = _norm_text(a.get("name"))
            cert_no = _norm_text(a.get("cert_no"))
            phone = _norm_text(a.get("phone"))
            if not (an or cert_no or phone):
                continue
            agents.append({"name": an, "cert_no": cert_no, "phone": phone, "order": a.get("order")})

    if not agents:
        for k in ("agent1", "agent2"):
            a = agency_info.get(k)
            if not isinstance(a, dict):
                continue
            an = _norm_text(a.get("name"))
            cert_no = _norm_text(a.get("cert_no"))
            phone = _norm_text(a.get("phone"))
            if not (an or cert_no or phone):
                continue
            agents.append({"name": an, "cert_no": cert_no, "phone": phone, "order": a.get("order")})

    if agents:
        try:
            agents = sorted(agents, key=lambda x: int(_norm_text(x.get("order")) or "0"))
        except Exception:
            pass
        dlg.agency_table.setRowCount(len(agents))
        for i, a in enumerate(agents):
            dlg.agency_table.setItem(i, 0, QTableWidgetItem(name))
            dlg.agency_table.setItem(i, 1, QTableWidgetItem(code))
            dlg.agency_table.setItem(i, 2, QTableWidgetItem(_norm_text(a.get("name"))))
            dlg.agency_table.setItem(i, 3, QTableWidgetItem(_norm_text(a.get("cert_no"))))
            dlg.agency_table.setItem(i, 4, QTableWidgetItem(_norm_text(a.get("phone"))))
        return

    dlg.agency_table.setRowCount(1)
    dlg.agency_table.setItem(0, 0, QTableWidgetItem(name))
    dlg.agency_table.setItem(0, 1, QTableWidgetItem(code))
    dlg.agency_table.setItem(0, 2, QTableWidgetItem(""))
    dlg.agency_table.setItem(0, 3, QTableWidgetItem(""))
    dlg.agency_table.setItem(0, 4, QTableWidgetItem(""))


def refresh_fact_table(dlg) -> None:
    rows = dlg._fact_rows or []
    dlg.fact_table.setRowCount(len(rows))

    for i, item in enumerate(rows):
        app = item.get("app") if isinstance(item.get("app"), dict) else {}
        inv = item.get("inv") if isinstance(item.get("inv"), dict) else {}

        dlg.fact_table.setItem(i, 0, QTableWidgetItem(_norm_text(app.get("name"))))
        dlg.fact_table.setItem(i, 1, QTableWidgetItem(_applicant_type_text_from_code(app.get("type_code") or app.get("type"))))
        dlg.fact_table.setItem(
            i,
            2,
            QTableWidgetItem(_applicant_id_type_text_from_code(app.get("id_type_code") or app.get("id_type"))),
        )
        dlg.fact_table.setItem(i, 3, QTableWidgetItem(_norm_text(app.get("id_no"))))
        dlg.fact_table.setItem(i, 4, QTableWidgetItem(_norm_text(app.get("phone"))))
        dlg.fact_table.setItem(i, 5, QTableWidgetItem(_norm_text(inv.get("name"))))
        dlg.fact_table.setItem(i, 6, QTableWidgetItem(_norm_text(inv.get("id_no"))))

        dlg.fact_table.setItem(i, 7, QTableWidgetItem(_norm_text(item.get("group_name"))))
        dlg.fact_table.setItem(i, 8, QTableWidgetItem(_norm_text(item.get("power_of_attorney_no"))))
        dlg.fact_table.setItem(i, 9, QTableWidgetItem(_norm_text(item.get("agency_ref_name"))))
        dlg.fact_table.setItem(i, 10, QTableWidgetItem(_norm_text(item.get("agency_ref_code"))))

    if len(rows) > 0:
        try:
            dlg.fact_table.selectRow(0)
        except Exception:
            pass


def ensure_fact_editor_prefilled(dlg) -> None:
    if not (dlg._fact_rows or []):
        dlg._current_fact_row_idx = None
        return

    row = -1
    try:
        row = int(dlg.fact_table.currentRow())
    except Exception:
        row = -1
    if row < 0:
        row = 0
        try:
            dlg.fact_table.selectRow(0)
        except Exception:
            pass

    dlg._current_fact_row_idx = int(row)
    load_fact_editor_from_row(dlg, int(row))


def update_fact_tab_layout(dlg) -> None:
    row_count = len(dlg._fact_rows or [])
    lay = getattr(dlg, "_fact_tab_layout", None)
    editor = getattr(dlg, "_fact_editor_frame", None)

    if lay is not None and editor is not None:
        try:
            if row_count <= 1:
                lay.setStretchFactor(dlg.fact_table, 0)
                lay.setStretchFactor(editor, 1)
            else:
                lay.setStretchFactor(dlg.fact_table, 1)
                lay.setStretchFactor(editor, 0)
        except Exception:
            pass

    if row_count <= 1:
        header_h = 0
        row_h = 0
        try:
            header_h = int(dlg.fact_table.horizontalHeader().height())
        except Exception:
            header_h = 0
        try:
            row_h = int(dlg.fact_table.rowHeight(0)) if row_count == 1 else 0
        except Exception:
            row_h = 0
        frame_w = 0
        try:
            frame_w = int(dlg.fact_table.frameWidth())
        except Exception:
            frame_w = 0
        try:
            dlg.fact_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        except Exception:
            pass
        max_h = max(90, header_h + row_h + frame_w * 2 + 12)
        try:
            dlg.fact_table.setMaximumHeight(int(max_h))
        except Exception:
            pass
    else:
        try:
            dlg.fact_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        except Exception:
            pass
        try:
            dlg.fact_table.setMaximumHeight(16777215)
        except Exception:
            pass


def on_fact_selection_changed(dlg) -> None:
    row = None
    try:
        row = dlg.fact_table.currentRow()
    except Exception:
        row = None
    if row is None or int(row) < 0:
        dlg._current_fact_row_idx = None
        return

    dlg._current_fact_row_idx = int(row)
    load_fact_editor_from_row(dlg, int(row))


def load_fact_editor_from_row(dlg, idx: int) -> None:
    if idx < 0 or idx >= len(dlg._fact_rows):
        return

    dlg._loading_fact_editor = True
    try:
        item = dlg._fact_rows[idx]
        app = item.get("app") if isinstance(item.get("app"), dict) else {}
        inv = item.get("inv") if isinstance(item.get("inv"), dict) else {}
        contact = item.get("contact") if isinstance(item.get("contact"), dict) else {}

        set_combo_text(dlg, dlg.fact_applicant_type, _applicant_type_text_from_code(app.get("type_code") or app.get("type")))
        set_combo_text(
            dlg,
            dlg.fact_applicant_id_type,
            _applicant_id_type_text_from_code(app.get("id_type_code") or app.get("id_type")),
        )

        dlg.fact_applicant_name.setText(_norm_text(app.get("name")))
        dlg.fact_applicant_id_no.setText(_norm_text(app.get("id_no")))
        dlg.fact_applicant_phone.setText(_norm_text(app.get("phone")))
        dlg.fact_applicant_email.setText(_norm_text(app.get("email")))

        app_addr = _format_merged_address(
            province_code=_norm_text(app.get("province_code")),
            city_code=_norm_text(app.get("city_code")),
            detail=_norm_text(app.get("address")),
            zip_code=_norm_text(app.get("zip")),
            masked=False,
        )
        dlg.fact_applicant_addr_full.setText(_norm_text(app_addr))

        dlg.fact_inventor_name.setText(_norm_text(inv.get("name")))
        set_combo_text(dlg, dlg.fact_inventor_id_type, _norm_text(inv.get("id_type")))
        dlg.fact_inventor_id_no.setText(_norm_text(inv.get("id_no")))
        dlg.fact_inventor_nat.setText(_norm_text(inv.get("nationality_code")) or "CN")

        dlg.fact_contact_name.setText(_norm_text(contact.get("name")))
        dlg.fact_contact_phone.setText(_norm_text(contact.get("phone")))
        dlg.fact_contact_email.setText(_norm_text(contact.get("email")))
        dlg.fact_contact_zip.setText(_norm_text(contact.get("zip")))

        c_addr = _format_merged_address(
            province_code=_norm_text(contact.get("province_code")),
            city_code=_norm_text(contact.get("city_code")),
            detail=_norm_text(contact.get("street")),
            zip_code="",
            masked=False,
        )
        dlg.fact_contact_addr_full.setText(_norm_text(c_addr))

        dlg.fact_group_name.setText(_norm_text(item.get("group_name")))
        dlg.fact_poa_no.setText(_norm_text(item.get("power_of_attorney_no")))
        dlg.fact_agency_name.setText(_norm_text(item.get("agency_ref_name")))
        dlg.fact_agency_code.setText(_norm_text(item.get("agency_ref_code")))
    finally:
        dlg._loading_fact_editor = False


def set_combo_text(dlg, combo: QComboBox, text: str) -> None:
    s = _norm_text(text)
    if not s:
        try:
            combo.setCurrentIndex(0)
        except Exception:
            pass
        if combo.isEditable():
            try:
                combo.setCurrentText("")
            except Exception:
                pass
        return

    idx = -1
    try:
        for i in range(combo.count()):
            if _norm_text(combo.itemText(i)) == s:
                idx = i
                break
    except Exception:
        idx = -1
    if idx >= 0:
        try:
            combo.setCurrentIndex(idx)
        except Exception:
            pass
    else:
        if combo.isEditable():
            try:
                combo.setCurrentText(s)
            except Exception:
                pass


def on_fact_editor_changed(dlg, *args) -> None:
    if dlg._loading_fact_editor:
        return

    idx = dlg._current_fact_row_idx
    if idx is None:
        return
    if idx < 0 or idx >= len(dlg._fact_rows):
        return

    item = dlg._fact_rows[idx]
    app = item.get("app") if isinstance(item.get("app"), dict) else {}
    inv = item.get("inv") if isinstance(item.get("inv"), dict) else {}
    contact = item.get("contact") if isinstance(item.get("contact"), dict) else {}

    applicant_name = _norm_text(dlg.fact_applicant_name.text())
    applicant_type_text = _norm_text(dlg.fact_applicant_type.currentText())
    applicant_type_code = _norm_text(_normalize_applicant_type_code("", applicant_type_text, ""))

    applicant_id_type_text = _norm_text(dlg.fact_applicant_id_type.currentText())
    applicant_id_type_code = _norm_text(_normalize_applicant_id_type_code(applicant_id_type_text))

    applicant_id_no = _norm_text(dlg.fact_applicant_id_no.text())
    applicant_phone = _norm_text(dlg.fact_applicant_phone.text())
    applicant_email = _norm_text(dlg.fact_applicant_email.text())
    applicant_addr_full = _norm_text(dlg.fact_applicant_addr_full.text())

    inventor_name = _norm_text(dlg.fact_inventor_name.text())
    inventor_id_type = _norm_text(dlg.fact_inventor_id_type.currentText())
    inventor_id_no = _norm_text(dlg.fact_inventor_id_no.text())
    inventor_nat = _norm_text(dlg.fact_inventor_nat.text()) or "CN"

    contact_name = _norm_text(dlg.fact_contact_name.text())
    contact_phone = _norm_text(dlg.fact_contact_phone.text())
    contact_email = _norm_text(dlg.fact_contact_email.text())
    contact_addr_full = _norm_text(dlg.fact_contact_addr_full.text())
    contact_zip = _norm_text(dlg.fact_contact_zip.text())

    group_name = _norm_text(dlg.fact_group_name.text())
    poa_no = _norm_text(dlg.fact_poa_no.text())
    agency_ref_name = _norm_text(dlg.fact_agency_name.text())
    agency_ref_code = _norm_text(dlg.fact_agency_code.text())

    app_province_code = _norm_text(app.get("province_code"))
    app_city_code = _norm_text(app.get("city_code"))
    app_address = _norm_text(app.get("address"))
    app_zip = _norm_text(app.get("zip"))

    if applicant_addr_full:
        app_zip_new, addr_no_zip = _extract_zip_and_remove(applicant_addr_full)
        app_rec = {"province": "", "city": "", "address": addr_no_zip}
        try:
            _infer_region_from_single_address(app_rec, "address")
        except Exception:
            pass
        app_province_code = _norm_text(app_rec.get("province_code"))
        app_city_code = _norm_text(app_rec.get("city_code"))
        app_address = _norm_text(app_rec.get("address")) or _norm_text(addr_no_zip)
        if app_zip_new:
            app_zip = _norm_text(app_zip_new)

    c_province_code = _norm_text(contact.get("province_code"))
    c_city_code = _norm_text(contact.get("city_code"))
    c_street = _norm_text(contact.get("street"))
    if contact_addr_full:
        c_rec = {"province": "", "city": "", "street": contact_addr_full}
        try:
            _infer_region_from_single_address(c_rec, "street")
        except Exception:
            pass
        c_province_code = _norm_text(c_rec.get("province_code"))
        c_city_code = _norm_text(c_rec.get("city_code"))
        c_street = _norm_text(c_rec.get("street")) or contact_addr_full

    app["name"] = applicant_name
    app["type"] = applicant_type_text
    app["type_code"] = applicant_type_code
    app["id_type"] = applicant_id_type_text
    app["id_type_code"] = applicant_id_type_code
    app["id_no"] = applicant_id_no
    app["province_code"] = app_province_code
    app["city_code"] = app_city_code
    app["address"] = app_address
    app["zip"] = app_zip
    app["phone"] = applicant_phone
    app["email"] = applicant_email
    app["power_of_attorney_no"] = poa_no

    inv["name"] = inventor_name
    inv["id_type"] = inventor_id_type
    inv["id_no"] = inventor_id_no
    inv["nationality_code"] = inventor_nat

    contact["name"] = contact_name
    contact["phone"] = contact_phone
    contact["email"] = contact_email
    contact["province_code"] = c_province_code
    contact["city_code"] = c_city_code
    contact["street"] = c_street
    contact["zip"] = contact_zip

    item["app"] = app
    item["inv"] = inv
    item["contact"] = contact
    item["group_name"] = group_name
    item["power_of_attorney_no"] = poa_no
    item["agency_ref_name"] = agency_ref_name
    item["agency_ref_code"] = agency_ref_code

    dlg._fact_rows[idx] = item
    dlg._dirty = True
    refresh_fact_table_row(dlg, idx)


def refresh_fact_table_row(dlg, idx: int) -> None:
    if idx < 0 or idx >= len(dlg._fact_rows):
        return
    item = dlg._fact_rows[idx]
    app = item.get("app") if isinstance(item.get("app"), dict) else {}
    inv = item.get("inv") if isinstance(item.get("inv"), dict) else {}

    dlg.fact_table.setItem(idx, 0, QTableWidgetItem(_norm_text(app.get("name"))))
    dlg.fact_table.setItem(
        idx,
        1,
        QTableWidgetItem(_applicant_type_text_from_code(app.get("type_code") or app.get("type"))),
    )
    dlg.fact_table.setItem(
        idx,
        2,
        QTableWidgetItem(_applicant_id_type_text_from_code(app.get("id_type_code") or app.get("id_type"))),
    )
    dlg.fact_table.setItem(idx, 3, QTableWidgetItem(_norm_text(app.get("id_no"))))
    dlg.fact_table.setItem(idx, 4, QTableWidgetItem(_norm_text(app.get("phone"))))
    dlg.fact_table.setItem(idx, 5, QTableWidgetItem(_norm_text(inv.get("name"))))
    dlg.fact_table.setItem(idx, 6, QTableWidgetItem(_norm_text(inv.get("id_no"))))
    dlg.fact_table.setItem(idx, 7, QTableWidgetItem(_norm_text(item.get("group_name"))))
    dlg.fact_table.setItem(idx, 8, QTableWidgetItem(_norm_text(item.get("power_of_attorney_no"))))
    dlg.fact_table.setItem(idx, 9, QTableWidgetItem(_norm_text(item.get("agency_ref_name"))))
    dlg.fact_table.setItem(idx, 10, QTableWidgetItem(_norm_text(item.get("agency_ref_code"))))
