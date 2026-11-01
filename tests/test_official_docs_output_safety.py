from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.official_docs.models import NoticeMeta, ParsedNotice, PdfSource, ProcessOptions
from core.official_docs.process import process_official_notice_archives


class OfficialDocsOutputSafetyTests(unittest.TestCase):
    def _run(self, root: Path, *, confirm_each: bool = False, confirm_cb=None, replace_hook=None, count: int = 1):
        sources = []
        for index in range(count):
            source = root / f"source-{index}.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("main.pdf", b"source")
            sources.append(str(source))
        parsed = ParsedNotice(
            source_zip_path=sources[0], notice_kind="exam_opinion",
            meta=NoticeMeta(app_no="2025113838195", notice_name="审查意见"),
            pdf_entries=[PdfSource(raw_name="main.pdf", display_name="main.pdf", kind="main")],
        )
        options = ProcessOptions(
            summary_root_dir=str(root / "summary"), archive_root_dir=str(root / "archive"),
            write_summary=True, write_archive=True, confirm_each=confirm_each,
        )
        with patch("core.official_docs.process.parse_official_notice_archive", return_value=parsed), \
             patch("core.official_docs.process.render_notice_output", return_value=SimpleNamespace(output_pdf_name="notice.pdf", archive_rel_dir="case")), \
             patch("core.official_docs.process.merge_pdf_bytes", return_value=b"new PDF"), \
             patch("core.official_docs.process.write_excel_report"):
            if replace_hook is None:
                return process_official_notice_archives(sources, options, confirm_cb=confirm_cb)
            with patch("core.official_docs.process.os.replace", side_effect=replace_hook):
                return process_official_notice_archives(sources, options, confirm_cb=confirm_cb)

    def test_archive_replace_failure_preserves_old_file_and_records_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old_archive = root / "archive" / "case" / "notice.pdf"
            old_archive.parent.mkdir(parents=True)
            old_archive.write_bytes(b"old PDF")
            actual_replace = os.replace

            def replace(src, dst):
                if Path(dst) == old_archive:
                    raise OSError("archive denied")
                return actual_replace(src, dst)

            summary = self._run(root, replace_hook=replace)
            item = summary.items[0]
            self.assertEqual((summary.success, summary.failed), (0, 1))
            self.assertEqual(old_archive.read_bytes(), b"old PDF")
            self.assertEqual(Path(item.summary_pdf_path).read_bytes(), b"new PDF")
            self.assertEqual(item.archive_pdf_path, "")
            self.assertIn("汇总 PDF 已写入", item.reason)
            self.assertEqual(list(old_archive.parent.glob(".官文_*.tmp")), [])

    def test_confirmation_errors_stop_before_writing(self):
        for callback in (None, lambda *_: None, lambda *_: "invalid", lambda *_: (_ for _ in ()).throw(RuntimeError("UI gone"))):
            with self.subTest(callback=callback), tempfile.TemporaryDirectory() as folder:
                summary = self._run(Path(folder), confirm_each=True, confirm_cb=callback, count=2)
                self.assertEqual((summary.failed, summary.skipped, summary.success), (1, 1, 0))
                self.assertFalse(list(Path(summary.summary_run_dir).glob("*.pdf")))

    def test_explicit_cancel_and_unique_second_level_run_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cancelled = self._run(root, confirm_each=True, confirm_cb=lambda *_: "cancel", count=2)
            self.assertEqual((cancelled.skipped, cancelled.failed), (2, 0))
            first = self._run(root, confirm_cb=None)
            second = self._run(root, confirm_cb=None)
            self.assertNotEqual(first.summary_run_dir, second.summary_run_dir)
            self.assertEqual(Path(first.items[0].summary_pdf_path).read_bytes(), b"new PDF")
            self.assertEqual(Path(second.items[0].summary_pdf_path).read_bytes(), b"new PDF")


if __name__ == "__main__":
    unittest.main()
