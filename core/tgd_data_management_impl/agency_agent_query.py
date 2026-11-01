from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .db import db_session
from .infra import get_db_path
from .migrations import ensure_db_ready


@dataclass(frozen=True)
class AgencyAgentQueryResult:
    records: List[Dict[str, Any]]
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


def query_agency_agents(*, agency_name: str = "", agency_code: str = "", agent_name: str = "", limit: int = 500) -> AgencyAgentQueryResult:
    where_parts: List[str] = []
    params: List[Any] = []

    an = _norm_text(agency_name)
    if an:
        where_parts.append("(agency_name LIKE ? OR agency_name_pinyin LIKE ? OR agency_name_initials LIKE ?)")
        p = _like_param(an)
        params.extend([p, p, p])

    ac = _norm_text(agency_code)
    if ac:
        if len(ac) >= 6:
            where_parts.append("agency_code = ?")
            params.append(ac)
        else:
            where_parts.append("agency_code LIKE ?")
            params.append(_like_param(ac))

    agn = _norm_text(agent_name)
    if agn:
        where_parts.append("(agent_name LIKE ? OR agent_name_pinyin LIKE ? OR agent_name_initials LIKE ?)")
        p = _like_param(agn)
        params.extend([p, p, p])

    db_path = get_db_path()
    ensure_db_ready(db_path)

    sql = "SELECT * FROM tgd_agency_agent"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY agency_code ASC, sort_order ASC, id ASC LIMIT ?"

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
    return AgencyAgentQueryResult(records=records, truncated=truncated)


def query_agency_codes_by_agent_name(*, agent_name: str, limit: int = 200) -> List[str]:
    s = _norm_text(agent_name)
    if not s:
        return []

    db_path = get_db_path()
    ensure_db_ready(db_path)

    q_limit = int(limit) if int(limit) > 0 else 200
    out: List[str] = []
    seen = set()
    p = _like_param(s)
    with db_session(db_path) as conn:
        cur = conn.execute(
            "SELECT DISTINCT agency_code FROM tgd_agency_agent WHERE (agent_name LIKE ? OR agent_name_pinyin LIKE ? OR agent_name_initials LIKE ?) ORDER BY agency_code ASC LIMIT ?",
            (p, p, p, q_limit),
        )
        for row in cur.fetchall() or []:
            try:
                code = _norm_text(row["agency_code"])
            except Exception:
                try:
                    code = _norm_text(row[0])
                except Exception:
                    code = ""
            if not code:
                continue
            if code in seen:
                continue
            seen.add(code)
            out.append(code)
    return out


__all__ = ["AgencyAgentQueryResult", "query_agency_agents", "query_agency_codes_by_agent_name"]
