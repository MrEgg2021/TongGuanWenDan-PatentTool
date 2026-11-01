from __future__ import annotations

import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from core.official_docs.pdf_entity_extract import PdfEntityExtractResult
from core.official_docs.models import NoticeMeta, NoticeTypeNamingConfig, ParsedNotice, PdfSource, ProcessOptions
from core.official_docs.process import process_official_notice_archives


try:
    import fitz  # type: ignore
    import openpyxl  # type: ignore

    _FITZ_AVAILABLE = True
except Exception:
    _FITZ_AVAILABLE = False


@unittest.skipUnless(_FITZ_AVAILABLE, "requires PyMuPDF")
class OfficialDocsProcessPdfParseTests(unittest.TestCase):
    def _make_pdf(self, text: str) -> bytes:
        doc = fitz.open()  # type: ignore[name-defined]
        try:
            page = doc.new_page()
            page.insert_text((72, 72), text)
            return doc.tobytes()
        finally:
            doc.close()

    def _make_zip(self, root: Path, *, name: str, notice_code: str, notice_name: str) -> str:
        list_xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<root>
  <FAWENXLH>FW-001</FAWENXLH>
  <TONGZHISXJ>
    <SHUXINGXX>
      <ANJUANH>AJ-01</ANJUANH>
      <NEIBUBH>NB-01</NEIBUBH>
      <SHENQINGH>2025113838195</SHENQINGH>
      <TONGZHISBM>{notice_code}</TONGZHISBM>
      <TONGZHISMC>{notice_name}</TONGZHISMC>
      <FAWENR>20251106</FAWENR>
      <YUQIRQ>2025-12-06</YUQIRQ>
      <QIXIAN>30</QIXIAN>
    </SHUXINGXX>
  </TONGZHISXJ>
</root>
"""
        zip_path = root / name
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("list.xml", list_xml.encode("utf-8"))
            zf.writestr(f"{notice_code}.pdf", self._make_pdf("main"))
        return str(zip_path)

    def _make_no_list_zip(self, root: Path, *, name: str, pdf_name: str = "main.pdf") -> str:
        text = "\n".join(
            [
                "第一次审查意见通知书",
                "申请号：2025113838195",
                "发明名称：一种测试装置",
                "发文日：2025年11月06日",
            ]
        )
        zip_path = root / name
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(pdf_name, self._make_pdf(text))
        return str(zip_path)

    def _custom_applicant_options(self, root: Path, *, enable_parse: bool) -> ProcessOptions:
        cfg = NoticeTypeNamingConfig(
            naming_mode="custom",
            filename_fields=["申请号", "申请人信息", "通知书名称"],
        )
        return ProcessOptions(
            summary_root_dir=str(root / "summary"),
            archive_root_dir=str(root / "archive"),
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            enable_exam_pdf_parse=enable_parse,
            pdf_parse_field_flags={"applicant": enable_parse},
            type_naming_configs={
                "exam_opinion": cfg,
                "210401|第一次审查意见通知书": cfg,
            },
        )

    def _excel_first_row(self, excel_path: str) -> dict[str, str]:
        wb = openpyxl.load_workbook(excel_path)  # type: ignore[name-defined]
        try:
            ws = wb.active
            rows = list(ws.iter_rows(min_row=1, max_row=2, values_only=True))
            headers = [str(value or "") for value in rows[0]]
            values = [str(value or "") for value in rows[1]]
            return dict(zip(headers, values))
        finally:
            wb.close()

    def _run(self, *, zip_path: str, enable_parse: bool):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
                enable_exam_pdf_parse=enable_parse,
                pdf_parse_field_flags={
                    "applicant": enable_parse,
                    "inventor": enable_parse,
                    "agency_raw": enable_parse,
                    "department": enable_parse,
                    "center": enable_parse,
                    "examiner": enable_parse,
                    "panel": enable_parse,
                    "reject_reason": enable_parse,
                    "prior_art": enable_parse,
                    "dossier_no": enable_parse,
                    "authorization_pub_no": enable_parse,
                    "authorization_pub_date": enable_parse,
                    "certificate_no": enable_parse,
                    "qrcode_link": enable_parse,
                    "qrcode_image": enable_parse,
                },
            )
            return process_official_notice_archives([zip_path], options)

    def test_parse_disabled_marks_unenabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="exam.zip",
                notice_code="210401",
                notice_name="第一次审查意见通知书",
            )
            with patch("core.official_docs.process.extract_pdf_entity_fields") as mocked:
                summary = self._run(zip_path=zip_path, enable_parse=False)
            self.assertEqual(summary.success, 1)
            self.assertEqual(summary.items[0].pdf_parse_status, "未启用")
            mocked.assert_not_called()

    def test_exam_notice_parse_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="exam.zip",
                notice_code="210401",
                notice_name="第一次审查意见通知书",
            )
            fake = PdfEntityExtractResult(
                status="成功",
                reject_reason="理由A",
                prior_art="CN123",
                examiner="张三",
                examiner_phone="010-12345678",
                department="专利审查协作湖北中心",
                applicant="杭州市拱墅区全息智能技术研究院",
                evidence={"evidence_department": "审查部门：专利审查协作湖北中心"},
            )
            with patch("core.official_docs.process.extract_pdf_entity_fields", return_value=fake):
                summary = self._run(zip_path=zip_path, enable_parse=True)
            item = summary.items[0]
            self.assertEqual(item.status, "success")
            self.assertEqual(item.pdf_parse_status, "成功")
            self.assertEqual(item.pdf_reject_reason, "理由A")
            self.assertEqual(item.pdf_reject_reasons, "理由A")
            self.assertEqual(item.pdf_clauses, "")
            self.assertEqual(item.pdf_cn_pubnos, "CN123")
            self.assertEqual(item.pdf_examiner_name, "张三")
            self.assertEqual(item.pdf_examiner_phone, "010-12345678")
            self.assertEqual(item.pdf_department, "专利审查协作湖北中心")
            self.assertEqual(item.pdf_applicant, "杭州市拱墅区全息智能技术研究院")
            self.assertEqual(item.business_fields.get("申请人信息"), "杭州市拱墅区全息智能技术研究院")
            self.assertIn("evidence_department", item.pdf_evidence)

    def test_rectification_marks_unparsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="rectification.zip",
                notice_code="220301",
                notice_name="第一次补正通知书",
            )
            with patch(
                "core.official_docs.process.extract_pdf_entity_fields",
                return_value=PdfEntityExtractResult(status="未命中"),
            ) as mocked:
                summary = self._run(zip_path=zip_path, enable_parse=True)
            self.assertEqual(summary.success, 1)
            self.assertEqual(summary.items[0].pdf_parse_status, "未命中")
            mocked.assert_called_once()

    def test_exam_parse_failure_does_not_break_processing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="exam.zip",
                notice_code="210401",
                notice_name="第一次审查意见通知书",
            )
            with patch("core.official_docs.process.extract_pdf_entity_fields", side_effect=RuntimeError("bad parse")):
                summary = self._run(zip_path=zip_path, enable_parse=True)
            item = summary.items[0]
            self.assertEqual(item.status, "success")
            self.assertEqual(item.pdf_parse_status, "失败")
            self.assertIn("bad parse", item.pdf_parse_error)

    def test_applicant_filename_field_triggers_pdf_extract_even_when_pdf_parse_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="exam.zip",
                notice_code="210401",
                notice_name="第一次审查意见通知书",
            )
            fake = PdfEntityExtractResult(status="成功", applicant="杭州市拱墅区全息智能技术研究院")
            options = self._custom_applicant_options(root, enable_parse=False)

            with patch("core.official_docs.process.extract_pdf_entity_fields", return_value=fake) as mocked:
                summary = process_official_notice_archives([zip_path], options)

            item = summary.items[0]
            row = self._excel_first_row(summary.excel_path)
            self.assertEqual(summary.success, 1)
            self.assertEqual(mocked.call_count, 1)
            self.assertIn("杭州市拱墅区全息智能技术研究院", item.output_pdf_name)
            self.assertEqual(item.business_fields.get("申请人信息"), "杭州市拱墅区全息智能技术研究院")
            self.assertEqual(item.pdf_parse_status, "未启用")
            self.assertEqual(item.pdf_applicant, "")
            self.assertEqual(row.get("申请人信息"), "杭州市拱墅区全息智能技术研究院")
            self.assertIn("杭州市拱墅区全息智能技术研究院", str(row.get("输出PDF名称", "")))

    def test_applicant_filename_reuses_pdf_parse_result_when_parse_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="exam.zip",
                notice_code="210401",
                notice_name="第一次审查意见通知书",
            )
            fake = PdfEntityExtractResult(
                status="成功",
                applicant="杭州市拱墅区全息智能技术研究院",
                inventor="李四",
            )
            options = self._custom_applicant_options(root, enable_parse=True)
            options = replace(options, pdf_parse_field_flags={"applicant": True, "inventor": True})

            with patch("core.official_docs.process.extract_pdf_entity_fields", return_value=fake) as mocked:
                summary = process_official_notice_archives([zip_path], options)

            item = summary.items[0]
            self.assertEqual(summary.success, 1)
            self.assertEqual(mocked.call_count, 1)
            self.assertIn("杭州市拱墅区全息智能技术研究院", item.output_pdf_name)
            self.assertEqual(item.business_fields.get("申请人信息"), "杭州市拱墅区全息智能技术研究院")
            self.assertEqual(item.pdf_parse_status, "成功")
            self.assertEqual(item.pdf_applicant, "杭州市拱墅区全息智能技术研究院")
            self.assertEqual(item.pdf_inventor, "李四")

    def test_applicant_filename_field_works_for_no_list_pdf_fallback_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_no_list_zip(root, name="no-list.zip")
            parsed = ParsedNotice(
                source_zip_path=zip_path,
                notice_kind="exam_opinion",
                meta_source="pdf_fallback",
                meta=NoticeMeta(
                    notice_code="210401",
                    notice_name="第一次审查意见通知书",
                    invention_name="一种测试装置",
                    app_no="2025113838195",
                    issue_date_raw="20251106",
                    issue_date="2025-11-06",
                    issue_date8="20251106",
                    patent_type="发明专利",
                ),
                flat_fields={
                    "SHENQINGH": "2025113838195",
                    "TONGZHISBM": "210401",
                    "TONGZHISMC": "第一次审查意见通知书",
                    "FAWENR": "20251106",
                },
                pdf_entries=[PdfSource(raw_name="main.pdf", display_name="main.pdf", kind="main")],
            )
            fake = PdfEntityExtractResult(status="成功", applicant="西安交通大学")
            options = self._custom_applicant_options(root, enable_parse=False)

            with patch("core.official_docs.process.parse_official_notice_archive", return_value=parsed):
                with patch("core.official_docs.process.extract_pdf_entity_fields", return_value=fake) as mocked:
                    summary = process_official_notice_archives([zip_path], options)

            item = summary.items[0]
            row = self._excel_first_row(summary.excel_path)
            self.assertEqual(summary.success, 1)
            self.assertEqual(mocked.call_count, 1)
            self.assertIn("西安交通大学", item.output_pdf_name)
            self.assertEqual(item.business_fields.get("申请人信息"), "西安交通大学")
            self.assertEqual(row.get("申请人信息"), "西安交通大学")

    def test_empty_applicant_extract_keeps_filename_without_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = self._make_zip(
                root,
                name="exam.zip",
                notice_code="210401",
                notice_name="第一次审查意见通知书",
            )
            fake = PdfEntityExtractResult(status="未命中", applicant="")
            options = self._custom_applicant_options(root, enable_parse=False)

            with patch("core.official_docs.process.extract_pdf_entity_fields", return_value=fake) as mocked:
                summary = process_official_notice_archives([zip_path], options)

            item = summary.items[0]
            row = self._excel_first_row(summary.excel_path)
            self.assertEqual(summary.success, 1)
            self.assertEqual(mocked.call_count, 1)
            self.assertNotIn("未知申请人", item.output_pdf_name)
            self.assertNotIn("申请人信息", item.output_pdf_name)
            self.assertEqual(item.business_fields.get("申请人信息"), "")
            self.assertEqual(row.get("申请人信息"), "")


if __name__ == "__main__":
    unittest.main()
