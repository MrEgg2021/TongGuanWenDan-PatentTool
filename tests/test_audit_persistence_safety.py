from __future__ import annotations
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from core.official_docs.excel_report import write_excel_report
from core.official_docs.models import ProcessItemResult
from core.tgd_data_management_impl import db, infra, migrations_impl
from core.tgd_data_management_impl.excel_io_impl.export_ops import export_tgd_excel_data
try:
    import openpyxl
except ImportError:
    openpyxl = None

class SettingsAndBackupSafetyTests(unittest.TestCase):

    def test_wal_backup_restores_and_separates_sources_without_deleting_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db1 = os.path.join(td, 'one.db')
            db2 = os.path.join(td, 'two.db')
            conn = sqlite3.connect(db1)
            try:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA wal_autocheckpoint=0')
                conn.execute('CREATE TABLE records(value TEXT)')
                conn.execute("INSERT INTO records VALUES ('from WAL')")
                conn.commit()
                self.assertTrue(os.path.exists(db1 + '-wal'))
                backup1 = infra.ensure_daily_backup(db1, keep_days=1)
            finally:
                conn.close()
            with closing(sqlite3.connect(db2)) as conn2:
                conn2.execute('CREATE TABLE records(value TEXT)')
                conn2.execute("INSERT INTO records VALUES ('second DB')")
                conn2.commit()
            old = os.path.join(td, '.backups', 'data_auto_20200101.bak')
            Path(old).write_bytes(b'legacy backup')
            backup2 = infra.ensure_daily_backup(db2, keep_days=1)
            self.assertNotEqual(backup1, backup2)
            self.assertEqual(Path(old).read_bytes(), b'legacy backup')
            for path, expected in ((backup1, 'from WAL'), (backup2, 'second DB')):
                with closing(sqlite3.connect(path)) as restored:
                    self.assertEqual(restored.execute('SELECT value FROM records').fetchone()[0], expected)

    def test_backup_failure_does_not_publish_or_migrate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'db.sqlite')
            with closing(sqlite3.connect(path)) as conn:
                conn.execute('CREATE TABLE old(value TEXT)')
                conn.commit()
            with patch.object(infra, '_verify_restorable_backup', side_effect=RuntimeError('bad restore')):
                with self.assertRaisesRegex(RuntimeError, 'bad restore'):
                    infra.ensure_daily_backup(path)
            self.assertEqual(os.listdir(os.path.join(td, '.backups')), [])
            with patch.object(migrations_impl, 'ensure_daily_backup', side_effect=OSError('backup denied')):
                with self.assertRaisesRegex(OSError, 'backup denied'):
                    migrations_impl.ensure_db_ready(path)
            with closing(sqlite3.connect(path)) as conn:
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 0)

    def test_invalid_existing_daily_backup_is_not_accepted_or_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'db.sqlite')
            with closing(sqlite3.connect(path)) as conn:
                conn.execute('CREATE TABLE records(value TEXT)')
                conn.commit()
            backup = infra.ensure_daily_backup(path)
            Path(backup).write_bytes(b'')
            with self.assertRaises(sqlite3.DatabaseError):
                infra.ensure_daily_backup(path)
            self.assertEqual(Path(backup).read_bytes(), b'')

    def test_migration_failure_keeps_verified_pre_migration_backup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'db.sqlite')
            with closing(sqlite3.connect(path)) as conn:
                conn.execute('CREATE TABLE records(value TEXT)')
                conn.execute("INSERT INTO records VALUES ('before')")
                conn.commit()
            with closing(sqlite3.connect(path)) as conn:

                def fail_migration(_conn):
                    raise RuntimeError('migration failed')
                with self.assertRaisesRegex(RuntimeError, 'migration failed'):
                    db.apply_migrations(conn, {0: fail_migration}, backup_db_path=path)
            backups = list(Path(td, '.backups').glob('data_auto_v2_*.bak'))
            self.assertEqual(len(backups), 1)
            with closing(sqlite3.connect(backups[0])) as recovered:
                self.assertEqual(recovered.execute('SELECT value FROM records').fetchone()[0], 'before')

@unittest.skipIf(openpyxl is None, 'requires openpyxl')
class ExcelTextSafetyTests(unittest.TestCase):

    def test_official_report_keeps_formula_shaped_business_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'report.xlsx')
            item = ProcessItemResult(source_zip_path='in.zip', status='success', business_fields={'发明名称': '=1+1'})
            write_excel_report(path, items=[item])
            wb = openpyxl.load_workbook(path)
            try:
                cell = wb.active['C2']
                self.assertEqual((cell.value, cell.data_type), ('=1+1', 's'))
            finally:
                wb.close()

    def test_tgd_export_keeps_formula_shaped_business_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, 'data.db')
            migrations_impl.ensure_db_ready(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute('INSERT INTO tgd_fact_record(record_hash, applicant_name) VALUES (?, ?)', ('hash1', '=1+1'))
                conn.execute('INSERT INTO tgd_agency_agent(agency_name, agency_code, agent_name, agent_cert_no, agent_phone) VALUES (?, ?, ?, ?, ?)', ('=2+2', 'A', 'B', 'C', 'D'))
                conn.commit()
            output = os.path.join(td, 'export.xlsx')
            with patch('core.tgd_data_management_impl.excel_io_impl.export_ops.get_db_path', return_value=db_path):
                export_tgd_excel_data(output)
            wb = openpyxl.load_workbook(output)
            try:
                self.assertEqual((wb.worksheets[0]['A2'].value, wb.worksheets[0]['A2'].data_type), ('=1+1', 's'))
                self.assertEqual((wb.worksheets[1]['A2'].value, wb.worksheets[1]['A2'].data_type), ('=2+2', 's'))
            finally:
                wb.close()
if __name__ == '__main__':
    unittest.main()
