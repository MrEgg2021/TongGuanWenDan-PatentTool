from __future__ import annotations

import unittest

from core.official_docs.field_governance import (
    build_notice_key,
    build_field_layers,
    extract_patent_type_code_from_app_no,
    infer_patent_type_from_app_no,
    map_patent_type_display,
    should_skip_by_filter,
)
from core.official_docs.models import NoticeMeta


class OfficialDocsFieldGovernanceTests(unittest.TestCase):
    def test_map_patent_type_display_marks_unknown_codes(self) -> None:
        self.assertEqual(map_patent_type_display("1"), "发明专利")
        self.assertEqual(map_patent_type_display("2"), "实用新型专利")
        self.assertEqual(map_patent_type_display("3"), "外观专利")
        self.assertEqual(map_patent_type_display("6"), "海牙外观")
        self.assertEqual(map_patent_type_display("8"), "PCT发明")
        self.assertEqual(map_patent_type_display("9"), "PCT实用新型")
        self.assertEqual(map_patent_type_display("0"), "")
        self.assertEqual(map_patent_type_display("5"), "")

    def test_extract_and_infer_from_app_no(self) -> None:
        self.assertEqual(extract_patent_type_code_from_app_no("2013106888347.5"), "1")
        self.assertEqual(extract_patent_type_code_from_app_no("02286689.2"), "2")
        self.assertEqual(extract_patent_type_code_from_app_no("PCT/CN2023/078301"), "")
        self.assertEqual(infer_patent_type_from_app_no("2013106888347.5"), ("1", "发明专利"))

    def test_build_field_layers_exports_business_and_uncertain_zones(self) -> None:
        meta = NoticeMeta(
            notice_code="210401",
            notice_name="第一次审查意见通知书",
            invention_name="一种测试装置",
            app_no="2025113838195",
            issue_date="2025-11-06",
            internal_no="NB-01",
            due_date="2025-12-06",
            limit_days="30",
            doc_serial="FW-01",
            dossier_no="AJ-01",
            applicant="西安交通大学",
        )
        raw_fields = {
            "SHUXINGXX/FAMINGLX": "2",
            "SHUXINGXX/DMHFLAG": "1",
            "SHUXINGXX/SHENQINGR": "20251001",
            "FUJIANLB/FUJIAN[1]/YEWULX": "A1",
            "FUJIANLB/FUJIAN[2]/YEWULX": "A1",
            "FUJIANLB/FUJIAN[3]/YEWULX": "A2",
        }
        layers = build_field_layers(meta=meta, raw_fields=raw_fields)
        self.assertEqual(layers.notice_key, "210401|第一次审查意见通知书")
        self.assertEqual(layers.business_fields.get("发明名称"), "一种测试装置")
        self.assertEqual(layers.business_fields.get("申请人信息"), "西安交通大学")
        self.assertEqual(layers.business_fields.get("专利类型"), "发明专利")
        self.assertEqual(layers.business_fields.get("申请日"), "2025-10-01")
        self.assertEqual(layers.uncertain_fields.get("DMHFLAG_raw"), "1")
        self.assertEqual(layers.uncertain_fields.get("FAMINGLX_raw"), "2")
        self.assertEqual(layers.uncertain_fields.get("附件YEWULX_raw_set"), "A1;A2")

    def test_build_field_layers_exports_receipt_line_items_and_ticket_headers(self) -> None:
        meta = NoticeMeta(
            notice_code="10071",
            notice_name="电子提交收据",
            app_no="2022106496310",
            receipt_payer="杭州黑白调科技有限公司",
            receipt_app_no="2022106496310",
            receipt_patent_type="发明专利",
            receipt_fee_item="著录事项变更费",
            receipt_fee_item_first="著录事项变更费",
            receipt_fee_item_summary="著录事项变更费+发明专利第4年年费",
            receipt_fee_item_detail="著录事项变更费200.00元+发明专利第4年年费180.00元",
            receipt_amount="380.00",
            receipt_payment_date="2025-05-15",
            receipt_payment_method="网上支付",
            receipt_order_no="202505159031113840",
            receipt_ticket_code="00010125",
            receipt_ticket_no="0003636953",
            receipt_invoice_date="2025-05-16",
            receipt_payer_credit_code="91330108MA2CDQKQ3B",
            receipt_check_code="715649",
            receipt_payee_unit="国家知识产权局专利局",
            receipt_reviewer="王舒",
            receipt_collector="董蕙如",
        )

        layers = build_field_layers(meta=meta, raw_fields={})

        self.assertEqual(layers.business_fields.get("收据_缴费项目"), "著录事项变更费")
        self.assertEqual(layers.business_fields.get("收据_缴费项目首项"), "著录事项变更费")
        self.assertEqual(layers.business_fields.get("收据_缴费项目汇总"), "著录事项变更费+发明专利第4年年费")
        self.assertEqual(layers.business_fields.get("收据_缴费项目明细"), "著录事项变更费200.00元+发明专利第4年年费180.00元")
        self.assertEqual(layers.business_fields.get("收据_交款人统一社会信用代码"), "91330108MA2CDQKQ3B")
        self.assertEqual(layers.business_fields.get("收据_校验码"), "715649")
        self.assertEqual(layers.business_fields.get("收据_收款单位"), "国家知识产权局专利局")
        self.assertEqual(layers.business_fields.get("收据_复核人"), "王舒")
        self.assertEqual(layers.business_fields.get("收据_收款人"), "董蕙如")

    def test_build_field_layers_unknown_when_app_no_invalid(self) -> None:
        meta = NoticeMeta(
            notice_code="210401",
            notice_name="第一次审查意见通知书",
            app_no="ABC",
        )
        layers = build_field_layers(meta=meta, raw_fields={"SHUXINGXX/FAMINGLX": "1"})
        self.assertEqual(layers.business_fields.get("专利类型"), "")
        self.assertEqual(layers.uncertain_fields.get("FAMINGLX_raw"), "1")

    def test_should_skip_by_filter_for_pct_and_receipt(self) -> None:
        pct_meta = NoticeMeta(notice_name="PCT国际申请相关通知书")
        pct_reason = should_skip_by_filter(meta=pct_meta, raw_fields={})
        self.assertIn("PCT", pct_reason)

        receipt_meta = NoticeMeta(notice_name="电子申请回执")
        receipt_reason = should_skip_by_filter(meta=receipt_meta, raw_fields={})
        self.assertIn("回执", receipt_reason)

    def test_should_not_skip_whitelisted_pct_notice_key(self) -> None:
        meta = NoticeMeta(
            notice_code="PCT/ISA/210C",
            notice_name="国际检索报告",
        )
        reason = should_skip_by_filter(meta=meta, raw_fields={})
        self.assertEqual(reason, "")

    def test_should_skip_unknown_pct_notice_key(self) -> None:
        meta = NoticeMeta(
            notice_code="PCT/NEW/999",
            notice_name="未知PCT通知书",
        )
        reason = should_skip_by_filter(meta=meta, raw_fields={})
        self.assertIn("PCT", reason)
        self.assertIn("白名单", reason)

    def test_build_notice_key_degrades_to_app_no_and_name(self) -> None:
        meta = NoticeMeta(
            notice_name="第一次审查意见通知书",
            app_no="2025113838195",
        )
        self.assertEqual(build_notice_key(meta), "2025113838195|第一次审查意见通知书")


if __name__ == "__main__":
    unittest.main()
