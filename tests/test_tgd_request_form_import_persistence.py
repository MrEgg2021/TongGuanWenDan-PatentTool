from __future__ import annotations

import os
import sqlite3
import tempfile
import types
import unittest
from contextlib import contextmanager
import uuid
from unittest.mock import patch

from gui.widgets_impl.request_form.fact_import_impl import persistence_ops


class TgdRequestFormImportPersistenceTests(unittest.TestCase):
    @staticmethod
    @contextmanager
    def _temp_db_path():
        db_path = os.path.join(tempfile.gettempdir(), f"tgd_import_test_{uuid.uuid4().hex}.db")
        try:
            yield db_path
        finally:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.remove(db_path + suffix)
                except Exception:
                    pass

    @staticmethod
    @contextmanager
    def _sqlite_session(db_path: str):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _ensure_fact_table(db_path: str) -> None:
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tgd_fact_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    group_name TEXT,
                    power_of_attorney_no TEXT,
                    agency_ref_name TEXT,
                    agency_ref_code TEXT,
                    record_hash TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    source_type TEXT,
                    source_ref TEXT
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_tgd_fact_record_hash_unique ON tgd_fact_record(record_hash)"
            )
            conn.commit()

    def _make_combo(
        self,
        *,
        agency_name: str = "杭州君度专利代理事务所（特殊普通合伙）",
        agency_code: str = "33240",
        inventor_id_type: str = "",
        inventor_id_no: str = "411521199109141518",
        inventor_nationality: str = "CN",
    ) -> dict:
        return {
            "app": {
                "name": "杭州瑞莱谱医疗科技有限公司",
                "type_code": "3",
                "id_type_code": "F",
                "id_no": "91330106MA2GM12345",
                "address": "浙江省杭州市滨江区",
                "zip": "310000",
            },
            "inv": {
                "name": "费鹏",
                "id_type": inventor_id_type,
                "id_no": inventor_id_no,
                "nationality_code": inventor_nationality,
            },
            "contact": {"name": "联系人A"},
            "group_name": "测试组",
            "power_of_attorney_no": "ZW0022312",
            "agency_ref_name": agency_name,
            "agency_ref_code": agency_code,
        }

    def _run_upsert(self, db_path: str, combos: list[dict]) -> tuple[list[dict], list[dict]]:
        dummy = types.SimpleNamespace(_source_file_path="bundle.zip", _request_form_cache_key="rf-cache")
        with (
            patch.object(persistence_ops, "get_db_path", return_value=db_path),
            patch.object(persistence_ops, "db_session", self._sqlite_session),
            patch.object(persistence_ops, "ensure_db_ready", side_effect=lambda _path: self._ensure_fact_table(db_path)),
        ):
            new_rows, dup_rows, skipped, errors = persistence_ops._upsert_fact_record_rows(dummy, combos)
        self.assertEqual(skipped, 0, f"unexpected skipped rows: {skipped}, errors={errors}")
        self.assertFalse(errors, f"unexpected upsert errors: {errors}")
        return new_rows, dup_rows

    def _fetch_one(self, db_path: str) -> dict:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT agency_ref_name, agency_ref_code, inventor_id_type, inventor_id_no, inventor_nationality_code
                FROM tgd_fact_record
                LIMIT 1
                """
            ).fetchone()
        self.assertIsNotNone(row, "expected one fact row after import")
        return dict(row)

    def test_tgd_request_import_persists_agency_ref_name(self) -> None:
        with self._temp_db_path() as db_path:
            new_rows, dup_rows = self._run_upsert(db_path, [self._make_combo()])
            self.assertEqual(len(new_rows), 1)
            self.assertEqual(len(dup_rows), 0)

            row = self._fetch_one(db_path)
            self.assertEqual(row["agency_ref_name"], "杭州君度专利代理事务所（特殊普通合伙）")
            self.assertEqual(row["agency_ref_code"], "33240")

    def test_tgd_request_import_defaults_inventor_id_type_for_cn(self) -> None:
        with self._temp_db_path() as db_path:
            self._run_upsert(
                db_path,
                [
                    self._make_combo(
                        inventor_id_type="",
                        inventor_id_no="330106197601270412",
                        inventor_nationality="CN",
                    )
                ],
            )

            row = self._fetch_one(db_path)
            self.assertEqual(row["inventor_id_no"], "330106197601270412")
            self.assertEqual(row["inventor_nationality_code"], "CN")
            self.assertEqual(row["inventor_id_type"], "居民身份证")

    def test_tgd_request_import_non_cn_keeps_empty_id_type(self) -> None:
        with self._temp_db_path() as db_path:
            self._run_upsert(
                db_path,
                [
                    self._make_combo(
                        inventor_id_type="",
                        inventor_id_no="P1234567",
                        inventor_nationality="US",
                    )
                ],
            )

            row = self._fetch_one(db_path)
            self.assertEqual(row["inventor_nationality_code"], "US")
            self.assertEqual(row["inventor_id_type"] or "", "")

    def test_tgd_request_import_agency_name_strategy_request_only(self) -> None:
        with self._temp_db_path() as db_path:
            self._run_upsert(
                db_path,
                [
                    self._make_combo(
                        agency_name="",
                        agency_code="33240",
                    )
                ],
            )

            row = self._fetch_one(db_path)
            self.assertEqual(row["agency_ref_code"], "33240")
            self.assertEqual(row["agency_ref_name"] or "", "")

    def test_tgd_request_import_empty_new_agency_name_does_not_erase_existing(self) -> None:
        with self._temp_db_path() as db_path:

            self._run_upsert(db_path, [self._make_combo(agency_name="杭州君度专利代理事务所（特殊普通合伙）")])
            new_rows, dup_rows = self._run_upsert(db_path, [self._make_combo(agency_name="")])
            self.assertEqual(len(new_rows), 0)
            self.assertEqual(len(dup_rows), 1)

            row = self._fetch_one(db_path)
            self.assertEqual(row["agency_ref_name"], "杭州君度专利代理事务所（特殊普通合伙）")


if __name__ == "__main__":
    unittest.main()
