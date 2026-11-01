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
class OfficialDocsPctFilterRuntimeTests(unittest.TestCase):
    def _make_pdf(self, text: str) -> bytes:
        doc = fitz.open()  # type: ignore[name-defined]
        try:
            page = doc.new_page()
            page.insert_text((72, 72), text)
            return doc.tobytes()
        finally:
            doc.close()

    def _make_zip(
        self,
        root: Path,
        *,
        name: str,
        notice_code: str,
        notice_name: str,
        app_no: str = "PCT/CN2023/078301",
    ) -> str:
        list_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<root>
  <FAWENXLH>FW-PCT-001</FAWENXLH>
  <TONGZHISXJ>
    <SHUXINGXX>
      <ANJUANH>AJ-PCT-01</ANJUANH>
      <SHENQINGH>{app_no}</SHENQINGH>
      <TONGZHISBM>{notice_code}</TONGZHISBM>
      <TONGZHISMC>{notice_name}</TONGZHISMC>
      <FAMINGMC>PCT测试发明</FAMINGMC>
      <FAWENR>2023-10-23</FAWENR>
      <QIXIAN>0</QIXIAN>
    </SHUXINGXX>
  </TONGZHISXJ>
</root>
"""
        zip_path = root / name
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("list.xml", list_xml.encode("utf-8"))
            zf.writestr("any.pdf", self._make_pdf("main"))
        return str(zip_path)

    def _run(self, zip_path: str):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            options = ProcessOptions(
                summary_root_dir=str(base / "summary"),
                archive_root_dir=str(base / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
            )
            return process_official_notice_archives([zip_path], options)

    def test_whitelisted_pct_notice_is_processed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="pct_ok.zip",
                notice_code="PCT/ISA/210C",
                notice_name="国际检索报告",
            )
            summary = self._run(zip_path)
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.success, 1)
            self.assertEqual(summary.skipped, 0)
            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.items[0].status, "success")

    def test_unknown_pct_notice_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="pct_unknown.zip",
                notice_code="PCT/NEW/999",
                notice_name="未知PCT通知书",
            )
            summary = self._run(zip_path)
            self.assertEqual(summary.total, 1)
            self.assertEqual(summary.success, 0)
            self.assertEqual(summary.skipped, 1)
            self.assertEqual(summary.failed, 0)
            self.assertIn("白名单", summary.items[0].reason)


if __name__ == "__main__":
    unittest.main()
