from __future__ import annotations

from datetime import datetime
from typing import Any

from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready
from gui.dialog_utils import show_blocking_alert_modal
from gui.widgets_impl.tgd_fact_record_manager_utils import _make_record_hash

from .collect_ops import _SaveFactDialog, _collect_pending
from .conflict_ops import (
    _apply_soft_conflicts_overwrite,
    _collect_db_conflicts,
    _extend_db_conflict_msgs,
    _extend_internal_duplicate_msgs,
    _find_soft_conflicts,
    _group_pending_by_hash,
    _prompt_soft_conflicts,
    _query_existing_by_hash,
)


def _dedupe_deleted_ids(values: Any) -> list[int]:
    try:
        return list(dict.fromkeys([int(x) for x in (values or []) if x is not None]))
    except Exception:
        return []


def _clear_deleted_ids_safe(dlg: _SaveFactDialog) -> None:
    try:
        dlg._deleted_fact_ids = []
    except Exception:
        pass


def _delete_fact_rows(conn, deleted_ids: list[int]) -> None:
    if not deleted_ids:
        return
    placeholders_del = ",".join(["?"] * len(deleted_ids))
    conn.execute(
        f"DELETE FROM tgd_fact_record WHERE id IN ({placeholders_del})",
        tuple(deleted_ids),
    )


def _update_tmp_hash_for_existing_ids(conn, pending: list[dict], now: str) -> None:
    for p in pending:
        pid = p.get("id")
        if pid is None:
            continue
        tmp_hash = _make_record_hash("__tmp__", pid, now, p.get("row"))
        conn.execute(
            "UPDATE tgd_fact_record SET record_hash=? WHERE id=?",
            (tmp_hash, pid),
        )


def _upsert_pending(conn, pending: list[dict], now: str) -> tuple[int, int]:
    inserted = 0
    updated = 0

    for p in pending:
        pid = p.get("id")
        record_hash = p.get("record_hash")
        if pid is not None:
            conn.execute(
                """
                UPDATE tgd_fact_record SET
                    record_hash=?, applicant_name=?, applicant_type_code=?, applicant_id_type_code=?, applicant_id_no=?,
                    applicant_province_code=?, applicant_city_code=?, applicant_address=?, applicant_zip=?, applicant_phone=?, applicant_email=?,
                    inventor_name=?, inventor_id_type=?, inventor_id_no=?, inventor_nationality_code=?,
                    contact_name=?, contact_phone=?, contact_email=?, contact_province_code=?, contact_city_code=?, contact_street=?, contact_zip=?,
                    group_name=?, power_of_attorney_no=?, agency_ref_name=?, agency_ref_code=?,
                    updated_at=?, source_type='manual'
                WHERE id=?
                """,
                (
                    record_hash,
                    p.get("applicant_name"),
                    p.get("app_type_code"),
                    p.get("app_id_type_code"),
                    p.get("app_id_no"),
                    p.get("app_prov"),
                    p.get("app_city"),
                    p.get("app_addr"),
                    p.get("app_zip"),
                    p.get("app_phone"),
                    p.get("app_email"),
                    p.get("inventor_name"),
                    p.get("inv_id_type"),
                    p.get("inv_id_no"),
                    p.get("inv_nat"),
                    p.get("ct_name"),
                    p.get("ct_phone"),
                    p.get("ct_email"),
                    p.get("ct_prov"),
                    p.get("ct_city"),
                    p.get("ct_street"),
                    p.get("ct_zip"),
                    p.get("group_name"),
                    p.get("poa"),
                    p.get("ag_name"),
                    p.get("ag_code"),
                    now,
                    pid,
                ),
            )
            updated += 1
        else:
            conn.execute(
                """
                INSERT INTO tgd_fact_record (
                    record_hash, applicant_name, applicant_type_code, applicant_id_type_code, applicant_id_no,
                    applicant_province_code, applicant_city_code, applicant_address, applicant_zip, applicant_phone, applicant_email,
                    inventor_name, inventor_id_type, inventor_id_no, inventor_nationality_code,
                    contact_name, contact_phone, contact_email, contact_province_code, contact_city_code, contact_street, contact_zip,
                    group_name, power_of_attorney_no, agency_ref_name, agency_ref_code,
                    created_at, updated_at, source_type, source_ref
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'manual','data_mgmt_manager')
                """,
                (
                    record_hash,
                    p.get("applicant_name"),
                    p.get("app_type_code"),
                    p.get("app_id_type_code"),
                    p.get("app_id_no"),
                    p.get("app_prov"),
                    p.get("app_city"),
                    p.get("app_addr"),
                    p.get("app_zip"),
                    p.get("app_phone"),
                    p.get("app_email"),
                    p.get("inventor_name"),
                    p.get("inv_id_type"),
                    p.get("inv_id_no"),
                    p.get("inv_nat"),
                    p.get("ct_name"),
                    p.get("ct_phone"),
                    p.get("ct_email"),
                    p.get("ct_prov"),
                    p.get("ct_city"),
                    p.get("ct_street"),
                    p.get("ct_zip"),
                    p.get("group_name"),
                    p.get("poa"),
                    p.get("ag_name"),
                    p.get("ag_code"),
                    now,
                    now,
                ),
            )
            inserted += 1

    return inserted, updated


def save_fact_record(dlg: _SaveFactDialog) -> None:
    db_path = get_db_path()
    ensure_db_ready(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    inserted = 0
    updated = 0

    try:
        with db_session(db_path) as conn:
            deleted_ids = _dedupe_deleted_ids(getattr(dlg, "_deleted_fact_ids", []))
            if deleted_ids:
                _delete_fact_rows(conn, deleted_ids)
                _clear_deleted_ids_safe(dlg)

            pending = _collect_pending(dlg)

            if not pending:
                if not deleted_ids:
                    show_blocking_alert_modal(dlg, "提示", "没有需要保存的修改。", primary_text="关闭", secondary_text="关闭")
                    return

            by_hash = _group_pending_by_hash(pending)
            conflict_msgs: list[str] = []

            _extend_internal_duplicate_msgs(by_hash, conflict_msgs)

            target_hashes = list(by_hash.keys())
            existing_rows = _query_existing_by_hash(conn, target_hashes)
            db_conflicts = _collect_db_conflicts(existing_rows, pending, by_hash)
            _extend_db_conflict_msgs(db_conflicts, conflict_msgs)

            if conflict_msgs:
                msg = "检测到本次保存存在重复记录（相同关键字段），为避免写入失败已阻止保存。\n\n" + "\n".join(conflict_msgs)
                show_blocking_alert_modal(dlg, "错误", msg, primary_text="关闭", secondary_text="关闭")
                return

            soft_conflicts = _find_soft_conflicts(conn, pending)
            if soft_conflicts:
                if not _prompt_soft_conflicts(dlg, soft_conflicts):
                    return
                _apply_soft_conflicts_overwrite(conn, pending, soft_conflicts)

            _update_tmp_hash_for_existing_ids(conn, pending, now)
            inserted, updated = _upsert_pending(conn, pending, now)

    except Exception as e:
        show_blocking_alert_modal(dlg, "错误", f"保存失败：{e}", primary_text="关闭", secondary_text="关闭")
        return

    msg = f"保存完成：新增 {inserted}，更新 {updated}"
    try:
        if deleted_ids:
            msg += f"，删除 {len(deleted_ids)}"
    except Exception:
        pass
    show_blocking_alert_modal(dlg, "完成", msg, primary_text="关闭", secondary_text="关闭")
    dlg._refresh_fact_table()
