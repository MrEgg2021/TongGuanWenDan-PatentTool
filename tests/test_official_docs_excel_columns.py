from __future__ import annotations

from dataclasses import replace
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
class OfficialDocsExcelColumnsTests(unittest.TestCase):
    def _sample_item(self) -> ProcessItemResult:
        return ProcessItemResult(
            source_zip_path="a.zip",
            status="success",
            notice_kind="exam_opinion",
            notice_key="210401|第一次审查意见通知书",
            output_pdf_name="a.pdf",
            summary_pdf_path="D:/summary/a.pdf",
            archive_pdf_path="D:/archive/2025/a.pdf",
            merged_sources=["main.pdf"],
            business_fields={
                "申请号": "2025113838195",
                "申请日": "2025-10-01",
                "内部编号": "NB-01",
                "案卷号": "AJ-01",
                "通知书名称": "第一次审查意见通知书",
                "发文日": "2025-11-06",
                "通知书代码": "210401",
                "专利类型": "发明专利",
                "期限天": "30",
                "逾期日": "2025-12-06",
                "发明名称": "一种测试装置",
                "申请人信息": "西安交通大学",
            },
            uncertain_fields={
                "DMHFLAG_raw": "1",
                "FAMINGLX_raw": "0",
                "附件YEWULX_raw_set": "A1;A2",
            },
            raw_fields={
                "SHUXINGXX/SHENQINGH": "2025113838195",
            },
            flat_fields={"SHUXINGXX/SHENQINGH": "2025113838195"},
            pdf_parse_status="成功",
            pdf_parse_error="",
            pdf_reject_reason="理由",
            pdf_cn_pubnos="CN123",
            pdf_examiner_name="张三",
            pdf_examiner_phone="010-12345678",
            pdf_inventor="赵六",
            pdf_agent="王五",
            pdf_agency_raw="北京测试代理有限公司",
            pdf_dossier_no="02911020002025021041",
        )

    def _headers(self, path: Path) -> list[str]:
        wb = openpyxl.load_workbook(path)  # type: ignore[name-defined]
        try:
            ws = wb.active
            return [str(cell.value or "") for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        finally:
            wb.close()

    def _first_row_mapping(self, path: Path) -> dict[str, str]:
        wb = openpyxl.load_workbook(path)  # type: ignore[name-defined]
        try:
            ws = wb.active
            rows = list(ws.iter_rows(min_row=1, max_row=2))
            headers = [str(cell.value or "") for cell in rows[0]]
            values = [str(cell.value or "") for cell in rows[1]]
            return dict(zip(headers, values))
        finally:
            wb.close()

    def test_parse_columns_hidden_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[self._sample_item()], include_exam_pdf_columns=False)
            headers = self._headers(path)
        self.assertEqual(
            headers,
            [
                "状态",
                "处理日期",
                "发明名称",
                "专利类型",
                "通知书名称",
                "申请号",
                "申请日",
                "发文日",
                "逾期日",
                "内部编号",
                "输出PDF名称",
                "申请人信息",
                "通知书类型",
                "通知书代码",
                "期限天",
                "案卷号",
                "汇总PDF路径",
                "归档PDF路径",
                "错误信息",
                "源ZIP",
            ],
        )
        self.assertNotIn("PDF解析状态", headers)
        self.assertNotIn("驳回理由", headers)
        self.assertIn("处理日期", headers)
        self.assertIn("申请号", headers)
        self.assertIn("汇总PDF路径", headers)
        self.assertIn("归档PDF路径", headers)
        self.assertIn("申请人信息", headers)
        self.assertNotIn("专利类型(显示)", headers)
        self.assertNotIn("DMHFLAG原值", headers)
        self.assertNotIn("附件YEWULX原值集合", headers)
        self.assertNotIn("证据_申请人信息", headers)
        self.assertNotIn("公告二维码图片", headers)
        self.assertNotIn("SHUXINGXX/SHENQINGH", headers)
        self.assertNotIn("通知书键", headers)
        self.assertNotIn("合并来源", headers)
        self.assertEqual(headers[:12], [
            "状态",
            "处理日期",
            "发明名称",
            "专利类型",
            "通知书名称",
            "申请号",
            "申请日",
            "发文日",
            "逾期日",
            "内部编号",
            "输出PDF名称",
            "申请人信息",
        ])
        self.assertEqual(headers.index("源ZIP"), len(headers) - 1)

    def test_parse_columns_present_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[self._sample_item()], include_exam_pdf_columns=True)
            headers = self._headers(path)
            row = self._first_row_mapping(path)
        self.assertEqual(headers[:15], [
            "状态",
            "处理日期",
            "发明名称",
            "专利类型",
            "通知书名称",
            "申请号",
            "申请日",
            "发文日",
            "逾期日",
            "内部编号",
            "输出PDF名称",
            "申请人信息",
            "发明人信息",
            "代理机构信息",
            "代理人信息",
        ])
        self.assertIn("PDF解析状态", headers)
        self.assertIn("PDF解析错误", headers)
        self.assertIn("发明人信息", headers)
        self.assertIn("代理机构信息", headers)
        self.assertIn("代理人信息", headers)
        self.assertIn("驳回理由", headers)
        self.assertNotIn("条款", headers)
        self.assertIn("对比件信息", headers)
        self.assertIn("审查员姓名", headers)
        self.assertIn("审查员电话", headers)
        self.assertNotIn("代理信息原文", headers)
        self.assertNotIn("DMHFLAG原值", headers)
        self.assertNotIn("附件YEWULX原值集合", headers)
        self.assertNotIn("证据_驳回理由", headers)
        self.assertNotIn("公告二维码图片", headers)
        self.assertEqual(row.get("发明人信息"), "赵六")
        self.assertEqual(row.get("代理机构信息"), "北京测试代理有限公司")
        self.assertEqual(row.get("代理人信息"), "王五")
        self.assertEqual(row.get("申请号"), "2025113838195")
        self.assertEqual(row.get("申请日"), "2025-10-01")
        self.assertEqual(row.get("内部编号"), "NB-01")
        self.assertEqual(row.get("案卷号"), "AJ-01")
        self.assertEqual(row.get("发明名称"), "一种测试装置")
        self.assertEqual(row.get("申请人信息"), "西安交通大学")
        self.assertEqual(row.get("专利类型"), "发明专利")
        self.assertRegex(str(row.get("处理日期", "")), r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(row.get("汇总PDF路径"), "D:/summary/a.pdf")
        self.assertEqual(row.get("归档PDF路径"), "D:/archive/2025/a.pdf")
        self.assertEqual(row.get("源ZIP"), "a.zip")
        self.assertNotIn("通知书键", headers)
        self.assertNotIn("合并来源", headers)

    def test_applicant_prefers_business_value_over_pdf_value(self) -> None:
        item = replace(
            self._sample_item(),
            pdf_applicant="PDF申请人",
            business_fields={**self._sample_item().business_fields, "申请人信息": "基础申请人"},
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[item], include_exam_pdf_columns=True)
            row = self._first_row_mapping(path)

        self.assertEqual(row.get("申请人信息"), "基础申请人")

    def test_applicant_falls_back_to_pdf_value_when_business_value_missing(self) -> None:
        item = replace(
            self._sample_item(),
            pdf_applicant="PDF申请人",
            business_fields={**self._sample_item().business_fields, "申请人信息": ""},
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[item], include_exam_pdf_columns=True)
            row = self._first_row_mapping(path)

        self.assertEqual(row.get("申请人信息"), "PDF申请人")

    def test_control_characters_are_sanitized(self) -> None:
        item = replace(
            self._sample_item(),
            reason="bad\x00reason\x07",
            pdf_reject_reason="line1\x0bline2",
            raw_fields={"BAD/CONTROL": "A\x00B\x1fC"},
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[item], include_exam_pdf_columns=True)
            row = self._first_row_mapping(path)

        self.assertEqual(row.get("错误信息"), "badreason")
        self.assertEqual(row.get("驳回理由"), "line1line2")
        self.assertIsNone(row.get("BAD/CONTROL"))

    def test_rows_follow_input_order_without_resort(self) -> None:
        item_b = self._sample_item()
        item_a = replace(
            self._sample_item(),
            source_zip_path="b.zip",
            business_fields={**self._sample_item().business_fields, "申请号": "2024113838195"},
            notice_key="210401|第二次审查意见通知书",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[item_b, item_a], include_exam_pdf_columns=False)
            wb = openpyxl.load_workbook(path)  # type: ignore[name-defined]
            try:
                ws = wb.active
                headers = [str(cell.value or "") for cell in next(ws.iter_rows(min_row=1, max_row=1))]
                rows = list(ws.iter_rows(min_row=2, max_row=3, values_only=True))
            finally:
                wb.close()
        index_zip = headers.index("源ZIP")
        self.assertEqual(str(rows[0][index_zip] or ""), "a.zip")
        self.assertEqual(str(rows[1][index_zip] or ""), "b.zip")

    def test_receipt_business_fields_are_exported_when_present(self) -> None:
        item = replace(
            self._sample_item(),
            notice_kind="10071|电子提交收据",
            notice_key="10071|电子提交收据",
            business_fields={
                "收据_缴费人": "杭州黑白调科技有限公司",
                "收据_申请号": "2022106496310",
                "收据_专利类型": "发明专利",
                "收据_缴费项目": "著录事项变更费",
                "收据_缴费项目首项": "著录事项变更费",
                "收据_缴费项目汇总": "著录事项变更费+发明专利第4年年费",
                "收据_缴费项目明细": "著录事项变更费200.00元+发明专利第4年年费180.00元",
                "收据_缴费金额": "380.00",
                "收据_缴费金额元": "380.00元",
                "收据_缴费日期": "2025-05-15",
                "收据_缴费方式": "网上支付",
                "收据_订单号": "202505159031113840",
                "收据_票据代码": "00010125",
                "收据_票据号码": "0003636953",
                "收据_开票日期": "2025-05-16",
                "收据_交款人统一社会信用代码": "91330108MA2CDQKQ3B",
                "收据_校验码": "715649",
                "收据_收款单位": "国家知识产权局专利局",
                "收据_复核人": "王舒",
                "收据_收款人": "董蕙如",
            },
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.xlsx"
            write_excel_report(str(path), items=[item], include_exam_pdf_columns=False)
            headers = self._headers(path)
            row = self._first_row_mapping(path)

        self.assertIn("收据_缴费项目首项", headers)
        self.assertIn("收据_缴费项目汇总", headers)
        self.assertIn("收据_缴费项目明细", headers)
        self.assertIn("收据_交款人统一社会信用代码", headers)
        self.assertIn("收据_校验码", headers)
        self.assertIn("收据_收款单位", headers)
        self.assertIn("收据_复核人", headers)
        self.assertIn("收据_收款人", headers)
        self.assertEqual(row.get("收据_缴费项目首项"), "著录事项变更费")
        self.assertEqual(row.get("收据_缴费项目汇总"), "著录事项变更费+发明专利第4年年费")
        self.assertEqual(row.get("收据_缴费项目明细"), "著录事项变更费200.00元+发明专利第4年年费180.00元")
        self.assertEqual(row.get("收据_交款人统一社会信用代码"), "91330108MA2CDQKQ3B")
        self.assertEqual(row.get("收据_校验码"), "715649")
        self.assertEqual(row.get("收据_收款单位"), "国家知识产权局专利局")
        self.assertEqual(row.get("收据_复核人"), "王舒")
        self.assertEqual(row.get("收据_收款人"), "董蕙如")


if __name__ == "__main__":
    unittest.main()
