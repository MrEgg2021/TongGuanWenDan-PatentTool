from __future__ import annotations

import os
from datetime import datetime


from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready
from gui.dialog_utils import show_blocking_alert_modal
from gui.widgets_impl.request_form import dialog as request_form_dialog
from gui.widgets_impl.tgd_zip_import_review_debug_ops import zip_dbg
from gui.widgets_impl.tgd_zip_import_review_utils import _norm_text


def validate_fact_rows(dlg) -> tuple[bool, list[str]]:
    missing: list[str] = []

    first_inv_obj = None
    try:
        if (dlg._fact_rows or []) and isinstance(dlg._fact_rows[0], dict):
            first_inv_obj = dlg._fact_rows[0].get("inv")
    except Exception:
        first_inv_obj = None

    for i, item in enumerate(dlg._fact_rows or [], start=1):
        app = item.get("app") if isinstance(item.get("app"), dict) else {}
        inv = item.get("inv") if isinstance(item.get("inv"), dict) else {}

        applicant_name = _norm_text(app.get("name"))
        applicant_type_code = _norm_text(app.get("type_code"))
        applicant_id_type_code = _norm_text(app.get("id_type_code"))
        applicant_id_no = _norm_text(app.get("id_no"))

        inventor_name = _norm_text(inv.get("name"))
        inventor_id_type = _norm_text(inv.get("id_type"))
        inventor_id_no = _norm_text(inv.get("id_no"))

        is_first_inventor = False
        try:
            is_first_inventor = first_inv_obj is not None and inv is first_inv_obj
        except Exception:
            is_first_inventor = False

        inventor_nat = _norm_text(inv.get("nationality_code")) or "CN"
        if inventor_nat:
            try:
                inv["nationality_code"] = inventor_nat
            except Exception:
                pass

        if (not inventor_id_type) and inventor_nat == "CN":
            inventor_id_type = "居民身份证"
            try:
                inv["id_type"] = inventor_id_type
            except Exception:
                pass

        row_missing = []
        if not applicant_name:
            row_missing.append("申请人名称")
        if not applicant_type_code:
            row_missing.append("申请人类型")
        if not applicant_id_type_code:
            row_missing.append("申请人证件类型")
        if not applicant_id_no:
            row_missing.append("申请人证件号码")
        if not inventor_name:
            row_missing.append("发明人姓名")
        if is_first_inventor:
            if inventor_nat == "CN" and (not inventor_id_type):
                row_missing.append("第一发明人证件类型")
            if not inventor_id_no:
                row_missing.append("第一发明人证件号码")

        if row_missing:
            missing.append(f"第{i}条：" + "、".join(row_missing))

    if missing:
        return False, missing
    return True, []


def collect_agency_rows(dlg) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    errors: list[str] = []

    try:
        rc = int(dlg.agency_table.rowCount())
    except Exception:
        rc = 0

    for i in range(rc):
        vals = []
        for c in range(5):
            it = None
            try:
                it = dlg.agency_table.item(i, c)
            except Exception:
                it = None
            vals.append(_norm_text(it.text() if it else ""))

        if not any(vals):
            continue

        name, code, agent_name, cert_no, phone = vals
        miss = []
        if not name:
            miss.append("代理机构名称")
        if not code:
            miss.append("代理机构代码")
        if not agent_name:
            miss.append("代理师姓名")
        if not cert_no:
            miss.append("代理师资格证号")
        if not phone:
            miss.append("代理师电话")
        if miss:
            errors.append(f"代理机构信息 第{i+1}行：" + "、".join(miss))
            continue

        rows.append(
            {
                "agency_name": name,
                "agency_code": code,
                "agent_name": agent_name,
                "agent_cert_no": cert_no,
                "agent_phone": phone,
                "row_index": int(i + 1),
            }
        )

    return rows, errors


def do_import(dlg) -> bool:
    ok, fact_errors = validate_fact_rows(dlg)
    if not ok:
        show_blocking_alert_modal(
            dlg,
            "提示",
            "以下字段不能为空：\n" + "\n".join(["- " + e for e in fact_errors]),
            primary_text="关闭",
            secondary_text="关闭",
        )
        try:
            zip_dbg(f"do_import invalid_fact_rows errors={len(fact_errors)}")
        except Exception:
            pass
        return False

    agency_rows, agency_errs = collect_agency_rows(dlg)
    if agency_errs:
        show_blocking_alert_modal(
            dlg,
            "提示",
            "代理机构信息有误：\n" + "\n".join(["- " + e for e in agency_errs]),
            primary_text="关闭",
            secondary_text="关闭",
        )
        try:
            zip_dbg(f"do_import invalid_agency_rows errors={len(agency_errs)}")
        except Exception:
            pass
        return False

    inserted, updated, skipped, errors = request_form_dialog._upsert_fact_record_rows(dlg, dlg._fact_rows)
    dlg._import_counts = (int(inserted), int(updated), int(skipped))
    dlg._import_errors = list(errors or [])

    if agency_rows:
        upsert_agency_agents(dlg, agency_rows)

    if dlg._import_errors:
        show_blocking_alert_modal(
            dlg,
            "导入结果",
            f"导入完成：新增 {inserted}，更新 {updated}，跳过 {skipped}\n\n错误/警告：\n" + "\n".join(["- " + e for e in dlg._import_errors[:60]]),
            primary_text="关闭",
            secondary_text="关闭",
        )

    try:
        zip_dbg(
            f"do_import done inserted={int(inserted)} updated={int(updated)} skipped={int(skipped)} errors={len(dlg._import_errors or [])} agency_rows={len(agency_rows or [])}"
        )
    except Exception:
        pass

    return True


def upsert_agency_agents(dlg, rows: list[dict]) -> None:
    db_path = get_db_path()
    ensure_db_ready(db_path)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base = os.path.basename(str(getattr(dlg, "_source_file_path", "") or ""))
    per_agency_counter: dict[str, int] = {}

    try:
        zip_dbg(f"upsert_agency_agents rows={len(rows or [])} db={db_path}")
    except Exception:
        pass

    try:
        with db_session(db_path) as conn:
            for r in rows:
                agency_name = _norm_text(r.get("agency_name"))
                agency_code = _norm_text(r.get("agency_code"))
                agent_name = _norm_text(r.get("agent_name"))
                agent_cert_no = _norm_text(r.get("agent_cert_no"))
                agent_phone = _norm_text(r.get("agent_phone"))
                row_index = int(r.get("row_index") or 0)

                if not all([agency_name, agency_code, agent_name, agent_cert_no, agent_phone]):
                    continue

                cnt = int(per_agency_counter.get(agency_code, 0)) + 1
                per_agency_counter[agency_code] = cnt
                sort_order = cnt

                existing = None
                try:
                    existing = conn.execute(
                        """
                        SELECT * FROM tgd_agency_agent
                        WHERE agency_code = ? AND agent_cert_no = ?
                        LIMIT 1
                        """,
                        (agency_code, agent_cert_no),
                    ).fetchone()
                except Exception:
                    existing = None

                source_type = "zip_import"
                source_ref = f"{base}#agency_row{row_index}" if base else f"zip_import#agency_row{row_index}"

                if existing:
                    try:
                        conn.execute(
                            """
                            UPDATE tgd_agency_agent
                            SET
                                agency_name = ?,
                                agent_name = ?,
                                agent_phone = ?,
                                sort_order = ?,
                                updated_at = ?,
                                source_type = ?,
                                source_ref = ?
                            WHERE id = ?
                            """,
                            (
                                agency_name,
                                agent_name,
                                agent_phone,
                                int(sort_order),
                                now,
                                source_type,
                                source_ref,
                                int(existing["id"]),
                            ),
                        )
                    except Exception:
                        continue
                else:
                    try:
                        conn.execute(
                            """
                            INSERT INTO tgd_agency_agent(
                                agency_name, agency_code, agent_name, agent_cert_no, agent_phone,
                                sort_order,
                                created_at, updated_at, source_type, source_ref
                            )
                            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                agency_name,
                                agency_code,
                                agent_name,
                                agent_cert_no,
                                agent_phone,
                                int(sort_order),
                                now,
                                now,
                                source_type,
                                source_ref,
                            ),
                        )
                    except Exception:
                        continue
    except Exception:
        return
