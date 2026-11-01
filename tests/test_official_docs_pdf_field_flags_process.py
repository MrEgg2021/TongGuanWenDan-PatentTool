from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from core.official_docs.models import ProcessOptions
from core.official_docs.pdf_entity_extract import PdfEntityExtractResult
from core.official_docs.process import process_official_notice_archives


try:
    import fitz  # type: ignore

    _FITZ_AVAILABLE = True
except Exception:
    _FITZ_AVAILABLE = False


@unittest.skipUnless(_FITZ_AVAILABLE, "requires PyMuPDF")
class OfficialDocsPdfFieldFlagsProcessTests(unittest.TestCase):
    def _make_pdf(self, text: str) -> bytes:
        doc = fitz.open()  # type: ignore[name-defined]
        try:
            page = doc.new_page()
            page.insert_text((72, 72), text)
            return doc.tobytes()
        finally:
            doc.close()

    def _make_zip(self, root: Path, *, notice_code: str = "210401", notice_name: str = "第一次审查意见通知书") -> str:
        list_xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<root>
  <TONGZHISXJ>
    <SHUXINGXX>
      <SHENQINGH>2025113838195</SHENQINGH>
      <TONGZHISBM>{notice_code}</TONGZHISBM>
      <TONGZHISMC>{notice_name}</TONGZHISMC>
      <FAWENR>2025-11-06</FAWENR>
    </SHUXINGXX>
  </TONGZHISXJ>
</root>
"""
        zip_path = root / "input.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("list.xml", list_xml.encode("utf-8"))
            zf.writestr(f"{notice_code}.pdf", self._make_pdf("main"))
        return str(zip_path)

    def test_parse_fields_are_masked_by_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(root)
            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
                enable_exam_pdf_parse=True,
                pdf_parse_field_flags={
                    "applicant": True,
                    "inventor": False,
                    "agent": True,
                    "agency_raw": True,
                    "department": False,
                    "center": False,
                    "examiner": True,
                    "panel": False,
                    "reject_reason": False,
                    "prior_art": False,
                    "dossier_no": False,
                    "authorization_pub_no": False,
                    "authorization_pub_date": False,
                    "certificate_no": False,
                    "qrcode_link": False,
                    "qrcode_image": False,
                },
            )
            fake = PdfEntityExtractResult(
                status="成功",
                applicant="申方公司",
                inventor="张三",
                agent="王五",
                agency_raw="某代理机构(12345)",
                department="审查部门A",
                center="审查协作中心A",
                examiner="李四",
                examiner_phone="010-0000",
                panel_head="组长",
                panel_main="主审",
                panel_member="参审",
                reject_reason="理由A",
                prior_art="CN123",
                dossier_no="02911020002025021041",
                evidence={
                    "evidence_applicant": "申请人：申方公司",
                    "evidence_inventor": "发明人：张三",
                    "evidence_agent": "代理人：王五",
                    "evidence_agency_raw": "代理机构：某代理机构",
                    "evidence_department": "审查部门：A",
                    "evidence_center": "审查协作中心：A",
                    "evidence_examiner": "审查员：李四",
                    "evidence_examiner_phone": "审查员电话：010-0000",
                    "evidence_panel_head": "合议组组长：组长",
                    "evidence_reject_reason": "权利要求1不符合专利法第26条第4款",
                    "evidence_prior_art": "CN123",
                    "evidence_dossier_no": "申请方案卷号：02911020002025021041",
                },
            )
            with patch("core.official_docs.process.extract_pdf_entity_fields", return_value=fake):
                summary = process_official_notice_archives([zip_path], options)

            item = summary.items[0]
            self.assertEqual(item.pdf_applicant, "申方公司")
            self.assertEqual(item.pdf_agent, "王五")
            self.assertEqual(item.pdf_agency_raw, "某代理机构(12345)")
            self.assertEqual(item.pdf_examiner_name, "李四")
            self.assertEqual(item.pdf_examiner_phone, "010-0000")
            self.assertEqual(item.pdf_inventor, "")
            self.assertEqual(item.pdf_department, "")
            self.assertEqual(item.pdf_center, "")
            self.assertEqual(item.pdf_panel_head, "")
            self.assertEqual(item.pdf_reject_reason, "")
            self.assertEqual(item.pdf_cn_pubnos, "")
            self.assertEqual(item.pdf_dossier_no, "")
            self.assertIn("evidence_applicant", item.pdf_evidence)
            self.assertIn("evidence_agent", item.pdf_evidence)
            self.assertNotIn("evidence_department", item.pdf_evidence)
            self.assertNotIn("evidence_panel_head", item.pdf_evidence)
            self.assertNotIn("evidence_reject_reason", item.pdf_evidence)

    def test_parse_enabled_with_no_selected_fields_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(root)
            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
                enable_exam_pdf_parse=True,
                pdf_parse_field_flags={
                    key: False
                    for key in (
                        "applicant",
                        "inventor",
                        "agent",
                        "agency_raw",
                        "department",
                        "center",
                        "examiner",
                        "panel",
                        "reject_reason",
                        "prior_art",
                        "dossier_no",
                        "authorization_pub_no",
                        "authorization_pub_date",
                        "certificate_no",
                        "qrcode_link",
                        "qrcode_image",
                    )
                },
            )
            with patch("core.official_docs.process.extract_pdf_entity_fields") as mocked:
                summary = process_official_notice_archives([zip_path], options)
            self.assertEqual(summary.success, 1)
            self.assertEqual(summary.items[0].status, "success")
            mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
