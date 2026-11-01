from __future__ import annotations

import unittest

from core.official_docs.field_governance import build_field_layers
from core.official_docs.models import NoticeMeta, ProcessOptions
from core.official_docs.naming_rules import render_notice_output
from core.official_docs.notice_name_rules import normalize_notice_name


class OfficialDocsNoticeNameNormalizationTests(unittest.TestCase):
    def test_design_notice_name_normalized_for_display(self) -> None:
        normalized = normalize_notice_name(
            notice_code="230302",
            notice_name="第一次审查意见通知书",
            patent_type_label="外观专利",
        )
        self.assertEqual(normalized, "第N次审查意见通知书")

    def test_business_fields_use_normalized_design_notice_name(self) -> None:
        meta = NoticeMeta(
            notice_code="230301",
            notice_name="第一次补正通知书",
            patent_type="外观专利",
            app_no="2025313838195",
        )
        layers = build_field_layers(meta=meta, raw_fields={})
        self.assertEqual(layers.notice_key, "230301|第一次补正通知书")
        self.assertEqual(layers.business_fields.get("通知书名称"), "第N次补正通知书")

    def test_filename_render_uses_normalized_design_notice_name(self) -> None:
        meta = NoticeMeta(
            notice_code="230302",
            notice_name="第一次审查意见通知书",
            patent_type="外观专利",
            app_no="2025313838195",
            issue_date="2025-11-06",
        )
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
        )
        rendered = render_notice_output(meta=meta, notice_kind="230302|第N次审查意见通知书", options=options)
        self.assertIn("第N次审查意见通知书", rendered.output_pdf_name)


if __name__ == "__main__":
    unittest.main()
