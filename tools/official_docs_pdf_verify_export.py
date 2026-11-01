from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import openpyxl

if __package__ in {None, ""}:  # pragma: no cover - runtime path bootstrap
    _HERE = os.path.abspath(os.path.dirname(__file__))
    _ROOT = os.path.abspath(os.path.join(_HERE, ".."))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from core.official_docs.excel_report_v3 import (
    _PARSE_HEADERS,
    _build_headers,
    _kind_label,
    _parse_value_map,
    _safe_join,
    _status_label,
)
from core.official_docs.field_governance import BUSINESS_FIELD_ORDER, UNCERTAIN_FIELD_ORDER, build_notice_key
from core.official_docs.models import ProcessItemResult, ProcessOptions, ProcessSummary
from core.official_docs.process import process_official_notice_archives


DEFAULT_INPUT_ROOT = "官方通知书文件参考"
FIELD_OUTPUT_SUBDIR = os.path.join("official_docs_pdf_verify")

UI_FIELDS: tuple[str, ...] = (
    "applicant",
    "inventor",
    "agency_raw",
    "department",
    "center",
    "examiner",
    "panel",
    "reject_reason",
    "prior_art",
    "dossier_no",
    "authorization_pub_no",
    "authorization_pub_date",
    "certificate_no",
    "qrcode_link",
    "qrcode_image",
)

UI_FIELD_LABELS: dict[str, str] = {
    "applicant": "申请人信息",
    "inventor": "发明人信息",
    "agency_raw": "代理机构信息",
    "department": "审查部门信息",
    "center": "审查协作中心信息",
    "examiner": "审查员信息",
    "panel": "合议组信息",
    "reject_reason": "驳回理由",
    "prior_art": "对比件信息",
    "dossier_no": "申请方案卷号",
    "authorization_pub_no": "授权公告号",
    "authorization_pub_date": "授权公告日",
    "certificate_no": "证书号",
    "qrcode_link": "公告二维码链接",
    "qrcode_image": "公告二维码图片",
}
LEGACY_UI_FIELD_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "agency_raw": ("代理信息原文",),
}

MANUAL_TRUTH_PREFIX = "人工确认_"
MANUAL_TRUTH_HEADERS: tuple[str, ...] = tuple(f"{MANUAL_TRUTH_PREFIX}{UI_FIELD_LABELS[field]}" for field in UI_FIELDS)
_UNCERTAIN_HEADER_MAP: dict[str, str] = {
    "DMHFLAG_raw": "DMHFLAG原值",
    "FAMINGLX_raw": "FAMINGLX原值",
    "附件YEWULX_raw_set": "附件YEWULX原值集合",
}
_VERIFY_PARSE_HEADERS: tuple[str, ...] = tuple(list(_PARSE_HEADERS) + ["公告二维码图片"])


def _build_wide_headers_prefix() -> tuple[str, ...]:
    base_headers = list(_build_headers(include_exam_pdf_columns=False))
    business_headers = [header for header in base_headers if header not in {"状态", "源ZIP"}]
    return tuple(
        ["状态", "源ZIP", "通知书键"]
        + business_headers
        + list(_VERIFY_PARSE_HEADERS)
        + [_UNCERTAIN_HEADER_MAP.get(col, str(col or "")) for col in UNCERTAIN_FIELD_ORDER]
    )


WIDE_HEADERS_PREFIX: tuple[str, ...] = _build_wide_headers_prefix()
MANUAL_INSERT_AFTER_BY_FIELD: dict[str, str] = {
    "applicant": "申请人信息",
    "inventor": "发明人信息",
    "agency_raw": "代理机构信息",
    "department": "审查部门信息",
    "center": "审查协作中心信息",
    "examiner": "审查员电话",
    "panel": "参审员",
    "reject_reason": "驳回理由",
    "prior_art": "对比件信息",
    "dossier_no": "申请方案卷号",
    "authorization_pub_no": "授权公告号",
    "authorization_pub_date": "授权公告日",
    "certificate_no": "证书号",
    "qrcode_link": "公告二维码链接",
    "qrcode_image": "公告二维码图片",
}


def _build_wide_headers() -> tuple[str, ...]:
    manual_by_anchor: dict[str, list[str]] = {}
    for field in UI_FIELDS:
        manual_col = f"{MANUAL_TRUTH_PREFIX}{UI_FIELD_LABELS[field]}"
        anchor = str(MANUAL_INSERT_AFTER_BY_FIELD.get(field, "") or "")
        if anchor:
            manual_by_anchor.setdefault(anchor, []).append(manual_col)

    result: list[str] = []
    inserted: set[str] = set()
    for header in WIDE_HEADERS_PREFIX:
        result.append(header)
        for manual_col in manual_by_anchor.get(header, []):
            result.append(manual_col)
            inserted.add(manual_col)

    for manual_col in MANUAL_TRUTH_HEADERS:
        if manual_col not in inserted:
            result.append(manual_col)
    return tuple(result)


WIDE_HEADERS: tuple[str, ...] = _build_wide_headers()

DIFF_HEADERS: tuple[str, ...] = (
    "源ZIP",
    "通知书代码",
    "通知书名称",
    "字段名称",
    "提取值",
    "人工确认值",
    "比对结果",
    "差异原因",
    "确认来源",
)
STRIKE_BASELINE_HEADERS: tuple[str, ...] = (
    "源ZIP",
    "字段名称",
    "当前提取值",
    "行号",
)
STRIKE_REMAIN_HEADERS: tuple[str, ...] = (
    "源ZIP",
    "字段名称",
    "基线值",
    "当前值",
    "基线行号",
    "结果",
    "原因",
)

_MANUAL_CSV_ENCODINGS: tuple[str, ...] = (
    "utf-8-sig",
    "utf-8",
    "gb18030",
    "gbk",
    "cp936",
)

_SPLIT_TOKEN_RE = re.compile(r"(?:[,;\|\uFF0C\uFF1B\u3001]|\s)+")
_SENTENCE_SPLIT_RE = re.compile(r"[;；。!！?？\n\r]+")
_CN_PUB_RE = re.compile(r"CN\s*\d{6,12}(?:\.[0-9A-Z]+|[A-Z][0-9]?)?", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\-\s]{5,}\d")
_DATE_RE = re.compile(r"^\s*(\d{4})[./\-\u5e74](\d{1,2})[./\-\u6708](\d{1,2})(?:\u65e5)?\s*$")
_DATE_8_RE = re.compile(r"^\s*(\d{4})(\d{2})(\d{2})\s*$")


def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _output_dir(output_root: str) -> str:
    root = os.path.abspath(str(output_root or "").strip() or "output")
    return os.path.join(root, FIELD_OUTPUT_SUBDIR, _timestamp())


def _collect_zip_paths(input_root: str) -> list[str]:
    root = os.path.abspath(str(input_root or "").strip())
    if (not root) or (not os.path.isdir(root)):
        return []
    paths: list[str] = []
    for dir_path, _dir_names, file_names in os.walk(root):
        for file_name in file_names:
            if str(file_name).lower().endswith(".zip"):
                paths.append(os.path.abspath(os.path.join(dir_path, file_name)))
    paths.sort()
    return paths


def _new_empty_summary() -> ProcessSummary:
    return ProcessSummary(
        summary_run_dir="",
        excel_path="",
        total=0,
        success=0,
        skipped=0,
        failed=0,
        items=[],
    )


def _build_options(*, summary_root_dir: str, archive_root_dir: str) -> ProcessOptions:
    all_true_flags = {name: True for name in UI_FIELDS}
    return ProcessOptions(
        summary_root_dir=str(summary_root_dir or ""),
        archive_root_dir=str(archive_root_dir or ""),
        write_summary=False,
        write_archive=False,
        confirm_each=False,
        enable_exam_pdf_parse=True,
        pdf_parse_field_flags=all_true_flags,
    )


def _write_csv(path: str, headers: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(headers))
        writer.writeheader()
        for row in rows:
            writer.writerow({name: str(row.get(name, "") or "") for name in headers})


def _write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)


def _xlsx_strike_rows(xlsx_path: str) -> tuple[list[str], list[dict[str, str]]]:
    workbook = openpyxl.load_workbook(xlsx_path)
    sheet = workbook[workbook.sheetnames[0]]
    headers = [str(sheet.cell(1, col).value or "").strip() for col in range(1, sheet.max_column + 1)]
    if "源ZIP" not in headers:
        raise ValueError("XLSX 缺少必要列：源ZIP")

    rows: list[dict[str, str]] = []
    for row_idx in range(2, sheet.max_row + 1):
        source_zip = str(sheet.cell(row_idx, headers.index("源ZIP") + 1).value or "").strip()
        for col_idx, header in enumerate(headers, start=1):
            if not header:
                continue
            cell = sheet.cell(row_idx, col_idx)
            if not (cell.font and bool(cell.font.strike)):
                continue
            rows.append(
                {
                    "源ZIP": source_zip,
                    "字段名称": header,
                    "当前提取值": str(cell.value or ""),
                    "行号": str(row_idx),
                }
            )
    return headers, rows


def _xlsx_value_map(xlsx_path: str) -> tuple[list[str], dict[tuple[str, str], str]]:
    workbook = openpyxl.load_workbook(xlsx_path)
    sheet = workbook[workbook.sheetnames[0]]
    headers = [str(sheet.cell(1, col).value or "").strip() for col in range(1, sheet.max_column + 1)]
    if "源ZIP" not in headers:
        raise ValueError("XLSX 缺少必要列：源ZIP")
    zip_col = headers.index("源ZIP") + 1

    values: dict[tuple[str, str], str] = {}
    for row_idx in range(2, sheet.max_row + 1):
        source_zip = str(sheet.cell(row_idx, zip_col).value or "").strip()
        for col_idx, header in enumerate(headers, start=1):
            if not header:
                continue
            values[(source_zip, header)] = str(sheet.cell(row_idx, col_idx).value or "")
    return headers, values


def export_strike_baseline(input_xlsx: str, output_root: str) -> dict[str, Any]:
    xlsx_path = os.path.abspath(str(input_xlsx or "").strip())
    if (not xlsx_path) or (not os.path.isfile(xlsx_path)):
        raise FileNotFoundError(f"找不到输入XLSX: {xlsx_path}")

    _headers, strike_rows = _xlsx_strike_rows(xlsx_path)
    output_dir = _output_dir(output_root)
    _safe_mkdir(output_dir)

    baseline_csv = os.path.join(output_dir, "strike_baseline.csv")
    _write_csv(baseline_csv, STRIKE_BASELINE_HEADERS, strike_rows)
    _write_json(
        os.path.join(output_dir, "strike_baseline_summary.json"),
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "input_xlsx": xlsx_path,
            "output_dir": output_dir,
            "total_strike_items": len(strike_rows),
            "unique_zip_count": len({str(row.get("源ZIP", "") or "").strip() for row in strike_rows}),
        },
    )
    return {
        "output_dir": output_dir,
        "baseline_csv": baseline_csv,
        "total_strike_items": len(strike_rows),
    }


def compare_strike_baseline(*, baseline_csv: str, target_xlsx: str, output_dir: str) -> dict[str, Any]:
    baseline_path = os.path.abspath(str(baseline_csv or "").strip())
    target_path = os.path.abspath(str(target_xlsx or "").strip())
    output_dir_abs = os.path.abspath(str(output_dir or "").strip())
    if (not baseline_path) or (not os.path.isfile(baseline_path)):
        raise FileNotFoundError(f"找不到基线CSV: {baseline_path}")
    if (not target_path) or (not os.path.isfile(target_path)):
        raise FileNotFoundError(f"找不到目标XLSX: {target_path}")
    if not output_dir_abs:
        raise ValueError("output_dir 不能为空")
    _safe_mkdir(output_dir_abs)

    with open(baseline_path, "r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        baseline_rows = [{str(key or ""): str(value or "") for key, value in row.items()} for row in reader]

    _headers, target_value_map = _xlsx_value_map(target_path)

    remaining_rows: list[dict[str, str]] = []
    fixed_count = 0
    missing_count = 0
    for row in baseline_rows:
        source_zip = str(row.get("源ZIP", "") or "").strip()
        field_name = str(row.get("字段名称", "") or "").strip()
        baseline_value = str(row.get("当前提取值", "") or "")
        current_value = target_value_map.get((source_zip, field_name), None)
        if current_value is None:
            missing_count += 1
            remaining_rows.append(
                {
                    "源ZIP": source_zip,
                    "字段名称": field_name,
                    "基线值": baseline_value,
                    "当前值": "",
                    "基线行号": str(row.get("行号", "") or ""),
                    "结果": "remaining",
                    "原因": "目标文件缺少对应的源ZIP+字段列",
                }
            )
            continue
        if _normalize_text(current_value) == _normalize_text(baseline_value):
            remaining_rows.append(
                {
                    "源ZIP": source_zip,
                    "字段名称": field_name,
                    "基线值": baseline_value,
                    "当前值": current_value,
                    "基线行号": str(row.get("行号", "") or ""),
                    "结果": "remaining",
                    "原因": "当前值与基线错误值一致",
                }
            )
            continue
        fixed_count += 1

    remain_csv = os.path.join(output_dir_abs, "strike_remaining.csv")
    summary_json = os.path.join(output_dir_abs, "strike_compare_summary.json")
    _write_csv(remain_csv, STRIKE_REMAIN_HEADERS, remaining_rows)
    _write_json(
        summary_json,
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "baseline_csv": baseline_path,
            "target_xlsx": target_path,
            "output_dir": output_dir_abs,
            "baseline_total": len(baseline_rows),
            "remaining_total": len(remaining_rows),
            "fixed_total": fixed_count,
            "missing_total": missing_count,
        },
    )
    return {
        "output_dir": output_dir_abs,
        "remaining_csv": remain_csv,
        "summary_json": summary_json,
        "baseline_total": len(baseline_rows),
        "remaining_total": len(remaining_rows),
        "fixed_total": fixed_count,
        "missing_total": missing_count,
    }


def _wide_row_from_item(item: ProcessItemResult) -> dict[str, str]:
    notice_key = str(item.notice_key or "").strip() or build_notice_key(item.meta)
    row = {header: "" for header in WIDE_HEADERS}

    row["状态"] = _status_label(item.status)
    row["源ZIP"] = str(item.source_zip_path or "")
    row["通知书键"] = notice_key
    row["通知书类型"] = _kind_label(item.notice_kind)
    row["输出PDF名称"] = str(item.output_pdf_name or "")
    row["汇总PDF路径"] = str(item.summary_pdf_path or "")
    row["归档PDF路径"] = str(item.archive_pdf_path or "")
    row["合并来源"] = _safe_join(item.merged_sources)
    row["错误信息"] = str(item.reason or "")

    parse_values = _parse_value_map(item)
    parse_values["公告二维码图片"] = "有" if bool(item.pdf_qrcode_image_bytes) else ""
    for header in _VERIFY_PARSE_HEADERS:
        row[header] = str(parse_values.get(header, "") or "")

    business_fields = item.business_fields if isinstance(item.business_fields, dict) else {}
    for key in BUSINESS_FIELD_ORDER:
        row[key] = str(business_fields.get(key, "") or "")

    uncertain_fields = item.uncertain_fields if isinstance(item.uncertain_fields, dict) else {}
    for key in UNCERTAIN_FIELD_ORDER:
        mapped_header = _UNCERTAIN_HEADER_MAP.get(key, str(key or ""))
        row[mapped_header] = str(uncertain_fields.get(key, "") or "")

    return row


def generate_wide_report(input_root: str, output_root: str) -> dict[str, Any]:
    zip_paths = _collect_zip_paths(input_root)
    output_dir = _output_dir(output_root)
    _safe_mkdir(output_dir)

    summary = _new_empty_summary()
    if zip_paths:
        with tempfile.TemporaryDirectory(prefix="official_docs_pdf_verify_") as work_dir:
            options = _build_options(
                summary_root_dir=os.path.join(work_dir, "summary"),
                archive_root_dir=os.path.join(work_dir, "archive"),
            )
            summary = process_official_notice_archives(zip_paths, options)

    rows = [_wide_row_from_item(item) for item in list(summary.items or [])]
    wide_csv = os.path.join(output_dir, "pdf_verify_wide.csv")
    _write_csv(wide_csv, WIDE_HEADERS, rows)

    return {
        "output_dir": output_dir,
        "wide_csv": wide_csv,
        "zip_count": len(zip_paths),
        "record_count": len(rows),
        "summary": {
            "total": int(summary.total),
            "success": int(summary.success),
            "skipped": int(summary.skipped),
            "failed": int(summary.failed),
        },
    }


def _normalize_text(text: str) -> str:
    src = str(text or "").replace("\u3000", " ").strip()
    return re.sub(r"\s+", "", src)


def _split_tokens(text: str) -> list[str]:
    tokens = [part.strip() for part in _SPLIT_TOKEN_RE.split(str(text or "")) if part.strip()]
    if tokens:
        return tokens
    base = str(text or "").strip()
    return [base] if base else []


def _split_notice_key(notice_key: str) -> tuple[str, str]:
    src = str(notice_key or "").strip()
    if not src:
        return "", ""
    if "|" not in src:
        return src, ""
    code, name = src.split("|", 1)
    return str(code or "").strip(), str(name or "").strip()


def _normalize_date(value: str) -> str:
    src = str(value or "").strip()
    if not src:
        return ""
    m = _DATE_RE.match(src)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m8 = _DATE_8_RE.match(src)
    if m8:
        return f"{int(m8.group(1)):04d}-{int(m8.group(2)):02d}-{int(m8.group(3)):02d}"
    compact = src.replace("/", "-").replace(".", "-")
    return compact


def _normalize_url(value: str) -> str:
    src = str(value or "").strip()
    if not src:
        return ""
    parsed = urlparse(src)
    if not parsed.scheme or not parsed.netloc:
        return _normalize_text(src).lower()
    path = str(parsed.path or "").rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}{query}"


def _normalize_presence(value: str) -> str:
    src = _normalize_text(str(value or "")).lower()
    if src in {"有", "yes", "true", "1", "y"}:
        return "有"
    if src in {"无", "空", "none", "no", "false", "0", "n"}:
        return "无"
    if not src:
        return "无"
    return src


def _compare_name_set(extracted: str, truth: str) -> tuple[bool, str]:
    extracted_set = {_normalize_text(token) for token in _split_tokens(extracted) if _normalize_text(token)}
    truth_set = {_normalize_text(token) for token in _split_tokens(truth) if _normalize_text(token)}
    if not truth_set:
        return True, ""
    if not extracted_set:
        return False, "提取值为空"
    if extracted_set == truth_set:
        return True, ""
    return False, "姓名集合不一致"


def _compare_agency(extracted: str, truth: str) -> tuple[bool, str]:
    left = _normalize_text(extracted)
    right = _normalize_text(truth)
    if not right:
        return True, ""
    if not left:
        return False, "提取值为空"
    if (left in right) or (right in left):
        return True, ""
    return False, "代理机构主体未命中"


def _parse_examiner_pair(value: str) -> tuple[str, str]:
    src = str(value or "").strip()
    if not src:
        return "", ""
    src = re.sub(r"审\s*查\s*员(?:名称|姓名)?\s*[:：]?", " ", src)
    src = re.sub(r"联\s*系\s*电\s*话\s*[:：]?", " ", src)
    src = re.sub(r"电\s*话\s*[:：]?", " ", src)
    phone_match = _PHONE_RE.search(src)
    phone = ""
    if phone_match:
        phone = re.sub(r"\D+", "", phone_match.group(0))
        src = src.replace(phone_match.group(0), " ")
    tokens = [token.strip() for token in re.split(r"[,;\|\uFF0C\uFF1B\u3001\s]+", src) if token.strip()]
    name = _normalize_text("".join(tokens))
    return name, phone


def _compare_examiner(extracted: str, truth: str) -> tuple[bool, str]:
    extracted_name, extracted_phone = _parse_examiner_pair(extracted)
    truth_name, truth_phone = _parse_examiner_pair(truth)
    if truth_name and truth_phone:
        if not extracted_name or not extracted_phone:
            return False, "提取值未同时包含姓名和电话"
        if (extracted_name == truth_name) and (extracted_phone == truth_phone):
            return True, ""
        return False, "审查员姓名或电话不一致"
    if truth_name:
        if not extracted_name:
            return False, "提取值缺少审查员姓名"
        if extracted_name == truth_name:
            return True, ""
        return False, "审查员姓名不一致"
    if truth_phone:
        if not extracted_phone:
            return False, "提取值缺少审查员电话"
        if extracted_phone == truth_phone:
            return True, ""
        return False, "审查员电话不一致"
    return False, "人工确认值为空"


def _parse_panel_components(value: str) -> tuple[str, str, str]:
    src = str(value or "").strip()
    if not src:
        return "", "", ""
    parts = [token.strip() for token in re.split(r"[,;\|\uFF0C\uFF1B\u3001\n\r]+", src) if token.strip()]
    if len(parts) >= 3:
        return _normalize_text(parts[0]), _normalize_text(parts[1]), _normalize_text(parts[2])
    normalized = _normalize_text(src)
    if not normalized:
        return "", "", ""
    return normalized, "", ""


def _compare_panel(extracted: str, truth: str) -> tuple[bool, str]:
    extracted_head, extracted_main, extracted_member = _parse_panel_components(extracted)
    truth_head, truth_main, truth_member = _parse_panel_components(truth)
    truth_values = [truth_head, truth_main, truth_member]
    if not any(truth_values):
        return False, "人工确认值为空"
    extracted_values = [extracted_head, extracted_main, extracted_member]
    if not any(extracted_values):
        return False, "提取值为空"
    if truth_main or truth_member:
        if extracted_values == truth_values:
            return True, ""
        return False, "合议组分量不一致"
    if extracted_head and truth_head and ((extracted_head in truth_head) or (truth_head in extracted_head)):
        return True, ""
    return False, "合议组分量不一致"


def _extract_cn_set(value: str) -> set[str]:
    return {re.sub(r"\s+", "", m.group(0).upper()) for m in _CN_PUB_RE.finditer(str(value or ""))}


def _compare_prior_art(extracted: str, truth: str) -> tuple[bool, str]:
    extracted_set = _extract_cn_set(extracted)
    truth_set = _extract_cn_set(truth)
    if not truth_set:
        return False, "人工确认值缺少CN公开号"
    if not extracted_set:
        return False, "提取值缺少CN公开号"
    if extracted_set == truth_set:
        return True, ""
    return False, "CN公开号集合不一致"


def _compare_sentence_set(extracted: str, truth: str) -> tuple[bool, str]:
    extracted_set = {_normalize_text(token) for token in _SENTENCE_SPLIT_RE.split(str(extracted or "")) if _normalize_text(token)}
    truth_set = {_normalize_text(token) for token in _SENTENCE_SPLIT_RE.split(str(truth or "")) if _normalize_text(token)}
    if not truth_set:
        return True, ""
    if not extracted_set:
        return False, "提取值为空"
    if extracted_set == truth_set:
        return True, ""
    return False, "句集合不一致"


def _compare_exact_text(extracted: str, truth: str, *, as_date: bool = False, as_url: bool = False) -> tuple[bool, str]:
    if as_date:
        left = _normalize_date(extracted)
        right = _normalize_date(truth)
    elif as_url:
        left = _normalize_url(extracted)
        right = _normalize_url(truth)
    else:
        left = _normalize_text(extracted)
        right = _normalize_text(truth)
    if not right:
        return True, ""
    if left == right:
        return True, ""
    return False, "提取值与人工确认值不一致"


def _compare_qrcode_image(extracted: str, truth: str) -> tuple[bool, str]:
    left = _normalize_presence(extracted)
    right = _normalize_presence(truth)
    if left == right:
        return True, ""
    return False, "二维码图片有无状态不一致"


def _compare_field(field: str, extracted: str, truth: str) -> tuple[bool, str]:
    if field in {"applicant", "inventor"}:
        return _compare_name_set(extracted, truth)
    if field == "agency_raw":
        return _compare_agency(extracted, truth)
    if field == "examiner":
        return _compare_examiner(extracted, truth)
    if field == "panel":
        return _compare_panel(extracted, truth)
    if field == "prior_art":
        return _compare_prior_art(extracted, truth)
    if field == "reject_reason":
        return _compare_sentence_set(extracted, truth)
    if field == "authorization_pub_date":
        return _compare_exact_text(extracted, truth, as_date=True)
    if field == "qrcode_link":
        return _compare_exact_text(extracted, truth, as_url=True)
    if field == "qrcode_image":
        return _compare_qrcode_image(extracted, truth)
    return _compare_exact_text(extracted, truth)


def _extract_ui_field_value_from_row(row: dict[str, str], field: str) -> str:
    if field == "examiner":
        parts = [str(row.get("审查员姓名", "") or "").strip(), str(row.get("审查员电话", "") or "").strip()]
        return "|".join([part for part in parts if part])
    if field == "panel":
        parts = [
            str(row.get("合议组组长", "") or "").strip(),
            str(row.get("主审员", "") or "").strip(),
            str(row.get("参审员", "") or "").strip(),
        ]
        return "|".join([part for part in parts if part])
    primary_label = UI_FIELD_LABELS[field]
    if str(row.get(primary_label, "") or "").strip():
        return str(row.get(primary_label, "") or "")
    for legacy_label in LEGACY_UI_FIELD_LABEL_ALIASES.get(field, ()):
        value = str(row.get(legacy_label, "") or "")
        if value.strip():
            return value
    return str(row.get(primary_label, "") or "")


def _manual_truth_value_from_row(row: dict[str, str], field: str) -> str:
    primary_label = UI_FIELD_LABELS[field]
    candidate_columns = [f"{MANUAL_TRUTH_PREFIX}{primary_label}"]
    candidate_columns.extend(
        f"{MANUAL_TRUTH_PREFIX}{legacy_label}"
        for legacy_label in LEGACY_UI_FIELD_LABEL_ALIASES.get(field, ())
    )
    for column_name in candidate_columns:
        value = str(row.get(column_name, "") or "").strip()
        if value:
            return value
    return ""


def _validate_manual_csv_headers(headers: list[str]) -> None:
    header_set = {str(name or "") for name in headers}
    missing: list[str] = []

    for name in WIDE_HEADERS_PREFIX:
        if name in header_set:
            continue
        matched_legacy = any(
            legacy_label in header_set
            for field, label in UI_FIELD_LABELS.items()
            if label == name
            for legacy_label in LEGACY_UI_FIELD_LABEL_ALIASES.get(field, ())
        )
        if not matched_legacy:
            missing.append(name)

    for field in UI_FIELDS:
        primary_name = f"{MANUAL_TRUTH_PREFIX}{UI_FIELD_LABELS[field]}"
        if primary_name in header_set:
            continue
        legacy_names = {
            f"{MANUAL_TRUTH_PREFIX}{legacy_label}"
            for legacy_label in LEGACY_UI_FIELD_LABEL_ALIASES.get(field, ())
        }
        if not legacy_names.intersection(header_set):
            missing.append(primary_name)

    if missing:
        raise ValueError(f"人工核对CSV缺少必要列: {', '.join(missing)}")


def _read_manual_csv_rows(manual_path: str) -> tuple[list[str], list[dict[str, str]], str]:
    last_error: Exception | None = None
    for encoding in _MANUAL_CSV_ENCODINGS:
        try:
            with open(manual_path, "r", encoding=encoding, newline="") as file_obj:
                reader = csv.DictReader(file_obj)
                headers = [str(name or "") for name in list(reader.fieldnames or [])]
                _validate_manual_csv_headers(headers)
                rows = [{str(key or ""): str(value or "") for key, value in row.items()} for row in reader]
                return headers, rows, encoding
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    detail = f"{type(last_error).__name__}: {last_error}" if last_error is not None else "unknown"
    raise UnicodeDecodeError("manual_csv", b"", 0, 1, f"无法识别CSV编码：{detail}")


def compare_manual_csv(manual_csv: str, output_dir: str) -> dict[str, Any]:
    manual_path = os.path.abspath(str(manual_csv or "").strip())
    if (not manual_path) or (not os.path.isfile(manual_path)):
        raise FileNotFoundError(f"找不到人工核对CSV: {manual_path}")

    output_dir_abs = os.path.abspath(str(output_dir or "").strip())
    if not output_dir_abs:
        raise ValueError("output_dir 不能为空")
    _safe_mkdir(output_dir_abs)

    _headers, rows, csv_encoding = _read_manual_csv_rows(manual_path)

    metrics: dict[str, dict[str, int]] = {
        UI_FIELD_LABELS[field]: {"explicit_match": 0, "explicit_mismatch": 0, "implicit_accept": 0}
        for field in UI_FIELDS
    }
    diff_rows: list[dict[str, str]] = []

    explicit_checked = 0
    explicit_mismatch = 0
    implicit_accept_total = 0
    for row in rows:
        source_zip = str(row.get("源ZIP", "") or "").strip()
        notice_code, notice_name = _split_notice_key(str(row.get("通知书键", "") or ""))
        for field in UI_FIELDS:
            label = UI_FIELD_LABELS[field]
            extracted_value = _extract_ui_field_value_from_row(row, field)
            manual_truth_value = _manual_truth_value_from_row(row, field)
            if not manual_truth_value:
                metrics[label]["implicit_accept"] += 1
                implicit_accept_total += 1
                continue

            matched, reason = _compare_field(field, extracted_value, manual_truth_value)
            explicit_checked += 1
            if matched:
                metrics[label]["explicit_match"] += 1
                continue

            metrics[label]["explicit_mismatch"] += 1
            explicit_mismatch += 1
            diff_rows.append(
                {
                    "源ZIP": source_zip,
                    "通知书代码": notice_code,
                    "通知书名称": notice_name,
                    "字段名称": label,
                    "提取值": str(extracted_value or ""),
                    "人工确认值": manual_truth_value,
                    "比对结果": "mismatch",
                    "差异原因": str(reason or "提取值与人工确认值不一致"),
                    "确认来源": "explicit_truth",
                }
            )

    field_metrics: dict[str, dict[str, float | int]] = {}
    for label, stat in metrics.items():
        explicit_match_count = int(stat["explicit_match"])
        explicit_mismatch_count = int(stat["explicit_mismatch"])
        implicit_accept_count = int(stat["implicit_accept"])
        explicit_total = explicit_match_count + explicit_mismatch_count
        checked_total = explicit_total + implicit_accept_count
        explicit_accuracy = (float(explicit_match_count) / float(explicit_total)) if explicit_total else 0.0
        overall_accuracy = (float(explicit_match_count + implicit_accept_count) / float(checked_total)) if checked_total else 0.0
        field_metrics[label] = {
            "explicit_match": explicit_match_count,
            "explicit_mismatch": explicit_mismatch_count,
            "implicit_accept": implicit_accept_count,
            "checked_total": checked_total,
            "explicit_accuracy": explicit_accuracy,
            "overall_accuracy": overall_accuracy,
        }

    total_rows = len(rows)
    total_fields = total_rows * len(UI_FIELDS)
    explicit_match_total = explicit_checked - explicit_mismatch
    overall_accuracy = (float(explicit_match_total + implicit_accept_total) / float(total_fields)) if total_fields else 0.0

    diff_csv_path = os.path.join(output_dir_abs, "manual_compare_diff.csv")
    summary_json_path = os.path.join(output_dir_abs, "manual_compare_summary.json")
    metrics_json_path = os.path.join(output_dir_abs, "manual_compare_field_metrics.json")

    _write_csv(diff_csv_path, DIFF_HEADERS, diff_rows)
    _write_json(
        summary_json_path,
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "manual_csv": manual_path,
            "output_dir": output_dir_abs,
            "total_rows": total_rows,
            "total_fields": total_fields,
            "explicit_checked": explicit_checked,
            "explicit_mismatch": explicit_mismatch,
            "implicit_accept": implicit_accept_total,
            "overall_accuracy": overall_accuracy,
            "csv_encoding": csv_encoding,
            "total_mismatch": len(diff_rows),
        },
    )
    _write_json(metrics_json_path, field_metrics)

    return {
        "output_dir": output_dir_abs,
        "manual_csv": manual_path,
        "diff_csv": diff_csv_path,
        "summary_json": summary_json_path,
        "field_metrics_json": metrics_json_path,
        "total_rows": total_rows,
        "total_fields": total_fields,
        "explicit_checked": explicit_checked,
        "explicit_mismatch": explicit_mismatch,
        "implicit_accept": implicit_accept_total,
        "overall_accuracy": overall_accuracy,
        "csv_encoding": csv_encoding,
        "total_mismatch": len(diff_rows),
    }


def _resolve_default_input_root() -> str:
    candidate = os.path.abspath(DEFAULT_INPUT_ROOT)
    if os.path.isdir(candidate):
        return candidate
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="官文 PDF 正确性核验工具（宽表模板 + 人工比对 + 删除线回归）。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate-wide", help="按 GUI Excel 口径生成宽表 CSV 模板。")
    generate_parser.add_argument(
        "--input-root",
        default=_resolve_default_input_root(),
        help="包含官方通知书 ZIP 的根目录。",
    )
    generate_parser.add_argument(
        "--output-root",
        default="output",
        help="输出根目录。",
    )

    compare_parser = subparsers.add_parser("compare-manual", help="读取人工确认列，输出差异与准确率统计。")
    compare_parser.add_argument(
        "--manual-csv",
        required=True,
        help="人工补录后的宽表 CSV 文件路径。",
    )
    compare_parser.add_argument(
        "--output-dir",
        required=True,
        help="差异结果输出目录。",
    )

    strike_export_parser = subparsers.add_parser("export-strike-baseline", help="从XLSX删除线标注导出错项基线。")
    strike_export_parser.add_argument(
        "--input-xlsx",
        required=True,
        help="包含删除线标注的官文Excel路径。",
    )
    strike_export_parser.add_argument(
        "--output-root",
        default="output",
        help="输出根目录。",
    )

    strike_compare_parser = subparsers.add_parser("compare-strike-baseline", help="对比基线错项在新XLSX中的剩余数量。")
    strike_compare_parser.add_argument(
        "--baseline-csv",
        required=True,
        help="export-strike-baseline 生成的 strike_baseline.csv 路径。",
    )
    strike_compare_parser.add_argument(
        "--target-xlsx",
        required=True,
        help="新的官文处理Excel路径（用于回归对比）。",
    )
    strike_compare_parser.add_argument(
        "--output-dir",
        required=True,
        help="对比结果输出目录。",
    )

    args = parser.parse_args()

    if args.command == "generate-wide":
        result = generate_wide_report(args.input_root, args.output_root)
    elif args.command == "compare-manual":
        result = compare_manual_csv(args.manual_csv, args.output_dir)
    elif args.command == "export-strike-baseline":
        result = export_strike_baseline(args.input_xlsx, args.output_root)
    else:
        result = compare_strike_baseline(
            baseline_csv=args.baseline_csv,
            target_xlsx=args.target_xlsx,
            output_dir=args.output_dir,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
