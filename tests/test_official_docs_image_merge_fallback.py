from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from core.official_docs.models import ProcessOptions
from core.official_docs.process import process_official_notice_archives


try:
    import fitz  # type: ignore

    _FITZ_AVAILABLE = True
except Exception:
    _FITZ_AVAILABLE = False


@unittest.skipUnless(_FITZ_AVAILABLE, "requires PyMuPDF")
class OfficialDocsImageMergeFallbackTests(unittest.TestCase):
    def _make_pdf(self, text: str) -> bytes:
        doc = fitz.open()  # type: ignore[name-defined]
        try:
            page = doc.new_page()
            page.insert_text((72, 72), text)
            return doc.tobytes()
        finally:
            doc.close()

    def _make_png(self, color: str = "white") -> bytes:
        image = Image.new("RGB", (240, 140), color=color)
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()

    def _read_pdf_page_count(self, path: Path) -> int:
        doc = fitz.open(path)  # type: ignore[name-defined]
        try:
            return int(doc.page_count)
        finally:
            doc.close()

    def _build_options(self, root: Path) -> ProcessOptions:
        return ProcessOptions(
            summary_root_dir=str(root / "summary"),
            archive_root_dir=str(root / "archive"),
            write_summary=True,
            write_archive=False,
            confirm_each=False,
        )

    def test_image_only_archive_is_processed_into_single_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_zip = root / "image_only.zip"
            list_xml = """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <TONGZHISXJ>
    <SHUXINGXX>
      <SHENQINGH>2025113838195</SHENQINGH>
      <TONGZHISBM>210401</TONGZHISBM>
      <TONGZHISMC>第一次审查意见通知书</TONGZHISMC>
      <FAWENR>2025-11-06</FAWENR>
    </SHUXINGXX>
  </TONGZHISXJ>
</root>
"""
            with zipfile.ZipFile(source_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("list.xml", list_xml.encode("utf-8"))
                zf.writestr("scan_001.png", self._make_png("lightgray"))

            summary = process_official_notice_archives([str(source_zip)], self._build_options(root))

            self.assertEqual(summary.success, 1)
            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.items[0].status, "success")
            self.assertIn("(image->pdf)", ";".join(summary.items[0].merged_sources))

            output_pdf = Path(summary.items[0].summary_pdf_path)
            self.assertTrue(output_pdf.exists())
            self.assertEqual(self._read_pdf_page_count(output_pdf), 1)

    def test_pdf_and_image_are_merged_into_single_output_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_zip = root / "pdf_image_mix.zip"
            list_xml = """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <TONGZHISXJ>
    <SHUXINGXX>
      <SHENQINGH>2025113838195</SHENQINGH>
      <TONGZHISBM>210401</TONGZHISBM>
      <TONGZHISMC>第一次审查意见通知书</TONGZHISMC>
      <FAWENR>2025-11-06</FAWENR>
    </SHUXINGXX>
  </TONGZHISXJ>
</root>
"""
            with zipfile.ZipFile(source_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("list.xml", list_xml.encode("utf-8"))
                zf.writestr("210401.pdf", self._make_pdf("main-page"))
                zf.writestr("attachment.png", self._make_png("white"))

            summary = process_official_notice_archives([str(source_zip)], self._build_options(root))

            self.assertEqual(summary.success, 1)
            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.items[0].status, "success")

            merged_sources = summary.items[0].merged_sources
            self.assertGreaterEqual(len(merged_sources), 2)
            self.assertEqual(merged_sources[0], "210401.pdf")
            self.assertTrue(any("(image->pdf)" in item for item in merged_sources[1:]))

            output_pdf = Path(summary.items[0].summary_pdf_path)
            self.assertTrue(output_pdf.exists())
            self.assertEqual(self._read_pdf_page_count(output_pdf), 2)


if __name__ == "__main__":
    unittest.main()
