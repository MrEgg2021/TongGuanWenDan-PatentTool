from __future__ import annotations

import unittest

from core.official_docs.models import (
    NamingGroupConfig,
    NoticeMeta,
    NoticeTypeNamingConfig,
    ProcessOptions,
)
from core.official_docs.naming_rules import render_notice_output


class OfficialDocsNamingGroupsResolutionTests(unittest.TestCase):
    RECEIPT_TYPE_KEY = "10071|电子提交收据"

    def _build_meta(self) -> NoticeMeta:
        return NoticeMeta(
            notice_code="210401",
            notice_name="第一次审查意见通知书",
            invention_name="一种装置",
            app_no="2025113838195",
            issue_date="2025-11-06",
            patent_type="发明专利",
        )

    def _build_receipt_meta(self) -> NoticeMeta:
        return NoticeMeta(
            notice_code="10071",
            notice_name="电子提交收据",
            app_no="2022106496310",
            applicant="杭州黑白调科技有限公司",
            patent_type="发明专利",
            receipt_payer="杭州黑白调科技有限公司",
            receipt_app_no="2022106496310",
            receipt_patent_type="发明专利",
            receipt_fee_item="著录事项变更费",
            receipt_fee_item_first="著录事项变更费",
            receipt_fee_item_summary="著录事项变更费+发明专利第4年年费",
            receipt_amount="380.00",
        )

    def test_group_config_keeps_filename_fields_but_group_alias_rules_do_not_apply(self) -> None:
        type_key = "210401|第一次审查意见通知书"
        meta = self._build_meta()
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            type_naming_configs={
                type_key: NoticeTypeNamingConfig(
                    naming_mode="custom",
                    filename_fields=["申请号"],
                    alias_rules=[],
                )
            },
            naming_groups={
                "notice-group": NamingGroupConfig(
                    id="notice-group",
                    name="通知书",
                    member_type_keys=[type_key],
                    group_config=NoticeTypeNamingConfig(
                        naming_mode="custom",
                        filename_fields=["通知书名称"],
                        alias_rules=[
                            {
                                "notice_name": "第一次审查意见通知书",
                                "short_name": "一审",
                                "enabled": True,
                            }
                        ],
                    ),
                )
            },
            type_group_membership={type_key: "notice-group"},
        )

        rendered = render_notice_output(meta=meta, notice_kind=type_key, options=options)

        self.assertEqual(rendered.output_pdf_name, "第一次审查意见通知书.pdf")

    def test_grouped_type_uses_its_own_alias_rules(self) -> None:
        type_key = "210401|第一次审查意见通知书"
        meta = self._build_meta()
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            type_naming_configs={
                type_key: NoticeTypeNamingConfig(
                    naming_mode="custom",
                    filename_fields=["通知书名称"],
                    alias_rules=[
                        {
                            "notice_name": "第一次审查意见通知书",
                            "short_name": "一审",
                            "enabled": True,
                        }
                    ],
                )
            },
            naming_groups={
                "notice-group": NamingGroupConfig(
                    id="notice-group",
                    name="通知书",
                    member_type_keys=[type_key],
                    group_config=NoticeTypeNamingConfig(
                        naming_mode="custom",
                        filename_fields=["通知书名称"],
                        alias_rules=[],
                    ),
                )
            },
            type_group_membership={type_key: "notice-group"},
        )

        rendered = render_notice_output(meta=meta, notice_kind=type_key, options=options)

        self.assertEqual(rendered.output_pdf_name, "一审.pdf")

    def test_ungrouped_type_keeps_its_own_config(self) -> None:
        type_key = "210401|第一次审查意见通知书"
        meta = self._build_meta()
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            type_naming_configs={
                type_key: NoticeTypeNamingConfig(
                    naming_mode="custom",
                    filename_fields=["申请号"],
                    alias_rules=[],
                )
            },
            naming_groups={},
            type_group_membership={},
        )

        rendered = render_notice_output(meta=meta, notice_kind=type_key, options=options)

        self.assertEqual(rendered.output_pdf_name, "2025113838195.pdf")

    def test_receipt_in_normal_group_falls_back_to_receipt_default_fields(self) -> None:
        normal_type_key = "210401|第一次审查意见通知书"
        receipt_meta = self._build_receipt_meta()
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            naming_groups={
                "mixed-group": NamingGroupConfig(
                    id="mixed-group",
                    name="混合分组",
                    member_type_keys=[normal_type_key, self.RECEIPT_TYPE_KEY],
                    group_config=NoticeTypeNamingConfig(
                        naming_mode="custom",
                        filename_fields=["专利类型", "发明名称", "申请号", "通知书名称", "发文日"],
                        alias_rules=[],
                    ),
                )
            },
            type_group_membership={
                normal_type_key: "mixed-group",
                self.RECEIPT_TYPE_KEY: "mixed-group",
            },
        )

        rendered = render_notice_output(meta=receipt_meta, notice_kind=self.RECEIPT_TYPE_KEY, options=options)

        self.assertEqual(
            rendered.output_pdf_name,
            "收据+杭州黑白调科技有限公司+2022106496310+发明专利+著录事项变更费+发明专利第4年年费+380.00元.pdf",
        )

    def test_normal_notice_in_receipt_group_falls_back_to_normal_default_fields(self) -> None:
        normal_type_key = "210401|第一次审查意见通知书"
        meta = self._build_meta()
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            naming_groups={
                "mixed-group": NamingGroupConfig(
                    id="mixed-group",
                    name="混合分组",
                    member_type_keys=[self.RECEIPT_TYPE_KEY, normal_type_key],
                    group_config=NoticeTypeNamingConfig(
                        naming_mode="custom",
                        filename_fields=["收据", "收据_缴费项目汇总"],
                        alias_rules=[],
                    ),
                )
            },
            type_group_membership={
                self.RECEIPT_TYPE_KEY: "mixed-group",
                normal_type_key: "mixed-group",
            },
        )

        rendered = render_notice_output(meta=meta, notice_kind=normal_type_key, options=options)

        self.assertEqual(rendered.output_pdf_name, "发明专利+一种装置+2025113838195+第一次审查意见通知书+20251106.pdf")

    def test_mixed_group_keeps_legacy_receipt_fee_item_token(self) -> None:
        normal_type_key = "210401|第一次审查意见通知书"
        receipt_meta = self._build_receipt_meta()
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            naming_groups={
                "mixed-group": NamingGroupConfig(
                    id="mixed-group",
                    name="混合分组",
                    member_type_keys=[normal_type_key, self.RECEIPT_TYPE_KEY],
                    group_config=NoticeTypeNamingConfig(
                        naming_mode="custom",
                        filename_fields=["收据", "收据_缴费项目"],
                        alias_rules=[],
                    ),
                )
            },
            type_group_membership={
                normal_type_key: "mixed-group",
                self.RECEIPT_TYPE_KEY: "mixed-group",
            },
        )

        rendered = render_notice_output(meta=receipt_meta, notice_kind=self.RECEIPT_TYPE_KEY, options=options)

        self.assertEqual(rendered.output_pdf_name, "收据+著录事项变更费.pdf")


if __name__ == "__main__":
    unittest.main()
