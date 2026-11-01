from __future__ import annotations

import hashlib
import sqlite3
from typing import Dict

from .db import MigrationFunc, apply_migrations, db_session, set_user_version
from .infra import ensure_daily_backup, get_db_path


def _migrate_0_to_1(conn: sqlite3.Connection) -> None:
    """v0 -> v1：创建基础表结构与多对多关系表，并设置 user_version=1。"""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS applicant_group (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            created_at TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS applicant (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            uscc TEXT,
            id_number TEXT,
            address TEXT,
            zip_code TEXT,
            province_city_code TEXT,
            fee_reduction INTEGER,
            fee_reduction_expire_date TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            update_time TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_applicant_uscc_unique
        ON applicant(uscc)
        WHERE uscc IS NOT NULL AND uscc <> '';

        CREATE UNIQUE INDEX IF NOT EXISTS idx_applicant_id_number_unique
        ON applicant(id_number)
        WHERE id_number IS NOT NULL AND id_number <> '';

        CREATE TABLE IF NOT EXISTS inventor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            id_number TEXT,
            nationality TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            update_time TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_inventor_id_number_unique
        ON inventor(id_number)
        WHERE id_number IS NOT NULL AND id_number <> '';

        CREATE TABLE IF NOT EXISTS contact (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            update_time TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agency_name TEXT,
            agency_code TEXT,
            agent_names TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            update_time TEXT
        );

        CREATE TABLE IF NOT EXISTS applicant_group_rel (
            applicant_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            created_at TEXT,
            PRIMARY KEY (applicant_id, group_id),
            FOREIGN KEY (applicant_id) REFERENCES applicant(id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES applicant_group(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS applicant_inventor_rel (
            applicant_id INTEGER NOT NULL,
            inventor_id INTEGER NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0,
            last_used_at TEXT,
            PRIMARY KEY (applicant_id, inventor_id),
            FOREIGN KEY (applicant_id) REFERENCES applicant(id) ON DELETE CASCADE,
            FOREIGN KEY (inventor_id) REFERENCES inventor(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_app_inv_usage
        ON applicant_inventor_rel(applicant_id, usage_count DESC);

        CREATE TABLE IF NOT EXISTS applicant_contact_rel (
            applicant_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0,
            last_used_at TEXT,
            PRIMARY KEY (applicant_id, contact_id),
            FOREIGN KEY (applicant_id) REFERENCES applicant(id) ON DELETE CASCADE,
            FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_app_contact_usage
        ON applicant_contact_rel(applicant_id, usage_count DESC);
        """
    )
    set_user_version(conn, 1)


def _migrate_1_to_2(conn: sqlite3.Connection) -> None:
    """v1 -> v2：创建单 Sheet 事实记录表（唯一真相源），并设置 user_version=2。"""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tgd_fact_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_hash TEXT NOT NULL,

            applicant_name TEXT,
            applicant_type_code TEXT,
            applicant_id_type_code TEXT,
            applicant_id_no TEXT,
            applicant_province_code TEXT,
            applicant_city_code TEXT,
            applicant_address TEXT,
            applicant_zip TEXT,
            applicant_phone TEXT,
            applicant_email TEXT,

            inventor_name TEXT,
            inventor_id_type TEXT,
            inventor_id_no TEXT,
            inventor_nationality_code TEXT,
            inventor_publish_not_public INTEGER,

            contact_name TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            contact_province_code TEXT,
            contact_city_code TEXT,
            contact_street TEXT,
            contact_zip TEXT,

            group_name TEXT,

            created_at TEXT,
            updated_at TEXT,
            source_type TEXT,
            source_ref TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_tgd_fact_record_hash_unique
        ON tgd_fact_record(record_hash);

        CREATE INDEX IF NOT EXISTS idx_tgd_fact_applicant_id
        ON tgd_fact_record(applicant_id_type_code, applicant_id_no);

        CREATE INDEX IF NOT EXISTS idx_tgd_fact_inventor_id
        ON tgd_fact_record(inventor_id_no);

        CREATE INDEX IF NOT EXISTS idx_tgd_fact_contact
        ON tgd_fact_record(contact_name, contact_phone);

        CREATE INDEX IF NOT EXISTS idx_tgd_fact_group
        ON tgd_fact_record(group_name);
        """
    )
    set_user_version(conn, 2)


def _norm_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _make_record_hash_v3(*parts) -> str:
    raw = "\x1f".join(_norm_text(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _coalesce_non_empty_str(new_val, old_val) -> str:
    nv = _norm_text(new_val)
    if nv:
        return nv
    return _norm_text(old_val)


def _migrate_2_to_3(conn: sqlite3.Connection) -> None:
    """v2 -> v3：

    - S1：移除 tgd_fact_record.inventor_publish_not_public
    - P2：tgd_fact_record 新增 POA + 关联代理机构字段；新增代理机构库表
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tgd_agency_agent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agency_name TEXT NOT NULL,
            agency_code TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            agent_cert_no TEXT NOT NULL,
            agent_phone TEXT NOT NULL,
            sort_order INTEGER,
            created_at TEXT,
            updated_at TEXT,
            source_type TEXT,
            source_ref TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tgd_agency_agent_unique
        ON tgd_agency_agent(agency_code, agent_cert_no);
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_agency_agent_agency
        ON tgd_agency_agent(agency_code, sort_order, id);
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tgd_fact_record_v3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_hash TEXT NOT NULL,

            applicant_name TEXT,
            applicant_type_code TEXT,
            applicant_id_type_code TEXT,
            applicant_id_no TEXT,
            applicant_province_code TEXT,
            applicant_city_code TEXT,
            applicant_address TEXT,
            applicant_zip TEXT,
            applicant_phone TEXT,
            applicant_email TEXT,

            inventor_name TEXT,
            inventor_id_type TEXT,
            inventor_id_no TEXT,
            inventor_nationality_code TEXT,

            contact_name TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            contact_province_code TEXT,
            contact_city_code TEXT,
            contact_street TEXT,
            contact_zip TEXT,

            power_of_attorney_no TEXT,
            agency_ref_name TEXT,
            agency_ref_code TEXT,

            group_name TEXT,

            created_at TEXT,
            updated_at TEXT,
            source_type TEXT,
            source_ref TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tgd_fact_record_hash_unique_v3
        ON tgd_fact_record_v3(record_hash);
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_fact_applicant_id_v3
        ON tgd_fact_record_v3(applicant_id_type_code, applicant_id_no);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_fact_inventor_id_v3
        ON tgd_fact_record_v3(inventor_id_no);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_fact_contact_v3
        ON tgd_fact_record_v3(contact_name, contact_phone);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_fact_group_v3
        ON tgd_fact_record_v3(group_name);
        """
    )

    try:
        cur = conn.execute("SELECT * FROM tgd_fact_record ORDER BY id ASC")
        rows = cur.fetchall() or []
    except Exception:
        rows = []

    for r in rows:
        try:
            applicant_name = _norm_text(r["applicant_name"])
            applicant_type_code = _norm_text(r["applicant_type_code"])
            applicant_id_type_code = _norm_text(r["applicant_id_type_code"])
            applicant_id_no = _norm_text(r["applicant_id_no"])
            applicant_province_code = _norm_text(r["applicant_province_code"])
            applicant_city_code = _norm_text(r["applicant_city_code"])
            applicant_address = _norm_text(r["applicant_address"])
            applicant_zip = _norm_text(r["applicant_zip"])
            applicant_phone = _norm_text(r["applicant_phone"])
            applicant_email = _norm_text(r["applicant_email"])

            inventor_name = _norm_text(r["inventor_name"])
            inventor_id_type = _norm_text(r["inventor_id_type"])
            inventor_id_no = _norm_text(r["inventor_id_no"])
            inventor_nationality_code = _norm_text(r["inventor_nationality_code"])

            contact_name = _norm_text(r["contact_name"])
            contact_phone = _norm_text(r["contact_phone"])
            contact_email = _norm_text(r["contact_email"])
            contact_province_code = _norm_text(r["contact_province_code"])
            contact_city_code = _norm_text(r["contact_city_code"])
            contact_street = _norm_text(r["contact_street"])
            contact_zip = _norm_text(r["contact_zip"])

            group_name = _norm_text(r["group_name"])

            created_at = _norm_text(r["created_at"])
            updated_at = _norm_text(r["updated_at"])
            source_type = _norm_text(r["source_type"])
            source_ref = _norm_text(r["source_ref"])
        except Exception:
            continue

        record_hash = _make_record_hash_v3(
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
            "",
            "",
        )

        try:
            existing = conn.execute(
                "SELECT * FROM tgd_fact_record_v3 WHERE record_hash = ? LIMIT 1", (record_hash,)
            ).fetchone()
        except Exception:
            existing = None

        if existing:
            try:
                conn.execute(
                    """
                    UPDATE tgd_fact_record_v3
                    SET
                        applicant_name = ?,
                        applicant_type_code = ?,
                        applicant_id_type_code = ?,
                        applicant_id_no = ?,
                        applicant_province_code = ?,
                        applicant_city_code = ?,
                        applicant_address = ?,
                        applicant_zip = ?,
                        applicant_phone = ?,
                        applicant_email = ?,

                        inventor_name = ?,
                        inventor_id_type = ?,
                        inventor_id_no = ?,
                        inventor_nationality_code = ?,

                        contact_name = ?,
                        contact_phone = ?,
                        contact_email = ?,
                        contact_province_code = ?,
                        contact_city_code = ?,
                        contact_street = ?,
                        contact_zip = ?,

                        group_name = ?,
                        created_at = ?,
                        updated_at = ?,
                        source_type = ?,
                        source_ref = ?
                    WHERE record_hash = ?
                    """,
                    (
                        _coalesce_non_empty_str(applicant_name, existing["applicant_name"]),
                        _coalesce_non_empty_str(applicant_type_code, existing["applicant_type_code"]),
                        _coalesce_non_empty_str(applicant_id_type_code, existing["applicant_id_type_code"]),
                        _coalesce_non_empty_str(applicant_id_no, existing["applicant_id_no"]),
                        _coalesce_non_empty_str(applicant_province_code, existing["applicant_province_code"]),
                        _coalesce_non_empty_str(applicant_city_code, existing["applicant_city_code"]),
                        _coalesce_non_empty_str(applicant_address, existing["applicant_address"]),
                        _coalesce_non_empty_str(applicant_zip, existing["applicant_zip"]),
                        _coalesce_non_empty_str(applicant_phone, existing["applicant_phone"]),
                        _coalesce_non_empty_str(applicant_email, existing["applicant_email"]),
                        _coalesce_non_empty_str(inventor_name, existing["inventor_name"]),
                        _coalesce_non_empty_str(inventor_id_type, existing["inventor_id_type"]),
                        _coalesce_non_empty_str(inventor_id_no, existing["inventor_id_no"]),
                        _coalesce_non_empty_str(inventor_nationality_code, existing["inventor_nationality_code"]),
                        _coalesce_non_empty_str(contact_name, existing["contact_name"]),
                        _coalesce_non_empty_str(contact_phone, existing["contact_phone"]),
                        _coalesce_non_empty_str(contact_email, existing["contact_email"]),
                        _coalesce_non_empty_str(contact_province_code, existing["contact_province_code"]),
                        _coalesce_non_empty_str(contact_city_code, existing["contact_city_code"]),
                        _coalesce_non_empty_str(contact_street, existing["contact_street"]),
                        _coalesce_non_empty_str(contact_zip, existing["contact_zip"]),
                        _coalesce_non_empty_str(group_name, existing["group_name"]),
                        _coalesce_non_empty_str(created_at, existing["created_at"]),
                        _coalesce_non_empty_str(updated_at, existing["updated_at"]),
                        _coalesce_non_empty_str(source_type, existing["source_type"]),
                        _coalesce_non_empty_str(source_ref, existing["source_ref"]),
                        record_hash,
                    ),
                )
            except Exception:
                pass
            continue

        try:
            conn.execute(
                """
                INSERT INTO tgd_fact_record_v3(
                    record_hash,
                    applicant_name, applicant_type_code, applicant_id_type_code, applicant_id_no,
                    applicant_province_code, applicant_city_code, applicant_address, applicant_zip,
                    applicant_phone, applicant_email,
                    inventor_name, inventor_id_type, inventor_id_no, inventor_nationality_code,
                    contact_name, contact_phone, contact_email, contact_province_code, contact_city_code, contact_street, contact_zip,
                    power_of_attorney_no, agency_ref_name, agency_ref_code,
                    group_name,
                    created_at, updated_at, source_type, source_ref
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_hash,
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
                    "",
                    "",
                    "",
                    group_name,
                    created_at,
                    updated_at,
                    source_type,
                    source_ref,
                ),
            )
        except Exception:
            continue

    try:
        conn.execute("DROP TABLE tgd_fact_record")
    except Exception:
        pass
    conn.execute("ALTER TABLE tgd_fact_record_v3 RENAME TO tgd_fact_record")

    try:
        conn.execute("DROP INDEX idx_tgd_fact_record_hash_unique_v3")
    except Exception:
        pass
    try:
        conn.execute("DROP INDEX idx_tgd_fact_applicant_id_v3")
    except Exception:
        pass
    try:
        conn.execute("DROP INDEX idx_tgd_fact_inventor_id_v3")
    except Exception:
        pass
    try:
        conn.execute("DROP INDEX idx_tgd_fact_contact_v3")
    except Exception:
        pass
    try:
        conn.execute("DROP INDEX idx_tgd_fact_group_v3")
    except Exception:
        pass
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tgd_fact_record_hash_unique
        ON tgd_fact_record(record_hash);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_fact_applicant_id
        ON tgd_fact_record(applicant_id_type_code, applicant_id_no);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_fact_inventor_id
        ON tgd_fact_record(inventor_id_no);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_fact_contact
        ON tgd_fact_record(contact_name, contact_phone);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgd_fact_group
        ON tgd_fact_record(group_name);
        """
    )

    set_user_version(conn, 3)


def _migrate_3_to_4(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("DROP INDEX IF EXISTS idx_tgd_fact_record_hash_unique")
    except Exception:
        pass

    try:
        cur = conn.execute("SELECT * FROM tgd_fact_record ORDER BY id ASC")
        rows = cur.fetchall() or []
    except Exception:
        rows = []

    for r in rows:
        try:
            row_id = int(r["id"])
        except Exception:
            continue

        try:
            applicant_name = _norm_text(r["applicant_name"])
            applicant_type_code = _norm_text(r["applicant_type_code"])
            applicant_id_type_code = _norm_text(r["applicant_id_type_code"])
            applicant_id_no = _norm_text(r["applicant_id_no"])
            applicant_province_code = _norm_text(r["applicant_province_code"])
            applicant_city_code = _norm_text(r["applicant_city_code"])
            applicant_address = _norm_text(r["applicant_address"])
            applicant_zip = _norm_text(r["applicant_zip"])
            applicant_phone = _norm_text(r["applicant_phone"])
            applicant_email = _norm_text(r["applicant_email"])

            inventor_name = _norm_text(r["inventor_name"])
            inventor_id_type = _norm_text(r["inventor_id_type"])
            inventor_id_no = _norm_text(r["inventor_id_no"])
            inventor_nationality_code = _norm_text(r["inventor_nationality_code"])

            contact_name = _norm_text(r["contact_name"])
            contact_phone = _norm_text(r["contact_phone"])
            contact_email = _norm_text(r["contact_email"])
            contact_province_code = _norm_text(r["contact_province_code"])
            contact_city_code = _norm_text(r["contact_city_code"])
            contact_street = _norm_text(r["contact_street"])
            contact_zip = _norm_text(r["contact_zip"])

            group_name = _norm_text(r["group_name"])
            poa_no = _norm_text(r["power_of_attorney_no"])
            agency_ref_code = _norm_text(r["agency_ref_code"])
        except Exception:
            continue

        record_hash = _make_record_hash_v3(
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

        try:
            conn.execute("UPDATE tgd_fact_record SET record_hash = ? WHERE id = ?", (record_hash, row_id))
        except Exception:
            continue

    try:
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tgd_fact_record_hash_unique
            ON tgd_fact_record(record_hash);
            """
        )
    except Exception:
        pass

    set_user_version(conn, 4)


def _migrate_4_to_5(conn: sqlite3.Connection) -> None:
    """v4 -> v5：新增拼音列（全拼+首字母）以支持拼音检索，并回填历史数据。

    涉及表：tgd_fact_record, tgd_agency_agent
    """
    # 1. tgd_fact_record
    fact_cols = [
        "applicant_name",
        "inventor_name",
        "contact_name",
        "agency_ref_name",
        "group_name",
    ]
    for col in fact_cols:
        try:
            conn.execute(f"ALTER TABLE tgd_fact_record ADD COLUMN {col}_pinyin TEXT")
        except Exception:
            pass
        try:
            conn.execute(f"ALTER TABLE tgd_fact_record ADD COLUMN {col}_initials TEXT")
        except Exception:
            pass

    # 2. tgd_agency_agent
    agency_cols = ["agency_name", "agent_name"]
    for col in agency_cols:
        try:
            conn.execute(f"ALTER TABLE tgd_agency_agent ADD COLUMN {col}_pinyin TEXT")
        except Exception:
            pass
        try:
            conn.execute(f"ALTER TABLE tgd_agency_agent ADD COLUMN {col}_initials TEXT")
        except Exception:
            pass

    # 3. Backfill
    from .pinyin_utils import get_pinyin_full, get_pinyin_initials

    # Backfill tgd_fact_record
    try:
        cur = conn.execute("SELECT id, applicant_name, inventor_name, contact_name, agency_ref_name, group_name FROM tgd_fact_record")
        rows = cur.fetchall() or []
        for r in rows:
            try:
                rid = r["id"]
                updates = []
                params = []

                for col in fact_cols:
                    val = _norm_text(r[col])
                    py = get_pinyin_full(val)
                    ini = get_pinyin_initials(val)
                    updates.append(f"{col}_pinyin = ?")
                    updates.append(f"{col}_initials = ?")
                    params.append(py)
                    params.append(ini)

                params.append(rid)
                sql = f"UPDATE tgd_fact_record SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, tuple(params))
            except Exception:
                pass
    except Exception:
        pass

    # Backfill tgd_agency_agent
    try:
        cur = conn.execute("SELECT id, agency_name, agent_name FROM tgd_agency_agent")
        rows = cur.fetchall() or []
        for r in rows:
            try:
                rid = r["id"]
                updates = []
                params = []

                for col in agency_cols:
                    val = _norm_text(r[col])
                    py = get_pinyin_full(val)
                    ini = get_pinyin_initials(val)
                    updates.append(f"{col}_pinyin = ?")
                    updates.append(f"{col}_initials = ?")
                    params.append(py)
                    params.append(ini)

                params.append(rid)
                sql = f"UPDATE tgd_agency_agent SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, tuple(params))
            except Exception:
                pass
    except Exception:
        pass

    set_user_version(conn, 5)


def ensure_db_ready(db_path: str | None = None) -> int:
    """确保 DB 可用：触发每日备份并执行必要迁移。

    返回迁移后的 `user_version`。
    """

    path = db_path or get_db_path()
    ensure_daily_backup(path)
    migrations: Dict[int, MigrationFunc] = {
        0: _migrate_0_to_1,
        1: _migrate_1_to_2,
        2: _migrate_2_to_3,
        3: _migrate_3_to_4,
        4: _migrate_4_to_5,
    }
    with db_session(path) as conn:
        return apply_migrations(conn, migrations, backup_db_path=path, backup_already_checked=True)
