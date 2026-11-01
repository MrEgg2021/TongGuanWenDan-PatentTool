import unittest

from core.official_docs.models import NoticeMeta, ProcessOptions
from core.official_docs.naming_rules import DEFAULT_FILENAME_FIELDS, default_alias_rules_for_type, render_notice_output


class OfficialDocsDefaultNamingFieldsV250Tests(unittest.TestCase):
    def test_default_filename_fields_order_includes_invention_name(self) -> None:
        self.assertEqual(
            DEFAULT_FILENAME_FIELDS,
            ("专利类型", "发明名称", "申请号", "通知书名称", "发文日"),
        )

    def test_missing_invention_name_is_skipped_without_extra_separator(self) -> None:
        meta = NoticeMeta(
            patent_type="发明专利",
            invention_name="",
            app_no="2025113838195",
            notice_name="第一次审查意见通知书",
            issue_date="2025-11-06",
        )
        options = ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
        )

        rendered = render_notice_output(meta=meta, notice_kind="exam_opinion", options=options)
        self.assertEqual(rendered.output_pdf_name, "发明专利+2025113838195+第一次审查意见通知书+20251106.pdf")
        self.assertNotIn("++", rendered.output_pdf_name)

    def test_default_alias_rules_disabled(self) -> None:
        exam_rules = default_alias_rules_for_type("exam_opinion")
        self.assertTrue(exam_rules)
        self.assertTrue(all(not bool(rule.enabled) for rule in exam_rules))


if __name__ == "__main__":
    unittest.main()
