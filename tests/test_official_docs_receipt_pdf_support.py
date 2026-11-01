from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from core.official_docs.field_registry import get_type_tokens, is_type_processable
from core.official_docs.models import NoticeTypeNamingConfig, ProcessOptions
from core.official_docs.naming_rules import render_notice_output
from core.official_docs.process import parse_official_notice_archive, process_official_notice_archives


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


class OfficialDocsReceiptPdfSupportTests(unittest.TestCase):
    def _make_zip(self, root: Path, pdf_payloads: dict[str, bytes]) -> Path:
        zip_path = root / "receipt.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for pdf_name, payload in pdf_payloads.items():
                zf.writestr(pdf_name, payload)
        return zip_path

    def _fake_fitz_open(self, text_map: dict[bytes, str]):
        def _open(*, stream=None, filetype=None, **_kwargs):
            _ = filetype
            return _FakeDoc(text_map.get(bytes(stream or b""), ""))

        return _open

    def _receipt_text(self, *, app_info: str = "申请号:2026205007486_缴费日期:2026-04-28_缴费方式:网上支付_订单号:202604289031119847") -> str:
        return (
            "中央非税收入统一票据（电子）\n"
            "票据号码：\n"
            "校验码:\n"
            "票据代码:\n"
            "交款人统一社会信用代码:\n"
            "交款人:\n"
            "开票日期:\n"
            "收款单位（章）：\n"
            "收款人：\n"
            "项目编码\n"
            "项目名称\n"
            "单位\n"
            "数量\n"
            "标准\n"
            "金额（元）\n"
            "备注\n"
            "91441300MA4UQG6K9B\n"
            "aab4c4\n"
            "00010125\n"
            "0029412599\n"
            "500.00\n"
            f"{app_info}\n"
            "国家知识产权局专利局\n"
            "惠州惠立勤电子科技有限公司\n"
            "王舒\n"
            "董蕙如\n"
            "0569901030\n"
            "实用新型专利申请费\n"
            "500.00\n"
            "元\n"
            "1\n"
            "500.00\n"
            "伍佰元整\n"
            "2026-04-29\n"
        )

    def _multi_item_receipt_text(self) -> str:
        return (
            "中央非税收入统一票据（电子）\n"
            "票据号码：\n"
            "校验码:\n"
            "票据代码:\n"
            "交款人统一社会信用代码:\n"
            "交款人:\n"
            "开票日期:\n"
            "收款单位（章）：\n"
            "复核人：\n"
            "收款人：\n"
            "项目编码\n"
            "项目名称\n"
            "单位\n"
            "数量\n"
            "标准\n"
            "金额（元）\n"
            "备注\n"
            "金额合计（大写）\n"
            "（小写）\n"
            "其\n"
            "他\n"
            "信\n"
            "息\n"
            "91330108MA2CDQKQ3B\n"
            "715649\n"
            "00010125\n"
            "0003636953\n"
            "380.00\n"
            "申请号:2022106496310_缴费日期:2025-05-15_缴费方式:网上支付_订单号:202505159031113840\n"
            "国家知识产权局专利局\n"
            "杭州黑白调科技有限公司\n"
            "王舒\n"
            "董蕙如\n"
            "0569901090\n"
            "著录事项变更费\n"
            "200.00\n"
            "元\n"
            "1\n"
            "200.00\n"
            "056990124040 发明专利第4年年费\n"
            "180.00\n"
            "元\n"
            "0.15\n"
            "1,200.00\n"
            "叁佰捌拾元整\n"
            "2025-05-16\n"
        )

    def test_receipt_pdf_without_list_xml_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"receipt-pdf"
            zip_path = self._make_zip(root, {"receipt.pdf": payload})

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open({payload: self._receipt_text()})):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta_source, "pdf_fallback")
            self.assertEqual(parsed.meta.notice_code, "10071")
            self.assertEqual(parsed.meta.notice_name, "电子提交收据")
            self.assertEqual(parsed.meta.app_no, "2026205007486")
            self.assertEqual(parsed.meta.applicant, "惠州惠立勤电子科技有限公司")
            self.assertEqual(parsed.flat_fields["收据_缴费项目"], "实用新型专利申请费")
            self.assertEqual(parsed.flat_fields["收据_缴费金额"], "500.00")
            self.assertEqual(parsed.flat_fields["收据_票据代码"], "00010125")
            self.assertEqual(parsed.flat_fields["收据_票据号码"], "0029412599")

    def test_multi_item_receipt_extracts_item_summary_detail_and_ticket_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"multi-item-receipt-pdf"
            zip_path = self._make_zip(root, {"receipt.pdf": payload})

            with patch(
                "core.official_docs.pdf_meta_fallback.fitz.open",
                side_effect=self._fake_fitz_open({payload: self._multi_item_receipt_text()}),
            ):
                parsed = parse_official_notice_archive(str(zip_path))

            self.assertTrue(parsed.ok, parsed.errors)
            self.assertEqual(parsed.meta.receipt_fee_item, "著录事项变更费")
            self.assertEqual(parsed.flat_fields["收据_缴费项目"], "著录事项变更费")
            self.assertEqual(parsed.flat_fields["收据_缴费项目首项"], "著录事项变更费")
            self.assertEqual(parsed.flat_fields["收据_缴费项目汇总"], "著录事项变更费+发明专利第4年年费")
            self.assertEqual(parsed.flat_fields["收据_缴费项目明细"], "著录事项变更费200.00元+发明专利第4年年费180.00元")
            self.assertEqual(parsed.flat_fields["收据_交款人统一社会信用代码"], "91330108MA2CDQKQ3B")
            self.assertEqual(parsed.flat_fields["收据_校验码"], "715649")
            self.assertEqual(parsed.flat_fields["收据_收款单位"], "国家知识产权局专利局")
            self.assertEqual(parsed.flat_fields["收据_复核人"], "王舒")
            self.assertEqual(parsed.flat_fields["收据_收款人"], "董蕙如")

    def test_receipt_default_filename_uses_plus_and_yuan_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"receipt-pdf"
            zip_path = self._make_zip(root, {"receipt.pdf": payload})
            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
            )

            with patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open({payload: self._receipt_text()})):
                parsed = parse_official_notice_archive(str(zip_path))

            rendered = render_notice_output(meta=parsed.meta, notice_kind=parsed.notice_kind, options=options)
            self.assertEqual(
                rendered.output_pdf_name,
                "收据+惠州惠立勤电子科技有限公司+2026205007486+实用新型专利+实用新型专利申请费+500.00元.pdf",
            )

    def test_multi_item_receipt_default_filename_uses_all_item_names_and_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"multi-item-receipt-pdf"
            zip_path = self._make_zip(root, {"receipt.pdf": payload})
            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
            )

            with patch(
                "core.official_docs.pdf_meta_fallback.fitz.open",
                side_effect=self._fake_fitz_open({payload: self._multi_item_receipt_text()}),
            ):
                parsed = parse_official_notice_archive(str(zip_path))

            rendered = render_notice_output(meta=parsed.meta, notice_kind=parsed.notice_kind, options=options)

            self.assertEqual(
                rendered.output_pdf_name,
                "收据+杭州黑白调科技有限公司+2022106496310+发明专利+著录事项变更费+发明专利第4年年费+380.00元.pdf",
            )

    def test_multi_application_receipt_stays_one_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"receipt-pdf"
            zip_path = self._make_zip(root, {"receipt.pdf": payload})
            app_info = (
                "申请号:2026205007486、2026204842026_"
                "缴费日期:2026-04-28_缴费方式:网上支付_订单号:202604289031119847"
            )
            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
            )

            with (
                patch("core.official_docs.pdf_meta_fallback.fitz.open", side_effect=self._fake_fitz_open({payload: self._receipt_text(app_info=app_info)})),
                patch("core.official_docs.process.merge_pdf_bytes", return_value=b"%PDF-1.4\nreceipt\n"),
            ):
                summary = process_official_notice_archives([str(zip_path)], options)

            self.assertEqual(summary.success, 1)
            self.assertEqual(len(summary.items), 1)
            item = summary.items[0]
            self.assertIn("2026205007486+2026204842026", item.output_pdf_name)
            self.assertEqual(item.business_fields["收据_申请号"], "2026205007486+2026204842026")

    def test_receipt_type_is_processable_but_application_receipt_is_not(self) -> None:
        self.assertTrue(is_type_processable("10071|电子提交收据"))
        self.assertFalse(is_type_processable("200105|电子申请回执"))
        tokens = get_type_tokens("10071|电子提交收据")
        self.assertIn("收据_缴费人", tokens)
        self.assertIn("收据_缴费项目首项", tokens)
        self.assertIn("收据_缴费项目汇总", tokens)
        self.assertIn("收据_缴费项目明细", tokens)
        self.assertIn("收据_缴费金额元", tokens)
        self.assertNotIn("收据_缴费项目", tokens)

    def test_receipt_custom_naming_uses_summary_and_keeps_legacy_fee_item_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"multi-item-receipt-pdf"
            zip_path = self._make_zip(root, {"receipt.pdf": payload})
            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
                type_naming_configs={
                    "10071|电子提交收据": NoticeTypeNamingConfig(
                        naming_mode="custom",
                        filename_fields=["收据", "收据_缴费项目汇总"],
                    )
                },
            )
            legacy_options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
                type_naming_configs={
                    "10071|电子提交收据": NoticeTypeNamingConfig(
                        naming_mode="custom",
                        filename_fields=["收据", "收据_缴费项目"],
                    )
                },
            )

            with patch(
                "core.official_docs.pdf_meta_fallback.fitz.open",
                side_effect=self._fake_fitz_open({payload: self._multi_item_receipt_text()}),
            ):
                parsed = parse_official_notice_archive(str(zip_path))

            rendered = render_notice_output(meta=parsed.meta, notice_kind=parsed.notice_kind, options=options)
            legacy_rendered = render_notice_output(meta=parsed.meta, notice_kind=parsed.notice_kind, options=legacy_options)

            self.assertEqual(rendered.output_pdf_name, "收据+著录事项变更费+发明专利第4年年费.pdf")
            self.assertEqual(legacy_rendered.output_pdf_name, "收据+著录事项变更费.pdf")

    def test_receipt_custom_naming_compacts_dates_without_changing_parsed_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = b"multi-item-receipt-pdf"
            zip_path = self._make_zip(root, {"receipt.pdf": payload})
            options = ProcessOptions(
                summary_root_dir=str(root / "summary"),
                archive_root_dir=str(root / "archive"),
                write_summary=True,
                write_archive=False,
                confirm_each=False,
                type_naming_configs={
                    "10071|电子提交收据": NoticeTypeNamingConfig(
                        naming_mode="custom",
                        filename_fields=["收据_缴费日期", "收据_开票日期"],
                    )
                },
            )

            with patch(
                "core.official_docs.pdf_meta_fallback.fitz.open",
                side_effect=self._fake_fitz_open({payload: self._multi_item_receipt_text()}),
            ):
                parsed = parse_official_notice_archive(str(zip_path))

            rendered = render_notice_output(meta=parsed.meta, notice_kind=parsed.notice_kind, options=options)

            self.assertEqual(rendered.output_pdf_name, "20250515+20250516.pdf")
            self.assertEqual(parsed.meta.receipt_payment_date, "2025-05-15")
            self.assertEqual(parsed.meta.receipt_invoice_date, "2025-05-16")
            self.assertEqual(parsed.flat_fields["收据_缴费日期"], "2025-05-15")
            self.assertEqual(parsed.flat_fields["收据_开票日期"], "2025-05-16")


if __name__ == "__main__":
    unittest.main()
