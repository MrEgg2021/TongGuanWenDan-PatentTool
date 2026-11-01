from __future__ import annotations

import unittest

from core.official_docs import naming_rules
from core.official_docs.models import NoticeMeta, NoticeTypeNamingConfig, ProcessOptions
from core.official_docs.naming_rules import render_notice_output, render_notice_output_preview


class OfficialDocsFilenameSeparatorTests(unittest.TestCase):
    def _meta(self) -> NoticeMeta:
        return NoticeMeta(
            notice_code="210401",
            notice_name="第一次审查意见通知书",
            invention_name="一种装置",
            app_no="2025113838195",
            issue_date="2025-11-06",
            patent_type="发明专利",
        )

    def _options(self, separator: str | None = None) -> ProcessOptions:
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            type_naming_configs={
                "exam_opinion": NoticeTypeNamingConfig(
                    naming_mode="custom",
                    filename_fields=["通知书名称", "发文日"],
                    alias_rules=[],
                )
            },
        )
        if separator is not None:
            object.__setattr__(options, "filename_separator", separator)
        return options

    def test_default_separator_stays_plus(self) -> None:
        rendered = render_notice_output(meta=self._meta(), notice_kind="exam_opinion", options=self._options())

        self.assertEqual(rendered.output_pdf_name, "第一次审查意见通知书+20251106.pdf")

    def test_custom_separator_applies_to_export_and_preview(self) -> None:
        options = self._options("_")

        rendered = render_notice_output(meta=self._meta(), notice_kind="exam_opinion", options=options)
        preview = render_notice_output_preview(meta=self._meta(), notice_kind="exam_opinion", options=options)

        self.assertEqual(rendered.output_pdf_name, "第一次审查意见通知书_20251106.pdf")
        self.assertEqual(preview.preview_pdf_name, "第一次审查意见通知书_20251106.pdf")
        self.assertEqual(self._meta().issue_date, "2025-11-06")

    def test_blank_separator_normalizes_to_plus(self) -> None:
        rendered = render_notice_output(meta=self._meta(), notice_kind="exam_opinion", options=self._options(""))

        self.assertEqual(rendered.output_pdf_name, "第一次审查意见通知书+20251106.pdf")

    def test_multi_character_separator_is_allowed(self) -> None:
        rendered = render_notice_output(meta=self._meta(), notice_kind="exam_opinion", options=self._options(" - "))

        self.assertEqual(rendered.output_pdf_name, "第一次审查意见通知书 - 20251106.pdf")

    def test_invalid_separator_is_reported(self) -> None:
        validator = getattr(naming_rules, "validate_filename_separator", None)

        self.assertIsNotNone(validator)
        self.assertTrue(validator("/"))
        self.assertTrue(validator("\n"))


if __name__ == "__main__":
    unittest.main()
