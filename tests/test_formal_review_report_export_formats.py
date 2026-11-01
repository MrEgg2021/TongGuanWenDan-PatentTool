import importlib.util
import tempfile
import unittest
from pathlib import Path

from core.formal_review.models import ClaimItem, FormalReviewDocument, Issue
from core.formal_review.report import build_report_payload, write_report_docx, write_report_xlsx


def _has_python_docx() -> bool:
    return importlib.util.find_spec("docx") is not None


def _has_openpyxl() -> bool:
    return importlib.util.find_spec("openpyxl") is not None


class FormalReviewReportExportFormatsTests(unittest.TestCase):
    def _build_payload(self):
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="一种装置，其特征在于，包含壳体（1）。", word_count=18, markers=["1"], refs=[])],
            description="说明书内容。",
            abstract="摘要内容。",
            drawings="图1为结构示意图。",
        )
        issues = [
            Issue(
                rule_id="claim.ref.marker_basis.missing",
                severity="warning",
                category="rule",
                section="claims",
                message="紧邻术语引用基础缺失。",
                claim_num=1,
                span_start=10,
                span_end=18,
                snippet="所述壳体",
                ignored=False,
            )
        ]
        return build_report_payload(source_file="plain_text_input", document=document, issues=issues)

    @unittest.skipUnless(_has_python_docx(), "requires python-docx")
    def test_write_report_docx_creates_readable_report(self) -> None:
        payload = self._build_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.docx"
            written = Path(write_report_docx(str(output), payload))
            self.assertTrue(written.exists())
            self.assertGreater(written.stat().st_size, 0)

            from docx import Document  # type: ignore

            doc = Document(str(written))
            paragraph_text = "\n".join(str(p.text or "") for p in doc.paragraphs)
            table_text = "\n".join(
                str(cell.text or "")
                for table in doc.tables
                for row in table.rows
                for cell in row.cells
            )
            self.assertIn("形式审查报告", paragraph_text)
            self.assertIn("来源：纯文本输入", paragraph_text)
            self.assertIn("检查项目", table_text)
            self.assertIn("附图标记引用基础缺失", table_text)
            self.assertIn("警告", table_text)
            self.assertNotIn("claims/", table_text)

    @unittest.skipUnless(_has_openpyxl(), "requires openpyxl")
    def test_write_report_xlsx_creates_issues_sheet(self) -> None:
        payload = self._build_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.xlsx"
            written = Path(write_report_xlsx(str(output), payload))
            self.assertTrue(written.exists())
            self.assertGreater(written.stat().st_size, 0)

            from openpyxl import load_workbook  # type: ignore

            wb = load_workbook(str(written))
            ws = wb["问题明细"]
            headers = [ws.cell(row=1, column=i).value for i in range(1, 9)]
            self.assertEqual(
                ["序号", "严重度", "检查项目", "分区", "权利要求号", "原因", "片段", "忽略"],
                headers,
            )
            self.assertEqual("警告", ws.cell(row=2, column=2).value)
            self.assertEqual("附图标记引用基础缺失", ws.cell(row=2, column=3).value)
            self.assertEqual("权利要求书", ws.cell(row=2, column=4).value)
            self.assertEqual("否", ws.cell(row=2, column=8).value)

    @unittest.skipUnless(_has_openpyxl(), "requires openpyxl")
    def test_write_report_xlsx_can_hide_ignored_column(self) -> None:
        payload = self._build_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report_no_ignored.xlsx"
            written = Path(write_report_xlsx(str(output), payload, include_ignored_column=False))
            self.assertTrue(written.exists())
            self.assertGreater(written.stat().st_size, 0)

            from openpyxl import load_workbook  # type: ignore

            wb = load_workbook(str(written))
            ws = wb["问题明细"]
            headers = [ws.cell(row=1, column=i).value for i in range(1, 8)]
            self.assertEqual(
                ["序号", "严重度", "检查项目", "分区", "权利要求号", "原因", "片段"],
                headers,
            )

    @unittest.skipUnless(_has_openpyxl(), "requires openpyxl")
    def test_write_report_xlsx_falls_back_for_unknown_values(self) -> None:
        payload = {
            "generated_at": "2026-02-25T12:00:00",
            "source_file": "plain_text_input",
            "summary": {"claims_count": 1, "issues_total": 1, "issues_ignored": 0, "issues_effective": 1},
            "document": {"claims": [], "description": "", "abstract": "", "drawings": ""},
            "issues": [
                {
                    "rule_id": "custom.rule.id",
                    "severity": "custom_severity",
                    "category": "rule",
                    "section": "custom_section",
                    "message": "x",
                    "claim_num": None,
                    "snippet": "",
                    "ignored": False,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "unknown.xlsx"
            written = Path(write_report_xlsx(str(output), payload))
            self.assertTrue(written.exists())

            from openpyxl import load_workbook  # type: ignore

            ws = load_workbook(str(written))["问题明细"]
            self.assertEqual("custom_severity", ws.cell(row=2, column=2).value)
            self.assertEqual("custom.rule.id", ws.cell(row=2, column=3).value)
            self.assertEqual("custom_section", ws.cell(row=2, column=4).value)

    @unittest.skipUnless(_has_python_docx() and _has_openpyxl(), "requires python-docx and openpyxl")
    def test_exporters_accept_empty_issues(self) -> None:
        payload = {
            "generated_at": "2026-02-25T12:00:00",
            "source_file": "plain_text_input",
            "summary": {"claims_count": 0, "issues_total": 0, "issues_ignored": 0, "issues_effective": 0},
            "document": {"claims": [], "description": "", "abstract": "", "drawings": ""},
            "issues": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(write_report_docx(str(Path(tmpdir) / "empty.docx"), payload))
            xlsx_path = Path(write_report_xlsx(str(Path(tmpdir) / "empty.xlsx"), payload))
            self.assertTrue(docx_path.exists())
            self.assertTrue(xlsx_path.exists())


if __name__ == "__main__":
    unittest.main()
