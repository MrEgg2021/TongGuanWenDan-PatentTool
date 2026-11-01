import unittest

from core.official_docs.models import ProcessOptions
from core.official_docs.template_render import build_meta_from_list_fields, render_output_paths


class OfficialDocsTemplateRenderTests(unittest.TestCase):
    def test_patent_type_is_inferred_from_app_no(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "2025113838195",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
                "FAMINGLX": "1",
            }
        )
        self.assertEqual(meta.patent_type, "发明专利")

    def test_invention_name_is_extracted(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "2025113838195",
                "FAMINGMC": "一种测试装置",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
            }
        )
        self.assertEqual(meta.invention_name, "一种测试装置")

    def test_empty_internal_no_collapses_filename_separators(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "2025113838195",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
                "NEIBUBH": "",
            }
        )
        options = ProcessOptions(
            summary_root_dir="D:/tmp",
            archive_root_dir="D:/archive",
            filename_template="{申请号}_{内部编号}_{发文日}",
            archive_dir_template="{申请号}/{通知书类别}",
            confirm_each=False,
        )
        rendered = render_output_paths(notice_kind="exam_opinion", meta=meta, options=options)
        self.assertEqual(rendered.output_pdf_name, "2025113838195_2025-11-06.pdf")

    def test_patent_type_empty_when_app_no_invalid(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "PCT/CN2023/078301",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
                "FAMINGLX": "5",
            }
        )
        self.assertEqual(meta.patent_type, "")

    def test_render_output_paths_supports_invention_name_token(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "2025113838195",
                "FAMINGMC": "一种测试装置",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
            }
        )
        options = ProcessOptions(
            summary_root_dir="D:/tmp",
            archive_root_dir="D:/archive",
            filename_template="{申请号}_{发明名称}_{发文日}",
            archive_dir_template="{申请号}",
            confirm_each=False,
        )
        rendered = render_output_paths(notice_kind="exam_opinion", meta=meta, options=options)
        self.assertEqual(rendered.output_pdf_name, "2025113838195_一种测试装置_2025-11-06.pdf")

    def test_build_meta_extracts_applicant_from_flat_fields(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "2025113838195",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
            },
            flat_fields={"SHUXINGXX/SHENQINGRMC": "西安交通大学"},
        )
        self.assertEqual(meta.applicant, "西安交通大学")

    def test_build_meta_ignores_applicant_related_narrative_noise(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "2025113838195",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
            },
            flat_fields={
                "正文/申请人说明": "申请人应当在指定期限内提交意见陈述书。",
                "SHUXINGXX/SHENQINGRMC": "西安交通大学",
            },
        )
        self.assertEqual(meta.applicant, "西安交通大学")

    def test_build_meta_returns_empty_when_only_narrative_noise_exists(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "2025113838195",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
            },
            flat_fields={"正文/申请人说明": "申请人应当在指定期限内提交意见陈述书。"},
        )
        self.assertEqual(meta.applicant, "")

    def test_render_output_paths_supports_applicant_token(self) -> None:
        meta = build_meta_from_list_fields(
            {
                "SHENQINGH": "2025113838195",
                "SHENQINGRMC": "西安交通大学",
                "TONGZHISMC": "第一次审查意见通知书",
                "TONGZHISBM": "210401",
                "FAWENR": "20251106",
            }
        )
        options = ProcessOptions(
            summary_root_dir="D:/tmp",
            archive_root_dir="D:/archive",
            filename_template="{申请号}_{申请人信息}_{发文日}",
            archive_dir_template="{申请号}",
            confirm_each=False,
        )
        rendered = render_output_paths(notice_kind="exam_opinion", meta=meta, options=options)
        self.assertEqual(rendered.output_pdf_name, "2025113838195_西安交通大学_2025-11-06.pdf")


if __name__ == "__main__":
    unittest.main()
