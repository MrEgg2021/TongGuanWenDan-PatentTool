from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from core.tgd_data_management_impl.fact_record_query import query_fact_records

from ..fact_dropdown import (
    _get_group_name_for_fact_query,
    _norm_text,
)


def _clear_combo_value(combo: QComboBox | None) -> None:
    if combo is None:
        return
    try:
        combo.blockSignals(True)
    except Exception:
        pass
    try:
        try:
            combo.setCurrentIndex(-1)
        except Exception:
            pass
        try:
            combo.setEditText("")
        except Exception:
            pass
    finally:
        try:
            combo.blockSignals(False)
        except Exception:
            pass

def _collect_all_applicant_anchor_groups_with_old_value(self, current_tab, old_col: str, old_value: str) -> list:
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

        if tab is current_tab and old_value:
            if old_col == "applicant_name":
                name = _norm_text(old_value)
                id_no = _norm_text(id_w.currentText() if isinstance(id_w, QComboBox) else "")
            else:
                name = _norm_text(name_w.currentText() if isinstance(name_w, QComboBox) else "")
                id_no = _norm_text(old_value)
        else:
            name = _norm_text(name_w.currentText() if isinstance(name_w, QComboBox) else "")
            id_no = _norm_text(id_w.currentText() if isinstance(id_w, QComboBox) else "")

        if not any([name, id_no]):
            continue
        groups.append({"name": name, "id_no": id_no})
    return groups

def _query_fact_records_with_anchor_groups(self, anchor_groups: list) -> list:
    if not anchor_groups:
        return []
    group_name_for_query = _get_group_name_for_fact_query(self)
    try:
        result = query_fact_records(
            group_name=group_name_for_query,
            applicant_groups=anchor_groups,
            inventor_filter=None,
            contact_filter=None,
            limit=500,
        )
        return result.records if isinstance(result.records, list) else []
    except Exception:
        return []

def _clear_line_edit_text(widget) -> None:
    if widget is None:
        return
    try:
        if isinstance(widget, QComboBox):
            widget.setEditText("")
        elif hasattr(widget, "setText"):
            widget.setText("")
        elif hasattr(widget, "setEditText"):
            widget.setEditText("")
    except Exception:
        pass

def _get_line_edit_text(widget) -> str:
    if widget is None:
        return ""
    try:
        if isinstance(widget, QComboBox):
            return _norm_text(widget.currentText())
        elif hasattr(widget, "text"):
            return _norm_text(widget.text())
        elif hasattr(widget, "currentText"):
            return _norm_text(widget.currentText())
    except Exception:
        pass
    return ""

