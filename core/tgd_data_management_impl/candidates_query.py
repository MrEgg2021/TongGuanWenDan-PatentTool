from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from .db import db_session
from .infra import get_db_path
from .migrations import ensure_db_ready


@dataclass(frozen=True)
class CandidatesQueryResult:
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


_FACT_COLS = {
    "applicant_name",
    "applicant_id_no",
    "applicant_phone",
    "applicant_email",
    "applicant_address",
    "applicant_zip",
    "inventor_name",
    "inventor_id_type",
    "inventor_id_no",
    "inventor_nationality_code",
    "contact_name",
    "contact_phone",
    "contact_email",
    "contact_street",
    "contact_zip",
    "power_of_attorney_no",
    "agency_ref_name",
    "agency_ref_code",
    "group_name",
}

_FACT_PINYIN_COLS = {
    "applicant_name",
    "inventor_name",
    "contact_name",
    "agency_ref_name",
    "group_name",
}


_FACT_PINYIN_COLS = {
    "applicant_name",
    "inventor_name",
    "contact_name",
    "agency_ref_name",
    "group_name",
}


_AGENCY_COLS = {
    "agency_name",
    "agency_code",
    "agent_name",
    "agent_cert_no",
    "agent_phone",
}

_AGENCY_PINYIN_COLS = {
    "agency_name",
    "agent_name",
}


def query_fact_record_candidates(
    *,
    group_name: Optional[str],
    col: str,
    typed: str = "",
    limit: int = 60,
) -> CandidatesQueryResult:
    c = str(col or "")
    if c not in _FACT_COLS:
        return CandidatesQueryResult(values=[], truncated=False)

    g = _norm_text(group_name) if group_name is not None else ""
    t = _norm_text(typed)
    q_limit = int(limit) if int(limit) > 0 else 60

    where_parts: List[str] = [f"({c} IS NOT NULL)", f"(TRIM({c}) != '')"]
    params: List[Any] = []

    if c != "group_name":
        if g:
            where_parts.append("(group_name = ?)")
            params.append(g)

    if t:
        if c in _FACT_PINYIN_COLS:
            where_parts.append(f"({c} LIKE ? OR {c}_pinyin LIKE ? OR {c}_initials LIKE ?)")
            p = _like_param(t)
            params.extend([p, p, p])
        else:
            where_parts.append(f"({c} LIKE ?)")
            params.append(_like_param(t))

    sql = (
        f"SELECT {c} AS v, MAX(id) AS mid "
        f"FROM tgd_fact_record "
        f"WHERE "
        + " AND ".join(where_parts)
        + f" GROUP BY {c} ORDER BY mid DESC LIMIT ?"
    )

    db_path = get_db_path()
    ensure_db_ready(db_path)

    vals: List[str] = []
    with db_session(db_path) as conn:
        cur = conn.execute(sql, tuple(params + [q_limit + 1]))
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
    return CandidatesQueryResult(values=vals, truncated=bool(truncated))


def query_group_name_candidates(*, typed: str = "", limit: int = 60) -> CandidatesQueryResult:
    return query_fact_record_candidates(group_name=None, col="group_name", typed=typed, limit=limit)


def query_agency_agent_candidates(
    *,
    col: str,
    typed: str = "",
    limit: int = 60,
) -> CandidatesQueryResult:
    c = str(col or "")
    if c not in _AGENCY_COLS:
        return CandidatesQueryResult(values=[], truncated=False)

    t = _norm_text(typed)
    q_limit = int(limit) if int(limit) > 0 else 60

    where_parts: List[str] = [f"({c} IS NOT NULL)", f"(TRIM({c}) != '')"]
    params: List[Any] = []

    if t:
        if c in _AGENCY_PINYIN_COLS:
            where_parts.append(f"({c} LIKE ? OR {c}_pinyin LIKE ? OR {c}_initials LIKE ?)")
            p = _like_param(t)
            params.extend([p, p, p])
        else:
            where_parts.append(f"({c} LIKE ?)")
            params.append(_like_param(t))

    sql = (
        f"SELECT {c} AS v, MAX(id) AS mid "
        f"FROM tgd_agency_agent "
        f"WHERE "
        + " AND ".join(where_parts)
        + f" GROUP BY {c} ORDER BY mid DESC LIMIT ?"
    )

    db_path = get_db_path()
    ensure_db_ready(db_path)

    vals: List[str] = []
    with db_session(db_path) as conn:
        cur = conn.execute(sql, tuple(params + [q_limit + 1]))
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
    return CandidatesQueryResult(values=vals, truncated=bool(truncated))


__all__ = [
    "CandidatesQueryResult",
    "query_fact_record_candidates",
    "query_group_name_candidates",
    "query_agency_agent_candidates",
]
