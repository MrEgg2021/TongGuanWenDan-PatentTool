from __future__ import annotations

import unittest

from core.official_docs.models import NoticeMeta, NoticeTypeNamingConfig, ProcessOptions
from core.official_docs.naming_rules import render_notice_output, render_notice_output_preview


class OfficialDocsPreviewPlaceholderTests(unittest.TestCase):
    def _build_options(self, fields: list[str]) -> ProcessOptions:
        return ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            type_naming_configs={
                "exam_opinion": NoticeTypeNamingConfig(
                    naming_mode="custom",
                    filename_fields=fields,
                    alias_rules=[],
                )
            },
        )

    def test_preview_uses_field_name_placeholder_when_value_empty(self) -> None:
        meta = NoticeMeta(
            notice_code="210401",
            notice_name="第一次审查意见通知书",
            app_no="2025113838195",
        )
        options = self._build_options(["发文日", "发文序号", "案卷号"])

        preview = render_notice_output_preview(meta=meta, notice_kind="exam_opinion", options=options)
        exported = render_notice_output(meta=meta, notice_kind="exam_opinion", options=options)

        self.assertEqual(preview.preview_pdf_name, "发文日+发文序号+案卷号.pdf")
        self.assertEqual(exported.output_pdf_name, "2025113838195.pdf")

    def test_preview_keeps_real_value_and_only_fills_missing_fields(self) -> None:
        meta = NoticeMeta(
            notice_code="210401",
            notice_name="第一次审查意见通知书",
            app_no="2025113838195",
            issue_date="2025-11-06",
            dossier_no="AJ-01",
        )
        options = self._build_options(["发文日", "发文序号", "案卷号"])

        preview = render_notice_output_preview(meta=meta, notice_kind="exam_opinion", options=options)
        exported = render_notice_output(meta=meta, notice_kind="exam_opinion", options=options)

        self.assertEqual(preview.preview_pdf_name, "20251106+发文序号+AJ-01.pdf")
        self.assertEqual(exported.output_pdf_name, "20251106+AJ-01.pdf")


if __name__ == "__main__":
    unittest.main()
