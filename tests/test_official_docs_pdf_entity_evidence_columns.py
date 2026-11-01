from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.official_docs.excel_report import write_excel_report
from core.official_docs.models import ProcessItemResult


try:
    import openpyxl

    _OPENPYXL_AVAILABLE = True
except Exception:
    _OPENPYXL_AVAILABLE = False


@unittest.skipUnless(_OPENPYXL_AVAILABLE, "requires openpyxl")
class OfficialDocsPdfEntityEvidenceColumnsTests(unittest.TestCase):
    def test_excel_keeps_business_parse_columns_but_drops_evidence_columns(self) -> None:
        item = ProcessItemResult(
            source_zip_path="a.zip",
            status="success",
            notice_kind="exam_opinion",
            notice_key="210401|第一次审查意见通知书",
            output_pdf_name="a.pdf",
            summary_pdf_path="D:/summary/a.pdf",
            archive_pdf_path="",
            merged_sources=["main.pdf"],
            pdf_parse_status="成功",
            pdf_department="专利审查协作北京中心",
            pdf_center="专利审查协作北京中心",
            pdf_applicant="西安交通大学",
            pdf_inventor="乔百杰",
            pdf_agent="段立彦",
            pdf_agency_raw="中济纬天专利代理有限公司",
            pdf_examiner_name="张三",
            pdf_examiner_phone="010-12345678",
            pdf_panel_head="刘丽伟",
            pdf_panel_main="徐锦丹",
            pdf_panel_member="李慧子",
            pdf_reject_reason="该申请不具备创造性",
            pdf_cn_pubnos="CN1234567A",
            pdf_dossier_no="02911020002025021041",
            pdf_authorization_pub_no="CN309620867S",
            pdf_authorization_pub_date="2025-11-21",
            pdf_certificate_no="第9636678号",
            pdf_qrcode_link="https://example.com/patent/CN309620867S",
            pdf_evidence={
                "evidence_department": "审查部门：专利审查协作北京中心",
                "evidence_applicant": "申请人：西安交通大学",
                "evidence_inventor": "发明人：乔百杰",
                "evidence_agency_raw": "专利代理机构：中济纬天专利代理有限公司",
                "evidence_panel_head": "合议组组长：刘丽伟",
                "evidence_reject_reason": "该申请不具备创造性",
                "evidence_prior_art": "对比文件：CN1234567A",
                "evidence_dossier_no": "申请方案卷号：02911020002025021041",
            },
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[item], include_exam_pdf_columns=True)
            wb = openpyxl.load_workbook(path)
            try:
                ws = wb.active
                headers = [str(cell.value or "") for cell in next(ws.iter_rows(min_row=1, max_row=1))]
                values = [str(cell.value or "") for cell in next(ws.iter_rows(min_row=2, max_row=2))]
            finally:
                wb.close()

        row = dict(zip(headers, values))
        self.assertIn("审查部门信息", headers)
        self.assertIn("代理人信息", headers)
        self.assertIn("代理机构信息", headers)
        self.assertIn("合议组组长", headers)
        self.assertIn("申请方案卷号", headers)
        self.assertIn("授权公告号", headers)
        self.assertIn("授权公告日", headers)
        self.assertIn("证书号", headers)
        self.assertIn("公告二维码链接", headers)
        self.assertNotIn("证据_申请人信息", headers)
        self.assertNotIn("证据_驳回理由", headers)
        self.assertNotIn("证据_对比件信息", headers)
        self.assertNotIn("公告二维码图片", headers)

        self.assertEqual(row.get("审查部门信息"), "专利审查协作北京中心")
        self.assertEqual(row.get("代理人信息"), "段立彦")
        self.assertEqual(row.get("代理机构信息"), "中济纬天专利代理有限公司")
        self.assertEqual(row.get("申请方案卷号"), "02911020002025021041")
        self.assertEqual(row.get("授权公告号"), "CN309620867S")
        self.assertEqual(row.get("证书号"), "第9636678号")


if __name__ == "__main__":
    unittest.main()
