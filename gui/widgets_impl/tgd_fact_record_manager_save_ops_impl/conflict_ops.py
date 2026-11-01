from __future__ import annotations

from core.logging_utils import swallow_exception
from core.request_form_xml_impl.normalize import _normalize_applicant_type_code
from core.tgd_data_management_impl.excel_io_impl.text_utils import (
    _format_merged_address,
    _normalize_applicant_id_type_code,
)
from gui.dialog_utils import ask_continue_cancel
from gui.widgets_impl.tgd_fact_record_manager_utils import _norm_text

from .collect_ops import _SaveFactDialog


def _group_pending_by_hash(pending: list[dict]) -> dict[str, list[dict]]:
    by_hash: dict[str, list[dict]] = {}
    for p in pending:
        h = _norm_text(p.get("record_hash"))
        if not h:
            continue
        by_hash.setdefault(h, []).append(p)
    return by_hash


def _extend_internal_duplicate_msgs(by_hash: dict[str, list[dict]], conflict_msgs: list[str]) -> None:
    internal_dup_hashes = [h for h, items in by_hash.items() if len(items) > 1]
    if not internal_dup_hashes:
        return

    for h in internal_dup_hashes[:20]:
        items = by_hash.get(h, [])
        rows_txt = ", ".join(str(int(it.get("row", 0))) for it in items)
        any_it = items[0] if items else {}
        conflict_msgs.append(
            f"【本次填写重复】第 {rows_txt} 行（申请人：{_norm_text(any_it.get('applicant_name'))}；发明人：{_norm_text(any_it.get('inventor_name'))}；分组：{_norm_text(any_it.get('group_name'))}）"
        )

    if len(internal_dup_hashes) > 20:
        conflict_msgs.append(f"... 还有 {len(internal_dup_hashes) - 20} 组重复未展示")


def _query_existing_by_hash(conn, target_hashes: list[str]) -> list:
    if not target_hashes:
        return []

    placeholders = ",".join(["?"] * len(target_hashes))
    try:
        return conn.execute(
            f"""
            SELECT id, record_hash, applicant_name, applicant_id_no, inventor_name, group_name
            FROM tgd_fact_record
            WHERE record_hash IN ({placeholders})
            """,
            tuple(target_hashes),
        ).fetchall()
    except Exception:
        swallow_exception("_query_existing_by_hash")
        return []


def _collect_db_conflicts(existing_rows: list, pending: list[dict], by_hash: dict[str, list[dict]]) -> list[tuple[dict, tuple]]:
    pending_ids = {p.get("id") for p in pending if p.get("id") is not None}
    pending_id_to_hash = {p.get("id"): p.get("record_hash") for p in pending if p.get("id") is not None}

    db_conflicts: list[tuple[dict, tuple]] = []
    for er in existing_rows:
        ex_id = er[0]
        ex_hash = _norm_text(er[1])
        for p in by_hash.get(ex_hash, []):
            pid = p.get("id")
            if pid == ex_id:
                continue
            if ex_id in pending_ids:
                nh = _norm_text(pending_id_to_hash.get(ex_id))
                if nh and nh != ex_hash:
                    continue
            db_conflicts.append((p, er))

    return db_conflicts


def _extend_db_conflict_msgs(db_conflicts: list[tuple[dict, tuple]], conflict_msgs: list[str]) -> None:
    if not db_conflicts:
        return

    for p, er in db_conflicts[:20]:
        rno = int(p.get("row", 0))
        ex_id = er[0]
        ex_app = _norm_text(er[2])
        ex_app_id_no = _norm_text(er[3])
        ex_inv = _norm_text(er[4])
        ex_group = _norm_text(er[5])
        cur_app = _norm_text(p.get("applicant_name"))
        cur_inv = _norm_text(p.get("inventor_name"))
        conflict_msgs.append(
            f"【与库中已有记录重复】第 {rno} 行（申请人：{cur_app}；发明人：{cur_inv}） 与 库中 id={ex_id}（申请人：{ex_app}；证件号：{ex_app_id_no}；发明人：{ex_inv}；分组：{ex_group}）重复"
        )

    if len(db_conflicts) > 20:
        conflict_msgs.append(f"... 还有 {len(db_conflicts) - 20} 条库冲突未展示")


def _make_display_tuple(d: dict) -> tuple:
    def _fmt_addr(prov, city, det, zip_c):
        return _format_merged_address(
            province_code=_norm_text(prov),
            city_code=_norm_text(city),
            detail=_norm_text(det),
            zip_code=_norm_text(zip_c),
            masked=False
        )

    return (
        _norm_text(d.get("applicant_name")),
        _normalize_applicant_type_code("", _norm_text(d.get("applicant_type_code")), ""), # normalize code logic might differ slightly, rely on what's stored or norm
        # Actually, pending has 'app_type_code' (normalized) and 'applicant_name'.
        # DB row has 'applicant_type_code'.
        # To be safe, compare the values as they are (normalized).
        _norm_text(d.get("applicant_type_code") or d.get("app_type_code")),
        _normalize_applicant_id_type_code(_norm_text(d.get("applicant_id_type_code") or d.get("app_id_type_code"))),
        _norm_text(d.get("applicant_id_no") or d.get("app_id_no")),
        _norm_text(d.get("applicant_phone") or d.get("app_phone")),
        _norm_text(d.get("applicant_email") or d.get("app_email")),
        _fmt_addr(
            d.get("applicant_province_code") or d.get("app_prov"),
            d.get("applicant_city_code") or d.get("app_city"),
            d.get("applicant_address") or d.get("app_addr"),
            d.get("applicant_zip") or d.get("app_zip")
        ),
        _norm_text(d.get("inventor_name")),
        _norm_text(d.get("inventor_id_type") or d.get("inv_id_type")),
        _norm_text(d.get("inventor_id_no") or d.get("inv_id_no")),
        _norm_text(d.get("inventor_nationality_code") or d.get("inv_nat")),
        _norm_text(d.get("contact_name") or d.get("ct_name")),
        _norm_text(d.get("contact_phone") or d.get("ct_phone")),
        _norm_text(d.get("contact_email") or d.get("ct_email")),
        _fmt_addr(
            d.get("contact_province_code") or d.get("ct_prov"),
            d.get("contact_city_code") or d.get("ct_city"),
            d.get("contact_street") or d.get("ct_street"),
            "", # Contact address usually doesn't have zip in the merged string in UI logic used here? 
            # Wait, _format_merged_address takes zip. 
            # In UI build: contact_addr = _format_merged_address(..., zip_code="", ...)
            # Let's match UI logic: zip is separate col in Right Table.
            # But let's include zip in tuple for strict visual match.
        ),
        _norm_text(d.get("contact_zip") or d.get("ct_zip")),
        _norm_text(d.get("group_name")),
        _norm_text(d.get("power_of_attorney_no") or d.get("poa")),
        _norm_text(d.get("agency_ref_name") or d.get("ag_name")),
        _norm_text(d.get("agency_ref_code") or d.get("ag_code")),
    )


def _find_soft_conflicts(conn, pending: list[dict]) -> list[tuple[dict, dict]]:
    pending_app_names = list(set(_norm_text(p.get("applicant_name")) for p in pending if p.get("applicant_name")))
    if not pending_app_names:
        return []

    placeholders_app = ",".join(["?"] * len(pending_app_names))
    db_candidates_cur = conn.execute(
        f"""
        SELECT *
        FROM tgd_fact_record
        WHERE applicant_name IN ({placeholders_app})
        """,
        tuple(pending_app_names),
    )
    db_rows = db_candidates_cur.fetchall() or []

    soft_conflicts: list[tuple[dict, dict]] = []
    for p in pending:
        p_disp = _make_display_tuple(p)
        p_id = p.get("id")

        for db_row in db_rows:
            d_row = dict(db_row)
            d_id = d_row.get("id")

            # Skip self
            if p_id is not None and int(p_id) == int(d_id):
                continue

            d_disp = _make_display_tuple(d_row)
            if p_disp == d_disp:
                soft_conflicts.append((p, d_row))
                break

    return soft_conflicts


def _prompt_soft_conflicts(dlg: _SaveFactDialog, soft_conflicts: list[tuple[dict, dict]]) -> bool:
    if not soft_conflicts:
        return True

    lines = []
    for p, d_row in soft_conflicts[:20]:
        rno = int(p.get("row", 0))
        app_name = _norm_text(p.get("applicant_name"))
        inv_name = _norm_text(p.get("inventor_name"))
        lines.append(f"第 {rno} 行（申请人：{app_name}，发明人：{inv_name}）与已有记录显示内容一致")

    extra = ""
    if len(soft_conflicts) > 20:
        extra = f"\n... 共 {len(soft_conflicts)} 条疑似重复未展示"

    msg = (
        "以下记录与已有记录的显示内容一致。为避免重复，可以用本次填写更新已有记录。\n\n"
        f"{chr(10).join(lines)}{extra}\n\n"
        "点击“覆盖旧记录”保存本次填写，或点击“取消保存”返回核对。"
    )

    choice = ask_continue_cancel(
        dlg,
        "疑似重复提示",
        msg,
        continue_text="覆盖旧记录 (推荐)",
        cancel_text="取消保存",
        default_continue=True,
    )
    return bool(choice)


def _apply_soft_conflicts_overwrite(conn, pending: list[dict], soft_conflicts: list[tuple[dict, dict]]) -> None:
    processed_pending_indices = set()
    ids_to_delete_additionally = []

    for p, d_row in soft_conflicts:
        p_idx = pending.index(p)
        if p_idx in processed_pending_indices:
            continue

        target_id = d_row.get("id")
        original_p_id = p.get("id")

        p["id"] = target_id

        if original_p_id is not None and int(original_p_id) != int(target_id):
            ids_to_delete_additionally.append(int(original_p_id))

        processed_pending_indices.add(p_idx)

    if ids_to_delete_additionally:
        placeholders_del_add = ",".join(["?"] * len(ids_to_delete_additionally))
        conn.execute(
            f"DELETE FROM tgd_fact_record WHERE id IN ({placeholders_del_add})",
            tuple(ids_to_delete_additionally),
        )
