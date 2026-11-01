from .widget_safe_ops import _set_edit_text_safe


def _reset_tabs(tab_widget) -> None:
    try:
        while tab_widget.count() > 0:
            tab_widget.removeTab(0)
    except Exception:
        try:
            while tab_widget.count() > 0:
                tab_widget.removeTab(0)
        except Exception:
            pass


def _load_applicant_list(info):
    app_list = []
    if isinstance(info, dict):
        app_list = info.get("applicants") or []
    if not isinstance(app_list, list) or not app_list:
        app_list = [{}]
    return app_list


def _ensure_first_applicant_poa(app_list, global_poa_text: str) -> None:
    if not (global_poa_text and isinstance(app_list, list) and app_list):
        return
    try:
        first = app_list[0]
    except Exception:
        first = None
    if not isinstance(first, dict):
        return
    try:
        existing_poa = str(first.get("power_of_attorney_no") or "").strip()
    except Exception:
        existing_poa = ""
    if existing_poa:
        return
    try:
        merged_first = dict(first)
        merged_first["power_of_attorney_no"] = global_poa_text
        app_list[0] = merged_first
    except Exception:
        pass


def _apply_applicant_tabs(self, info, global_poa_text: str) -> None:
    _reset_tabs(self.app_tabs)

    app_list = _load_applicant_list(info)

    _ensure_first_applicant_poa(app_list, global_poa_text)
    for app in app_list[:5]:
        if not isinstance(app, dict):
            app = {}
        self._add_applicant_tab(app)


def _apply_fee_reduction_checkbox(self, info) -> None:
    fee_enabled = None
    if isinstance(info, dict) and "fee_reduction_enabled" in info:
        try:
            fee_enabled = bool(info.get("fee_reduction_enabled"))
        except Exception:
            fee_enabled = None
    if fee_enabled is None:
        self.fee_reduction_checkbox.setChecked(True)
    else:
        self.fee_reduction_checkbox.setChecked(fee_enabled)


def _apply_inventor_tabs(self, info) -> None:
    _reset_tabs(self.inv_tabs)
    inv_list = []
    if isinstance(info, dict):
        inv_list = info.get("inventors") or []
    if not isinstance(inv_list, list) or not inv_list:
        inv_list = [{}]
    for inv in inv_list[:15]:
        if not isinstance(inv, dict):
            inv = {}
        self._add_inventor_tab(inv)


def _apply_contact_fields(self, info) -> None:
    contact = {}
    if isinstance(info, dict):
        contact = info.get("contact") or {}
    if not isinstance(contact, dict):
        return

    _set_edit_text_safe(getattr(self, "contact_name_edit", None), str(contact.get("name") or ""))
    _set_edit_text_safe(getattr(self, "contact_phone_edit", None), str(contact.get("phone") or ""))
    _set_edit_text_safe(getattr(self, "contact_email_edit", None), str(contact.get("email") or ""))

    prov_val = contact.get("province_code", contact.get("province")) or ""
    city_val = contact.get("city_code", contact.get("city")) or ""
    try:
        init_region = getattr(self, "_init_contact_region_widgets", None)
    except Exception:
        init_region = None
    if callable(init_region):
        try:
            init_region(province_code=str(prov_val), city_code=str(city_val))
        except Exception:
            pass
    else:
        try:
            set_region = getattr(self, "_set_region_combo_value", None)
        except Exception:
            set_region = None
        if callable(set_region):
            try:
                set_region(getattr(self, "contact_province_combo", None), str(prov_val), kind="province")
            except Exception:
                pass
            try:
                set_region(getattr(self, "contact_city_combo", None), str(city_val), kind="city")
            except Exception:
                pass
        else:
            _set_edit_text_safe(getattr(self, "contact_province_combo", None), str(prov_val))
            _set_edit_text_safe(getattr(self, "contact_city_combo", None), str(city_val))

    _set_edit_text_safe(getattr(self, "contact_street_edit", None), str(contact.get("street") or ""))
    _set_edit_text_safe(getattr(self, "contact_zip_edit", None), str(contact.get("zip") or ""))


def _apply_abstract_figure_no(self, info) -> None:
    if isinstance(info, dict) and "abstract_figure_no" in info:
        val = info.get("abstract_figure_no")
        if val is not None:
            self.abstract_figure_no_edit.setText(str(val))
