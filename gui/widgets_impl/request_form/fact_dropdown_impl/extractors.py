from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from .text_widget_utils import _norm_text


def _get_applicant_tab_data(self, tab) -> dict:
    if tab is None:
        return {}
    name_edit = getattr(tab, "name_edit", None)
    name = _norm_text(
        name_edit.currentText() if isinstance(name_edit, QComboBox) else (name_edit.text() if name_edit else "")
    )
    type_combo = getattr(tab, "type_combo", None)
    id_type_combo = getattr(tab, "id_type_combo", None)
    id_edit = getattr(tab, "id_edit", None)
    address_edit = getattr(tab, "address_edit", None)
    zip_edit = getattr(tab, "zip_edit", None)
    phone_edit = getattr(tab, "phone_edit", None)
    email_edit = getattr(tab, "email_edit", None)

    type_text = _norm_text(type_combo.currentText() if type_combo else "")
    id_type_text = _norm_text(id_type_combo.currentText() if id_type_combo else "")
    id_no = _norm_text(id_edit.currentText() if isinstance(id_edit, QComboBox) else (id_edit.text() if id_edit else ""))
    prov = _norm_text(self._get_region_code_from_combo(getattr(tab, "province_combo", None)))
    city = _norm_text(self._get_region_code_from_combo(getattr(tab, "city_combo", None)))
    addr = _norm_text(
        address_edit.currentText() if isinstance(address_edit, QComboBox) else (address_edit.text() if address_edit else "")
    )
    zip_code = _norm_text(zip_edit.currentText() if isinstance(zip_edit, QComboBox) else (zip_edit.text() if zip_edit else ""))
    phone = _norm_text(phone_edit.currentText() if isinstance(phone_edit, QComboBox) else (phone_edit.text() if phone_edit else ""))
    email = _norm_text(email_edit.currentText() if isinstance(email_edit, QComboBox) else (email_edit.text() if email_edit else ""))

    type_data = None
    try:
        type_data = type_combo.currentData() if type_combo else None
    except Exception:
        type_data = None
    type_code = _norm_text(type_data)
    if not type_code and type_text:
        type_code = type_text

    id_type_data = None
    try:
        id_type_data = id_type_combo.currentData() if id_type_combo else None
    except Exception:
        id_type_data = None
    id_type_code = _norm_text(id_type_data)
    if not id_type_code and id_type_text:
        txt = id_type_text
        txt_upper = txt.upper()
        if (
            ("统一社会信用代码" in txt)
            or ("社会信用代码" in txt)
            or ("统一社会信用" in txt)
            or txt_upper.startswith("F")
        ):
            id_type_code = "F"
        elif ("身份证" in txt) or ("居民" in txt) or txt_upper.startswith("I"):
            id_type_code = "I"
        elif ("其他" in txt) or txt_upper.startswith("O"):
            id_type_code = "0"
        else:
            id_type_code = txt

    if not any([name, type_text, id_no, prov, city, addr, zip_code, email, phone]):
        return {}

    return {
        "name": name,
        "type": type_text,
        "type_code": type_code,
        "id_type": id_type_text,
        "id_type_code": id_type_code,
        "id_no": id_no,
        "province_code": prov,
        "city_code": city,
        "address": addr,
        "zip": zip_code,
        "phone": phone,
        "email": email,
    }


def _get_inventor_tab_data(self, tab) -> dict:
    if tab is None:
        return {}
    name_edit = getattr(tab, "name_edit", None)
    id_type_combo = getattr(tab, "id_type_combo", None)
    id_edit = getattr(tab, "id_edit", None)
    nat_combo = getattr(tab, "nationality_combo", None)

    name = _norm_text(
        name_edit.currentText() if isinstance(name_edit, QComboBox) else (name_edit.text() if name_edit else "")
    )
    id_type = _norm_text(id_type_combo.currentText() if id_type_combo else "")
    id_no = _norm_text(id_edit.currentText() if isinstance(id_edit, QComboBox) else (id_edit.text() if id_edit else ""))
    nat = _norm_text(nat_combo.currentText() if nat_combo else "") or "CN"

    if not any([name, id_no, id_type]):
        return {}
    return {
        "name": name,
        "id_type": id_type,
        "id_no": id_no,
        "nationality_code": nat,
    }


def _get_contact_data(self) -> dict:
    name_w = getattr(self, "contact_name_edit", None)
    phone_w = getattr(self, "contact_phone_edit", None)
    email_w = getattr(self, "contact_email_edit", None)
    street_w = getattr(self, "contact_street_edit", None)
    zip_w = getattr(self, "contact_zip_edit", None)
    return {
        "name": _norm_text(name_w.currentText() if isinstance(name_w, QComboBox) else (name_w.text() if name_w else "")),
        "phone": _norm_text(phone_w.currentText() if isinstance(phone_w, QComboBox) else (phone_w.text() if phone_w else "")),
        "email": _norm_text(email_w.currentText() if isinstance(email_w, QComboBox) else (email_w.text() if email_w else "")),
        "province_code": _norm_text(self._get_region_code_from_combo(getattr(self, "contact_province_combo", None))),
        "city_code": _norm_text(self._get_region_code_from_combo(getattr(self, "contact_city_combo", None))),
        "street": _norm_text(street_w.currentText() if isinstance(street_w, QComboBox) else (street_w.text() if street_w else "")),
        "zip": _norm_text(zip_w.currentText() if isinstance(zip_w, QComboBox) else (zip_w.text() if zip_w else "")),
    }
