from .widget_safe_ops import _set_checked_safe, _set_edit_text_safe, _set_text_safe, _to_text


def _apply_agency_default_checkboxes(self) -> None:
    _set_checked_safe(getattr(self, "agency_enabled_checkbox", None), False)
    _set_checked_safe(getattr(self, "early_publication_checkbox", None), True)
    try:
        cb = getattr(self, "substantive_exam_checkbox", None)
    except Exception:
        cb = None
    _set_checked_safe(cb, True)


def _compute_agency_enabled(info: dict) -> bool:
    try:
        agency_enabled = bool(info.get("agency_enabled"))
    except Exception:
        agency_enabled = False
    return bool(agency_enabled)


def _compute_early_publication_enabled(info: dict, *, patent_type) -> bool:
    early_pub = True
    try:
        if "early_publication_enabled" in info:
            early_pub = bool(info.get("early_publication_enabled"))
    except Exception:
        early_pub = True
    if patent_type == "utility_model":
        early_pub = False
    return bool(early_pub)


def _compute_substantive_exam_enabled(info: dict, *, patent_type) -> bool:
    substantive_exam = True
    try:
        if "substantive_exam_enabled" in info:
            substantive_exam = bool(info.get("substantive_exam_enabled"))
    except Exception:
        substantive_exam = True
    if patent_type == "utility_model":
        substantive_exam = False
    return bool(substantive_exam)


def _read_global_poa_text(info: dict, *, agency_enabled: bool) -> str:
    if not agency_enabled:
        return ""

    poa_val = None
    try:
        poa_val = info.get("power_of_attorney_no")
    except Exception:
        poa_val = None
    if poa_val is None:
        return ""
    try:
        return str(poa_val).strip()
    except Exception:
        return ""


def _apply_agency_checkboxes_and_poa(self, info, *, patent_type) -> tuple[bool, str]:
    if not isinstance(info, dict):
        _apply_agency_default_checkboxes(self)
        return False, ""

    agency_enabled = _compute_agency_enabled(info)
    early_pub = _compute_early_publication_enabled(info, patent_type=patent_type)
    substantive_exam = _compute_substantive_exam_enabled(info, patent_type=patent_type)

    _set_checked_safe(getattr(self, "agency_enabled_checkbox", None), agency_enabled)
    _set_checked_safe(getattr(self, "early_publication_checkbox", None), early_pub)
    try:
        cb = getattr(self, "substantive_exam_checkbox", None)
    except Exception:
        cb = None
    _set_checked_safe(cb, substantive_exam)

    global_poa_text = _read_global_poa_text(info, agency_enabled=agency_enabled)
    return bool(agency_enabled), str(global_poa_text or "")


def _set_agency_info_from_info(self, info) -> None:
    try:
        self._agency_info = info.get("agency_info") if isinstance(info, dict) else None
    except Exception:
        self._agency_info = None


def _read_agency_org_fields(agency_info) -> tuple[str, str]:
    if not isinstance(agency_info, dict):
        return "", ""
    return _to_text(agency_info.get("name")), _to_text(agency_info.get("code"))


def _read_agency_agent_fields(agency_info, agent_key: str) -> tuple[str, str, str]:
    if not isinstance(agency_info, dict):
        return "", "", ""
    agent = agency_info.get(agent_key)
    if not isinstance(agent, dict):
        agent = {}
    return _to_text(agent.get("name")), _to_text(agent.get("cert_no")), _to_text(agent.get("phone"))


def _apply_agency_info_fields(self) -> None:
    try:
        agency_info = getattr(self, "_agency_info", None)
    except Exception:
        agency_info = None

    org_name, org_code = _read_agency_org_fields(agency_info)
    a1_name, a1_cert, a1_phone = _read_agency_agent_fields(agency_info, "agent1")
    a2_name, a2_cert, a2_phone = _read_agency_agent_fields(agency_info, "agent2")

    def _set_text_compat(widget, text: str) -> None:
        try:
            if widget is not None and hasattr(widget, "setEditText"):
                _set_edit_text_safe(widget, text)
                return
        except Exception:
            pass
        _set_text_safe(widget, text)

    _set_text_compat(getattr(self, "agency_org_name_edit", None), org_name)
    _set_text_compat(getattr(self, "agency_org_code_edit", None), org_code)
    _set_text_compat(getattr(self, "agency_agent1_name_edit", None), a1_name)
    _set_text_compat(getattr(self, "agency_agent1_cert_edit", None), a1_cert)
    _set_text_compat(getattr(self, "agency_agent1_phone_edit", None), a1_phone)
    _set_text_compat(getattr(self, "agency_agent2_name_edit", None), a2_name)
    _set_text_compat(getattr(self, "agency_agent2_cert_edit", None), a2_cert)
    _set_text_compat(getattr(self, "agency_agent2_phone_edit", None), a2_phone)
