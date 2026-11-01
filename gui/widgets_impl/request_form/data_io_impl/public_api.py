from .agency_ops import _apply_agency_checkboxes_and_poa, _apply_agency_info_fields, _set_agency_info_from_info
from .merge_ops import _merge_data_mgmt_draft_if_any
from .tabs_apply_ops import (
    _apply_abstract_figure_no,
    _apply_applicant_tabs,
    _apply_contact_fields,
    _apply_fee_reduction_checkbox,
    _apply_inventor_tabs,
)


def _apply_patent_type_widgets(self, info):
    patent_type = None
    if isinstance(info, dict):
        patent_type = info.get("patent_type")
    if patent_type == "utility_model":
        self.radio_utility_model.setChecked(True)
    else:
        self.radio_invention.setChecked(True)
    return patent_type


def _apply_title_and_group_name(self, info) -> None:
    if isinstance(info, dict):
        title_val = info.get("title")
        if isinstance(title_val, str):
            self.title_edit.setText(title_val)

    if isinstance(info, dict):
        try:
            group_name = str(info.get("group_name") or "").strip()
        except Exception:
            group_name = ""
        try:
            group_edit = getattr(self, "group_name_edit", None)
            if group_edit is not None:
                group_edit.setText(group_name)
        except Exception:
            pass


def set_initial_data(self, info):
    info = _merge_data_mgmt_draft_if_any(self, info)

    patent_type = _apply_patent_type_widgets(self, info)

    _apply_title_and_group_name(self, info)

    _, global_poa_text = _apply_agency_checkboxes_and_poa(
        self,
        info,
        patent_type=patent_type,
    )

    _set_agency_info_from_info(self, info)
    _apply_agency_info_fields(self)

    _apply_applicant_tabs(self, info, global_poa_text)
    _apply_fee_reduction_checkbox(self, info)
    _apply_inventor_tabs(self, info)
    _apply_contact_fields(self, info)
    _apply_abstract_figure_no(self, info)


def get_request_data(self):
    def _get_patent_type() -> str:
        return "utility_model" if self.radio_utility_model.isChecked() else "invention"

    def _get_title() -> str:
        try:
            return self.title_edit.text().strip()
        except Exception:
            return ""

    def _get_group_name() -> str:
        group_name = ""
        try:
            group_edit = getattr(self, "group_name_edit", None)
            if group_edit is not None:
                group_name = str(group_edit.text() or "").strip()
        except Exception:
            group_name = ""
        return group_name

    def _infer_applicant_type_code(tab) -> str:
        type_text = tab.type_combo.currentText().strip()
        type_data = tab.type_combo.currentData()
        type_code = str(type_data).strip() if type_data is not None else ""
        if not type_code and type_text:
            type_code = type_text
        return type_text, type_code

    def _infer_applicant_id_type_code(tab) -> str:
        id_type_text = tab.id_type_combo.currentText().strip()
        id_type_data = tab.id_type_combo.currentData()
        id_type_code = str(id_type_data).strip() if id_type_data is not None else ""
        if not id_type_code and id_type_text:
            txt = id_type_text
            txt_upper = txt.upper()
            if ("统一社会信用代码" in txt) or ("社会信用代码" in txt) or ("统一社会信用" in txt) or txt_upper.startswith("F"):
                id_type_code = "F"
            elif ("身份证" in txt) or ("居民" in txt) or txt_upper.startswith("I"):
                id_type_code = "I"
            elif ("其他" in txt) or txt_upper.startswith("O"):
                id_type_code = "0"
            else:
                id_type_code = txt
        return id_type_text, id_type_code

    def _get_applicant_poa_text(tab) -> str:
        poa_text = ""
        try:
            poa_edit = getattr(tab, "poa_edit", None)
            if poa_edit is not None:
                poa_text = poa_edit.currentText().strip()
        except Exception:
            poa_text = ""
        return poa_text

    def _collect_applicants() -> list[dict]:
        applicants: list[dict] = []
        for i in range(self.app_tabs.count()):
            tab = self.app_tabs.widget(i)
            name = tab.name_edit.currentText().strip()

            type_text, type_code = _infer_applicant_type_code(tab)
            id_type_text, id_type_code = _infer_applicant_id_type_code(tab)

            id_no = tab.id_edit.currentText().strip()
            prov = self._get_region_code_from_combo(tab.province_combo)
            city = self._get_region_code_from_combo(tab.city_combo)
            addr = tab.address_edit.currentText().strip()
            zip_code = tab.zip_edit.currentText().strip()
            email = tab.email_edit.currentText().strip()
            phone = tab.phone_edit.currentText().strip()

            poa_text = _get_applicant_poa_text(tab)

            if not any([name, type_text, id_no, prov, city, addr, zip_code, email, phone]):
                continue

            app = {
                "name": name,
                "type": type_text,
                "type_code": type_code,
                "id_type": id_type_text,
                "id_type_code": id_type_code,
                "id_no": id_no,
                "province_code": prov,
                "city_code": city,
                "district_code": "",
                "address": addr,
                "zip": zip_code,
                "email": email,
                "phone": phone,
                "power_of_attorney_no": poa_text,
            }
            applicants.append(app)

        if not applicants:
            applicants.append(
                {
                    "name": "",
                    "type_code": "",
                    "id_type_code": "",
                    "id_no": "",
                    "province_code": "",
                    "city_code": "",
                    "district_code": "",
                    "address": "",
                    "zip": "",
                    "email": "",
                    "phone": "",
                    "power_of_attorney_no": "",
                }
            )
        return applicants

    def _collect_inventors() -> list[dict]:
        inventors: list[dict] = []
        for i in range(self.inv_tabs.count()):
            tab = self.inv_tabs.widget(i)
            name = tab.name_edit.currentText().strip()
            id_type_text = tab.id_type_combo.currentText().strip()
            id_no = tab.id_edit.currentText().strip()
            nationality = tab.nationality_combo.currentText().strip() or "CN"

            if not any([name, id_no]):
                continue

            inv = {
                "name": name,
                "id_type_code": id_type_text,
                "id_no": id_no,
                "nationality_code": nationality,
            }
            inventors.append(inv)

        if not inventors:
            inventors.append(
                {
                    "name": "",
                    "id_type_code": "",
                    "id_no": "",
                    "nationality_code": "CN",
                }
            )
        return inventors

    def _collect_contact() -> dict:
        return {
            "name": self.contact_name_edit.currentText().strip(),
            "phone": self.contact_phone_edit.currentText().strip(),
            "email": self.contact_email_edit.currentText().strip(),
            "province_code": self._get_region_code_from_combo(self.contact_province_combo),
            "city_code": self._get_region_code_from_combo(self.contact_city_combo),
            "street": self.contact_street_edit.currentText().strip(),
            "zip": self.contact_zip_edit.currentText().strip(),
        }

    def _get_abstract_figure_no():
        abs_no_text = self.abstract_figure_no_edit.text().strip()
        return abs_no_text or None

    def _get_agency_enabled() -> bool:
        try:
            agency_enabled = bool(self.agency_enabled_checkbox.isChecked())
        except Exception:
            agency_enabled = False
        return bool(agency_enabled)

    def _clear_applicant_poa_if_agency_disabled(applicants: list[dict], agency_enabled: bool) -> None:
        if agency_enabled:
            return
        try:
            for a in applicants:
                if isinstance(a, dict):
                    a["power_of_attorney_no"] = ""
        except Exception:
            pass

    def _get_early_publication_enabled(patent_type: str) -> bool:
        try:
            early_publication_enabled = bool(self.early_publication_checkbox.isChecked())
        except Exception:
            early_publication_enabled = False
        if patent_type == "utility_model":
            early_publication_enabled = False
        return bool(early_publication_enabled)

    def _get_substantive_exam_enabled(patent_type: str) -> bool:
        try:
            substantive_exam_enabled = bool(self.substantive_exam_checkbox.isChecked())
        except Exception:
            substantive_exam_enabled = True
        if patent_type == "utility_model":
            substantive_exam_enabled = False
        return bool(substantive_exam_enabled)

    def _read_text_from_widget(w) -> str:
        if w is None:
            return ""
        try:
            if hasattr(w, "currentText"):
                return str(w.currentText() or "").strip()
        except Exception:
            pass
        try:
            if hasattr(w, "text"):
                return str(w.text() or "").strip()
        except Exception:
            pass
        return ""

    patent_type = _get_patent_type()
    title_val = _get_title()
    group_name = _get_group_name()

    applicants = _collect_applicants()
    inventors = _collect_inventors()
    contact = _collect_contact()

    abstract_figure_no = _get_abstract_figure_no()

    agency_enabled = _get_agency_enabled()
    _clear_applicant_poa_if_agency_disabled(applicants, agency_enabled)

    early_publication_enabled = _get_early_publication_enabled(patent_type)
    substantive_exam_enabled = _get_substantive_exam_enabled(patent_type)

    request_info = {
        "patent_type": patent_type,
        "title": title_val,
        "inventors": inventors,
        "applicants": applicants,
        "contact": contact,
        "group_name": group_name,
        "fee_reduction_enabled": self.fee_reduction_checkbox.isChecked(),
        "agency_enabled": agency_enabled,
        "early_publication_enabled": early_publication_enabled,
        "substantive_exam_enabled": substantive_exam_enabled,
    }

    try:
        org_name = _read_text_from_widget(getattr(self, "agency_org_name_edit", None))
        org_code = _read_text_from_widget(getattr(self, "agency_org_code_edit", None))
        a1_name = _read_text_from_widget(getattr(self, "agency_agent1_name_edit", None))
        a1_cert = _read_text_from_widget(getattr(self, "agency_agent1_cert_edit", None))
        a1_phone = _read_text_from_widget(getattr(self, "agency_agent1_phone_edit", None))
        a2_name = _read_text_from_widget(getattr(self, "agency_agent2_name_edit", None))
        a2_cert = _read_text_from_widget(getattr(self, "agency_agent2_cert_edit", None))
        a2_phone = _read_text_from_widget(getattr(self, "agency_agent2_phone_edit", None))

        agency_info: dict = {}
        if org_name or org_code:
            agency_info["name"] = org_name
            agency_info["code"] = org_code
        if any([a1_name, a1_cert, a1_phone]):
            agency_info["agent1"] = {"name": a1_name, "cert_no": a1_cert, "phone": a1_phone}
        if any([a2_name, a2_cert, a2_phone]):
            agency_info["agent2"] = {"name": a2_name, "cert_no": a2_cert, "phone": a2_phone}

        try:
            self._agency_info = agency_info if agency_info else None
        except Exception:
            pass
    except Exception:
        pass

    try:
        agency_info = getattr(self, "_agency_info", None)
    except Exception:
        agency_info = None
    if isinstance(agency_info, dict) and agency_info:
        request_info["agency_info"] = agency_info
    if abstract_figure_no is not None:
        request_info["abstract_figure_no"] = abstract_figure_no
    return request_info, patent_type
