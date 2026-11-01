from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from core.tgd_data_management_impl.agency_agent_query import query_agency_agents

from ..fact_dropdown import (
    _find_tab_owner_for_widget,
    _get_fact_selected_exact_for_ctx,
    _get_inline_fact_combo_ctx_key,
    _get_inline_fact_combo_field,
    _norm_text,
)
from .anchor_ops import _on_applicant_anchor_committed
from .common_ops import _clear_combo_value
from .prefill_ops import _auto_prefill_current_scope


def _on_inline_fact_combo_activated(self, combo: QComboBox) -> None:
    if combo is None:
        return
    scope, col = _get_inline_fact_combo_field(self, combo)
    if not scope or not col:
        return


    ctx_key = _get_inline_fact_combo_ctx_key(self, combo, scope)
    try:
        idx = combo.currentIndex()
    except Exception:
        idx = -1
    chosen = ""
    if idx is not None and int(idx) >= 0:
        try:
            data = combo.itemData(int(idx))
        except Exception:
            data = None
        if data is not None and _norm_text(data):
            chosen = _norm_text(data)
            try:
                combo.blockSignals(True)
                combo.setEditText(chosen)
            except Exception:
                pass
            finally:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass
    if not chosen:
        try:
            chosen = _norm_text(combo.currentText())
        except Exception:
            chosen = ""
    if not chosen:
        return

    if scope == "agency":
        def _read_combo_text(w) -> str:
            if w is None:
                return ""
            try:
                if isinstance(w, QComboBox):
                    return _norm_text(w.currentText())
            except Exception:
                pass
            try:
                if hasattr(w, "text"):
                    return _norm_text(w.text())
            except Exception:
                pass
            try:
                if hasattr(w, "currentText"):
                    return _norm_text(w.currentText())
            except Exception:
                pass
            return ""

        def _set_combo_text_silent(w, text: str) -> None:
            if w is None:
                return
            try:
                le = w.lineEdit() if isinstance(w, QComboBox) else None
            except Exception:
                le = None
            try:
                w.blockSignals(True)
            except Exception:
                pass
            try:
                if le is not None:
                    le.blockSignals(True)
            except Exception:
                pass
            try:
                if isinstance(w, QComboBox):
                    try:
                        w.setCurrentIndex(-1)
                    except Exception:
                        pass
                    try:
                        w.setEditText(_norm_text(text))
                    except Exception:
                        pass
                elif hasattr(w, "setText"):
                    w.setText(_norm_text(text))
                elif hasattr(w, "setEditText"):
                    w.setEditText(_norm_text(text))
            finally:
                try:
                    if le is not None:
                        le.blockSignals(False)
                except Exception:
                    pass
                try:
                    w.blockSignals(False)
                except Exception:
                    pass

        org_name_w = getattr(self, "agency_org_name_edit", None)
        org_code_w = getattr(self, "agency_org_code_edit", None)
        org_name = _read_combo_text(org_name_w)
        org_code = _read_combo_text(org_code_w)

        try:
            exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=True)
            if not isinstance(exact, dict):
                exact = {}
            exact[col] = chosen
        except Exception:
            pass

        if col in ("agency_name", "agency_code"):
            if col == "agency_name":
                org_name = chosen
                try:
                    rows = query_agency_agents(agency_name=org_name, agency_code=org_code, agent_name="", limit=500).records
                except Exception:
                    rows = []
                try:
                    codes = []
                    seen = set()
                    for r in rows or []:
                        if not isinstance(r, dict):
                            continue
                        if _norm_text(r.get("agency_name")) != _norm_text(org_name):
                            continue
                        c = _norm_text(r.get("agency_code"))
                        if not c or c in seen:
                            continue
                        seen.add(c)
                        codes.append(c)
                    if len(codes) == 1:
                        _set_combo_text_silent(org_code_w, codes[0])
                        org_code = _norm_text(codes[0])
                except Exception:
                    pass
            else:
                org_code = chosen
                try:
                    rows = query_agency_agents(agency_name=org_name, agency_code=org_code, agent_name="", limit=500).records
                except Exception:
                    rows = []
                try:
                    names = []
                    seen = set()
                    for r in rows or []:
                        if not isinstance(r, dict):
                            continue
                        if _norm_text(r.get("agency_code")) != _norm_text(org_code):
                            continue
                        n = _norm_text(r.get("agency_name"))
                        if not n or n in seen:
                            continue
                        seen.add(n)
                        names.append(n)
                    if len(names) == 1:
                        _set_combo_text_silent(org_name_w, names[0])
                        org_name = _norm_text(names[0])
                except Exception:
                    pass

            try:
                rows = query_agency_agents(agency_name=org_name, agency_code=org_code, agent_name="", limit=500).records
            except Exception:
                rows = []
            try:
                filtered = []
                for r in rows or []:
                    if not isinstance(r, dict):
                        continue
                    if org_code and _norm_text(r.get("agency_code")) != _norm_text(org_code):
                        continue
                    if org_name and _norm_text(r.get("agency_name")) != _norm_text(org_name):
                        continue
                    filtered.append(r)
                rows = filtered
            except Exception:
                rows = []

            valid_agents = []
            seen_agents = set()
            for r in rows or []:
                if not isinstance(r, dict):
                    continue
                an = _norm_text(r.get("agent_name"))
                if not an:
                    continue
                acn = _norm_text(r.get("agent_cert_no"))
                aph = _norm_text(r.get("agent_phone"))
                sig = (an, acn, aph)
                if sig in seen_agents:
                    continue
                seen_agents.add(sig)
                valid_agents.append({"name": an, "cert_no": acn, "phone": aph})

            a1_name_w = getattr(self, "agency_agent1_name_edit", None)
            a1_cert_w = getattr(self, "agency_agent1_cert_edit", None)
            a1_phone_w = getattr(self, "agency_agent1_phone_edit", None)
            a2_name_w = getattr(self, "agency_agent2_name_edit", None)
            a2_cert_w = getattr(self, "agency_agent2_cert_edit", None)
            a2_phone_w = getattr(self, "agency_agent2_phone_edit", None)

            if len(valid_agents) == 1:
                a = valid_agents[0]
                _set_combo_text_silent(a1_name_w, _norm_text(a.get("name")))
                _set_combo_text_silent(a1_cert_w, _norm_text(a.get("cert_no")))
                _set_combo_text_silent(a1_phone_w, _norm_text(a.get("phone")))

                _set_combo_text_silent(a2_name_w, "")
                _set_combo_text_silent(a2_cert_w, "")
                _set_combo_text_silent(a2_phone_w, "")
            else:
                _set_combo_text_silent(a1_name_w, "")
                _set_combo_text_silent(a1_cert_w, "")
                _set_combo_text_silent(a1_phone_w, "")
                _set_combo_text_silent(a2_name_w, "")
                _set_combo_text_silent(a2_cert_w, "")
                _set_combo_text_silent(a2_phone_w, "")

        try:
            self._fact_candidates_cache_dirty = True
        except Exception:
            pass
        return

    old_anchor_value = ""
    if scope == "applicant" and col in ("applicant_name", "applicant_id_no"):
        try:
            old_exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=False)
            if isinstance(old_exact, dict):
                old_anchor_value = _norm_text(old_exact.get(col))
        except Exception:
            old_anchor_value = ""

    if scope == "inventor" and col == "inventor_name":
        tab = None
        try:
            tab = _find_tab_owner_for_widget(getattr(self, "inv_tabs", None), combo)
        except Exception:
            tab = None
        if tab is None:
            try:
                tab = self.inv_tabs.currentWidget() if getattr(self, "inv_tabs", None) else None
            except Exception:
                tab = None
        try:
            if tab is not None:
                id_type_combo = getattr(tab, "id_type_combo", None)
                if isinstance(id_type_combo, QComboBox):
                    default_idx = id_type_combo.findText("居民身份证")
                    if default_idx < 0:
                        default_idx = 0
                    id_type_combo.setCurrentIndex(default_idx)
                else:
                    _clear_combo_value(id_type_combo)
                _clear_combo_value(getattr(tab, "id_edit", None))
                _clear_combo_value(getattr(tab, "nationality_combo", None))
        except Exception:
            pass
        try:
            ex = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=False)
            if isinstance(ex, dict):
                for k in ("inventor_id_type", "inventor_id_no", "inventor_nationality_code"):
                    if k in ex:
                        del ex[k]
        except Exception:
            pass

    if scope == "contact" and col == "contact_name":
        try:
            _clear_combo_value(getattr(self, "contact_phone_edit", None))
            _clear_combo_value(getattr(self, "contact_email_edit", None))
            _clear_combo_value(getattr(self, "contact_province_combo", None))
            _clear_combo_value(getattr(self, "contact_city_combo", None))
            _clear_combo_value(getattr(self, "contact_street_edit", None))
            _clear_combo_value(getattr(self, "contact_zip_edit", None))
        except Exception:
            pass
        try:
            ex = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=False)
            if isinstance(ex, dict):
                for k in (
                    "contact_phone",
                    "contact_email",
                    "contact_province_code",
                    "contact_city_code",
                    "contact_street",
                    "contact_zip",
                ):
                    if k in ex:
                        del ex[k]
        except Exception:
            pass

    try:
        exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=True)
        if not isinstance(exact, dict):
            exact = {}
        exact[col] = chosen
    except Exception:
        pass

    try:
        self._fact_candidates_cache_dirty = True
    except Exception:
        pass

    try:
        _auto_prefill_current_scope(self, scope, ctx_key=str(ctx_key or ""))
    except Exception:
        pass

    if scope == "applicant" and col == "applicant_name":
        try:
            _on_applicant_anchor_committed(self, combo, ctx_key, col, chosen, old_anchor_value)
        except Exception:
            pass

