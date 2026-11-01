from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from core.official_docs.field_governance import build_notice_key
from core.official_docs.field_registry import get_supported_type_catalog
from core.official_docs.models import ProcessOptions
from core.official_docs.pdf_meta_fallback import (
    extract_doc_serial_from_pdf_lines,
    extract_issue_date_from_pdf_lines,
    resolve_pdf_fallback_notice,
)
from core.official_docs.process import parse_official_notice_archive, process_official_notice_archives
from core.official_docs.zip_reader import NoticeZipReader


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = str(text or "")

    def get_text(self, _mode: str) -> str:
        return self._text


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self._pages = [_FakePage(text)]

    @property
    def page_count(self) -> int:
        return len(self._pages)

    def __getitem__(self, index: int) -> _FakePage:
        return self._pages[index]

    def close(self) -> None:
        return None


class OfficialDocsPdfFallbackParseTests(unittest.TestCase):
    def test_extract_doc_serial_from_pdf_lines_supports_same_line_and_next_line(self) -> None:
        self.assertEqual(
            extract_doc_serial_from_pdf_lines(
                [
                    "第一次审查意见通知书",
                    "发文序号：2025120300916070",
                ]
            ),
            "2025120300916070",
        )
        self.assertEqual(
            extract_doc_serial_from_pdf_lines(
                [
                    "第一次补正通知书",
                    "发文编号：",
                    "2025120201953620",
                ]
            ),
            "2025120201953620",
        )

    def test_extract_doc_serial_from_pdf_lines_tolerates_label_side_noise(self) -> None:
        self.assertEqual(
            extract_doc_serial_from_pdf_lines(
                [
                    "第二次审查意见通知书",
                    "发文序号：{2025061702233200",
                ]
            ),
            "2025061702233200",
        )
        self.assertEqual(
            extract_doc_serial_from_pdf_lines(
                [
                    "第二次审查意见通知书",
                    "发文编号：",
                    "[2025082001550670",
                ]
            ),
            "2025082001550670",
        )

    def test_extract_issue_date_from_pdf_lines_tolerates_label_side_noise(self) -> None:
        self.assertEqual(
            extract_issue_date_from_pdf_lines(
                [
                    "第二次审查意见通知书",
                    "发文日：{2025年06月17日",
                ]
            ),
            "2025年06月17日",
        )
        self.assertEqual(
            extract_issue_date_from_pdf_lines(
                [
                    "第二次审查意见通知书",
                    "发文日期：",
                    "[2025-08-20",
                ]
            ),
            "2025-08-20",
        )

    def test_extract_doc_serial_from_pdf_lines_avoids_application_number_false_positive(self) -> None:
        self.assertEqual(
            extract_doc_serial_from_pdf_lines(
                [
                    "第一次审查意见通知书",
                    "申请号：2025113838195",
                    "国家知识产权局",
                ]
            ),
            "",
        )

    def _make_zip(
        self,
        root: Path,
        *,
        name: str,
        pdf_payloads: dict[str, bytes],
        list_xml: bytes | None = None,
    ) -> Path:
        zip_path = root / name
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            if list_xml is not None:
                zf.writestr("list.xml", list_xml)
            for pdf_name, payload in pdf_payloads.items():
                zf.writestr(pdf_name, payload)
        return zip_path

    def _fake_fitz_open(self, text_map: dict[bytes, str]):
        def _open(*, stream=None, filetype=None, **_kwargs):
            _ = filetype
            return _FakeDoc(text_map.get(bytes(stream or b""), ""))

        return _open

    def _build_options(self, root: Path) -> ProcessOptions:
        return ProcessOptions(
            summary_root_dir=str(root / "summary"),
            archive_root_dir=str(root / "archive"),
            write_summary=True,
            write_archive=False,
            confirm_each=False,
        )

    def test_missing_list_xml_uses_pdf_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"main-pdf"
            zip_path = self._make_zip(root, name="missing-list.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "第一次审查意见通知书\n"
                    "申请号: 2025113838195\n"
                    "发文日: 2025-11-06\n"
                    "发文序号: 2025110600247580"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.meta.app_no, "2025113838195")
            self.assertIn("第一次审查意见通知书", parsed.meta.notice_name)
            self.assertEqual(parsed.meta.issue_date, "2025-11-06")
            self.assertEqual(parsed.meta.doc_serial, "2025110600247580")
            self.assertEqual(parsed.pdf_entries[0].kind, "main")
            self.assertEqual(parsed.pdf_entries[0].display_name, "main.pdf")

    def test_pdf_fallback_extracts_invention_name_from_inline_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"inline-title"
            zip_path = self._make_zip(root, name="inline-title.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "收费减缴审批通知书\n"
                    "申请号: 2025113838195\n"
                    "发明创造名称：一种光伏组件转移装置\n"
                    "发文日: 2025-11-06"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.meta.invention_name, "一种光伏组件转移装置")
            self.assertEqual(parsed.flat_fields.get("FAMINGMC"), "一种光伏组件转移装置")

    def test_pdf_fallback_recovers_210326_header_code_and_compound_invention_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"foreign-filing-secrecy"
            zip_path = self._make_zip(root, name="foreign-filing.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "国家知识产权局\n"
                    "210326\n"
                    "回函请寄：100088 北京市海淀区\n"
                    "2022.10\n"
                    "申请号或请求号：202621259502.0\n"
                    "发明名称或实用新型名称：一种散热模组用散热鳍片\n"
                    "向外国申请专利保密审查意见通知书\n"
                    "发文日：2026年08月17日"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.meta.notice_code, "210326")
            self.assertEqual(build_notice_key(parsed.meta), "210326|向外国申请专利保密审查意见通知书")
            self.assertEqual(parsed.meta.invention_name, "一种散热模组用散热鳍片")

    def test_pdf_fallback_prefers_200029_header_code_over_partial_catalog_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"procedure-correction"
            zip_path = self._make_zip(root, name="procedure-correction.zip", pdf_payloads={"main.pdf": payload})
            legacy_catalog = [
                item
                for item in get_supported_type_catalog()
                if str(item.get("key", "") or "") != "200029|办理手续补正通知书"
            ]
            text_map = {
                payload: (
                    "国家知识产权局\n"
                    "200029\n"
                    "办理手续补正通知书\n"
                    "申请号：202611121860.X\n"
                    "发文日：2026年08月17日"
                ),
            }

            with (
                patch(
                    "core.official_docs.pdf_meta_fallback.get_supported_type_catalog",
                    return_value=legacy_catalog,
                ),
                patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)),
            ):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta.notice_code, "200029")
            self.assertEqual(parsed.meta.app_no, "202611121860.X")
            self.assertEqual(build_notice_key(parsed.meta), "200029|办理手续补正通知书")

    def test_pdf_fallback_does_not_promote_body_number_without_header_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"body-number"
            zip_path = self._make_zip(root, name="body-number.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "第一次补正通知书\n"
                    "申请号：202611121860.X\n"
                    "发文日：2026年08月17日\n"
                    "正文说明第一行\n"
                    "正文说明第二行\n"
                    "200029"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertNotEqual(parsed.meta.notice_code, "200029")

    def test_pdf_fallback_does_not_promote_header_number_without_recognized_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"unrecognized-header"
            zip_path = self._make_zip(root, name="unrecognized-header.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "国家知识产权局\n"
                    "518132\n"
                    "申请号：2025113838195\n"
                    "发文日：2025-11-06\n"
                    "正文内容"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.meta.notice_code, "")

    def test_pdf_fallback_extracts_invention_name_from_next_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"next-line-title"
            zip_path = self._make_zip(root, name="next-line-title.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "收费减缴审批通知书\n"
                    "申请号: 2025113838195\n"
                    "发明名称\n"
                    "一种太阳能光伏板的自调节装置\n"
                    "发文日: 2025-11-06"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.meta.invention_name, "一种太阳能光伏板的自调节装置")
            self.assertEqual(parsed.flat_fields.get("SHUXINGXX/FAMINGMC"), "一种太阳能光伏板的自调节装置")

    def test_pdf_fallback_allows_missing_invention_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"no-title"
            zip_path = self._make_zip(root, name="no-title.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "收费减缴审批通知书\n"
                    "申请号: 2025113838195\n"
                    "发文日: 2025-11-06"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.meta.invention_name, "")
            self.assertNotIn("FAMINGMC", parsed.flat_fields)

    def test_pdf_fallback_prefers_labeled_issue_date_on_same_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"same-line-issue-date"
            zip_path = self._make_zip(root, name="same-line-issue-date.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "收费减缴审批通知书\n"
                    "申请号: 2025113838195\n"
                    "发文日: 2025-11-06\n"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta.issue_date_raw, "2025-11-06")
            self.assertEqual(parsed.meta.issue_date, "2025-11-06")

    def test_pdf_fallback_extracts_issue_date_from_next_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"next-line-issue-date"
            zip_path = self._make_zip(root, name="next-line-issue-date.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "收费减缴审批通知书\n"
                    "申请号: 2025113838195\n"
                    "发文日：\n"
                    "2026 年03 月17 日\n"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta.issue_date_raw, "2026 年03 月17 日")
            self.assertEqual(parsed.meta.issue_date, "2026-03-17")

    def test_pdf_fallback_does_not_use_header_year_month_when_labeled_date_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"header-year-month"
            zip_path = self._make_zip(root, name="header-year-month.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "国家知识产权局\n"
                    "2023.03\n"
                    "收费减缴审批通知书\n"
                    "发文日：\n"
                    "2026 年03 月17 日\n"
                    "申请号: 2025113838195\n"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta.issue_date_raw, "2026 年03 月17 日")
            self.assertEqual(parsed.meta.issue_date, "2026-03-17")

    def test_pdf_fallback_does_not_promote_header_year_month_without_labeled_issue_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"header-only-year-month"
            zip_path = self._make_zip(root, name="header-only-year-month.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: (
                    "国家知识产权局\n"
                    "2023.03\n"
                    "收费减缴审批通知书\n"
                    "申请号: 2025113838195\n"
                ),
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta.issue_date_raw, "")
            self.assertEqual(parsed.meta.issue_date, "")

    def test_broken_list_xml_falls_back_to_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"broken-list-main"
            zip_path = self._make_zip(
                root,
                name="broken-list.zip",
                pdf_payloads={"notice.pdf": payload},
                list_xml=b"<broken",
            )
            text_map = {
                payload: "授予发明专利权通知书\n申请号: 2025113838195\n发文日: 2025-11-06",
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.pdf_entries[0].display_name, "notice.pdf")

    def test_multi_pdf_fallback_selects_highest_scored_main_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            weak_payload = b"weak-pdf"
            strong_payload = b"strong-pdf"
            zip_path = self._make_zip(
                root,
                name="multi-pdf-fallback.zip",
                pdf_payloads={
                    "A.pdf": weak_payload,
                    "B.pdf": strong_payload,
                },
            )
            text_map = {
                weak_payload: "申请号: 2025113838195",
                strong_payload: "第一次审查意见通知书\n申请号: 2025113838195\n发文日: 2025-11-06",
            }

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.pdf_entries[0].display_name, "B.pdf")
            self.assertEqual(parsed.pdf_entries[0].kind, "main")

    def test_partial_metadata_without_notice_code_still_names_stably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"partial-meta"
            zip_path = self._make_zip(root, name="partial-meta.zip", pdf_payloads={"main.pdf": payload})
            text_map = {
                payload: "申请号: 2025113838195\n发文日: 2025-11-06\n正文内容",
            }

            with (
                patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)),
                patch("core.official_docs.process.merge_pdf_bytes", return_value=b"%PDF-1.4\npartial\n"),
            ):
                summary = process_official_notice_archives([str(zip_path)], self._build_options(root))

            self.assertEqual(summary.success, 1, f"failed={summary.failed} skipped={summary.skipped}")
            item = summary.items[0]
            self.assertEqual(item.status, "success")
            self.assertEqual(item.meta_source, "pdf_fallback")
            self.assertEqual(item.notice_key, "2025113838195")
            self.assertIn("2025113838195", item.output_pdf_name)

    def test_supported_catalog_labels_are_covered_by_pdf_fallback_matching(self) -> None:
        processable = [item for item in get_supported_type_catalog() if bool(item.get("processable", True))]
        self.assertTrue(processable)

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for index, item in enumerate(processable, start=1):
                display_name = str(item.get("display_name", "") or "").strip()
                if not display_name:
                    continue
                payload = f"pdf-{index}".encode("ascii")
                zip_path = self._make_zip(root, name=f"catalog-{index}.zip", pdf_payloads={"main.pdf": payload})
                text_map = {
                    payload: f"{display_name}\n申请号: 2025113838195\n发文日: 2025-11-06",
                }
                with self.subTest(type_key=str(item.get("key", ""))):
                    with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open(text_map)):
                        with NoticeZipReader(str(zip_path)) as reader:
                            result = resolve_pdf_fallback_notice(reader)
                    self.assertTrue(result.ok, result.error)
                    self.assertEqual(result.main_pdf_raw_name, "main.pdf")
                    self.assertEqual(result.meta.app_no, "2025113838195")
                    self.assertTrue(str(result.meta.notice_name or "").strip())


if __name__ == "__main__":
    unittest.main()
