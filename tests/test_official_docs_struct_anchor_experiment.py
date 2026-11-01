from __future__ import annotations

import csv
import os
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook
from openpyxl.styles import Font

from tools import official_docs_struct_anchor_experiment as exp


class _FakeRect:
    def __init__(self, width: float) -> None:
        self.width = float(width)


class _FakePage:
    def __init__(self, lines: list[str], *, width: float = 1000.0) -> None:
        self.rect = _FakeRect(width)
        self._words = self._build_words(lines)
        self._rawdict = self._build_rawdict(lines)

    @staticmethod
    def _build_words(lines: list[str]) -> list[tuple[float, float, float, float, str, int, int, int]]:
        words: list[tuple[float, float, float, float, str, int, int, int]] = []
        for row, text in enumerate(lines):
            src = str(text or "").strip()
            if not src:
                continue
            x0 = 30.0
            y0 = 50.0 + row * 22.0
            x1 = x0 + max(10.0, float(len(src) * 12))
            y1 = y0 + 14.0
            words.append((x0, y0, x1, y1, src, 0, row, 0))
        return words

    @staticmethod
    def _build_rawdict(lines: list[str]) -> dict:
        raw_lines: list[dict] = []
        for row, text in enumerate(lines):
            src = str(text or "").strip()
            if not src:
                continue
            y0 = 50.0 + row * 22.0
            raw_lines.append(
                {
                    "bbox": [30.0, y0, 30.0 + max(10.0, float(len(src) * 12)), y0 + 14.0],
                    "spans": [{"text": src}],
                }
            )
        return {"blocks": [{"type": 0, "lines": raw_lines}]}

    def get_text(self, mode: str):
        if mode == "words":
            return self._words
        if mode == "rawdict":
            return self._rawdict
        raise ValueError(mode)


class _FakeDoc:
    def __init__(self, pages: list[_FakePage]) -> None:
        self._pages = list(pages)
        self.page_count = len(self._pages)

    def __getitem__(self, index: int) -> _FakePage:
        return self._pages[index]

    def close(self) -> None:
        return None


class OfficialDocsStructAnchorExperimentTests(unittest.TestCase):
    def _extract_results(self, lines: list[str]):
        doc = _FakeDoc([_FakePage(lines)])
        results, _stats = exp._extract_from_doc(doc, exp.DEFAULT_FIELDS)
        return results

    def _extract_values(self, lines: list[str]) -> dict[str, str]:
        results = self._extract_results(lines)
        return {key: str(value.value or "") for key, value in results.items()}

    def test_extract_applicant_same_line(self) -> None:
        values = self._extract_values(["申请人：张三", "发明人：李四"])
        self.assertEqual(values["applicant"], "张三")

    def test_extract_applicant_next_line(self) -> None:
        values = self._extract_values(["申请人：", "张三", "发明人：李四"])
        self.assertEqual(values["applicant"], "张三")

    def test_extract_applicant_stops_on_next_label(self) -> None:
        values = self._extract_values(["申请人：张三", "地址：北京市"])
        self.assertEqual(values["applicant"], "张三")

    def test_extract_applicant_stops_on_invent_name_label(self) -> None:
        values = self._extract_values(["申请人：宁波诺丁汉新材料研究院有限公司", "发明名称：一种竖式微波热解沼渣制备合成气的系统和方法"])
        self.assertEqual(values["applicant"], "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_stops_on_title_line(self) -> None:
        values = self._extract_values(["申请人：西安交通大学", "复审通知书", "发明人：张三"])
        self.assertEqual(values["applicant"], "西安交通大学")

    def test_extract_applicant_stops_on_numbered_item(self) -> None:
        values = self._extract_values(["申请人：宁波诺丁汉新材料研究院有限公司", "1. 本意见包括关于下列各项标明的内容："])
        self.assertEqual(values["applicant"], "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_filters_checkbox_noise(self) -> None:
        values = self._extract_values(["申请人：✓ 全部规定费用已经缴纳", "发明人：李四"])
        self.assertEqual(values["applicant"], "")

    def test_extract_applicant_filters_archive_header_pollution(self) -> None:
        values = self._extract_values(
            [
                "或代理人的档案号 BJ-QSPCT-23022501",
                "申请人：宁波诺丁汉新材料研究院有限公司",
                "国际申请号 PCT/CN2023/078301",
            ]
        )
        self.assertEqual(values["applicant"], "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_stops_long_body_line(self) -> None:
        values = self._extract_values(
            [
                "申请人：西安交通大学 北京微纳精密机械有限公司",
                "根据专利法实施细则第50条的规定，审查员对上述申请进行了初步审查。",
            ]
        )
        self.assertEqual(values["applicant"], "西安交通大学北京微纳精密机械有限公司")

    def test_extract_applicant_preserves_multi_entities_semicolon(self) -> None:
        values = self._extract_values(["申请人：北京宝隆泓瑞科技有限公司；重庆泓宝科技股份有限公司"])
        self.assertEqual(values["applicant"], "北京宝隆泓瑞科技有限公司；重庆泓宝科技股份有限公司")

    def test_extract_applicant_handles_review_title_chars(self) -> None:
        values = self._extract_values(
            [
                "复审请求人：",
                "陕西师范大学",
                "复",
                "审",
                "通",
                "知",
                "书",
                "复审请求人：",
                "国家知识产权局对上述专利申请的复审请求已经开始审理。",
            ]
        )
        self.assertEqual(values["applicant"], "陕西师范大学")

    def test_extract_applicant_fallback_from_review_body_pattern(self) -> None:
        values = self._extract_values(
            [
                "国家知识产权局实质审查部门以本发明专利申请（下称本申请）不符合专利法相关规定。",
                "应申请人陕西师范大学（下称复审请求人）于2021年8月23日提出的复审请求，国家知识产权局成立合议组进行审理。",
            ]
        )
        self.assertEqual(values["applicant"], "陕西师范大学")

    def test_extract_applicant_reads_right_value_before_label_same_row(self) -> None:
        lines = [
            exp.VisualLine(
                page=0,
                x0=131.2,
                y0=330.50,
                x1=400.0,
                y1=344.0,
                text="西安交通大学北京微纳精密机械有限公司",
                line_id="0-0",
            ),
            exp.VisualLine(
                page=0,
                x0=59.2,
                y0=330.58,
                x1=120.0,
                y1=344.0,
                text="复审请求人：",
                line_id="0-1",
            ),
            exp.VisualLine(page=0, x0=212.0, y0=372.7, x1=230.0, y1=386.0, text="复", line_id="0-2"),
            exp.VisualLine(page=0, x0=251.0, y0=372.7, x1=269.0, y1=386.0, text="审", line_id="0-3"),
            exp.VisualLine(page=0, x0=290.0, y0=372.7, x1=308.0, y1=386.0, text="通", line_id="0-4"),
            exp.VisualLine(page=0, x0=329.0, y0=372.7, x1=347.0, y1=386.0, text="知", line_id="0-5"),
            exp.VisualLine(page=0, x0=368.0, y0=372.7, x1=386.0, y1=386.0, text="书", line_id="0-6"),
            exp.VisualLine(
                page=0,
                x0=53.8,
                y0=400.0,
                x1=120.0,
                y1=414.0,
                text="复审请求人：",
                line_id="0-7",
            ),
            exp.VisualLine(
                page=0,
                x0=74.8,
                y0=418.0,
                x1=580.0,
                y1=432.0,
                text="国家知识产权局对上述专利申请的复审请求已经开始审理。",
                line_id="0-8",
            ),
        ]
        result = exp._extract_field(lines, {0: 595.0}, exp.FIELD_CONFIGS["applicant"])
        self.assertEqual(result.value, "西安交通大学北京微纳精密机械有限公司")

    def test_extract_applicant_auto_category_clean(self) -> None:
        results = self._extract_results(["申请人：张三", "发明人：李四"])
        self.assertEqual(results["applicant"].evidence.auto_category, "clean_candidate")

    def test_extract_agency_multiline(self) -> None:
        values = self._extract_values(["专利代理机构：北京前审知识产", "权代理有限公司", "代理人：王五"])
        self.assertEqual(values["agency_raw"], "北京前审知识产权代理有限公司")

    def test_extract_examiner_filters_body_sentence(self) -> None:
        values = self._extract_values(["审查员：认为本申请不符合规定", "审查员电话：010-12345678"])
        self.assertEqual(values["examiner"], "")

    def test_extract_examiner_phone_from_nearby_line(self) -> None:
        values = self._extract_values(["审查员：张三", "联系电话：010-12345678"])
        self.assertEqual(values["examiner"], "张三")
        self.assertEqual(values["examiner_phone"], "010-12345678")

    def test_eval_strike_mapping_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx_path = os.path.join(tmp_dir, "strike.xlsx")
            workbook = Workbook()
            sheet = workbook.active
            headers = [
                "源ZIP",
                "输出PDF名称",
                "汇总PDF路径",
                "归档PDF路径",
                "申请人信息",
                "代理机构信息",
                "审查员姓名",
                "审查员电话",
            ]
            sheet.append(headers)
            sheet.append(["A.zip", "A.pdf", "", "", "错误值", "", "", ""])
            strike_col = headers.index("申请人信息") + 1
            sheet.cell(2, strike_col).font = Font(strike=True)
            workbook.save(xlsx_path)
            workbook.close()

            fake_records = [
                {
                    "pdf_path": os.path.join(tmp_dir, "A.pdf"),
                    "pdf_name": "A.pdf",
                    "values": {
                        "applicant": "正确值",
                        "agency_raw": "",
                        "examiner": "",
                        "examiner_phone": "",
                    },
                    "evidence": {"applicant": {"auto_category": "clean_candidate"}},
                    "rawdict_line_count": 1,
                    "word_line_count": 1,
                }
            ]
            fake_summary = {
                "pdf_root": tmp_dir,
                "total_pdfs": 1,
                "success_pdfs": 1,
                "failed_pdfs": 0,
                "errors": [],
                "fields": list(exp.DEFAULT_FIELDS),
            }

            with patch(
                "tools.official_docs_struct_anchor_experiment.extract_pdf_directory",
                return_value=(fake_records, fake_summary),
            ):
                result = exp.run_eval_strike(tmp_dir, xlsx_path, tmp_dir)

            self.assertEqual(int(result["strike_total"]), 1)
            self.assertEqual(int(result["mapped_total"]), 1)
            self.assertEqual(int(result["changed_candidate_fixed_total"]), 1)
            self.assertTrue(os.path.exists(str(result["strike_eval_csv"])))
            self.assertTrue(os.path.exists(str(result["strike_eval_summary_json"])))
            self.assertTrue(os.path.exists(str(result["unmapped_rows_csv"])))
            self.assertTrue(os.path.exists(str(result["applicant_round2_review_csv"])))

    def test_eval_strike_generates_applicant_round2_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx_path = os.path.join(tmp_dir, "strike.xlsx")
            workbook = Workbook()
            sheet = workbook.active
            headers = [
                "源ZIP",
                "输出PDF名称",
                "汇总PDF路径",
                "归档PDF路径",
                "申请人信息",
                "代理机构信息",
                "审查员姓名",
                "审查员电话",
            ]
            sheet.append(headers)
            sheet.append(["A.zip", "A.pdf", "", "", "错误A", "", "", ""])
            sheet.append(["B.zip", "B.pdf", "", "", "错误B", "", "", ""])
            applicant_col = headers.index("申请人信息") + 1
            sheet.cell(2, applicant_col).font = Font(strike=True)
            sheet.cell(3, applicant_col).font = Font(strike=True)
            workbook.save(xlsx_path)
            workbook.close()

            fake_records = [
                {
                    "pdf_path": os.path.join(tmp_dir, "A.pdf"),
                    "pdf_name": "A.pdf",
                    "values": {"applicant": "正确A", "agency_raw": "", "examiner": "", "examiner_phone": ""},
                    "evidence": {"applicant": {"auto_category": "clean_candidate"}},
                    "rawdict_line_count": 1,
                    "word_line_count": 1,
                },
                {
                    "pdf_path": os.path.join(tmp_dir, "B.pdf"),
                    "pdf_name": "B.pdf",
                    "values": {"applicant": "正确B", "agency_raw": "", "examiner": "", "examiner_phone": ""},
                    "evidence": {"applicant": {"auto_category": "suspect_title_pollution"}},
                    "rawdict_line_count": 1,
                    "word_line_count": 1,
                },
            ]
            fake_summary = {
                "pdf_root": tmp_dir,
                "total_pdfs": 2,
                "success_pdfs": 2,
                "failed_pdfs": 0,
                "errors": [],
                "fields": list(exp.DEFAULT_FIELDS),
            }
            with patch("tools.official_docs_struct_anchor_experiment.extract_pdf_directory", return_value=(fake_records, fake_summary)):
                result = exp.run_eval_strike(tmp_dir, xlsx_path, tmp_dir)

            review_csv = str(result["applicant_round2_review_csv"])
            self.assertTrue(os.path.exists(review_csv))
            with open(review_csv, "r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))
            self.assertEqual(len(rows), 2)
            self.assertEqual(int(result["applicant_clean_total"]), 1)
            self.assertEqual(int(result["applicant_suspect_total"]), 1)


if __name__ == "__main__":
    unittest.main()
