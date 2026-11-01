from __future__ import annotations

from typing import Any

from core.tgd_data_management_impl.pinyin_utils import get_pinyin_full, get_pinyin_initials

from ..fact_dropdown import _norm_text
from .base_ops import _coalesce_non_empty_str, _contact_match_key, _inv_match_key


def _query_associated_applicant_anchors_for_inventor(
    conn,
    *,
    group_name: str,
    inv: dict,
    limit: int = 500,
) -> list[tuple[str, str, str]]:
    inv_id_type, inv_id_no, inv_name, inv_nat = _inv_match_key(inv)
    where: list[str] = []
    params: list[Any] = []
    g = _norm_text(group_name)
    if g:
        where.append("group_name = ?")
        params.append(g)

    if inv_id_no:
        where.append("inventor_id_no = ?")
        params.append(inv_id_no)
        if inv_id_type:
            where.append("inventor_id_type = ?")
            params.append(inv_id_type)
    else:
        if inv_name:
            where.append("inventor_name = ?")
            params.append(inv_name)
        if inv_nat:
            where.append("inventor_nationality_code = ?")
            params.append(inv_nat)

    if not where:
        return []

    sql = (
        "SELECT DISTINCT group_name, applicant_id_type_code, applicant_id_no "
        "FROM tgd_fact_record WHERE "
        + " AND ".join(where)
        + " LIMIT ?"
    )
    params2 = list(params)
    params2.append(int(limit))
    anchors: list[tuple[str, str, str]] = []
    try:
        cur = conn.execute(sql, tuple(params2))
        for row in cur.fetchall() or []:
            try:
                anchors.append(
                    (
                        _norm_text(row["group_name"]),
                        _norm_text(row["applicant_id_type_code"]),
                        _norm_text(row["applicant_id_no"]),
                    )
                )
            except Exception:
                continue
    except Exception:
        return []

    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for a in anchors:
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out

def _query_associated_applicant_anchors_for_contact(
    conn,
    *,
    group_name: str,
    contact: dict,
    limit: int = 500,
) -> list[tuple[str, str, str]]:
    _name, phone, email = _contact_match_key(contact)
    where: list[str] = []
    params: list[Any] = []
    g = _norm_text(group_name)
    if g:
        where.append("group_name = ?")
        params.append(g)

    if phone:
        where.append("contact_phone = ?")
        params.append(phone)
    elif email:
        where.append("contact_email = ?")
        params.append(email)
    else:
        return []

    sql = (
        "SELECT DISTINCT group_name, applicant_id_type_code, applicant_id_no "
        "FROM tgd_fact_record WHERE "
        + " AND ".join(where)
        + " LIMIT ?"
    )
    params2 = list(params)
    params2.append(int(limit))
    anchors: list[tuple[str, str, str]] = []
    try:
        cur = conn.execute(sql, tuple(params2))
        for row in cur.fetchall() or []:
            try:
                anchors.append(
                    (
                        _norm_text(row["group_name"]),
                        _norm_text(row["applicant_id_type_code"]),
                        _norm_text(row["applicant_id_no"]),
                    )
                )
            except Exception:
                continue
    except Exception:
        return []

    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for a in anchors:
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out

def _update_inventor_fields_for_applicant_anchors(
    conn,
    *,
    group_name: str,
    inv: dict,
    target_anchors: list[tuple[str, str, str]],
    now: str,
    source_type: str,
    source_ref: str,
) -> int:
    inv_id_type, inv_id_no, inv_name, inv_nat = _inv_match_key(inv)
    new_name = _norm_text(inv.get("name"))
    new_id_type = _norm_text(inv.get("id_type_code") or inv.get("id_type"))
    new_id_no = _norm_text(inv.get("id_no"))
    new_nat = _norm_text(inv.get("nationality_code")) or "CN"
    if (not new_id_type) and new_nat == "CN":
        new_id_type = "居民身份证"

    if not target_anchors:
        return 0

    updated = 0
    for _g, app_id_type, app_id_no in target_anchors:
        if not _norm_text(app_id_no):
            continue
        where: list[str] = []
        params: list[Any] = []

        g = _norm_text(group_name)
        if g:
            where.append("group_name = ?")
            params.append(g)

        if inv_id_no:
            where.append("inventor_id_no = ?")
            params.append(inv_id_no)
            if inv_id_type:
                where.append("inventor_id_type = ?")
                params.append(inv_id_type)
        else:
            if inv_name:
                where.append("inventor_name = ?")
                params.append(inv_name)
            if inv_nat:
                where.append("inventor_nationality_code = ?")
                params.append(inv_nat)

        where.append("applicant_id_type_code = ?")
        params.append(_norm_text(app_id_type))
        where.append("applicant_id_no = ?")
        params.append(_norm_text(app_id_no))

        if not where:
            continue
        sql_sel = "SELECT id, inventor_name, inventor_id_type, inventor_id_no, inventor_nationality_code FROM tgd_fact_record WHERE " + " AND ".join(where)
        try:
            cur = conn.execute(sql_sel, tuple(params))
            rows = cur.fetchall() or []
        except Exception:
            rows = []
        for r in rows:
            try:
                row_id = int(r["id"])
            except Exception:
                continue
            try:
                old_name = r["inventor_name"]
                old_id_type = r["inventor_id_type"]
                old_id_no = r["inventor_id_no"]
                old_nat = r["inventor_nationality_code"]
            except Exception:
                old_name = ""
                old_id_type = ""
                old_id_no = ""
                old_nat = ""

            v_name = _coalesce_non_empty_str(new_name, old_name)
            v_id_type = _coalesce_non_empty_str(new_id_type, old_id_type)
            v_id_no = _coalesce_non_empty_str(new_id_no, old_id_no)
            v_nat = _coalesce_non_empty_str(new_nat, old_nat)

            v_name_pinyin = get_pinyin_full(v_name)
            v_name_initials = get_pinyin_initials(v_name)

            try:
                conn.execute(
                    """
                    UPDATE tgd_fact_record
                    SET
                        inventor_name = ?,
                        inventor_id_type = ?,
                        inventor_id_no = ?,
                        inventor_nationality_code = ?,
                        updated_at = ?,
                        source_type = ?,
                        source_ref = ?,
                        inventor_name_pinyin = ?,
                        inventor_name_initials = ?
                    WHERE id = ?
                    """,
                    (v_name, v_id_type, v_id_no, v_nat, now, source_type, source_ref, v_name_pinyin, v_name_initials, row_id),
                )
                updated += 1
            except Exception:
                continue
    return int(updated)

def _update_contact_fields_for_applicant_anchors(
    conn,
    *,
    group_name: str,
    contact: dict,
    target_anchors: list[tuple[str, str, str]],
    now: str,
    source_type: str,
    source_ref: str,
) -> int:
    _name, phone, email = _contact_match_key(contact)
    new_name = _norm_text(contact.get("name"))
    new_phone = _norm_text(contact.get("phone"))
    new_email = _norm_text(contact.get("email"))
    new_prov = _norm_text(contact.get("province_code"))
    new_city = _norm_text(contact.get("city_code"))
    new_street = _norm_text(contact.get("street"))
    new_zip = _norm_text(contact.get("zip"))

    if not target_anchors:
        return 0

    updated = 0
    for _g, app_id_type, app_id_no in target_anchors:
        if not _norm_text(app_id_no):
            continue
        where: list[str] = []
        params: list[Any] = []

        g = _norm_text(group_name)
        if g:
            where.append("group_name = ?")
            params.append(g)

        if phone:
            where.append("contact_phone = ?")
            params.append(phone)
        elif email:
            where.append("contact_email = ?")
            params.append(email)
        else:
            continue

        where.append("applicant_id_type_code = ?")
        params.append(_norm_text(app_id_type))
        where.append("applicant_id_no = ?")
        params.append(_norm_text(app_id_no))

        sql_sel = (
            "SELECT id, contact_name, contact_phone, contact_email, contact_province_code, contact_city_code, contact_street, contact_zip "
            "FROM tgd_fact_record WHERE "
            + " AND ".join(where)
        )
        try:
            cur = conn.execute(sql_sel, tuple(params))
            rows = cur.fetchall() or []
        except Exception:
            rows = []
        for r in rows:
            try:
                row_id = int(r["id"])
            except Exception:
                continue

            try:
                old_name = r["contact_name"]
                old_phone = r["contact_phone"]
                old_email = r["contact_email"]
                old_prov = r["contact_province_code"]
                old_city = r["contact_city_code"]
                old_street = r["contact_street"]
                old_zip = r["contact_zip"]
            except Exception:
                old_name = ""
                old_phone = ""
                old_email = ""
                old_prov = ""
                old_city = ""
                old_street = ""
                old_zip = ""

            v_name = _coalesce_non_empty_str(new_name, old_name)
            v_phone = _coalesce_non_empty_str(new_phone, old_phone)
            v_email = _coalesce_non_empty_str(new_email, old_email)
            v_prov = _coalesce_non_empty_str(new_prov, old_prov)
            v_city = _coalesce_non_empty_str(new_city, old_city)
            v_street = _coalesce_non_empty_str(new_street, old_street)
            v_zip = _coalesce_non_empty_str(new_zip, old_zip)

            v_name_pinyin = get_pinyin_full(v_name)
            v_name_initials = get_pinyin_initials(v_name)

            try:
                conn.execute(
                    """
                    UPDATE tgd_fact_record
                    SET
                        contact_name = ?,
                        contact_phone = ?,
                        contact_email = ?,
                        contact_province_code = ?,
                        contact_city_code = ?,
                        contact_street = ?,
                        contact_zip = ?,
                        updated_at = ?,
                        source_type = ?,
                        source_ref = ?,
                        contact_name_pinyin = ?,
                        contact_name_initials = ?
                    WHERE id = ?
                    """,
                    (v_name, v_phone, v_email, v_prov, v_city, v_street, v_zip, now, source_type, source_ref, v_name_pinyin, v_name_initials, row_id),
                )
                updated += 1
            except Exception:
                continue
    return int(updated)

