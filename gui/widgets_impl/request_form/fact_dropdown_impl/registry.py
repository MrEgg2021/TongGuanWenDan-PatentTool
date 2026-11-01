from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget

from .delegate import FactCandidateDelegate
from .extractors import _get_applicant_tab_data
from .text_widget_utils import _norm_text


def _register_inline_fact_combo(self, combo: QComboBox | None, *, scope: str, col: str) -> None:
    if combo is None:
        return

    already_registered = False
    try:
        already_registered = bool(combo.property("_tgd_inline_fact_registered"))
    except Exception:
        already_registered = False
    try:
        if not isinstance(getattr(self, "_fact_combo_field_map", None), dict):
            self._fact_combo_field_map = {}
        self._fact_combo_field_map[combo] = (str(scope or ""), str(col or ""))
    except Exception:
        pass

    try:
        combo.setEditable(True)
    except Exception:
        pass

    try:
        if not isinstance(getattr(self, "_fact_combo_managed_targets", None), set):
            self._fact_combo_managed_targets = set()
    except Exception:
        pass

    try:
        le = combo.lineEdit()
    except Exception:
        le = None
    if le is not None:
        try:
            if not isinstance(getattr(self, "_fact_combo_line_edit_map", None), dict):
                self._fact_combo_line_edit_map = {}
            self._fact_combo_line_edit_map[le] = combo
        except Exception:
            pass
        try:
            le.installEventFilter(self)
        except Exception:
            pass

    try:
        combo.installEventFilter(self)
    except Exception:
        pass
    try:
        self._fact_combo_managed_targets.add(combo)
    except Exception:
        pass

    try:
        self._register_combo_wheel_block(combo)
    except Exception:
        pass

    if str(scope or "") == "inventor" and str(col or "") == "inventor_name":
        try:
            combo.setItemDelegate(FactCandidateDelegate(combo))
        except Exception:
            pass

    if not already_registered:
        try:
            le = combo.lineEdit()
            if le is not None:
                le.textEdited.connect(lambda _t, c=combo: self._on_inline_fact_combo_text_edited(c))
        except Exception:
            pass

        try:
            combo.activated.connect(lambda _i, c=combo: self._on_inline_fact_combo_activated(c))
        except Exception:
            pass

        if str(scope or "") == "applicant" and str(col or "") in ("applicant_name", "applicant_id_no"):
            try:
                le = combo.lineEdit()
                if le is not None:
                    le.editingFinished.connect(lambda c=combo: self._on_applicant_anchor_editing_finished(c))
            except Exception:
                pass

        try:
            combo.setProperty("_tgd_inline_fact_registered", True)
        except Exception:
            pass



def _get_inline_fact_combo_field(self, combo: QComboBox | None) -> tuple[str, str]:
    if combo is None:
        return ("", "")
    try:
        mp = getattr(self, "_fact_combo_field_map", None) or {}
        if isinstance(mp, dict) and combo in mp:
            scope, col = mp.get(combo) or ("", "")
            return (str(scope or ""), str(col or ""))
    except Exception:
        pass
    return ("", "")


def _find_tab_owner_for_widget(tabs, widget: QWidget | None) -> QWidget | None:
    if tabs is None or widget is None:
        return None
    try:
        cnt = int(tabs.count())
    except Exception:
        cnt = 0
    for i in range(cnt):
        try:
            tab = tabs.widget(i)
        except Exception:
            tab = None
        if tab is None:
            continue
        try:
            if tab is widget or bool(tab.isAncestorOf(widget)):
                return tab
        except Exception:
            continue
    return None


def _get_inline_fact_combo_ctx_key(self, combo: QComboBox | None, scope: str) -> str:
    s = str(scope or "")
    if not s:
        return ""
    if s == "contact":
        return "contact"
    if s in ("applicant", "poa"):
        try:
            tab = _find_tab_owner_for_widget(getattr(self, "app_tabs", None), combo)
        except Exception:
            tab = None
        if tab is not None:
            return f"{s}@{id(tab)}"
        return s
    if s == "inventor":
        try:
            tab = _find_tab_owner_for_widget(getattr(self, "inv_tabs", None), combo)
        except Exception:
            tab = None
        if tab is not None:
            return f"{s}@{id(tab)}"
        return s
    return s


def _get_fact_selected_exact_for_ctx(self, ctx_key: str, *, create: bool = True) -> dict:
    try:
        mp = getattr(self, "_fact_selected_exact_by_ctx", None)
    except Exception:
        mp = None
    if not isinstance(mp, dict):
        mp = {}
        try:
            self._fact_selected_exact_by_ctx = mp
        except Exception:
            pass
    key = str(ctx_key or "")
    if not key:
        key = "_default"
    cur = mp.get(key)
    if isinstance(cur, dict):
        return cur
    if not bool(create):
        return {}
    cur = {}
    try:
        mp[key] = cur
    except Exception:
        pass
    return cur


def _setup_inline_fact_dropdowns_for_applicant_tab(self, tab) -> None:
    if tab is None:
        return
    _register_inline_fact_combo(self, getattr(tab, "name_edit", None), scope="applicant", col="applicant_name")
    _register_inline_fact_combo(self, getattr(tab, "poa_edit", None), scope="poa", col="power_of_attorney_no")
    _register_inline_fact_combo(self, getattr(tab, "id_edit", None), scope="applicant", col="applicant_id_no")
    _register_inline_fact_combo(self, getattr(tab, "address_edit", None), scope="applicant", col="applicant_address")
    _register_inline_fact_combo(self, getattr(tab, "zip_edit", None), scope="applicant", col="applicant_zip")
    _register_inline_fact_combo(self, getattr(tab, "phone_edit", None), scope="applicant", col="applicant_phone")
    _register_inline_fact_combo(self, getattr(tab, "email_edit", None), scope="applicant", col="applicant_email")


def _setup_inline_fact_dropdowns_for_inventor_tab(self, tab) -> None:
    if tab is None:
        return
    _register_inline_fact_combo(self, getattr(tab, "name_edit", None), scope="inventor", col="inventor_name")
    _register_inline_fact_combo(self, getattr(tab, "id_edit", None), scope="inventor", col="inventor_id_no")


def _setup_inline_fact_dropdowns_for_contact(self) -> None:
    _register_inline_fact_combo(self, getattr(self, "contact_name_edit", None), scope="contact", col="contact_name")
    _register_inline_fact_combo(self, getattr(self, "contact_phone_edit", None), scope="contact", col="contact_phone")
    _register_inline_fact_combo(self, getattr(self, "contact_email_edit", None), scope="contact", col="contact_email")
    _register_inline_fact_combo(self, getattr(self, "contact_street_edit", None), scope="contact", col="contact_street")
    _register_inline_fact_combo(self, getattr(self, "contact_zip_edit", None), scope="contact", col="contact_zip")


def _setup_inline_fact_dropdowns_for_agency(self) -> None:
    _register_inline_fact_combo(self, getattr(self, "agency_org_name_edit", None), scope="agency", col="agency_name")
    _register_inline_fact_combo(self, getattr(self, "agency_org_code_edit", None), scope="agency", col="agency_code")

    _register_inline_fact_combo(self, getattr(self, "agency_agent1_name_edit", None), scope="agency", col="agent_name")
    _register_inline_fact_combo(self, getattr(self, "agency_agent1_cert_edit", None), scope="agency", col="agent_cert_no")
    _register_inline_fact_combo(self, getattr(self, "agency_agent1_phone_edit", None), scope="agency", col="agent_phone")

    _register_inline_fact_combo(self, getattr(self, "agency_agent2_name_edit", None), scope="agency", col="agent_name")
    _register_inline_fact_combo(self, getattr(self, "agency_agent2_cert_edit", None), scope="agency", col="agent_cert_no")
    _register_inline_fact_combo(self, getattr(self, "agency_agent2_phone_edit", None), scope="agency", col="agent_phone")


def _collect_all_applicant_groups(self) -> list:
    groups = []
    try:
        cnt = int(self.app_tabs.count()) if getattr(self, "app_tabs", None) else 0
    except Exception:
        cnt = 0
    for i in range(cnt):
        try:
            tab = self.app_tabs.widget(i)
        except Exception:
            tab = None
        cur = _get_applicant_tab_data(self, tab)
        if cur:
            groups.append(cur)
    return groups


def _collect_all_applicant_anchor_groups(self) -> list:
    groups = []
    try:
        cnt = int(self.app_tabs.count()) if getattr(self, "app_tabs", None) else 0
    except Exception:
        cnt = 0
    for i in range(cnt):
        try:
            tab = self.app_tabs.widget(i)
        except Exception:
            tab = None
        if tab is None:
            continue
        name_w = getattr(tab, "name_edit", None)
        id_w = getattr(tab, "id_edit", None)
        name = _norm_text(name_w.currentText() if isinstance(name_w, QComboBox) else (name_w.text() if name_w else ""))
        id_no = _norm_text(id_w.currentText() if isinstance(id_w, QComboBox) else (id_w.text() if id_w else ""))
        if not any([name, id_no]):
            continue
        groups.append({"name": name, "id_no": id_no})
    return groups


def _get_agency_ref_code_for_poa(self) -> str:
    code = ""
    try:
        w = getattr(self, "agency_org_code_edit", None)
        if w is not None:
            if isinstance(w, QComboBox):
                code = _norm_text(w.currentText())
            else:
                code = _norm_text(w.text())
    except Exception:
        code = ""
    if code:
        return _norm_text(code)
    try:
        agency_info = getattr(self, "_agency_info", None)
    except Exception:
        agency_info = None
    if isinstance(agency_info, dict):
        code = _norm_text(agency_info.get("code"))
    return _norm_text(code)


def _collect_poa_applicant_anchor_groups_for_ctx(self, *, ctx_key: str, combo: QComboBox | None = None) -> list:
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

    if tab is None and combo is not None:
        try:
            tab = _find_tab_owner_for_widget(getattr(self, "app_tabs", None), combo)
        except Exception:
            tab = None

    if tab is None:
        try:
            tab = self.app_tabs.currentWidget() if getattr(self, "app_tabs", None) else None
        except Exception:
            tab = None

    if tab is None:
        return []

    name_w = getattr(tab, "name_edit", None)
    id_w = getattr(tab, "id_edit", None)
    name = _norm_text(name_w.currentText() if isinstance(name_w, QComboBox) else "")
    id_no = _norm_text(id_w.currentText() if isinstance(id_w, QComboBox) else "")
    if not any([name, id_no]):
        return []
    return [{"name": name, "id_no": id_no}]
