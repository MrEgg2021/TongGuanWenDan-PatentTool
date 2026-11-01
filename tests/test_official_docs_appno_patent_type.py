from __future__ import annotations

import unittest

from core.official_docs.field_governance import (
    extract_patent_type_code_from_app_no,
    infer_patent_type_from_app_no,
)


class OfficialDocsAppNoPatentTypeTests(unittest.TestCase):
    def test_extract_code_from_12_digits(self) -> None:
        self.assertEqual(extract_patent_type_code_from_app_no("2013106888347.5"), "1")
        self.assertEqual(extract_patent_type_code_from_app_no("202221278546X"), "2")
        self.assertEqual(extract_patent_type_code_from_app_no("2021304828765"), "3")
        self.assertEqual(extract_patent_type_code_from_app_no("2020600000012"), "6")
        self.assertEqual(extract_patent_type_code_from_app_no("2020800000012"), "8")
        self.assertEqual(extract_patent_type_code_from_app_no("2020900000012"), "9")

    def test_extract_code_from_8_digits(self) -> None:
        self.assertEqual(extract_patent_type_code_from_app_no("02286689.2"), "2")
        self.assertEqual(extract_patent_type_code_from_app_no("01312345.6"), "3")
        self.assertEqual(extract_patent_type_code_from_app_no("01812345.6"), "8")
        self.assertEqual(extract_patent_type_code_from_app_no("01912345.6"), "9")
        self.assertEqual(extract_patent_type_code_from_app_no("01612345.6"), "6")

    def test_pct_style_and_invalid_return_empty(self) -> None:
        self.assertEqual(extract_patent_type_code_from_app_no("PCT/CN2023/078301"), "")
        self.assertEqual(extract_patent_type_code_from_app_no(""), "")
        self.assertEqual(extract_patent_type_code_from_app_no("ABC"), "")
        self.assertEqual(extract_patent_type_code_from_app_no("1234"), "")

    def test_infer_patent_type_label(self) -> None:
        self.assertEqual(infer_patent_type_from_app_no("2013106888347.5"), ("1", "发明专利"))
        self.assertEqual(infer_patent_type_from_app_no("02286689.2"), ("2", "实用新型专利"))
        self.assertEqual(infer_patent_type_from_app_no("01312345.6"), ("3", "外观专利"))
        self.assertEqual(infer_patent_type_from_app_no("01612345.6"), ("6", "海牙外观"))
        self.assertEqual(infer_patent_type_from_app_no("01812345.6"), ("8", "PCT发明"))
        self.assertEqual(infer_patent_type_from_app_no("01912345.6"), ("9", "PCT实用新型"))
        self.assertEqual(infer_patent_type_from_app_no("PCT/CN2023/078301"), ("", ""))


if __name__ == "__main__":
    unittest.main()
