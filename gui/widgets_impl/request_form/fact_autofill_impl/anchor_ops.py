from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from ..fact_dropdown import (
    _find_tab_owner_for_widget,
    _get_fact_selected_exact_for_ctx,
    _get_inline_fact_combo_ctx_key,
    _get_inline_fact_combo_field,
    _norm_text,
    _unique_values,
)
from .common_ops import (
    _clear_combo_value,
    _clear_line_edit_text,
    _collect_all_applicant_anchor_groups_with_old_value,
    _get_line_edit_text,
    _query_fact_records_with_anchor_groups,
)
from .prefill_ops import _auto_prefill_current_scope


def _clear_inventor_fields_if_match_old_unique(self, old_rows: list, new_rows: list | None = None) -> None:
    try:
        cnt = int(self.inv_tabs.count()) if getattr(self, "inv_tabs", None) else 0
    except Exception:
        cnt = 0

    inv_name_old = set(_unique_values(old_rows, "inventor_name"))
    inv_id_type_old = set(_unique_values(old_rows, "inventor_id_type"))
    inv_id_no_old = set(_unique_values(old_rows, "inventor_id_no"))
    inv_nat_old = set(_unique_values(old_rows, "inventor_nationality_code"))

    inv_name_new = set(_unique_values(new_rows, "inventor_name")) if isinstance(new_rows, list) else set()
    inv_id_type_new = set(_unique_values(new_rows, "inventor_id_type")) if isinstance(new_rows, list) else set()
    inv_id_no_new = set(_unique_values(new_rows, "inventor_id_no")) if isinstance(new_rows, list) else set()
    inv_nat_new = set(_unique_values(new_rows, "inventor_nationality_code")) if isinstance(new_rows, list) else set()

    for i in range(cnt):
        try:
            tab = self.inv_tabs.widget(i)
        except Exception:
            tab = None
        if tab is None:
            continue

        ctx_key = f"inventor@{id(tab)}"

        name_w = getattr(tab, "name_edit", None)
        if name_w is not None:
            cur = _norm_text(_get_line_edit_text(name_w))
            if cur and (cur in inv_name_old) and (cur not in inv_name_new):
                _clear_line_edit_text(name_w)
                try:
                    ex = _get_fact_selected_exact_for_ctx(self, ctx_key, create=False)
                    if isinstance(ex, dict) and "inventor_name" in ex:
                        del ex["inventor_name"]
                except Exception:
                    pass

        id_type_w = getattr(tab, "id_type_combo", None)
        if id_type_w is not None:
            cur_val = _norm_text(id_type_w.currentText() if isinstance(id_type_w, QComboBox) else "")
            if cur_val and (cur_val in inv_id_type_old) and (cur_val not in inv_id_type_new):
                try:
                    if isinstance(id_type_w, QComboBox):
                        default_idx = id_type_w.findText("居民身份证")
                        if default_idx < 0:
                            default_idx = 0
                        id_type_w.setCurrentIndex(default_idx)
                except Exception:
                    pass

        id_w = getattr(tab, "id_edit", None)
        if id_w is not None:
            cur = _norm_text(_get_line_edit_text(id_w))
            if cur and (cur in inv_id_no_old) and (cur not in inv_id_no_new):
                _clear_line_edit_text(id_w)
                try:
                    ex = _get_fact_selected_exact_for_ctx(self, ctx_key, create=False)
                    if isinstance(ex, dict) and "inventor_id_no" in ex:
                        del ex["inventor_id_no"]
                except Exception:
                    pass

        nat_w = getattr(tab, "nationality_combo", None)
        if nat_w is not None:
            cur_val = _norm_text(nat_w.currentText() if isinstance(nat_w, QComboBox) else "")
            if cur_val and (cur_val in inv_nat_old) and (cur_val not in inv_nat_new):
                try:
                    nat_w.setCurrentIndex(-1)
                    if isinstance(nat_w, QComboBox):
                        nat_w.setEditText("")
                except Exception:
                    pass

def _clear_contact_fields_if_match_old_unique(self, old_rows: list, new_rows: list | None = None) -> None:
    contact_name_old = set(_unique_values(old_rows, "contact_name"))
    contact_phone_old = set(_unique_values(old_rows, "contact_phone"))
    contact_email_old = set(_unique_values(old_rows, "contact_email"))
    contact_prov_old = set(_unique_values(old_rows, "contact_province_code"))
    contact_city_old = set(_unique_values(old_rows, "contact_city_code"))
    contact_street_old = set(_unique_values(old_rows, "contact_street"))
    contact_zip_old = set(_unique_values(old_rows, "contact_zip"))

    contact_name_new = set(_unique_values(new_rows, "contact_name")) if isinstance(new_rows, list) else set()
    contact_phone_new = set(_unique_values(new_rows, "contact_phone")) if isinstance(new_rows, list) else set()
    contact_email_new = set(_unique_values(new_rows, "contact_email")) if isinstance(new_rows, list) else set()
    contact_prov_new = set(_unique_values(new_rows, "contact_province_code")) if isinstance(new_rows, list) else set()
    contact_city_new = set(_unique_values(new_rows, "contact_city_code")) if isinstance(new_rows, list) else set()
    contact_street_new = set(_unique_values(new_rows, "contact_street")) if isinstance(new_rows, list) else set()
    contact_zip_new = set(_unique_values(new_rows, "contact_zip")) if isinstance(new_rows, list) else set()

    ctx_key = "contact"

    name_w = getattr(self, "contact_name_edit", None)
    if name_w is not None:
        cur = _norm_text(_get_line_edit_text(name_w))
        if cur and (cur in contact_name_old) and (cur not in contact_name_new):
            _clear_line_edit_text(name_w)
            try:
                ex = _get_fact_selected_exact_for_ctx(self, ctx_key, create=False)
                if isinstance(ex, dict) and "contact_name" in ex:
                    del ex["contact_name"]
            except Exception:
                pass

    phone_w = getattr(self, "contact_phone_edit", None)
    if phone_w is not None:
        cur = _norm_text(_get_line_edit_text(phone_w))
        if cur and (cur in contact_phone_old) and (cur not in contact_phone_new):
            _clear_line_edit_text(phone_w)
            try:
                ex = _get_fact_selected_exact_for_ctx(self, ctx_key, create=False)
                if isinstance(ex, dict) and "contact_phone" in ex:
                    del ex["contact_phone"]
            except Exception:
                pass

    email_w = getattr(self, "contact_email_edit", None)
    if email_w is not None:
        cur = _norm_text(_get_line_edit_text(email_w))
        if cur and (cur in contact_email_old) and (cur not in contact_email_new):
            _clear_line_edit_text(email_w)
            try:
                ex = _get_fact_selected_exact_for_ctx(self, ctx_key, create=False)
                if isinstance(ex, dict) and "contact_email" in ex:
                    del ex["contact_email"]
            except Exception:
                pass

    prov_w = getattr(self, "contact_province_combo", None)
    if prov_w is not None:
        cur_prov = _norm_text(self._get_region_code_from_combo(prov_w))
        if cur_prov and (cur_prov in contact_prov_old) and (cur_prov not in contact_prov_new):
            try:
                if isinstance(prov_w, QComboBox):
                    _clear_combo_value(prov_w)
            except Exception:
                pass

    city_w = getattr(self, "contact_city_combo", None)
    if city_w is not None:
        cur_city = _norm_text(self._get_region_code_from_combo(city_w))
        if cur_city and (cur_city in contact_city_old) and (cur_city not in contact_city_new):
            try:
                if isinstance(city_w, QComboBox):
                    _clear_combo_value(city_w)
            except Exception:
                pass

    street_w = getattr(self, "contact_street_edit", None)
    if street_w is not None:
        cur = _norm_text(_get_line_edit_text(street_w))
        if cur and (cur in contact_street_old) and (cur not in contact_street_new):
            _clear_line_edit_text(street_w)
            try:
                ex = _get_fact_selected_exact_for_ctx(self, ctx_key, create=False)
                if isinstance(ex, dict) and "contact_street" in ex:
                    del ex["contact_street"]
            except Exception:
                pass

    zip_w = getattr(self, "contact_zip_edit", None)
    if zip_w is not None:
        cur = _norm_text(_get_line_edit_text(zip_w))
        if cur and (cur in contact_zip_old) and (cur not in contact_zip_new):
            _clear_line_edit_text(zip_w)
            try:
                ex = _get_fact_selected_exact_for_ctx(self, ctx_key, create=False)
                if isinstance(ex, dict) and "contact_zip" in ex:
                    del ex["contact_zip"]
            except Exception:
                pass

def _on_applicant_anchor_committed(self, combo: QComboBox, ctx_key: str, col: str, new_value: str, old_value: str) -> None:
    tab = _find_tab_owner_for_widget(getattr(self, "app_tabs", None), combo)
    if tab is None:
        return

    if str(col or "") != "applicant_name":
        return

    old_anchor_groups = _collect_all_applicant_anchor_groups_with_old_value(self, tab, col, old_value)
    old_rows = _query_fact_records_with_anchor_groups(self, old_anchor_groups)

    try:
        applicant_ctx_key = f"applicant@{id(tab)}"
        ex = _get_fact_selected_exact_for_ctx(self, applicant_ctx_key, create=False)
        if isinstance(ex, dict):
            for k in ("applicant_id_no", "applicant_address", "applicant_zip", "applicant_phone", "applicant_email"):
                if k in ex:
                    del ex[k]
            if _norm_text(new_value):
                ex["applicant_name"] = _norm_text(new_value)
            elif "applicant_name" in ex:
                del ex["applicant_name"]
    except Exception:
        pass

    try:
        _clear_combo_value(getattr(tab, "type_combo", None))
        _clear_combo_value(getattr(tab, "id_type_combo", None))
        _clear_combo_value(getattr(tab, "id_edit", None))
        _clear_combo_value(getattr(tab, "address_edit", None))
        _clear_combo_value(getattr(tab, "zip_edit", None))
        _clear_combo_value(getattr(tab, "phone_edit", None))
        _clear_combo_value(getattr(tab, "email_edit", None))
    except Exception:
        pass

    try:
        init_region = getattr(self, "_init_applicant_region_widgets", None)
        if callable(init_region):
            init_region(tab, province_code="", city_code="")
        else:
            _clear_combo_value(getattr(tab, "province_combo", None))
            _clear_combo_value(getattr(tab, "city_combo", None))
    except Exception:
        pass

    try:
        poa_edit = getattr(tab, "poa_edit", None)
        if poa_edit is not None:
            _clear_combo_value(poa_edit)
    except Exception:
        pass
    try:
        poa_ctx_key = f"poa@{id(tab)}"
        poa_exact = _get_fact_selected_exact_for_ctx(self, poa_ctx_key, create=False)
        if isinstance(poa_exact, dict) and "power_of_attorney_no" in poa_exact:
            del poa_exact["power_of_attorney_no"]
    except Exception:
        pass

    try:
        self._fact_candidates_cache_dirty = True
    except Exception:
        pass

    try:
        applicant_ctx_key = f"applicant@{id(tab)}"
        _auto_prefill_current_scope(self, "applicant", ctx_key=str(applicant_ctx_key or ""))
    except Exception:
        pass

    try:
        poa_ctx_key = f"poa@{id(tab)}"
        _auto_prefill_current_scope(self, "poa", ctx_key=str(poa_ctx_key or ""))
    except Exception:
        pass

    new_rows = []
    try:
        new_anchor_groups = _collect_all_applicant_anchor_groups_with_old_value(self, tab, col, "")
        new_rows = _query_fact_records_with_anchor_groups(self, new_anchor_groups)
    except Exception:
        new_rows = []

    _clear_inventor_fields_if_match_old_unique(self, old_rows, new_rows)
    _clear_contact_fields_if_match_old_unique(self, old_rows, new_rows)

    return

def _on_applicant_anchor_editing_finished(self, combo: QComboBox) -> None:
    if combo is None:
        return
    scope, col = _get_inline_fact_combo_field(self, combo)
    if scope != "applicant" or col not in ("applicant_name", "applicant_id_no"):
        return


    ctx_key = _get_inline_fact_combo_ctx_key(self, combo, scope)
    try:
        new_value = _norm_text(combo.currentText())
    except Exception:
        new_value = ""

    if new_value:
        matched = False
        try:
            for i in range(int(combo.count())):
                if _norm_text(combo.itemText(int(i))) == _norm_text(new_value):
                    matched = True
                    break
        except Exception:
            matched = True
        if not matched:
            try:
                exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=True)
                if isinstance(exact, dict) and col in exact:
                    del exact[col]
            except Exception:
                pass
            try:
                self._fact_candidates_cache_dirty = True
            except Exception:
                pass
            return

    old_value = ""
    try:
        old_exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=False)
        if isinstance(old_exact, dict):
            old_value = _norm_text(old_exact.get(col))
    except Exception:
        old_value = ""

    if new_value == old_value:
        return

    try:
        exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=True)
        if not isinstance(exact, dict):
            exact = {}
        if new_value:
            exact[col] = new_value
        elif col in exact:
            del exact[col]
    except Exception:
        pass

    try:
        self._fact_candidates_cache_dirty = True
    except Exception:
        pass

    if str(col or "") == "applicant_name":
        try:
            _on_applicant_anchor_committed(self, combo, ctx_key, col, new_value, old_value)
        except Exception:
            pass
        return

    try:
        _auto_prefill_current_scope(self, scope, ctx_key=str(ctx_key or ""))
    except Exception:
        pass

