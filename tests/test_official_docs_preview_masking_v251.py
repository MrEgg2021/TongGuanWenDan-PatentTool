from __future__ import annotations

import unittest

from core.official_docs.models import NoticeMeta, NoticeTypeNamingConfig, ProcessOptions
from core.official_docs.naming_rules import (
    mask_app_no_for_preview,
    render_notice_output,
    render_notice_output_preview,
)


class OfficialDocsPreviewMaskingV251Tests(unittest.TestCase):
    def _build_options(self) -> ProcessOptions:
        return ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=True,
            confirm_each=False,
        )

    def test_mask_rule_keep_first4_last4(self) -> None:
        self.assertEqual(mask_app_no_for_preview("2025113838195"), "2025*****8195")
        self.assertEqual(mask_app_no_for_preview("2025-113838195"), "2025-*****8195")

    def test_mask_rule_short_values(self) -> None:
        self.assertEqual(mask_app_no_for_preview("12345678"), "1******8")
        self.assertEqual(mask_app_no_for_preview("12"), "**")
        self.assertEqual(mask_app_no_for_preview("A-1"), "*-*")

    def test_preview_masks_but_real_output_keeps_raw_app_no(self) -> None:
        meta = NoticeMeta(
            patent_type="发明专利",
            invention_name="一种示例发明",
            app_no="2025113838195",
            notice_name="第一次审查意见通知书",
            issue_date="2025-11-06",
        )
        options = self._build_options()

        preview = render_notice_output_preview(meta=meta, notice_kind="exam_opinion", options=options)
        rendered = render_notice_output(meta=meta, notice_kind="exam_opinion", options=options)

        masked = mask_app_no_for_preview(meta.app_no).replace("*", "_")
        self.assertIn(masked, preview.preview_pdf_name)
        self.assertNotIn(meta.app_no, preview.preview_pdf_name)
        self.assertIn(meta.app_no, rendered.output_pdf_name)

    def test_preview_masks_app_no_with_dots_token(self) -> None:
        meta = NoticeMeta(
            patent_type="发明专利",
            app_no="2025113838195",
            app_no_dotted="2025.113838195",
            notice_name="第一次审查意见通知书",
            issue_date="2025-11-06",
        )
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            type_naming_configs={
                "exam_opinion": NoticeTypeNamingConfig(
                    naming_mode="custom",
                    filename_fields=["申请号带点"],
                    alias_rules=[],
                )
            },
        )

        preview = render_notice_output_preview(meta=meta, notice_kind="exam_opinion", options=options)
        rendered = render_notice_output(meta=meta, notice_kind="exam_opinion", options=options)

        raw = meta.app_no_dotted
        masked = mask_app_no_for_preview(raw).replace("*", "_")
        self.assertIn(masked, preview.preview_pdf_name)
        self.assertNotIn(raw, preview.preview_pdf_name)
        self.assertIn(raw, rendered.output_pdf_name)


if __name__ == "__main__":
    unittest.main()
