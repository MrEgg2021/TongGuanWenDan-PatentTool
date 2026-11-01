from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready

from ..fact_dropdown import _norm_text
from .base_ops import _coalesce_non_empty_str, _make_record_hash


def _make_record_hash_override_for_e1(*parts: Any) -> str:
    return _make_record_hash(*parts)

def _build_fact_records_from_request_info(self, info: dict) -> tuple[list[dict], list[str]]:
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

    agency_ref_name = ""
    agency_ref_code = ""
    try:
        agency_info = info.get("agency_info")
    except Exception:
        agency_info = None
    if isinstance(agency_info, dict):
        agency_ref_name = _norm_text(agency_info.get("name"))
        agency_ref_code = _norm_text(agency_info.get("code"))

    apps_raw = [
        a
        for a in applicants
        if isinstance(a, dict)
        and any(_norm_text(a.get(k)) for k in ("name", "id_no", "address", "phone", "email"))
    ]
    invs_raw = [v for v in inventors if isinstance(v, dict) and any(_norm_text(v.get(k)) for k in ("name", "id_no"))]

    invs = [v for v in invs_raw if _norm_text(v.get("id_no"))]
    apps = apps_raw if apps_raw else [{}]
    invs = invs if invs else [{}]

    errors: list[str] = []
    contact_has_any = False
    try:
        contact_has_any = isinstance(contact, dict) and any(_norm_text(contact.get(k)) for k in ("name", "phone", "email"))
    except Exception:
        contact_has_any = False
    if (not apps_raw) and (not invs_raw) and (not contact_has_any):
        errors.append("请求书信息为空")

    rows: list[dict] = []
    for app in apps:
        for inv in invs:
            poa_no = ""
            try:
                poa_no = _norm_text(app.get("power_of_attorney_no"))
            except Exception:
                poa_no = ""
            rows.append(
                {
                    "app": app,
                    "inv": inv,
                    "contact": contact if isinstance(contact, dict) else {},
                    "group_name": group_name,
                    "power_of_attorney_no": poa_no,
                    "agency_ref_name": agency_ref_name,
                    "agency_ref_code": agency_ref_code,
                }
            )
    return rows, errors

def _upsert_fact_record_rows(self, combos: list[dict]) -> tuple[list[dict], list[dict], int, list[str]]:
    new_details: list[dict] = []
    dup_details: list[dict] = []
    skipped = 0
    errors: list[str] = []

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base = os.path.basename(str(getattr(self, "_source_file_path", "") or "") or str(getattr(self, "_request_form_cache_key", "") or ""))
    source_type = "request_form"
    source_ref = (base or "") + "#request_form"

    db_path = get_db_path()
    ensure_db_ready(db_path)

    with db_session(db_path) as conn:
        for idx, item in enumerate(combos, start=1):
            if not isinstance(item, dict):
                continue
            app = item.get("app") if isinstance(item.get("app"), dict) else {}
            inv = item.get("inv") if isinstance(item.get("inv"), dict) else {}
            contact = item.get("contact") if isinstance(item.get("contact"), dict) else {}

            applicant_name = _norm_text(app.get("name"))
            applicant_type_code = _norm_text(app.get("type_code") or app.get("type"))
            applicant_id_type_code = _norm_text(app.get("id_type_code") or app.get("id_type"))
            applicant_id_no = _norm_text(app.get("id_no"))
            applicant_province_code = _norm_text(app.get("province_code"))
            applicant_city_code = _norm_text(app.get("city_code"))
            applicant_address = _norm_text(app.get("address"))
            applicant_zip = _norm_text(app.get("zip"))
            applicant_phone = _norm_text(app.get("phone"))
            applicant_email = _norm_text(app.get("email"))

            inventor_name = _norm_text(inv.get("name"))
            inventor_id_type = _norm_text(inv.get("id_type_code") or inv.get("id_type"))
            inventor_id_no = _norm_text(inv.get("id_no"))
            inventor_nationality_code = _norm_text(inv.get("nationality_code"))
            if (not inventor_id_type) and inventor_id_no and inventor_nationality_code.upper() == "CN":
                inventor_id_type = "居民身份证"

            contact_name = _norm_text(contact.get("name"))
            contact_phone = _norm_text(contact.get("phone"))
            contact_email = _norm_text(contact.get("email"))
            contact_province_code = _norm_text(contact.get("province_code"))
            contact_city_code = _norm_text(contact.get("city_code"))
            contact_street = _norm_text(contact.get("street"))
            contact_zip = _norm_text(contact.get("zip"))

            group_name = _norm_text(item.get("group_name"))
            poa_no = _norm_text(item.get("power_of_attorney_no"))
            agency_ref_name = _norm_text(item.get("agency_ref_name"))
            agency_ref_code = _norm_text(item.get("agency_ref_code"))

            # Construct display info for report
            detail_obj = {
                "applicant": applicant_name,
                "inventor": inventor_name,
                "source": base,
            }

            record_hash = _make_record_hash(
                applicant_name,
                applicant_type_code,
                applicant_id_type_code,
                applicant_id_no,
                applicant_province_code,
                applicant_city_code,
                applicant_address,
                applicant_zip,
                applicant_phone,
                applicant_email,
                inventor_name,
                inventor_id_type,
                inventor_id_no,
                inventor_nationality_code,
                contact_name,
                contact_phone,
                contact_email,
                contact_province_code,
                contact_city_code,
                contact_street,
                contact_zip,
                group_name,
                poa_no,
                agency_ref_code,
            )

            existing = None
            try:
                existing = conn.execute(
                    "SELECT * FROM tgd_fact_record WHERE record_hash = ? LIMIT 1", (record_hash,)
                ).fetchone()
            except Exception as e:
                skipped += 1
                if len(errors) < 30:
                    errors.append(f"第{idx}条组合：查询失败：{e}")
                continue

            if existing:
                try:
                    agency_ref_name_merged = _coalesce_non_empty_str(
                        agency_ref_name, existing["agency_ref_name"]
                    )
                    conn.execute(
                        """
                        UPDATE tgd_fact_record
                        SET
                            applicant_name = ?, applicant_type_code = ?, applicant_id_type_code = ?, applicant_id_no = ?,
                            applicant_province_code = ?, applicant_city_code = ?, applicant_address = ?, applicant_zip = ?,
                            applicant_phone = ?, applicant_email = ?,
                            inventor_name = ?, inventor_id_type = ?, inventor_id_no = ?, inventor_nationality_code = ?,
                            contact_name = ?, contact_phone = ?, contact_email = ?,
                            contact_province_code = ?, contact_city_code = ?, contact_street = ?, contact_zip = ?,
                            group_name = ?, power_of_attorney_no = ?, agency_ref_name = ?, agency_ref_code = ?,
                            updated_at = ?, source_type = ?, source_ref = ?
                        WHERE record_hash = ?
                        """,
                        (
                            applicant_name, applicant_type_code, applicant_id_type_code, applicant_id_no,
                            applicant_province_code, applicant_city_code, applicant_address, applicant_zip,
                            applicant_phone, applicant_email,
                            inventor_name, inventor_id_type, inventor_id_no, inventor_nationality_code,
                            contact_name, contact_phone, contact_email,
                            contact_province_code, contact_city_code, contact_street, contact_zip,
                            group_name, poa_no, agency_ref_name_merged, agency_ref_code,
                            now, source_type, source_ref,
                            record_hash
                        ),
                    )
                    dup_details.append(detail_obj)
                except Exception as e:
                    skipped += 1
                    if len(errors) < 30:
                        errors.append(f"第{idx}条组合：更新失败：{e}")
            else:
                try:
                    conn.execute(
                        """
                        INSERT INTO tgd_fact_record (
                            applicant_name, applicant_type_code, applicant_id_type_code, applicant_id_no,
                            applicant_province_code, applicant_city_code, applicant_address, applicant_zip,
                            applicant_phone, applicant_email,
                            inventor_name, inventor_id_type, inventor_id_no, inventor_nationality_code,
                            contact_name, contact_phone, contact_email,
                            contact_province_code, contact_city_code, contact_street, contact_zip,
                            group_name, power_of_attorney_no, agency_ref_name, agency_ref_code,
                            record_hash, created_at, updated_at, source_type, source_ref
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            applicant_name, applicant_type_code, applicant_id_type_code, applicant_id_no,
                            applicant_province_code, applicant_city_code, applicant_address, applicant_zip,
                            applicant_phone, applicant_email,
                            inventor_name, inventor_id_type, inventor_id_no, inventor_nationality_code,
                            contact_name, contact_phone, contact_email,
                            contact_province_code, contact_city_code, contact_street, contact_zip,
                            group_name, poa_no, agency_ref_name, agency_ref_code,
                            record_hash, now, now, source_type, source_ref
                        ),
                    )
                    new_details.append(detail_obj)
                except Exception as e:
                    skipped += 1
                    if len(errors) < 30:
                        errors.append(f"第{idx}条组合：新增失败：{e}")

    return new_details, dup_details, skipped, errors

