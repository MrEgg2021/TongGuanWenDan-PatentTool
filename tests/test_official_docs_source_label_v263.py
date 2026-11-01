from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from core.official_docs.excel_report import write_excel_report
from core.official_docs.models import NoticeMeta, ProcessItemResult, ProcessOptions
from core.official_docs.process import process_official_notice_archives


try:
    import openpyxl

    _OPENPYXL_AVAILABLE = True
except Exception:
    _OPENPYXL_AVAILABLE = False


class OfficialDocsSourceLabelV263Tests(unittest.TestCase):
    def test_process_result_prefers_source_label_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = root / "input.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("main.pdf", b"%PDF-1.4\nstub\n")

            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=False,
                write_archive=False,
                confirm_each=False,
                source_label_by_zip_path={str(zip_path): "outer.zip > main.pdf"},
            )

            summary = process_official_notice_archives([str(zip_path)], options)

        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.items[0].source_zip_path, "outer.zip > main.pdf")

    @unittest.skipUnless(_OPENPYXL_AVAILABLE, "requires openpyxl")
    def test_excel_keeps_readable_source_label(self) -> None:
        item = ProcessItemResult(
            source_zip_path="outer.zip > inner.pdf",
            status="success",
            meta=NoticeMeta(),
            output_pdf_name="done.pdf",
            business_fields={},
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[item], include_exam_pdf_columns=False)
            wb = openpyxl.load_workbook(path)  # type: ignore[name-defined]
            try:
                ws = wb.active
                headers = [str(cell.value or "") for cell in next(ws.iter_rows(min_row=1, max_row=1))]
                values = [str(cell.value or "") for cell in next(ws.iter_rows(min_row=2, max_row=2))]
            finally:
                wb.close()

        row = dict(zip(headers, values))
        self.assertEqual(row.get("源ZIP"), "outer.zip > inner.pdf")


if __name__ == "__main__":
    unittest.main()
