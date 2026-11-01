from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from .db import db_session
from .infra import get_db_path
from .migrations import ensure_db_ready


@dataclass(frozen=True)
class FactRecordQueryResult:
    records: List[Dict[str, Any]]
    truncated: bool


@dataclass(frozen=True)
class FactRecordManagerQueryResult:
    records: List[Dict[str, Any]]
    truncated: bool


@dataclass(frozen=True)
class FactManagerCandidatesResult:
    values: List[str]
    truncated: bool


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        s = str(value)
    except Exception:
        return ""
    return s.strip()


def _like_param(s: str) -> str:
    return f"%{s}%"


def _is_code6(s: str) -> bool:
    return bool(s) and s.isdigit() and len(s) == 6


_PINYIN_COLS = {
    "applicant_name",
    "inventor_name",
    "contact_name",
    "agency_ref_name",
    "group_name",
}


def _add_like_clause(clauses: List[str], params: List[Any], col: str, value: Any) -> None:
    s = _norm_text(value)
    if not s:
        return

    if col in _PINYIN_COLS:
        clauses.append(f"({col} LIKE ? OR {col}_pinyin LIKE ? OR {col}_initials LIKE ?)")
        p = _like_param(s)
        params.extend([p, p, p])
    else:
        clauses.append(f"{col} LIKE ?")
        params.append(_like_param(s))


def _add_eq_clause(clauses: List[str], params: List[Any], col: str, value: Any) -> None:
    s = _norm_text(value)
    if not s:
        return
    clauses.append(f"{col} = ?")
    params.append(s)


def _add_eq_or_like_clause(
    clauses: List[str],
    params: List[Any],
    col: str,
    value: Any,
    *,
    min_len_for_eq: int = 15,
) -> None:
    s = _norm_text(value)
    if not s:
        return
    if len(s) >= int(min_len_for_eq):
        clauses.append(f"{col} = ?")
        params.append(s)
        return
    clauses.append(f"{col} LIKE ?")
    params.append(_like_param(s))


def query_fact_records(
    *,
    group_name: str | None = None,
    applicant_groups: Sequence[Dict[str, Any]] | None = None,
    inventor_filter: Dict[str, Any] | None = None,
    contact_filter: Dict[str, Any] | None = None,
    limit: int = 500,
) -> FactRecordQueryResult:
    """查询事实记录表（tgd_fact_record），用于请求书弹窗的检索/自动预填。

    规则：
    - 所有非空条件均参与 AND
    - applicant_groups 内部为 OR；每个 applicant dict 内部条件为 AND
    - 证件号：优先精确匹配；当输入较短时使用 LIKE
    """
    applicant_groups = applicant_groups or []
    inventor_filter = inventor_filter or {}
    contact_filter = contact_filter or {}

    where_parts: List[str] = []
    params: List[Any] = []

    if group_name is not None:
        g = _norm_text(group_name)
        if g:
            # Group name search supports pinyin
            _add_like_clause(where_parts, params, "group_name", g)
        else:
            where_parts.append("(group_name IS NULL OR group_name = '')")

    app_or_parts: List[str] = []
    for app in applicant_groups:
        if not isinstance(app, dict):
            continue
        sub: List[str] = []
        sub_params: List[Any] = []

        _add_eq_clause(sub, sub_params, "applicant_type_code", app.get("type_code"))
        _add_eq_or_like_clause(sub, sub_params, "applicant_id_no", app.get("id_no"), min_len_for_eq=15)
        _add_eq_clause(sub, sub_params, "applicant_id_type_code", app.get("id_type_code"))
        _add_like_clause(sub, sub_params, "applicant_name", app.get("name"))

        prov = _norm_text(app.get("province_code"))
        if prov:
            if _is_code6(prov):
                _add_eq_clause(sub, sub_params, "applicant_province_code", prov)
            else:
                _add_like_clause(sub, sub_params, "applicant_province_code", prov)

        city = _norm_text(app.get("city_code"))
        if city:
            if _is_code6(city):
                _add_eq_clause(sub, sub_params, "applicant_city_code", city)
            else:
                _add_like_clause(sub, sub_params, "applicant_city_code", city)

        _add_like_clause(sub, sub_params, "applicant_address", app.get("address"))
        _add_like_clause(sub, sub_params, "applicant_zip", app.get("zip"))
        _add_like_clause(sub, sub_params, "applicant_phone", app.get("phone"))
        _add_like_clause(sub, sub_params, "applicant_email", app.get("email"))

        if not sub:
            continue
        app_or_parts.append("(" + " AND ".join(sub) + ")")
        params.extend(sub_params)

    if app_or_parts:
        where_parts.append("(" + " OR ".join(app_or_parts) + ")")

    inv_parts: List[str] = []
    _add_eq_clause(inv_parts, params, "inventor_id_no", inventor_filter.get("id_no"))
    _add_like_clause(inv_parts, params, "inventor_name", inventor_filter.get("name"))
    _add_like_clause(inv_parts, params, "inventor_id_type", inventor_filter.get("id_type"))
    if inv_parts:
        where_parts.append("(" + " AND ".join(inv_parts) + ")")

    contact_parts: List[str] = []
    _add_like_clause(contact_parts, params, "contact_name", contact_filter.get("name"))
    _add_like_clause(contact_parts, params, "contact_phone", contact_filter.get("phone"))
    _add_like_clause(contact_parts, params, "contact_email", contact_filter.get("email"))

    cprov = _norm_text(contact_filter.get("province_code"))
    if cprov:
        if _is_code6(cprov):
            _add_eq_clause(contact_parts, params, "contact_province_code", cprov)
        else:
            _add_like_clause(contact_parts, params, "contact_province_code", cprov)

    ccity = _norm_text(contact_filter.get("city_code"))
    if ccity:
        if _is_code6(ccity):
            _add_eq_clause(contact_parts, params, "contact_city_code", ccity)
        else:
            _add_like_clause(contact_parts, params, "contact_city_code", ccity)

    _add_like_clause(contact_parts, params, "contact_street", contact_filter.get("street"))
    _add_like_clause(contact_parts, params, "contact_zip", contact_filter.get("zip"))

    if contact_parts:
        where_parts.append("(" + " AND ".join(contact_parts) + ")")

    db_path = get_db_path()
    ensure_db_ready(db_path)

    sql = "SELECT * FROM tgd_fact_record"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY id DESC LIMIT ?"

    q_limit = int(limit) if int(limit) > 0 else 500
    params_with_limit = list(params)
    params_with_limit.append(q_limit)

    records: List[Dict[str, Any]] = []
    with db_session(db_path) as conn:
        cur = conn.execute(sql, tuple(params_with_limit))
        for row in cur.fetchall() or []:
            try:
                records.append(dict(row))
            except Exception:
                rec: Dict[str, Any] = {}
                try:
                    for k in row.keys():
                        rec[str(k)] = row[k]
                except Exception:
                    rec = {}
                records.append(rec)

    truncated = len(records) >= q_limit
    return FactRecordQueryResult(records=records, truncated=truncated)


def query_fact_records_for_manager(
    *,
    group_name: str = "",
    applicant_name: str = "",
    applicant_id_no: str = "",
    inventor_name: str = "",
    inventor_id_no: str = "",
    agency_ref_name: str = "",
    agency_ref_code: str = "",
    agent_name: str = "",
    limit: int = 500,
) -> FactRecordManagerQueryResult:
    where_parts: List[str] = []
    params: List[Any] = []

    g = _norm_text(group_name)
    if g:
        where_parts.append("group_name = ?")
        params.append(g)

    _add_like_clause(where_parts, params, "applicant_name", applicant_name)
    _add_eq_or_like_clause(where_parts, params, "applicant_id_no", applicant_id_no, min_len_for_eq=15)

    _add_like_clause(where_parts, params, "inventor_name", inventor_name)
    _add_eq_or_like_clause(where_parts, params, "inventor_id_no", inventor_id_no, min_len_for_eq=10)

    _add_like_clause(where_parts, params, "agency_ref_name", agency_ref_name)

    arc = _norm_text(agency_ref_code)
    if arc:
        if len(arc) >= 6:
            where_parts.append("agency_ref_code = ?")
            params.append(arc)
        else:
            where_parts.append("agency_ref_code LIKE ?")
            params.append(_like_param(arc))

    agent = _norm_text(agent_name)
    if agent:
        codes: List[str] = []
        try:
            from .agency_agent_query import query_agency_codes_by_agent_name

            codes = query_agency_codes_by_agent_name(agent_name=agent, limit=200)
        except Exception:
            codes = []

        if not codes:
            return FactRecordManagerQueryResult(records=[], truncated=False)

        placeholders = ",".join(["?"] * len(codes))
        where_parts.append(f"agency_ref_code IN ({placeholders})")
        params.extend(codes)

    db_path = get_db_path()
    ensure_db_ready(db_path)

    sql = "SELECT * FROM tgd_fact_record"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY id DESC LIMIT ?"

    q_limit = int(limit) if int(limit) > 0 else 500
    params2 = list(params)
    params2.append(q_limit)

    records: List[Dict[str, Any]] = []
    with db_session(db_path) as conn:
        cur = conn.execute(sql, tuple(params2))
        for row in cur.fetchall() or []:
            try:
                records.append(dict(row))
            except Exception:
                rec: Dict[str, Any] = {}
                try:
                    for k in row.keys():
                        rec[str(k)] = row[k]
                except Exception:
                    rec = {}
                records.append(rec)

    truncated = len(records) >= q_limit
    return FactRecordManagerQueryResult(records=records, truncated=truncated)


def query_fact_candidates_for_manager(
    *,
    target_col: str,
    typed: str = "",
    group_name: str = "",
    applicant_name: str = "",
    applicant_id_no: str = "",
    inventor_name: str = "",
    inventor_id_no: str = "",
    agency_ref_name: str = "",
    agency_ref_code: str = "",
    agent_name: str = "",
    limit: int = 60,
) -> FactManagerCandidatesResult:
    """查询事实记录管理界面的下拉候选项，支持全字段联动筛选。"""
    c = _norm_text(target_col)
    if not c:
        return FactManagerCandidatesResult(values=[], truncated=False)

    where_parts: List[str] = []
    params: List[Any] = []

    # 1. Base filters (same as manager query)
    g = _norm_text(group_name)
    if g:
        where_parts.append("group_name = ?")
        params.append(g)

    _add_like_clause(where_parts, params, "applicant_name", applicant_name)
    _add_eq_or_like_clause(where_parts, params, "applicant_id_no", applicant_id_no, min_len_for_eq=15)

    _add_like_clause(where_parts, params, "inventor_name", inventor_name)
    _add_eq_or_like_clause(where_parts, params, "inventor_id_no", inventor_id_no, min_len_for_eq=10)

    _add_like_clause(where_parts, params, "agency_ref_name", agency_ref_name)

    arc = _norm_text(agency_ref_code)
    if arc:
        if len(arc) >= 6:
            where_parts.append("agency_ref_code = ?")
            params.append(arc)
        else:
            where_parts.append("agency_ref_code LIKE ?")
            params.append(_like_param(arc))

    agent = _norm_text(agent_name)
    if agent:
        codes: List[str] = []
        try:
            from .agency_agent_query import query_agency_codes_by_agent_name

            codes = query_agency_codes_by_agent_name(agent_name=agent, limit=200)
        except Exception:
            codes = []

        if not codes:
            return FactManagerCandidatesResult(values=[], truncated=False)

        placeholders = ",".join(["?"] * len(codes))
        where_parts.append(f"agency_ref_code IN ({placeholders})")
        params.extend(codes)

    # 2. Additional filter for the target column's typed text
    t = _norm_text(typed)
    if t:
        where_parts.append(f"({c} LIKE ?)")
        params.append(_like_param(t))

    # 3. Basic validity
    where_parts.append(f"({c} IS NOT NULL)")
    where_parts.append(f"(TRIM({c}) != '')")

    db_path = get_db_path()
    ensure_db_ready(db_path)

    # 4. Construct Query
    sql = (
        f"SELECT {c} AS v, MAX(id) AS mid "
        f"FROM tgd_fact_record "
    )
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    
    sql += f" GROUP BY {c} ORDER BY mid DESC LIMIT ?"

    q_limit = int(limit) if int(limit) > 0 else 60
    params2 = list(params)
    params2.append(q_limit + 1)

    vals: List[str] = []
    with db_session(db_path) as conn:
        cur = conn.execute(sql, tuple(params2))
        for row in cur.fetchall() or []:
            v = ""
            try:
                v = _norm_text(row["v"])
            except Exception:
                try:
                    v = _norm_text(row[0])
                except Exception:
                    v = ""
            if v:
                vals.append(v)

    truncated = len(vals) > q_limit
    if truncated:
        vals = vals[:q_limit]
    
    return FactManagerCandidatesResult(values=vals, truncated=truncated)


__all__ = [
    "FactRecordQueryResult",
    "FactRecordManagerQueryResult",
    "FactManagerCandidatesResult",
    "query_fact_records",
    "query_fact_records_for_manager",
    "query_fact_candidates_for_manager",
]
