from __future__ import annotations

import unittest

from core.official_docs.models import NoticeMeta, NoticeTypeNamingConfig, ProcessOptions
from core.official_docs.naming_rules import render_notice_output


class OfficialDocsNamingNoOutputPrefixTests(unittest.TestCase):
    def _build_options(self, fields: list[str]) -> ProcessOptions:
        return ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
            type_naming_configs={
                "unknown": NoticeTypeNamingConfig(
                    naming_mode="custom",
                    filename_fields=fields,
                    alias_rules=[],
                )
            },
        )

    def test_pct_name_no_longer_injects_output_segment(self) -> None:
        options = self._build_options(["专利类型", "申请号", "通知书名称", "发文日"])
        meta = NoticeMeta(
            app_no="PCT/CN2023/078301",
            notice_name="国际检索报告",
            issue_date="2023-10-23",
        )

        rendered = render_notice_output(meta=meta, notice_kind="unknown", options=options)

        self.assertEqual(rendered.output_pdf_name, "PCT_CN2023_078301+国际检索报告+20231023.pdf")
        self.assertNotIn("output", rendered.output_pdf_name.lower())

    def test_all_empty_fields_falls_back_to_notice(self) -> None:
        options = self._build_options(["发文日", "申请日"])
        meta = NoticeMeta()

        rendered = render_notice_output(meta=meta, notice_kind="unknown", options=options)

        self.assertEqual(rendered.output_pdf_name, "notice.pdf")
        self.assertNotIn("output", rendered.output_pdf_name.lower())


if __name__ == "__main__":
    unittest.main()
