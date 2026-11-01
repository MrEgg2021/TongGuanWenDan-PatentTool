from __future__ import annotations

import unittest
from unittest.mock import patch

from core.official_docs.exam_pdf_extract import extract_exam_pdf_fields


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = str(text or "")

    def get_text(self, mode: str) -> str:
        _ = mode
        return self._text


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self.page_count = 1
        self._page = _FakePage(text)

    def __getitem__(self, index: int) -> _FakePage:
        _ = index
        return self._page

    def close(self) -> None:
        return None


class OfficialDocsExamPdfExtractTests(unittest.TestCase):
    def test_extract_fields_filters_placeholder_and_keeps_order(self) -> None:
        sample_text = "\n".join(
            [
                "权利要求____不符合专利法第二十二条第三款的规定。",
                "权利要求1-3不符合专利法第二十二条第三款的规定。",
                "该申请不具备创造性，不能授予专利权，被驳回。",
                "对比文件：CN1234567A；CN1234567A；CN7654321B。",
                "审 查 员: 张三",
                "本案审查员电话: 010-12345678",
            ]
        )
        with patch("core.official_docs.exam_pdf_extract.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_exam_pdf_fields(b"pdf")

        self.assertEqual(result.status, "成功")
        self.assertNotIn("权利要求____", result.reject_reasons)
        self.assertIn("权利要求1-3不符合专利法第二十二条第三款的规定。", result.reject_reasons)
        self.assertIn("专利法第二十二条第三款", result.clauses)
        pubnos = str(result.cn_pubnos or "").replace("；", ";")
        self.assertEqual(pubnos, "CN1234567A;CN7654321B")
        self.assertEqual(result.examiner_name, "张三")
        self.assertEqual(result.examiner_phone, "010-12345678")

    def test_open_pdf_failure_returns_failed_status(self) -> None:
        with patch("core.official_docs.exam_pdf_extract.fitz.open", side_effect=RuntimeError("boom")):
            result = extract_exam_pdf_fields(b"pdf")
        self.assertEqual(result.status, "失败")
        self.assertIn("boom", result.error)


if __name__ == "__main__":
    unittest.main()
