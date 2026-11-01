import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

from core.official_docs import parse_official_notice_archive, process_official_notice_archives
from core.official_docs.models import ProcessOptions


try:
    import fitz  # type: ignore

    _FITZ_AVAILABLE = True
except Exception:
    _FITZ_AVAILABLE = False

_OPENPYXL_AVAILABLE = importlib.util.find_spec("openpyxl") is not None


@unittest.skipUnless(_FITZ_AVAILABLE and _OPENPYXL_AVAILABLE, "Requires PyMuPDF + openpyxl")
class OfficialDocsEndToEndTests(unittest.TestCase):
    def _make_pdf(self, text: str) -> bytes:
        doc = fitz.open()  # type: ignore[name-defined]
        try:
            page = doc.new_page()
            page.insert_text((72, 72), text)
            return doc.tobytes()
        finally:
            doc.close()

    def test_nested_zip_end_to_end(self) -> None:
        list_xml = (
            """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <FAWENXLH>FW-001</FAWENXLH>
  <TONGZHISXJ>
    <SHUXINGXX>
      <ANJUANH>AJ-01</ANJUANH>
      <NEIBUBH>NB-01</NEIBUBH>
      <SHENQINGH>2025113838195</SHENQINGH>
      <TONGZHISBM>210401</TONGZHISBM>
      <TONGZHISMC>第一次审查意见通知书</TONGZHISMC>
      <FAWENR>20251106</FAWENR>
      <YUQIRQ>2025-12-06</YUQIRQ>
      <QIXIAN>30</QIXIAN>
    </SHUXINGXX>
    <FUJIANLB>
      <FUJIAN>
        <WENJIANMC>附件A</WENJIANMC>
        <WENJIANMS>desc</WENJIANMS>
      </FUJIAN>
    </FUJIANLB>
  </TONGZHISXJ>
</root>
"""
        ).encode("utf-8")

        main_pdf = self._make_pdf("main")
        attachment_pdf = self._make_pdf("attachment")

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            summary_root = root / "summary"
            archive_root = root / "archive"
            summary_root.mkdir(parents=True, exist_ok=True)
            archive_root.mkdir(parents=True, exist_ok=True)

            inner_zip = root / "inner.zip"
            with zipfile.ZipFile(inner_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("list.xml", list_xml)
                zf.writestr("210401.pdf", main_pdf)
                zf.writestr("附件A.pdf", attachment_pdf)

            outer_zip = root / "outer.zip"
            with zipfile.ZipFile(outer_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(inner_zip, arcname="package.zip")

            parsed = parse_official_notice_archive(str(outer_zip))
            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "list_xml")
            self.assertEqual(parsed.notice_kind, "exam_opinion")
            self.assertEqual(parsed.meta.app_no, "2025113838195")
            self.assertEqual(parsed.meta.notice_code, "210401")
            self.assertEqual(len(parsed.pdf_entries), 2)

            options = ProcessOptions(
                summary_root_dir=str(summary_root),
                archive_root_dir=str(archive_root),
                write_summary=True,
                write_archive=True,
                confirm_each=False,
            )
            summary = process_official_notice_archives([str(outer_zip)], options)
            self.assertEqual(summary.success, 1, f"failed={summary.failed} skipped={summary.skipped}")
            self.assertTrue(summary.excel_path)

            item = summary.items[0]
            self.assertEqual(item.status, "success", item.reason)
            self.assertTrue(item.summary_pdf_path and Path(item.summary_pdf_path).exists())
            self.assertTrue(item.archive_pdf_path and Path(item.archive_pdf_path).exists())
            self.assertTrue(Path(summary.excel_path).exists())

            merged = fitz.open(item.summary_pdf_path)  # type: ignore[name-defined]
            try:
                self.assertEqual(merged.page_count, 2)
            finally:
                merged.close()


if __name__ == "__main__":
    unittest.main()
