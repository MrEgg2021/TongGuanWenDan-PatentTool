from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from core.tgd_data_management_impl.agency_agent_query import query_agency_agents
from core.tgd_data_management_impl.candidates_query import query_agency_agent_candidates, query_fact_record_candidates

from .query_cache import _get_current_fact_rows, _get_group_name_for_fact_query, _use_weak_fact_filters
from .registry import (
    _collect_all_applicant_anchor_groups,
    _collect_poa_applicant_anchor_groups_for_ctx,
    _get_agency_ref_code_for_poa,
    _get_fact_selected_exact_for_ctx,
    _get_inline_fact_combo_ctx_key,
    _get_inline_fact_combo_field,
)
from .text_widget_utils import _norm_text


def _candidate_values_for_col(rows: list, col: str, typed: str, *, limit: int) -> list[str]:
    out: list[str] = []
    seen = set()
    key = _norm_text(typed).lower()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        v = _norm_text(row.get(col))
        if not v:
            continue
        
        # Enhanced filtering: check value AND pinyin/initials if available
        matched = False
        if not key:
            matched = True
        elif key in v.lower():
            matched = True
        else:
            # Check pinyin fields if they exist in the row
            py = _norm_text(row.get(f"{col}_pinyin")).lower()
            ini = _norm_text(row.get(f"{col}_initials")).lower()
            if py and key in py:
                matched = True
            elif ini and key in ini:
                matched = True
        
        if not matched:
            continue

        if v in seen:
            continue
        seen.add(v)
        out.append(v)
        if len(out) >= int(limit):
            break
    return out


def _read_agency_filters(self) -> tuple[str, str]:
    org_name = ""
    org_code = ""
    try:
        w = getattr(self, "agency_org_name_edit", None)
        org_name = _norm_text(w.currentText() if w is not None else "")
    except Exception:
        org_name = ""
    try:
        w = getattr(self, "agency_org_code_edit", None)
        org_code = _norm_text(w.currentText() if w is not None else "")
    except Exception:
        org_code = ""
    return _norm_text(org_name), _norm_text(org_code)


def _refresh_agency_inline_fact_dropdown(self, *, col: str, typed_norm: str) -> list[str]:
    q_limit = 60 if typed_norm else 30
    c = _norm_text(col)

    if c in ("agency_name", "agency_code"):
        values: list[str] = []
        try:
            result = query_agency_agent_candidates(col=c, typed=typed_norm, limit=int(q_limit))
            values = result.values
        except Exception:
            values = []

        if values:
            return values

        fact_col = "agency_ref_name" if c == "agency_name" else "agency_ref_code"
        group_name_for_query = _get_group_name_for_fact_query(self)
        try:
            result2 = query_fact_record_candidates(
                group_name=group_name_for_query,
                col=fact_col,
                typed=typed_norm,
                limit=int(q_limit),
            )
            return result2.values
        except Exception:
            return []

    if c in ("agent_name", "agent_cert_no", "agent_phone"):
        org_name, org_code = _read_agency_filters(self)
        if org_name or org_code:
            try:
                result = query_agency_agents(agency_name=org_name, agency_code=org_code, agent_name="", limit=500)
                return _candidate_values_for_col(result.records, c, typed_norm, limit=int(q_limit))
            except Exception:
                return []

        try:
            result = query_agency_agent_candidates(col=c, typed=typed_norm, limit=int(q_limit))
            return result.values
        except Exception:
            return []

    return []


def _refresh_inline_fact_dropdown(self, combo: QComboBox, *, show_popup: bool = False) -> None:
    if combo is None:
        return
    scope, col = _get_inline_fact_combo_field(self, combo)
    if not scope or not col:
        return

    try:
        if bool(combo.property("_inline_fact_refreshing")):
            return
    except Exception:
        pass
    try:
        combo.setProperty("_inline_fact_refreshing", True)
    except Exception:
        pass

    ctx_key = _get_inline_fact_combo_ctx_key(self, combo, scope)

    try:
        typed = combo.currentText()
    except Exception:
        typed = ""
    typed_norm = _norm_text(typed)

    values: list[str] = []
    rows_for_display: list[dict] = []
    if scope == "agency":
        values = _refresh_agency_inline_fact_dropdown(self, col=str(col or ""), typed_norm=typed_norm)
    elif _use_weak_fact_filters(self):
        exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=False)
        exact_dict = exact if isinstance(exact, dict) else {}
        has_exact = any(_norm_text(v) for v in exact_dict.values())

        anchor_apps = []
        agency_ref_code = ""
        if scope != "applicant":
            if scope == "poa":
                anchor_apps = _collect_poa_applicant_anchor_groups_for_ctx(self, ctx_key=str(ctx_key or ""), combo=combo)
                agency_ref_code = _get_agency_ref_code_for_poa(self)
            else:
                anchor_apps = _collect_all_applicant_anchor_groups(self)

        if scope == "poa" and ((not anchor_apps) or (not _norm_text(agency_ref_code))):
            should_query_records = False
        else:
            should_query_records = bool(has_exact) or bool(anchor_apps)

        if should_query_records:
            rows, _trunc = _get_current_fact_rows(self, ctx_key=str(ctx_key or ""), scope=str(scope or ""))
            rows_for_display = rows if isinstance(rows, list) else []
            if typed_norm:
                values = _candidate_values_for_col(rows, col, typed_norm, limit=60)
            else:
                values = _candidate_values_for_col(rows, col, "", limit=30)
        else:
            if scope == "poa":
                values = []
            else:
                group_name_for_query = _get_group_name_for_fact_query(self)
                try:
                    q_limit = 60 if typed_norm else 30
                    result = query_fact_record_candidates(
                        group_name=group_name_for_query,
                        col=col,
                        typed=typed_norm,
                        limit=int(q_limit),
                    )
                    values = result.values
                except Exception:
                    values = []
    else:
        rows, _trunc = _get_current_fact_rows(self, ctx_key=str(ctx_key or ""), scope=str(scope or ""))
        rows_for_display = rows if isinstance(rows, list) else []
        if typed_norm:
            values = _candidate_values_for_col(rows, col, typed_norm, limit=60)
        else:
            values = _candidate_values_for_col(rows, col, "", limit=30)

    cur_text = typed_norm
    le = None
    try:
        le = combo.lineEdit()
    except Exception:
        le = None
    try:
        cursor_pos = int(le.cursorPosition()) if le is not None else None
    except Exception:
        cursor_pos = None

    display_map: dict[str, list[str]] = {}
    if scope in ("inventor", "contact") and col in ("inventor_name", "contact_name") and rows_for_display:
        app_name_set: set[str] = set()
        try:
            for g in _collect_all_applicant_anchor_groups(self) or []:
                if not isinstance(g, dict):
                    continue
                name = _norm_text(g.get("name"))
                if name:
                    app_name_set.add(name)
        except Exception:
            app_name_set = set()

        for row in rows_for_display or []:
            if not isinstance(row, dict):
                continue
            key = _norm_text(row.get(col))
            if not key:
                continue
            app_name = _norm_text(row.get("applicant_name"))
            if not app_name:
                continue
            if app_name_set and app_name not in app_name_set:
                continue
            cur = display_map.get(key)
            if cur is None:
                display_map[key] = [app_name]
            elif app_name not in cur:
                cur.append(app_name)

    try:
        combo.blockSignals(True)
        if le is not None:
            le.blockSignals(True)
        combo.clear()
        for v in values:
            try:
                raw = _norm_text(v)
                assoc = display_map.get(raw, []) if raw else []
                if assoc:
                    shown = "、".join(assoc[:2])
                    if len(assoc) > 2:
                        shown = f"{shown}等/共{len(assoc)}个"
                    
                    if scope == "inventor" and col == "inventor_name":
                        # Use delegate approach: clean text + side data
                        combo.addItem(v, v)
                        # UserRole + 1 for associated info (see delegate.py)
                        combo.setItemData(combo.count() - 1, shown, Qt.UserRole + 1)
                    else:
                        # Legacy approach: text suffix
                        display_text = f"{v} |关联：{shown}"
                        combo.addItem(display_text, v)
                else:
                    combo.addItem(v, v) # Set UserRole as well for consistency
            except Exception:
                pass
        try:
            combo.setCurrentIndex(-1)
        except Exception:
            pass
        try:
            combo.setEditText(cur_text)
        except Exception:
            pass
        if le is not None and cursor_pos is not None:
            try:
                le.setCursorPosition(min(int(cursor_pos), len(cur_text)))
            except Exception:
                pass
    finally:
        try:
            if le is not None:
                le.blockSignals(False)
        except Exception:
            pass
        try:
            combo.blockSignals(False)
        except Exception:
            pass

    view = None
    try:
        view = combo.view()
    except Exception:
        view = None
    vp = None
    try:
        vp = view.viewport() if view is not None else None
    except Exception:
        vp = None

    try:
        mp = getattr(self, "_combo_popup_owner_map", None)
        if isinstance(mp, dict):
            if view is not None:
                mp[view] = combo
            if vp is not None:
                mp[vp] = combo
    except Exception:
        pass

    try:
        if view is not None:
            view.setFocusPolicy(Qt.NoFocus)
            if vp is not None:
                vp.setFocusPolicy(Qt.NoFocus)
    except Exception:
        pass

    view_visible = False
    try:
        view_visible = bool(view is not None and bool(view.isVisible()))
    except Exception:
        view_visible = False

    show_popup_effective = bool(show_popup) or bool(view_visible)

    if show_popup_effective:
        try:
            if values:
                if view is None or (not bool(view.isVisible())):
                    combo.showPopup()
                else:
                    try:
                        combo.update()
                    except Exception:
                        pass
            else:
                combo.hidePopup()
        except Exception:
            pass

    try:
        combo.setProperty("_inline_fact_refreshing", False)
    except Exception:
        pass


def _on_inline_fact_combo_text_edited(self, combo: QComboBox) -> None:
    if combo is None:
        return
    try:
        if bool(combo.property("_inline_fact_refreshing")):
            return
    except Exception:
        pass
    scope, col = _get_inline_fact_combo_field(self, combo)
    if not scope or not col:
        return

    ctx_key = _get_inline_fact_combo_ctx_key(self, combo, scope)
    try:
        txt = _norm_text(combo.currentText())
    except Exception:
        txt = ""

    try:
        exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=False)
        if isinstance(exact, dict) and _norm_text(exact.get(col)) and _norm_text(exact.get(col)) != _norm_text(txt):
            try:
                del exact[col]
            except Exception:
                pass
    except Exception:
        pass

    try:
        if not _use_weak_fact_filters(self):
            self._fact_candidates_cache_dirty = True
    except Exception:
        pass
    try:
        want_popup = False
        try:
            view = combo.view()
            want_popup = bool(view is not None and bool(view.isVisible()))
        except Exception:
            want_popup = False
        try:
            le = combo.lineEdit()
            want_popup = bool(want_popup) or bool(combo.hasFocus()) or bool(le is not None and le.hasFocus())
        except Exception:
            want_popup = False
        self._refresh_inline_fact_dropdown(combo, show_popup=bool(want_popup))
    except Exception:
        pass
    finally:
        try:
            combo.setProperty("_inline_fact_refreshing", False)
        except Exception:
            pass
