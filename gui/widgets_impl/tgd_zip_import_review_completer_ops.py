from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QStringListModel
from PySide6.QtWidgets import QCompleter, QLineEdit

from core.tgd_data_management_impl.candidates_query import (
    query_agency_agent_candidates,
    query_fact_record_candidates,
    query_group_name_candidates,
)

from gui.widgets_impl.tgd_zip_import_review_debug_ops import zip_dbg
from gui.widgets_impl.tgd_zip_import_review_utils import _norm_text


def setup_candidate_completers(dlg) -> None:
    register_cpl(dlg, getattr(dlg, "fact_applicant_name", None), scope="fact", col="applicant_name")
    register_cpl(dlg, getattr(dlg, "fact_applicant_id_no", None), scope="fact", col="applicant_id_no")
    register_cpl(dlg, getattr(dlg, "fact_applicant_phone", None), scope="fact", col="applicant_phone")
    register_cpl(dlg, getattr(dlg, "fact_applicant_email", None), scope="fact", col="applicant_email")
    register_cpl(dlg, getattr(dlg, "fact_applicant_addr_full", None), scope="fact", col="applicant_address")

    register_cpl(dlg, getattr(dlg, "fact_inventor_name", None), scope="fact", col="inventor_name")
    register_cpl(dlg, getattr(dlg, "fact_inventor_id_no", None), scope="fact", col="inventor_id_no")
    register_cpl(dlg, getattr(dlg, "fact_inventor_nat", None), scope="fact", col="inventor_nationality_code")

    register_cpl(dlg, getattr(dlg, "fact_contact_name", None), scope="fact", col="contact_name")
    register_cpl(dlg, getattr(dlg, "fact_contact_phone", None), scope="fact", col="contact_phone")
    register_cpl(dlg, getattr(dlg, "fact_contact_email", None), scope="fact", col="contact_email")
    register_cpl(dlg, getattr(dlg, "fact_contact_addr_full", None), scope="fact", col="contact_street")
    register_cpl(dlg, getattr(dlg, "fact_contact_zip", None), scope="fact", col="contact_zip")

    register_cpl(dlg, getattr(dlg, "fact_group_name", None), scope="fact", col="group_name")
    register_cpl(dlg, getattr(dlg, "fact_poa_no", None), scope="fact", col="power_of_attorney_no")

    register_cpl(dlg, getattr(dlg, "fact_agency_name", None), scope="agency", col="agency_name")
    register_cpl(dlg, getattr(dlg, "fact_agency_code", None), scope="agency", col="agency_code")


def register_cpl(dlg, edit: QLineEdit | None, *, scope: str, col: str) -> None:
    if edit is None:
        return
    if not isinstance(edit, QLineEdit):
        return

    try:
        dlg._cpl_targets[edit] = (str(scope or ""), str(col or ""))
    except Exception:
        return

    try:
        timer = QTimer(edit)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda e=edit: refresh_completer_for_edit(dlg, e))
        dlg._cpl_timers[edit] = timer
    except Exception:
        pass

    try:
        edit.textEdited.connect(lambda _t, e=edit: schedule_refresh_completer(dlg, e))
    except Exception:
        pass

    try:
        model = QStringListModel([], edit)
        cpl = QCompleter(model, edit)
        cpl.setCaseSensitivity(Qt.CaseInsensitive)
        cpl.setFilterMode(Qt.MatchContains)
        cpl.setCompletionMode(QCompleter.PopupCompletion)
        edit.setCompleter(cpl)
        dlg._cpl_models[edit] = model
    except Exception:
        pass


def schedule_refresh_completer(dlg, edit: QLineEdit) -> None:
    t = None
    try:
        t = dlg._cpl_timers.get(edit)
    except Exception:
        t = None
    if t is None:
        return
    try:
        t.start(200)
    except Exception:
        pass


def _get_group_for_candidates(dlg) -> str:
    try:
        return _norm_text(dlg.fact_group_name.text())
    except Exception:
        return ""


def refresh_completer_for_edit(dlg, edit: QLineEdit) -> None:
    meta = None
    try:
        meta = dlg._cpl_targets.get(edit)
    except Exception:
        meta = None
    if not meta:
        return

    scope, col = meta
    typed = ""
    try:
        typed = _norm_text(edit.text())
    except Exception:
        typed = ""

    group_key = _get_group_for_candidates(dlg) if scope == "fact" else ""
    cache_key = (scope, col, (group_key + "\n" + typed).lower())

    values = None
    try:
        values = dlg._cpl_cache.get(cache_key)
    except Exception:
        values = None

    if values is None:
        if scope == "agency":
            res = query_agency_agent_candidates(col=col, typed=typed, limit=60)
            values = list(res.values or [])
        else:
            if col == "group_name":
                res = query_group_name_candidates(typed=typed, limit=60)
                values = list(res.values or [])
            else:
                group_arg = group_key if group_key else None
                res = query_fact_record_candidates(group_name=group_arg, col=col, typed=typed, limit=60)
                values = list(res.values or [])

        try:
            dlg._cpl_cache[cache_key] = list(values)
        except Exception:
            pass

    model = None
    try:
        model = dlg._cpl_models.get(edit)
    except Exception:
        model = None
    if model is None:
        return

    try:
        model.setStringList(list(values))
    except Exception:
        pass

    try:
        zip_dbg(
            f"completer scope={scope} col={col} typed_len={len(typed)} group_len={len(group_key)} values={len(values or [])}"
        )
    except Exception:
        pass


def setup_agency_table_candidate_delegate(dlg, delegate_cls) -> None:
    if getattr(dlg, "agency_table", None) is None:
        return

    mapping = {
        0: "agency_name",
        1: "agency_code",
        2: "agent_name",
        3: "agent_cert_no",
        4: "agent_phone",
    }

    for idx, col in mapping.items():
        try:
            dlg.agency_table.setItemDelegateForColumn(int(idx), delegate_cls(dlg.agency_table, dialog=dlg, col=col))
        except Exception:
            pass


def attach_agency_editor_completer(dlg, edit: QLineEdit, *, col: str) -> None:
    if edit is None:
        return
    if not isinstance(edit, QLineEdit):
        return

    try:
        model = QStringListModel([], edit)
        cpl = QCompleter(model, edit)
        cpl.setCaseSensitivity(Qt.CaseInsensitive)
        cpl.setFilterMode(Qt.MatchContains)
        cpl.setCompletionMode(QCompleter.PopupCompletion)
        edit.setCompleter(cpl)
    except Exception:
        return

    try:
        timer = QTimer(edit)
        timer.setSingleShot(True)
    except Exception:
        timer = None

    def _refresh() -> None:
        typed = ""
        try:
            typed = _norm_text(edit.text())
        except Exception:
            typed = ""
        key = (str(col or ""), typed.lower())
        values = None
        try:
            values = dlg._agency_cell_cache.get(key)
        except Exception:
            values = None

        if values is None:
            res = query_agency_agent_candidates(col=str(col or ""), typed=typed, limit=60)
            values = list(res.values or [])
            try:
                dlg._agency_cell_cache[key] = list(values)
            except Exception:
                pass

        try:
            model.setStringList(list(values))
        except Exception:
            pass

        try:
            zip_dbg(f"agency_cell_cpl col={col} typed_len={len(typed)} values={len(values or [])}")
        except Exception:
            pass

    if timer is not None:
        try:
            timer.timeout.connect(_refresh)
        except Exception:
            timer = None

    def _schedule(_t: str) -> None:
        if timer is None:
            _refresh()
            return
        try:
            timer.start(200)
        except Exception:
            _refresh()

    try:
        edit.textEdited.connect(_schedule)
    except Exception:
        pass
