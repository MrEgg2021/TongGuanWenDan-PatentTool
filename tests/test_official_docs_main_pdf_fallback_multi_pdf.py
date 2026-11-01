from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from core.official_docs.models import ProcessOptions
from core.official_docs.process import process_official_notice_archives


try:
    import fitz  # type: ignore

    _FITZ_AVAILABLE = True
except Exception:
    _FITZ_AVAILABLE = False


@unittest.skipUnless(_FITZ_AVAILABLE, "requires PyMuPDF")
class OfficialDocsMainPdfFallbackTests(unittest.TestCase):
    def _make_pdf(self, text: str) -> bytes:
        doc = fitz.open()  # type: ignore[name-defined]
        try:
            page = doc.new_page()
            page.insert_text((72, 72), text)
            return doc.tobytes()
        finally:
            doc.close()

    def test_multi_pdf_uses_sorted_first_when_code_not_matched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_zip = root / "multi.pdf.zip"
            list_xml = """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <FAWENXLH>FW-001</FAWENXLH>
  <TONGZHISXJ>
    <SHUXINGXX>
      <SHENQINGH>2025113838195</SHENQINGH>
      <TONGZHISBM>NO_MATCH_CODE</TONGZHISBM>
      <TONGZHISMC>办理登记手续通知书</TONGZHISMC>
      <FAWENR>2025-11-06</FAWENR>
      <QIXIAN>30</QIXIAN>
    </SHUXINGXX>
  </TONGZHISXJ>
</root>
"""
            with zipfile.ZipFile(source_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("list.xml", list_xml.encode("utf-8"))
                zf.writestr("B.pdf", self._make_pdf("B"))
                zf.writestr("A.pdf", self._make_pdf("A"))

            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
            )
            summary = process_official_notice_archives([str(source_zip)], options)
            self.assertEqual(summary.success, 1)
            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.skipped, 0)
            self.assertEqual(summary.items[0].status, "success")
            self.assertGreaterEqual(len(summary.items[0].merged_sources), 2)
            self.assertEqual(summary.items[0].merged_sources[0], "A.pdf")


if __name__ == "__main__":
    unittest.main()
