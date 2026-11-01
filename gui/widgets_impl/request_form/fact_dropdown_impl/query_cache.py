from __future__ import annotations

import linecache
import sys
import time
import traceback
from collections import deque

from core.tgd_data_management_impl.fact_record_query import query_fact_records

from .extractors import _get_contact_data, _get_inventor_tab_data
from .registry import (
    _collect_all_applicant_anchor_groups,
    _collect_all_applicant_groups,
    _collect_poa_applicant_anchor_groups_for_ctx,
    _get_agency_ref_code_for_poa,
    _get_fact_selected_exact_for_ctx,
)
from .text_widget_utils import _norm_text, _stable_sig_for_dict


_TGD_FACT_DROPDOWN_LAST_EXC_KEY = ""
_TGD_FACT_DROPDOWN_LAST_EXC_TS = 0.0


def _dump_exception_last_frames(e: BaseException, *, limit: int = 80) -> None:
    try:
        tb = getattr(e, "__traceback__", None)
        if tb is None:
            return
        dq = deque(maxlen=int(limit) if int(limit) > 0 else 80)
        try:
            for frame, lineno in traceback.walk_tb(tb):
                dq.append((frame, int(lineno)))
        except Exception:
            return
        print(f"[TGD][fact_dropdown] traceback_last_frames={len(dq)} (showing last {int(limit)})", file=sys.stderr)
        for frame, lineno in dq:
            try:
                fn = str(getattr(frame.f_code, "co_filename", ""))
                name = str(getattr(frame.f_code, "co_name", ""))
                src = ""
                try:
                    src = (linecache.getline(fn, lineno) or "").strip()
                except Exception:
                    src = ""
                print(f"  File '{fn}', line {lineno}, in {name}", file=sys.stderr)
                if src:
                    print(f"    {src}", file=sys.stderr)
            except Exception:
                continue
    except Exception:
        return


def _should_log_fact_dropdown_exc(*, key: str, min_interval_s: float = 2.0) -> bool:
    global _TGD_FACT_DROPDOWN_LAST_EXC_KEY
    global _TGD_FACT_DROPDOWN_LAST_EXC_TS
    try:
        now = time.monotonic()
        if _TGD_FACT_DROPDOWN_LAST_EXC_KEY == key and (now - float(_TGD_FACT_DROPDOWN_LAST_EXC_TS)) < float(min_interval_s):
            return False
        _TGD_FACT_DROPDOWN_LAST_EXC_KEY = key
        _TGD_FACT_DROPDOWN_LAST_EXC_TS = now
        return True
    except Exception:
        return True


def _use_weak_fact_filters(self) -> bool:
    try:
        return bool(getattr(self, "_fact_dropdown_weak_filter_mode", False))
    except Exception:
        return False


def _get_group_name_for_fact_query(self) -> str | None:
    group_name = ""
    try:
        ge = getattr(self, "group_name_edit", None)
        if ge is not None:
            group_name = _norm_text(ge.text())
    except Exception:
        group_name = ""
    group_name_for_query = _norm_text(group_name)
    if not group_name_for_query:
        return None
    return group_name_for_query


def _build_fact_query_filters_from_exact(exact: dict) -> tuple[list, dict, dict]:
    if not isinstance(exact, dict) or not exact:
        return ([], {}, {})

    app: dict = {}
    inv: dict = {}
    contact: dict = {}

    if _norm_text(exact.get("applicant_name")):
        app["name"] = _norm_text(exact.get("applicant_name"))
    if _norm_text(exact.get("applicant_id_no")):
        app["id_no"] = _norm_text(exact.get("applicant_id_no"))
    if _norm_text(exact.get("applicant_address")):
        app["address"] = _norm_text(exact.get("applicant_address"))
    if _norm_text(exact.get("applicant_zip")):
        app["zip"] = _norm_text(exact.get("applicant_zip"))
    if _norm_text(exact.get("applicant_phone")):
        app["phone"] = _norm_text(exact.get("applicant_phone"))
    if _norm_text(exact.get("applicant_email")):
        app["email"] = _norm_text(exact.get("applicant_email"))

    if _norm_text(exact.get("inventor_name")):
        inv["name"] = _norm_text(exact.get("inventor_name"))
    if _norm_text(exact.get("inventor_id_no")):
        inv["id_no"] = _norm_text(exact.get("inventor_id_no"))

    if _norm_text(exact.get("contact_name")):
        contact["name"] = _norm_text(exact.get("contact_name"))
    if _norm_text(exact.get("contact_phone")):
        contact["phone"] = _norm_text(exact.get("contact_phone"))
    if _norm_text(exact.get("contact_email")):
        contact["email"] = _norm_text(exact.get("contact_email"))
    if _norm_text(exact.get("contact_street")):
        contact["street"] = _norm_text(exact.get("contact_street"))
    if _norm_text(exact.get("contact_zip")):
        contact["zip"] = _norm_text(exact.get("contact_zip"))

    app_groups = [app] if app else []
    return (app_groups, inv, contact)


def _compute_fact_query_signature(self, *, ctx_key: str, scope: str) -> tuple:
    group_name_for_query = _get_group_name_for_fact_query(self)

    ctx = _norm_text(ctx_key)
    sc = _norm_text(scope)
    if _use_weak_fact_filters(self):
        exact = _get_fact_selected_exact_for_ctx(self, ctx, create=False)
        anchor_apps = []
        agency_ref_code = ""
        if sc == "poa":
            anchor_apps = _collect_poa_applicant_anchor_groups_for_ctx(self, ctx_key=str(ctx_key or ""))
            agency_ref_code = _get_agency_ref_code_for_poa(self)
        elif sc and sc != "applicant":
            anchor_apps = _collect_all_applicant_anchor_groups(self)
        try:
            anchor_sig = tuple(_stable_sig_for_dict(a) for a in (anchor_apps or []) if isinstance(a, dict))
        except Exception:
            anchor_sig = tuple()
        if sc == "poa":
            return (
                "weak",
                ctx,
                sc,
                _norm_text(group_name_for_query),
                _norm_text(agency_ref_code),
                anchor_sig,
                _stable_sig_for_dict(exact if isinstance(exact, dict) else {}),
            )
        return (
            "weak",
            ctx,
            sc,
            _norm_text(group_name_for_query),
            anchor_sig,
            _stable_sig_for_dict(exact if isinstance(exact, dict) else {}),
        )

    apps = _collect_all_applicant_groups(self)

    group_name = ""
    try:
        ge = getattr(self, "group_name_edit", None)
        if ge is not None:
            group_name = _norm_text(ge.text())
    except Exception:
        group_name = ""
    try:
        inv_tab = self.inv_tabs.currentWidget() if getattr(self, "inv_tabs", None) else None
    except Exception:
        inv_tab = None
    inv_filter = _get_inventor_tab_data(self, inv_tab)
    contact_filter = _get_contact_data(self)
    try:
        app_sig = tuple(_stable_sig_for_dict(a) for a in (apps or []) if isinstance(a, dict))
    except Exception:
        app_sig = tuple()
    return (
        "strong",
        ctx,
        sc,
        _norm_text(group_name),
        app_sig,
        _stable_sig_for_dict(inv_filter or {}),
        _stable_sig_for_dict(contact_filter or {}),
    )


def _query_fact_records_cached(self, *, ctx_key: str, scope: str) -> tuple[list, bool]:
    sig = _compute_fact_query_signature(self, ctx_key=str(ctx_key or ""), scope=str(scope or ""))
    try:
        if (not bool(getattr(self, "_fact_candidates_cache_dirty", True))) and sig == getattr(self, "_fact_candidates_cache_sig", None):
            rows = getattr(self, "_fact_candidates_cache_rows", None) or []
            truncated = bool(getattr(self, "_fact_candidates_cache_truncated", False))
            return (rows if isinstance(rows, list) else [], truncated)
    except Exception:
        pass

    if _use_weak_fact_filters(self):
        group_name_for_query = _get_group_name_for_fact_query(self)
        exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=False)
        apps, inv_filter, contact_filter = _build_fact_query_filters_from_exact(exact if isinstance(exact, dict) else {})

        sc = _norm_text(scope)
        agency_ref_code = ""
        if sc == "poa":
            apps = _collect_poa_applicant_anchor_groups_for_ctx(self, ctx_key=str(ctx_key or ""))
            agency_ref_code = _get_agency_ref_code_for_poa(self)
            if (not apps) or (not _norm_text(agency_ref_code)):
                try:
                    self._fact_candidates_cache_rows = []
                    self._fact_candidates_cache_truncated = False
                    self._fact_candidates_cache_sig = sig
                    self._fact_candidates_cache_dirty = False
                except Exception:
                    pass
                return ([], False)
        elif sc and sc != "applicant":
            apps = _collect_all_applicant_anchor_groups(self)
        if (not apps) and (not inv_filter) and (not contact_filter):
            try:
                self._fact_candidates_cache_rows = []
                self._fact_candidates_cache_truncated = False
                self._fact_candidates_cache_sig = sig
                self._fact_candidates_cache_dirty = False
            except Exception:
                pass
            return ([], False)

        try:
            result = query_fact_records(
                group_name=group_name_for_query,
                applicant_groups=apps,
                inventor_filter=inv_filter,
                contact_filter=contact_filter,
                limit=500,
            )
            rows = result.records
            truncated = bool(result.truncated)
        except Exception as e:
            rows = []
            truncated = False
            try:
                exc_type = type(e).__name__
                key = f"weak|{exc_type}"
                if _should_log_fact_dropdown_exc(key=key):
                    print(
                        f"[TGD][fact_dropdown] 检索失败 (weak|ctx={_norm_text(ctx_key)}|scope={_norm_text(scope)}|exc={exc_type}): {e}",
                        file=sys.stderr,
                    )
                    msg = str(e)
                    if isinstance(e, RecursionError) or ("recursion" in (msg or "").lower()):
                        _dump_exception_last_frames(e)
            except Exception:
                pass

        if sc == "poa" and _norm_text(agency_ref_code):
            try:
                rows = [r for r in (rows or []) if isinstance(r, dict) and _norm_text(r.get("agency_ref_code")) == _norm_text(agency_ref_code)]
            except Exception:
                rows = []

        try:
            self._fact_candidates_cache_rows = rows if isinstance(rows, list) else []
            self._fact_candidates_cache_truncated = bool(truncated)
            self._fact_candidates_cache_sig = sig
            self._fact_candidates_cache_dirty = False
        except Exception:
            pass

        return (rows if isinstance(rows, list) else [], bool(truncated))

    apps = _collect_all_applicant_groups(self)

    group_name = ""
    try:
        ge = getattr(self, "group_name_edit", None)
        if ge is not None:
            group_name = _norm_text(ge.text())
    except Exception:
        group_name = ""
    try:
        inv_tab = self.inv_tabs.currentWidget() if getattr(self, "inv_tabs", None) else None
    except Exception:
        inv_tab = None
    inv_filter = _get_inventor_tab_data(self, inv_tab)
    contact_filter = _get_contact_data(self)

    try:
        group_name_for_query = _norm_text(group_name)
        if not group_name_for_query:
            group_name_for_query = None
        result = query_fact_records(
            group_name=group_name_for_query,
            applicant_groups=apps,
            inventor_filter=inv_filter,
            contact_filter=contact_filter,
            limit=500,
        )
        rows = result.records
        truncated = bool(result.truncated)
    except Exception as e:
        rows = []
        truncated = False
        try:
            exc_type = type(e).__name__
            key = f"strong|{exc_type}"
            if _should_log_fact_dropdown_exc(key=key):
                print(
                    f"[TGD][fact_dropdown] 检索失败 (strong|ctx={_norm_text(ctx_key)}|scope={_norm_text(scope)}|exc={exc_type}): {e}",
                    file=sys.stderr,
                )
                msg = str(e)
                if isinstance(e, RecursionError) or ("recursion" in (msg or "").lower()):
                    _dump_exception_last_frames(e)
        except Exception:
            pass

    try:
        self._fact_candidates_cache_rows = rows if isinstance(rows, list) else []
        self._fact_candidates_cache_truncated = bool(truncated)
        self._fact_candidates_cache_sig = sig
        self._fact_candidates_cache_dirty = False
    except Exception:
        pass

    return (rows if isinstance(rows, list) else [], bool(truncated))


def _apply_exact_filters(rows: list, exact: dict) -> list:
    if not isinstance(rows, list) or not rows:
        return []
    if not isinstance(exact, dict) or not exact:
        return rows
    narrowed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ok = True
        for col, v in (exact or {}).items():
            if not _norm_text(v):
                continue
            if _norm_text(row.get(col)) != _norm_text(v):
                ok = False
                break
        if ok:
            narrowed.append(row)
    return narrowed


def _get_current_fact_rows(self, *, ctx_key: str, scope: str) -> tuple[list, bool]:
    base_rows, truncated = _query_fact_records_cached(self, ctx_key=str(ctx_key or ""), scope=str(scope or ""))
    exact = _get_fact_selected_exact_for_ctx(self, str(ctx_key or ""), create=False)
    rows = _apply_exact_filters(base_rows, exact if isinstance(exact, dict) else {})
    try:
        self._fact_candidates = rows
        self._fact_candidates_truncated = bool(truncated)
    except Exception:
        pass
    return rows, bool(truncated)
