from __future__ import annotations

import os
from datetime import datetime

from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal

from ..fact_dropdown import _norm_text
from ..value_picker import pick_multi_values_from_list
from .association_ops import (
    _query_associated_applicant_anchors_for_contact,
    _query_associated_applicant_anchors_for_inventor,
    _update_contact_fields_for_applicant_anchors,
    _update_inventor_fields_for_applicant_anchors,
)
from .base_ops import (
    _app_anchor_key,
    _format_applicant_for_pick,
    _get_agency_ref_from_request_info,
    _get_group_name_from_request_info,
)
from .persistence_ops import _make_record_hash_override_for_e1, _upsert_fact_record_rows


def _on_btn_import_to_data_mgmt_clicked(self) -> None:
    ok = ask_continue_cancel(
        self,
        "保存到常用信息",
        "确认将当前请求书中的申请人/发明人/联系人信息保存到常用信息？\n\n"
        "保存规则：同一条 record_hash 视为同一记录；新值仅在非空时覆盖旧值。",
        continue_text="确认保存",
        cancel_text="取消",
    )
    if not ok:
        return

    info = {}
    try:
        info, _ptype = self.get_request_data()
    except Exception:
        info = {}

    inserted, updated, skipped, errors = _import_request_info_to_data_mgmt_orchestrated(self, info if isinstance(info, dict) else {})
    msg = f"保存完成：新增 {inserted}，更新 {updated}，跳过 {skipped}"
    if errors:
        msg += "\n\n错误/警告：\n" + "\n".join(["- " + e for e in errors])
    show_blocking_alert_modal(self, "保存结果", msg, primary_text="关闭", secondary_text="关闭")

def _import_request_info_to_data_mgmt_orchestrated(self, info: dict) -> tuple[int, int, int, list[str]]:
    errors: list[str] = []

    applicants = []
    inventors = []
    contact: dict = {}
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

    applicants = [a for a in (applicants or []) if isinstance(a, dict) and any(_norm_text(a.get(k)) for k in ("name", "id_no", "address", "phone", "email"))]
    inventors = [v for v in (inventors or []) if isinstance(v, dict) and any(_norm_text(v.get(k)) for k in ("name", "id_no"))]
    contact_has_any = False
    try:
        contact_has_any = isinstance(contact, dict) and any(_norm_text(contact.get(k)) for k in ("name", "phone", "email"))
    except Exception:
        contact_has_any = False

    if (not applicants) and (not inventors) and (not contact_has_any):
        return 0, 0, 0, ["请求书信息为空"]

    group_name = _get_group_name_from_request_info(info)
    agency_ref_name, agency_ref_code = _get_agency_ref_from_request_info(info)

    base = os.path.basename(str(getattr(self, "_source_file_path", "") or "") or str(getattr(self, "_request_form_cache_key", "") or ""))
    source_type = "request_form"
    source_ref = (base or "") + "#request_form"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    app_display_items = [_format_applicant_for_pick(a) for a in applicants]
    app_count = len(applicants)

    cur_anchor_non_empty_set: set[tuple[str, str, str]] = set()
    for a in applicants:
        ak = _app_anchor_key(group_name, a)
        if _norm_text(ak[2]):
            cur_anchor_non_empty_set.add(ak)

    db_path = get_db_path()
    ensure_db_ready(db_path)

    inv_db_anchors: list[tuple[dict, list[tuple[str, str, str]]]] = []
    contact_db_anchors: list[tuple[dict, list[tuple[str, str, str]]]] = []
    try:
        with db_session(db_path) as conn:
            for inv in inventors:
                inv_db_anchors.append((inv, _query_associated_applicant_anchors_for_inventor(conn, group_name=group_name, inv=inv)))
            if contact_has_any and isinstance(contact, dict):
                contact_db_anchors.append((contact, _query_associated_applicant_anchors_for_contact(conn, group_name=group_name, contact=contact)))
    except Exception:
        inv_db_anchors = [(inv, []) for inv in inventors]
        if contact_has_any and isinstance(contact, dict):
            contact_db_anchors = [(contact, [])]

    inv_selected_app_indices: list[tuple[dict, list[int], str]] = []
    for inv, anchors in inv_db_anchors:
        a_db = anchors or []
        a_hit = [a for a in a_db if a in cur_anchor_non_empty_set]
        if a_hit:
            inv_selected_app_indices.append((inv, [], "hit"))
            continue

        if a_db:
            if app_count <= 0:
                errors.append("发明人断链：当前无申请人可供选择，已跳过")
                continue
            action, idxs = pick_multi_values_from_list(
                self,
                "发明人关联确认",
                app_display_items,
                prompt=(
                    f"发明人 {_norm_text(inv.get('name'))} 在常用信息中已存在，但其历史关联申请人不在当前请求书申请人列表中。\n\n"
                    f"请选择要关联到的申请人（可多选）。\n\n"
                    f"提示：保存不会自动删除历史关联；如需清理请到‘常用信息管理’页面手动处理。"
                ),
            )
            if action == "cancel":
                return 0, 0, 0, ["已取消保存"]
            if action == "skip":
                errors.append(f"发明人 {_norm_text(inv.get('name'))}：已跳过关联确认")
                continue
            inv_selected_app_indices.append((inv, idxs, "selected"))
            continue

        if app_count == 1:
            inv_selected_app_indices.append((inv, [0], "selected"))
            continue
        if app_count <= 0:
            errors.append("发明人新增：当前无申请人可供选择，已跳过")
            continue
        action, idxs = pick_multi_values_from_list(
            self,
            "发明人关联确认",
            app_display_items,
            prompt=(
                f"发明人 {_norm_text(inv.get('name'))} 在常用信息中不存在。\n\n"
                f"请选择要关联到的申请人（可多选）。"
            ),
        )
        if action == "cancel":
            return 0, 0, 0, ["已取消保存"]
        if action == "skip":
            errors.append(f"发明人 {_norm_text(inv.get('name'))}：已跳过关联确认")
            continue
        inv_selected_app_indices.append((inv, idxs, "selected"))

    contact_selected_app_indices: list[tuple[dict, list[int], str]] = []
    for c, anchors in contact_db_anchors:
        a_db = anchors or []
        a_hit = [a for a in a_db if a in cur_anchor_non_empty_set]
        if a_hit:
            contact_selected_app_indices.append((c, [], "hit"))
            continue

        if a_db:
            if app_count <= 0:
                errors.append("联系人断链：当前无申请人可供选择，已跳过")
                continue
            action, idxs = pick_multi_values_from_list(
                self,
                "联系人关联确认",
                app_display_items,
                prompt=(
                    f"联系人 {_norm_text(c.get('name'))} 在常用信息中已存在，但其历史关联申请人不在当前请求书申请人列表中。\n\n"
                    f"请选择要关联到的申请人（可多选）。\n\n"
                    f"提示：保存不会自动删除历史关联；如需清理请到‘常用信息管理’页面手动处理。"
                ),
            )
            if action == "cancel":
                return 0, 0, 0, ["已取消保存"]
            if action == "skip":
                errors.append(f"联系人 {_norm_text(c.get('name'))}：已跳过关联确认")
                continue
            contact_selected_app_indices.append((c, idxs, "selected"))
            continue

        if app_count == 1:
            contact_selected_app_indices.append((c, [0], "selected"))
            continue
        if app_count <= 0:
            errors.append("联系人新增：当前无申请人可供选择，已跳过")
            continue
        action, idxs = pick_multi_values_from_list(
            self,
            "联系人关联确认",
            app_display_items,
            prompt=(
                f"联系人 {_norm_text(c.get('name'))} 在常用信息中不存在。\n\n"
                f"请选择要关联到的申请人（可多选）。"
            ),
        )
        if action == "cancel":
            return 0, 0, 0, ["已取消保存"]
        if action == "skip":
            errors.append(f"联系人 {_norm_text(c.get('name'))}：已跳过关联确认")
            continue
        contact_selected_app_indices.append((c, idxs, "selected"))

    manual_updated = 0
    try:
        with db_session(db_path) as conn:
            for inv, anchors in inv_db_anchors:
                a_hit = [a for a in (anchors or []) if a in cur_anchor_non_empty_set]
                if not a_hit:
                    continue
                manual_updated += _update_inventor_fields_for_applicant_anchors(
                    conn,
                    group_name=group_name,
                    inv=inv,
                    target_anchors=a_hit,
                    now=now,
                    source_type=source_type,
                    source_ref=source_ref,
                )
            for c, anchors in contact_db_anchors:
                a_hit = [a for a in (anchors or []) if a in cur_anchor_non_empty_set]
                if not a_hit:
                    continue
                manual_updated += _update_contact_fields_for_applicant_anchors(
                    conn,
                    group_name=group_name,
                    contact=c,
                    target_anchors=a_hit,
                    now=now,
                    source_type=source_type,
                    source_ref=source_ref,
                )
    except Exception as e:
        errors.append(f"更新既有关联字段失败：{e}")

    rows_to_insert: list[dict] = []
    for app in applicants:
        poa_no = ""
        try:
            poa_no = _norm_text(app.get("power_of_attorney_no"))
        except Exception:
            poa_no = ""
        rows_to_insert.append(
            {
                "app": app,
                "inv": {},
                "contact": {},
                "group_name": group_name,
                "power_of_attorney_no": poa_no,
                "agency_ref_name": agency_ref_name,
                "agency_ref_code": agency_ref_code,
            }
        )

    for inv, idxs, mode in inv_selected_app_indices:
        if mode != "selected":
            continue
        for j in idxs:
            try:
                j2 = int(j)
            except Exception:
                continue
            if j2 < 0 or j2 >= len(applicants):
                continue
            app = applicants[j2]
            poa_no = ""
            try:
                poa_no = _norm_text(app.get("power_of_attorney_no"))
            except Exception:
                poa_no = ""
            rows_to_insert.append(
                {
                    "app": app,
                    "inv": inv,
                    "contact": {},
                    "group_name": group_name,
                    "power_of_attorney_no": poa_no,
                    "agency_ref_name": agency_ref_name,
                    "agency_ref_code": agency_ref_code,
                }
            )

    for c, idxs, mode in contact_selected_app_indices:
        if mode != "selected":
            continue
        for j in idxs:
            try:
                j2 = int(j)
            except Exception:
                continue
            if j2 < 0 or j2 >= len(applicants):
                continue
            app = applicants[j2]
            poa_no = ""
            try:
                poa_no = _norm_text(app.get("power_of_attorney_no"))
            except Exception:
                poa_no = ""
            rows_to_insert.append(
                {
                    "app": app,
                    "inv": {},
                    "contact": c,
                    "group_name": group_name,
                    "power_of_attorney_no": poa_no,
                    "agency_ref_name": agency_ref_name,
                    "agency_ref_code": agency_ref_code,
                }
            )

    for k, item in enumerate(rows_to_insert, start=1):
        app = item.get("app") if isinstance(item.get("app"), dict) else {}
        ak = _app_anchor_key(group_name, app)
        if not _norm_text(ak[2]):
            try:
                item["record_hash_override"] = _make_record_hash_override_for_e1(
                    "E1",
                    now,
                    source_ref,
                    k,
                    _norm_text(app.get("name")),
                    _norm_text(app.get("id_no")),
                )
            except Exception:
                pass

    new_recs, dup_recs, skipped, upsert_errors = _upsert_fact_record_rows(self, rows_to_insert)
    inserted = len(new_recs)
    updated_upsert = len(dup_recs)

    if upsert_errors:
        errors.extend(list(upsert_errors or [])[:60])
    return int(inserted), int(updated_upsert + manual_updated), int(skipped), errors

