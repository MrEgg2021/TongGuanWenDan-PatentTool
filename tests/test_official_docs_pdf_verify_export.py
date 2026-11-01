from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import openpyxl
from openpyxl.styles import Font

from core.official_docs.models import NoticeMeta, ProcessItemResult, ProcessSummary
from tools.official_docs_pdf_verify_export import (
    MANUAL_INSERT_AFTER_BY_FIELD,
    MANUAL_TRUTH_HEADERS,
    MANUAL_TRUTH_PREFIX,
    STRIKE_BASELINE_HEADERS,
    STRIKE_REMAIN_HEADERS,
    UI_FIELDS,
    UI_FIELD_LABELS,
    WIDE_HEADERS,
    compare_manual_csv,
    compare_strike_baseline,
    export_strike_baseline,
    generate_wide_report,
)


def _build_item(
    *,
    source_zip_path: str,
    status: str = "success",
    authorization_pub_date: str = "2025-01-01",
    reason: str = "",
) -> ProcessItemResult:
    return ProcessItemResult(
        source_zip_path=source_zip_path,
        status=status,
        notice_kind="unknown",
        notice_key="400001|发明专利证书",
        meta=NoticeMeta(
            notice_code="400001",
            notice_name="发明专利证书",
        ),
        reason=reason,
        output_pdf_name="a.pdf",
        summary_pdf_path="D:/summary/a.pdf",
        archive_pdf_path="D:/archive/a.pdf",
        merged_sources=["main.pdf"],
        pdf_parse_status="成功" if status == "success" else "",
        pdf_parse_error="",
        pdf_applicant="测试申请人",
        pdf_inventor="张三,李四",
        pdf_agency_raw="测试代理有限公司",
        pdf_department="专利审查协作湖北中心",
        pdf_center="专利审查协作湖北中心",
        pdf_examiner_name="王五",
        pdf_examiner_phone="01012345678",
        pdf_panel_head="组长A",
        pdf_panel_main="主审B",
        pdf_panel_member="参审C",
        pdf_reject_reason="不具备创造性",
        pdf_cn_pubnos="CN1234567A;CN7654321B",
        pdf_dossier_no="AJ-001",
        pdf_authorization_pub_no="CN1234567B",
        pdf_authorization_pub_date=authorization_pub_date,
        pdf_certificate_no="9636678",
        pdf_qrcode_link="https://example.com/cert/9636678",
        pdf_qrcode_image_bytes=b"PNGDATA",
        business_fields={
            "申请号": "2025113838195",
            "通知书名称": "第一次审查意见通知书",
            "发明名称": "一种测试装置",
            "通知书代码": "210401",
            "发文日": "2025-11-06",
            "专利类型": "发明专利",
            "期限天": "30",
            "逾期日": "2025-12-06",
            "内部编号": "NB-01",
            "发文序号": "FW-01",
            "案卷号": "AJ-01",
            "申请日": "2025-10-01",
        },
        uncertain_fields={
            "DMHFLAG_raw": "1",
            "FAMINGLX_raw": "0",
            "附件YEWULX_raw_set": "A1;A2",
        },
        pdf_evidence={
            "evidence_applicant": "申请人:测试申请人",
            "evidence_inventor": "发明人:张三,李四",
            "evidence_agency_raw": "代理机构:测试代理有限公司",
            "evidence_department": "审查部门:专利审查协作湖北中心",
            "evidence_center": "审查部门:专利审查协作湖北中心",
            "evidence_examiner": "审查员:王五",
            "evidence_examiner_phone": "审查员电话:01012345678",
            "evidence_panel_head": "合议组组长:组长A",
            "evidence_panel_main": "主审员:主审B",
            "evidence_panel_member": "参审员:参审C",
            "evidence_prior_art": "对比文件:CN1234567A;CN7654321B",
            "evidence_dossier_no": "申请方案卷号:AJ-001",
            "evidence_authorization_pub_no": "授权公告号:CN1234567B",
            "evidence_authorization_pub_date": f"授权公告日:{authorization_pub_date}",
            "evidence_certificate_no": "证书号:9636678",
            "evidence_qrcode_link": "二维码链接:https://example.com/cert/9636678",
        },
    )


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: str(row.get(header, "") or "") for header in headers})


def _write_csv_with_encoding(path: Path, headers: list[str], rows: list[dict[str, str]], encoding: str) -> None:
    with path.open("w", encoding=encoding, newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: str(row.get(header, "") or "") for header in headers})


class OfficialDocsPdfVerifyExportTests(unittest.TestCase):
    def _make_dummy_zip(self, root: Path, file_name: str) -> Path:
        zip_path = root / file_name
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dummy.txt", b"ok")
        return zip_path

    def _write_xlsx(
        self,
        path: Path,
        *,
        headers: list[str],
        rows: list[dict[str, str]],
        strike_cells: list[tuple[int, str]],
    ) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "官文处理"
        for col, header in enumerate(headers, start=1):
            ws.cell(1, col, header)
        for row_idx, row in enumerate(rows, start=2):
            for col, header in enumerate(headers, start=1):
                ws.cell(row_idx, col, str(row.get(header, "") or ""))
        header_to_col = {header: idx for idx, header in enumerate(headers, start=1)}
        for row_idx, header in strike_cells:
            col_idx = header_to_col[header]
            cell = ws.cell(row_idx, col_idx)
            cell.font = Font(strike=True)
        wb.save(path)

    def test_generate_wide_csv_matches_gui_headers_and_manual_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_root = root / "input"
            output_root = root / "output"
            input_root.mkdir(parents=True, exist_ok=True)
            output_root.mkdir(parents=True, exist_ok=True)
            zip_a = self._make_dummy_zip(input_root, "a.zip")
            zip_b = self._make_dummy_zip(input_root, "b.zip")
            item_a = _build_item(source_zip_path=str(zip_a.resolve()), status="success")
            item_b = _build_item(source_zip_path=str(zip_b.resolve()), status="fail", reason="解析失败")
            summary = ProcessSummary(
                summary_run_dir="",
                excel_path="",
                total=2,
                success=1,
                skipped=0,
                failed=1,
                items=[item_a, item_b],
            )

            with patch("tools.official_docs_pdf_verify_export.process_official_notice_archives", return_value=summary):
                result = generate_wide_report(str(input_root), str(output_root))

            wide_csv = Path(result["wide_csv"])
            self.assertTrue(wide_csv.exists())

            with wide_csv.open("r", encoding="utf-8-sig", newline="") as file_obj:
                reader = csv.DictReader(file_obj)
                headers = list(reader.fieldnames or [])
                rows = [{key: str(value or "") for key, value in row.items()} for row in reader]

            self.assertEqual(headers, list(WIDE_HEADERS))
            for field in UI_FIELDS:
                source_col = MANUAL_INSERT_AFTER_BY_FIELD[field]
                manual_col = f"{MANUAL_TRUTH_PREFIX}{UI_FIELD_LABELS[field]}"
                self.assertEqual(headers.index(manual_col), headers.index(source_col) + 1)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].get("公告二维码图片"), "有")
            self.assertEqual(rows[1].get("状态"), "失败")
            self.assertEqual(rows[1].get("错误信息"), "解析失败")
            self.assertTrue(all(str(rows[0].get(col, "")).strip() == "" for col in MANUAL_TRUTH_HEADERS))

    def test_compare_manual_empty_truth_becomes_implicit_accept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_csv = root / "manual.csv"
            output_dir = root / "compare_output"
            headers = list(WIDE_HEADERS)
            row = {header: "" for header in headers}
            row["源ZIP"] = "D:/zip/a.zip"
            row["通知书键"] = "400001|发明专利证书"
            row["申请人信息"] = "测试申请人"
            _write_csv(manual_csv, headers, [row])

            result = compare_manual_csv(str(manual_csv), str(output_dir))

            metrics = json.loads(Path(result["field_metrics_json"]).read_text(encoding="utf-8"))
            applicant_metrics = metrics.get(UI_FIELD_LABELS["applicant"], {})
            self.assertEqual(int(applicant_metrics.get("implicit_accept", -1)), 1)
            self.assertEqual(int(applicant_metrics.get("checked_total", -1)), 1)
            self.assertEqual(int(applicant_metrics.get("explicit_match", -1)), 0)
            self.assertEqual(int(result["explicit_checked"]), 0)
            self.assertEqual(int(result["implicit_accept"]), len(UI_FIELDS))
            self.assertEqual(int(result["total_mismatch"]), 0)

    def test_compare_manual_detects_mismatch_and_outputs_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_csv = root / "manual.csv"
            output_dir = root / "compare_output"
            headers = list(WIDE_HEADERS)
            row = {header: "" for header in headers}
            row["源ZIP"] = "D:/zip/a.zip"
            row["通知书键"] = "400001|发明专利证书"
            row["授权公告日"] = "2025-01-01"
            row["人工确认_授权公告日"] = "2025-01-02"
            _write_csv(manual_csv, headers, [row])

            result = compare_manual_csv(str(manual_csv), str(output_dir))

            diff_rows: list[dict[str, str]] = []
            with open(result["diff_csv"], "r", encoding="utf-8-sig", newline="") as file_obj:
                reader = csv.DictReader(file_obj)
                for diff_row in reader:
                    diff_rows.append({key: str(value or "") for key, value in diff_row.items()})

            self.assertEqual(len(diff_rows), 1)
            self.assertEqual(diff_rows[0].get("字段名称"), "授权公告日")
            self.assertEqual(diff_rows[0].get("通知书代码"), "400001")
            self.assertIn("不一致", str(diff_rows[0].get("差异原因", "")))
            self.assertEqual(diff_rows[0].get("确认来源"), "explicit_truth")
            self.assertEqual(int(result["explicit_checked"]), 1)
            self.assertEqual(int(result["explicit_mismatch"]), 1)
            self.assertEqual(int(result["total_mismatch"]), 1)

    def test_compare_manual_matches_examiner_and_panel_aggregated_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_csv = root / "manual.csv"
            output_dir = root / "compare_output"
            headers = list(WIDE_HEADERS)
            row = {header: "" for header in headers}
            row["源ZIP"] = "D:/zip/a.zip"
            row["通知书键"] = "400001|发明专利证书"
            row["审查员姓名"] = "王五"
            row["审查员电话"] = "01012345678"
            row["合议组组长"] = "组长A"
            row["主审员"] = "主审B"
            row["参审员"] = "参审C"
            row["公告二维码图片"] = "有"
            row["人工确认_审查员信息"] = "王五|01012345678"
            row["人工确认_合议组信息"] = "组长A|主审B|参审C"
            row["人工确认_公告二维码图片"] = "有"
            _write_csv(manual_csv, headers, [row])

            result = compare_manual_csv(str(manual_csv), str(output_dir))
            metrics = json.loads(Path(result["field_metrics_json"]).read_text(encoding="utf-8"))

            examiner = metrics.get("审查员信息", {})
            panel = metrics.get("合议组信息", {})
            qrcode_image = metrics.get("公告二维码图片", {})

            self.assertEqual(int(examiner.get("explicit_match", -1)), 1)
            self.assertEqual(int(examiner.get("explicit_mismatch", -1)), 0)
            self.assertEqual(int(panel.get("explicit_match", -1)), 1)
            self.assertEqual(int(panel.get("explicit_mismatch", -1)), 0)
            self.assertEqual(int(qrcode_image.get("explicit_match", -1)), 1)
            self.assertEqual(int(result["total_mismatch"]), 0)

    def test_compare_manual_examiner_name_only_truth_can_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_csv = root / "manual.csv"
            output_dir = root / "compare_output"
            headers = list(WIDE_HEADERS)
            row = {header: "" for header in headers}
            row["源ZIP"] = "D:/zip/a.zip"
            row["通知书键"] = "400001|发明专利证书"
            row["审查员姓名"] = "段立彦"
            row["人工确认_审查员信息"] = "审查员：段立彦"
            _write_csv(manual_csv, headers, [row])

            result = compare_manual_csv(str(manual_csv), str(output_dir))
            metrics = json.loads(Path(result["field_metrics_json"]).read_text(encoding="utf-8"))
            examiner = metrics.get("审查员信息", {})

            self.assertEqual(int(examiner.get("explicit_match", -1)), 1)
            self.assertEqual(int(examiner.get("explicit_mismatch", -1)), 0)
            self.assertEqual(int(result["total_mismatch"]), 0)

    def test_compare_manual_counts_explicit_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_csv = root / "manual.csv"
            output_dir = root / "compare_output"
            headers = list(WIDE_HEADERS)
            row = {header: "" for header in headers}
            row["源ZIP"] = "D:/zip/a.zip"
            row["通知书键"] = "400001|发明专利证书"
            row["授权公告日"] = "2025-01-01"
            row["人工确认_授权公告日"] = "2025-01-01"
            _write_csv(manual_csv, headers, [row])

            result = compare_manual_csv(str(manual_csv), str(output_dir))
            metrics = json.loads(Path(result["field_metrics_json"]).read_text(encoding="utf-8"))
            target = metrics.get("授权公告日", {})

            self.assertEqual(int(target.get("explicit_match", -1)), 1)
            self.assertEqual(int(target.get("explicit_mismatch", -1)), 0)
            self.assertEqual(int(target.get("implicit_accept", -1)), 0)
            self.assertEqual(int(result["explicit_checked"]), 1)
            self.assertEqual(int(result["explicit_mismatch"]), 0)
            self.assertEqual(int(result["total_mismatch"]), 0)

    def test_compare_manual_name_set_accepts_space_separator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_csv = root / "manual.csv"
            output_dir = root / "compare_output"
            headers = list(WIDE_HEADERS)
            row = {header: "" for header in headers}
            source_col = headers[1]
            notice_key_col = headers[2]
            applicant_col = UI_FIELD_LABELS["applicant"]
            manual_col = f"{MANUAL_TRUTH_PREFIX}{applicant_col}"
            row[source_col] = "D:/zip/a.zip"
            row[notice_key_col] = "400001|发明专利证书"
            row[applicant_col] = "西安交通大学，北京微纳精密机械有限公司"
            row[manual_col] = "西安交通大学 北京微纳精密机械有限公司"
            _write_csv(manual_csv, headers, [row])

            result = compare_manual_csv(str(manual_csv), str(output_dir))
            metrics = json.loads(Path(result["field_metrics_json"]).read_text(encoding="utf-8"))
            applicant_metrics = metrics.get(applicant_col, {})

            self.assertEqual(int(applicant_metrics.get("explicit_match", -1)), 1)
            self.assertEqual(int(applicant_metrics.get("explicit_mismatch", -1)), 0)
            self.assertEqual(int(result["explicit_checked"]), 1)
            self.assertEqual(int(result["explicit_mismatch"]), 0)
            self.assertEqual(int(result["total_mismatch"]), 0)

    def test_compare_manual_supports_gbk_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_csv = root / "manual_gbk.csv"
            output_dir = root / "compare_output"
            headers = list(WIDE_HEADERS)
            row = {header: "" for header in headers}
            row["源ZIP"] = "D:/zip/a.zip"
            row["通知书键"] = "400001|发明专利证书"
            row["代理机构信息"] = "中济纬天专利代理有限公司"
            row["人工确认_代理机构信息"] = "北京中济纬天专利代理有限公司"
            _write_csv_with_encoding(manual_csv, headers, [row], encoding="gbk")

            result = compare_manual_csv(str(manual_csv), str(output_dir))
            self.assertEqual(str(result.get("csv_encoding", "")), "gb18030")
            self.assertEqual(int(result["explicit_checked"]), 1)
            self.assertEqual(int(result["total_mismatch"]), 0)

    def test_export_strike_baseline_writes_strike_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            xlsx = root / "source.xlsx"
            output_root = root / "output"
            headers = ["状态", "源ZIP", "申请人信息", "代理机构信息"]
            rows = [
                {"状态": "成功", "源ZIP": "D:/zip/a.zip", "申请人信息": "错误A", "代理机构信息": "正确"},
                {"状态": "成功", "源ZIP": "D:/zip/b.zip", "申请人信息": "正确", "代理机构信息": "错误B"},
            ]
            self._write_xlsx(
                xlsx,
                headers=headers,
                rows=rows,
                strike_cells=[(2, "申请人信息"), (3, "代理机构信息")],
            )

            result = export_strike_baseline(str(xlsx), str(output_root))
            baseline_csv = Path(result["baseline_csv"])
            self.assertTrue(baseline_csv.exists())

            with baseline_csv.open("r", encoding="utf-8-sig", newline="") as file_obj:
                reader = csv.DictReader(file_obj)
                headers_read = list(reader.fieldnames or [])
                rows_read = [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]

            self.assertEqual(headers_read, list(STRIKE_BASELINE_HEADERS))
            self.assertEqual(len(rows_read), 2)
            self.assertEqual(rows_read[0].get("字段名称"), "申请人信息")
            self.assertEqual(rows_read[1].get("字段名称"), "代理机构信息")

    def test_compare_strike_baseline_counts_remaining_and_fixed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            baseline_csv = root / "baseline.csv"
            target_xlsx = root / "target.xlsx"
            output_dir = root / "compare_output"

            baseline_rows = [
                {"源ZIP": "D:/zip/a.zip", "字段名称": "申请人信息", "当前提取值": "旧错值A", "行号": "2"},
                {"源ZIP": "D:/zip/b.zip", "字段名称": "代理机构信息", "当前提取值": "旧错值B", "行号": "3"},
            ]
            _write_csv(baseline_csv, list(STRIKE_BASELINE_HEADERS), baseline_rows)

            headers = ["状态", "源ZIP", "申请人信息", "代理机构信息"]
            rows = [
                {"状态": "成功", "源ZIP": "D:/zip/a.zip", "申请人信息": "新值A", "代理机构信息": ""},
                {"状态": "成功", "源ZIP": "D:/zip/b.zip", "申请人信息": "", "代理机构信息": "旧错值B"},
            ]
            self._write_xlsx(target_xlsx, headers=headers, rows=rows, strike_cells=[])

            result = compare_strike_baseline(
                baseline_csv=str(baseline_csv),
                target_xlsx=str(target_xlsx),
                output_dir=str(output_dir),
            )

            self.assertEqual(int(result["baseline_total"]), 2)
            self.assertEqual(int(result["fixed_total"]), 1)
            self.assertEqual(int(result["remaining_total"]), 1)

            remain_csv = Path(result["remaining_csv"])
            self.assertTrue(remain_csv.exists())
            with remain_csv.open("r", encoding="utf-8-sig", newline="") as file_obj:
                reader = csv.DictReader(file_obj)
                headers_read = list(reader.fieldnames or [])
                rows_read = [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]
            self.assertEqual(headers_read, list(STRIKE_REMAIN_HEADERS))
            self.assertEqual(len(rows_read), 1)
            self.assertEqual(rows_read[0].get("字段名称"), "代理机构信息")
            self.assertEqual(rows_read[0].get("结果"), "remaining")


if __name__ == "__main__":
    unittest.main()
