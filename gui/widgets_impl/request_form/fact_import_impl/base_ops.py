from __future__ import annotations

import hashlib
from typing import Any

from gui.dialog_utils import show_blocking_alert_modal

from ..fact_dropdown import _norm_text


def _set_cache_context(self, request_form_cache, cache_key: str, *, source_file_path: str = "") -> None:
    try:
        if isinstance(request_form_cache, dict):
            self._request_form_cache = request_form_cache
        else:
            self._request_form_cache = None
    except Exception:
        self._request_form_cache = None
    try:
        self._request_form_cache_key = str(cache_key or "")
    except Exception:
        self._request_form_cache_key = ""
    try:
        self._source_file_path = str(source_file_path or "")
    except Exception:
        self._source_file_path = ""

def _copy_list_of_dicts(items) -> list:
    out = []
    for it in items or []:
        if isinstance(it, dict):
            try:
                out.append(dict(it))
            except Exception:
                out.append({})
    return out

def _get_data_mgmt_draft_from_ui(self) -> dict:
    info = {}
    try:
        info, _ptype = self.get_request_data()
    except Exception:
        info = {}

    applicants = []
    inventors = []
    contact = {}
    try:
        applicants = info.get("applicants") or []
    except Exception:
        applicants = []
    try:
        inventors = info.get("inventors") or []
    except Exception:
        inventors = []
    try:
        contact = info.get("contact") or {}
    except Exception:
        contact = {}

    group_name = ""
    try:
        group_name = _norm_text(info.get("group_name"))
    except Exception:
        group_name = ""

    return {
        "applicants": _copy_list_of_dicts(applicants),
        "inventors": _copy_list_of_dicts(inventors),
        "contact": dict(contact) if isinstance(contact, dict) else {},
        "group_name": group_name,
    }

def _on_btn_save_clicked(self) -> None:
    cache = getattr(self, "_request_form_cache", None)
    key = _norm_text(getattr(self, "_request_form_cache_key", ""))
    if (not isinstance(cache, dict)) or (not key):
        show_blocking_alert_modal(self, "提示", "本次填写暂时无法保存。请先复制重要内容，返回后重新打开请求书；如仍失败，请查看程序日志排查。", primary_text="关闭", secondary_text="关闭")
        return

    draft = _get_data_mgmt_draft_from_ui(self)
    entry = cache.get(key)
    if not isinstance(entry, dict):
        entry = {}
    entry["data_mgmt_draft"] = draft
    cache[key] = entry
    show_blocking_alert_modal(self, "完成", "已保存（仅本次转档有效）。", primary_text="关闭", secondary_text="关闭")

def _normalize_applicant_type_code(v: Any) -> str:
    s = _norm_text(v)
    if not s:
        return ""
    if s and s[0].isdigit():
        return s[0]
    return s

def _normalize_applicant_id_type_code(v: Any) -> str:
    s = _norm_text(v)
    if not s:
        return ""
    upper = s.upper()
    if "统一社会信用" in s or upper.startswith("F"):
        return "F"
    if "身份证" in s or upper.startswith("I"):
        return "I"
    if "其他" in s or upper.startswith("O"):
        return "0"
    return s

def _coalesce_non_empty_str(new_val: Any, old_val: Any) -> str:
    nv = _norm_text(new_val)
    if nv:
        return nv
    return _norm_text(old_val)

def _coalesce_non_empty_int(new_val: Any, old_val: Any) -> int | None:
    if new_val is None:
        try:
            return int(old_val) if old_val is not None else None
        except Exception:
            return None
    try:
        return int(new_val)
    except Exception:
        return None

def _make_record_hash(*parts: Any) -> str:
    raw = "\x1f".join(_norm_text(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _mask_id_no(id_no: str) -> str:
    s = _norm_text(id_no)
    if not s:
        return ""
    if len(s) <= 8:
        return s
    return s[:4] + "***" + s[-4:]

def _format_applicant_for_pick(app: dict) -> str:
    name = _norm_text(app.get("name"))
    id_type = _normalize_applicant_id_type_code(app.get("id_type_code") or app.get("id_type"))
    id_no = _norm_text(app.get("id_no"))
    if id_no:
        return f"{name}｜{id_type}:{_mask_id_no(id_no)}"
    return f"{name}｜证件号为空"

def _get_group_name_from_request_info(info: dict) -> str:
    try:
        return _norm_text(info.get("group_name"))
    except Exception:
        return ""

def _get_agency_ref_from_request_info(info: dict) -> tuple[str, str]:
    agency_ref_name = ""
    agency_ref_code = ""
    try:
        agency_info = info.get("agency_info")
    except Exception:
        agency_info = None
    if isinstance(agency_info, dict):
        agency_ref_name = _norm_text(agency_info.get("name"))
        agency_ref_code = _norm_text(agency_info.get("code"))
    return agency_ref_name, agency_ref_code

def _app_anchor_key(group_name: str, app: dict) -> tuple[str, str, str]:
    g = _norm_text(group_name)
    id_type = _normalize_applicant_id_type_code(app.get("id_type_code") or app.get("id_type"))
    id_no = _norm_text(app.get("id_no"))
    return (g, _norm_text(id_type), _norm_text(id_no))

def _inv_match_key(inv: dict) -> tuple[str, str, str, str]:
    inv_id_type = _norm_text(inv.get("id_type_code") or inv.get("id_type"))
    inv_id_no = _norm_text(inv.get("id_no"))
    inv_name = _norm_text(inv.get("name"))
    inv_nat = _norm_text(inv.get("nationality_code")) or "CN"
    return (inv_id_type, inv_id_no, inv_name, inv_nat)

def _contact_match_key(contact: dict) -> tuple[str, str, str]:
    name = _norm_text(contact.get("name"))
    phone = _norm_text(contact.get("phone"))
    email = _norm_text(contact.get("email"))
    return (name, phone, email)

