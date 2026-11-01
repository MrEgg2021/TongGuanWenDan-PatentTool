import os
from datetime import datetime
from typing import Any

from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready

from gui.widgets_impl.request_form import dialog as request_form_dialog

from .text_utils import _norm_text


def _is_effective_agent(agent: Any) -> bool:
    if not isinstance(agent, dict):
        return False
    return any(_norm_text(agent.get(k)) for k in ("name", "cert_no", "phone"))


def _collect_agency_agent_rows_from_info(info: dict) -> list[dict]:
    agency_info = None
    try:
        agency_info = info.get("agency_info")
    except Exception:
        agency_info = None

    if not isinstance(agency_info, dict):
        return []

    agency_name = _norm_text(agency_info.get("name"))
    agency_code = _norm_text(agency_info.get("code"))

    agents: list[dict] = []
    raw_agents = None
    try:
        raw_agents = agency_info.get("agents")
    except Exception:
        raw_agents = None
    if isinstance(raw_agents, list):
        for a in raw_agents:
            if not _is_effective_agent(a):
                continue
            agents.append(
                {
                    "name": _norm_text(a.get("name")),
                    "cert_no": _norm_text(a.get("cert_no")),
                    "phone": _norm_text(a.get("phone")),
                    "order": int(a.get("order") or 0),
                }
            )

    if not agents:
        for k in ("agent1", "agent2"):
            a = agency_info.get(k) if isinstance(agency_info.get(k), dict) else None
            if not _is_effective_agent(a):
                continue
            agents.append(
                {
                    "name": _norm_text(a.get("name")),
                    "cert_no": _norm_text(a.get("cert_no")),
                    "phone": _norm_text(a.get("phone")),
                    "order": int(a.get("order") or 0),
                }
            )

    try:
        agents = sorted(agents, key=lambda x: int(x.get("order") or 0))
    except Exception:
        pass

    rows: list[dict] = []
    for idx, a in enumerate(agents, start=1):
        rows.append(
            {
                "agency_name": agency_name,
                "agency_code": agency_code,
                "agent_name": _norm_text(a.get("name")),
                "agent_cert_no": _norm_text(a.get("cert_no")),
                "agent_phone": _norm_text(a.get("phone")),
                "row_index": int(idx),
            }
        )
    return rows


def _validate_agency_agent_rows(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    for i, r in enumerate(rows or [], start=1):
        if not isinstance(r, dict):
            continue
        miss: list[str] = []
        if not _norm_text(r.get("agency_name")):
            miss.append("代理机构名称")
        if not _norm_text(r.get("agency_code")):
            miss.append("代理机构代码")
        if not _norm_text(r.get("agent_name")):
            miss.append("代理师姓名")
        if not _norm_text(r.get("agent_cert_no")):
            miss.append("代理师资格证号")
        if not _norm_text(r.get("agent_phone")):
            miss.append("代理师电话")
        if miss:
            errors.append(f"代理机构信息 第{i}行：" + "、".join(miss))
    return errors


def _upsert_agency_agents_rows_to_db(rows: list[dict], *, source_path: str) -> None:
    if not rows:
        return
    db_path = get_db_path()
    ensure_db_ready(db_path)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base = os.path.basename(str(source_path or ""))
    per_agency_counter: dict[str, int] = {}

    try:
        with db_session(db_path) as conn:
            for r in rows:
                if not isinstance(r, dict):
                    continue
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


class _SilentImportCtx:
    def __init__(self, source_file_path: str):
        self._source_file_path = str(source_file_path or "")
        self._request_form_cache_key = self._source_file_path


def _silent_import_request_info_to_db(window, info: dict, *, source_path: str) -> tuple[list[dict], list[dict], int, list[str]]:
    ctx = _SilentImportCtx(source_path)
    combos, pre_errors = request_form_dialog._build_fact_records_from_request_info(ctx, info if isinstance(info, dict) else {})
    if pre_errors:
        return [], [], 0, [f"{os.path.basename(source_path)}：" + e for e in pre_errors]
    
    new_recs, dup_recs, skipped, errors = request_form_dialog._upsert_fact_record_rows(ctx, combos)
    
    merged_errors: list[str] = []
    if errors:
        merged_errors.extend([f"{os.path.basename(source_path)}：" + e for e in errors])
    return new_recs, dup_recs, skipped, merged_errors


def _collect_agency_rows_and_errors(parsed_info: dict) -> tuple[list[dict], list[str]]:
    agency_enabled = False
    try:
        agency_enabled = bool(parsed_info.get("agency_enabled"))
    except Exception:
        agency_enabled = False

    if not agency_enabled:
        try:
            for a in parsed_info.get("applicants") or []:
                if isinstance(a, dict) and _norm_text(a.get("power_of_attorney_no")):
                    agency_enabled = True
                    break
        except Exception:
            agency_enabled = agency_enabled

    if not agency_enabled:
        return [], []

    agency_rows_from_xml = _collect_agency_agent_rows_from_info(parsed_info)
    agency_errs_from_xml = _validate_agency_agent_rows(agency_rows_from_xml)
    if not agency_rows_from_xml:
        agency_errs_from_xml = ["代理机构信息缺失：请至少提供 1 条代理师信息（姓名/资格证号/电话）。"]
    return agency_rows_from_xml, agency_errs_from_xml
