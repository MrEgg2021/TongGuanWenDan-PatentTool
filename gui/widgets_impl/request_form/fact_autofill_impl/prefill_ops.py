from __future__ import annotations

from ..fact_dropdown import (
    _get_current_fact_rows,
    _norm_text,
    _set_combo_by_data_or_text,
    _set_line_edit_if_empty,
    _unique_values,
)
from .common_ops import _clear_combo_value

_INVENTOR_ID_TYPE_DEFAULT = "\u5c45\u6c11\u8eab\u4efd\u8bc1"


def _normalize_inventor_id_type(value: object) -> str:
    text = _norm_text(value)
    if not text:
        return _INVENTOR_ID_TYPE_DEFAULT
    upper = text.upper()
    if upper in {"I", "ID", "IDCARD"} or ("\u8eab\u4efd\u8bc1" in text):
        return "\u5c45\u6c11\u8eab\u4efd\u8bc1"
    if upper in {"P", "PASSPORT"} or ("\u62a4\u7167" in text):
        return "\u62a4\u7167"
    if upper in {"O", "OTHER", "0"} or ("\u5176\u4ed6" in text):
        return "\u5176\u4ed6"
    if text in {"\u5c45\u6c11\u8eab\u4efd\u8bc1", "\u62a4\u7167", "\u5176\u4ed6"}:
        return text
    return _INVENTOR_ID_TYPE_DEFAULT


def _auto_prefill_current_scope(self, scope: str, *, ctx_key: str) -> None:
    rows, _trunc = _get_current_fact_rows(self, ctx_key=str(ctx_key or ""), scope=str(scope or ""))
    if not rows:
        return

    if scope == "applicant":
        tab = None
        try:
            tab = self.app_tabs.currentWidget() if getattr(self, "app_tabs", None) else None
        except Exception:
            tab = None
        if tab is None:
            return

        vals = _unique_values(rows, "applicant_name")
        if len(vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "name_edit", None), _norm_text(vals[0]))

        type_vals = _unique_values(rows, "applicant_type_code")
        if len(type_vals) == 1:
            _set_combo_by_data_or_text(getattr(tab, "type_combo", None), _norm_text(type_vals[0]), data_first=True)

        idt_vals = _unique_values(rows, "applicant_id_type_code")
        if len(idt_vals) == 1:
            code = _norm_text(idt_vals[0])
            mapped = code
            if code == "I":
                mapped = "身份证"
            elif code == "0":
                mapped = "其他"
            _set_combo_by_data_or_text(getattr(tab, "id_type_combo", None), mapped, data_first=True)

        idno_vals = _unique_values(rows, "applicant_id_no")
        if len(idno_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "id_edit", None), _norm_text(idno_vals[0]))

        prov_vals = _unique_values(rows, "applicant_province_code")
        city_vals = _unique_values(rows, "applicant_city_code")
        prov_code = _norm_text(prov_vals[0]) if len(prov_vals) == 1 else ""
        city_code = _norm_text(city_vals[0]) if len(city_vals) == 1 else ""
        try:
            prov_combo = getattr(tab, "province_combo", None)
            city_combo = getattr(tab, "city_combo", None)
            cur_prov = _norm_text(self._get_region_code_from_combo(prov_combo)) if prov_combo is not None else ""
            cur_city = _norm_text(self._get_region_code_from_combo(city_combo)) if city_combo is not None else ""

            want_prov = cur_prov or prov_code
            want_city = cur_city or city_code
            init_region = getattr(self, "_init_applicant_region_widgets", None)
            if callable(init_region) and (want_prov or want_city):
                if (not cur_prov and prov_code) or (not cur_city and city_code):
                    init_region(tab, province_code=str(want_prov), city_code=str(want_city))
            else:
                if prov_code:
                    _set_line_edit_if_empty(prov_combo, prov_code)
                if city_code:
                    _set_line_edit_if_empty(city_combo, city_code)
        except Exception:
            pass

        addr_vals = _unique_values(rows, "applicant_address")
        if len(addr_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "address_edit", None), _norm_text(addr_vals[0]))

        zip_vals = _unique_values(rows, "applicant_zip")
        if len(zip_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "zip_edit", None), _norm_text(zip_vals[0]))

        phone_vals = _unique_values(rows, "applicant_phone")
        if len(phone_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "phone_edit", None), _norm_text(phone_vals[0]))

        email_vals = _unique_values(rows, "applicant_email")
        if len(email_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "email_edit", None), _norm_text(email_vals[0]))
        return

    if scope == "poa":
        tab = None
        tab_id = None
        key = _norm_text(ctx_key)
        if key and "@" in key:
            try:
                prefix, suffix = key.split("@", 1)
            except Exception:
                prefix, suffix = "", ""
            if _norm_text(prefix) in ("poa", "applicant"):
                try:
                    tab_id = int(_norm_text(suffix))
                except Exception:
                    tab_id = None

        if tab_id is not None:
            try:
                tabs = getattr(self, "app_tabs", None)
            except Exception:
                tabs = None
            if tabs is not None:
                try:
                    for i in range(int(tabs.count())):
                        t = tabs.widget(i)
                        if t is None:
                            continue
                        if int(id(t)) == int(tab_id):
                            tab = t
                            break
                except Exception:
                    tab = None

        if tab is None:
            try:
                tab = self.app_tabs.currentWidget() if getattr(self, "app_tabs", None) else None
            except Exception:
                tab = None
        if tab is None:
            return

        poa_edit = getattr(tab, "poa_edit", None)
        if poa_edit is None:
            return
        try:
            _clear_combo_value(poa_edit)
        except Exception:
            pass
        poa_vals = []
        seen = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            val = _norm_text(row.get("power_of_attorney_no"))
            if val in seen:
                continue
            seen.add(val)
            poa_vals.append(val)
        if len(poa_vals) == 1:
            poa_val = _norm_text(poa_vals[0])
            if poa_val:
                _set_line_edit_if_empty(poa_edit, poa_val)
        return

    if scope == "inventor":
        tab = None
        try:
            tab = self.inv_tabs.currentWidget() if getattr(self, "inv_tabs", None) else None
        except Exception:
            tab = None
        if tab is None:
            return

        inv_name_vals = _unique_values(rows, "inventor_name")
        if len(inv_name_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "name_edit", None), _norm_text(inv_name_vals[0]))

        inv_type_vals = _unique_values(rows, "inventor_id_type")
        if len(inv_type_vals) == 1:
            _set_combo_by_data_or_text(
                getattr(tab, "id_type_combo", None),
                _normalize_inventor_id_type(inv_type_vals[0]),
                data_first=False,
            )

        inv_id_vals = _unique_values(rows, "inventor_id_no")
        if len(inv_id_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "id_edit", None), _norm_text(inv_id_vals[0]))

        nat_vals = _unique_values(rows, "inventor_nationality_code")
        if len(nat_vals) == 1:
            _set_combo_by_data_or_text(getattr(tab, "nationality_combo", None), _norm_text(nat_vals[0]) or "CN", data_first=False)

        return

    if scope == "contact":
        contact_name_vals = _unique_values(rows, "contact_name")
        if len(contact_name_vals) == 1:
            _set_line_edit_if_empty(getattr(self, "contact_name_edit", None), _norm_text(contact_name_vals[0]))
        contact_phone_vals = _unique_values(rows, "contact_phone")
        if len(contact_phone_vals) == 1:
            _set_line_edit_if_empty(getattr(self, "contact_phone_edit", None), _norm_text(contact_phone_vals[0]))
        contact_email_vals = _unique_values(rows, "contact_email")
        if len(contact_email_vals) == 1:
            _set_line_edit_if_empty(getattr(self, "contact_email_edit", None), _norm_text(contact_email_vals[0]))

        cprov_vals = _unique_values(rows, "contact_province_code")
        ccity_vals = _unique_values(rows, "contact_city_code")
        cprov_code = _norm_text(cprov_vals[0]) if len(cprov_vals) == 1 else ""
        ccity_code = _norm_text(ccity_vals[0]) if len(ccity_vals) == 1 else ""
        try:
            prov_combo = getattr(self, "contact_province_combo", None)
            city_combo = getattr(self, "contact_city_combo", None)
            cur_prov = _norm_text(self._get_region_code_from_combo(prov_combo)) if prov_combo is not None else ""
            cur_city = _norm_text(self._get_region_code_from_combo(city_combo)) if city_combo is not None else ""

            want_prov = cur_prov or cprov_code
            want_city = cur_city or ccity_code
            init_region = getattr(self, "_init_contact_region_widgets", None)
            if callable(init_region) and (want_prov or want_city):
                if (not cur_prov and cprov_code) or (not cur_city and ccity_code):
                    init_region(province_code=str(want_prov), city_code=str(want_city))
            else:
                if cprov_code:
                    _set_line_edit_if_empty(prov_combo, cprov_code)
                if ccity_code:
                    _set_line_edit_if_empty(city_combo, ccity_code)
        except Exception:
            pass

        cstreet_vals = _unique_values(rows, "contact_street")
        if len(cstreet_vals) == 1:
            _set_line_edit_if_empty(getattr(self, "contact_street_edit", None), _norm_text(cstreet_vals[0]))
        czip_vals = _unique_values(rows, "contact_zip")
        if len(czip_vals) == 1:
            _set_line_edit_if_empty(getattr(self, "contact_zip_edit", None), _norm_text(czip_vals[0]))
        return

def _trigger_all_inventor_autofill(self) -> None:
    try:
        cnt = int(self.inv_tabs.count()) if getattr(self, "inv_tabs", None) else 0
    except Exception:
        cnt = 0
    for i in range(cnt):
        try:
            tab = self.inv_tabs.widget(i)
        except Exception:
            tab = None
        if tab is None:
            continue
        ctx_key = f"inventor@{id(tab)}"
        try:
            _auto_prefill_current_scope_for_tab(self, "inventor", ctx_key=ctx_key, tab=tab)
        except Exception:
            pass

def _auto_prefill_current_scope_for_tab(self, scope: str, *, ctx_key: str, tab) -> None:
    rows, _trunc = _get_current_fact_rows(self, ctx_key=str(ctx_key or ""), scope=str(scope or ""))
    if not rows:
        return

    if scope == "inventor" and tab is not None:
        inv_name_vals = _unique_values(rows, "inventor_name")
        if len(inv_name_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "name_edit", None), _norm_text(inv_name_vals[0]))

        inv_type_vals = _unique_values(rows, "inventor_id_type")
        if len(inv_type_vals) == 1:
            _set_combo_by_data_or_text(
                getattr(tab, "id_type_combo", None),
                _normalize_inventor_id_type(inv_type_vals[0]),
                data_first=False,
            )

        inv_id_vals = _unique_values(rows, "inventor_id_no")
        if len(inv_id_vals) == 1:
            _set_line_edit_if_empty(getattr(tab, "id_edit", None), _norm_text(inv_id_vals[0]))

        nat_vals = _unique_values(rows, "inventor_nationality_code")
        if len(nat_vals) == 1:
            _set_combo_by_data_or_text(getattr(tab, "nationality_combo", None), _norm_text(nat_vals[0]) or "CN", data_first=False)

