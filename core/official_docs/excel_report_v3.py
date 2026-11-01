from __future__ import annotations

from datetime import datetime
from typing import Iterable

from core.excel_text import append_text_row

from .field_governance import BUSINESS_FIELD_ORDER
from .models import NoticeKind, ProcessItemResult


_EXCEL_CELL_MAX_LEN = 32767
_PROCESS_DATE_HEADER = "处理日期"
_BASE_HEADERS: list[str] = [
    "状态",
    _PROCESS_DATE_HEADER,
    "发明名称",
    "专利类型",
    "通知书名称",
    "申请号",
    "申请日",
    "发文日",
    "逾期日",
    "内部编号",
    "输出PDF名称",
    "申请人信息",
    "通知书类型",
    "通知书代码",
    "期限天",
    "案卷号",
    "汇总PDF路径",
    "归档PDF路径",
    "错误信息",
    "源ZIP",
]
_PARSE_INSERT_HEADER = "申请人信息"
_PARSE_CORE_HEADERS: list[str] = ["发明人信息", "代理机构信息", "代理人信息"]

_PARSE_HEADERS: list[str] = [
    "PDF解析状态",
    "PDF解析错误",
    "申请人信息",
    "发明人信息",
    "代理人信息",
    "代理机构信息",
    "审查部门信息",
    "审查协作中心信息",
    "审查员姓名",
    "审查员电话",
    "合议组组长",
    "主审员",
    "参审员",
    "驳回理由",
    "对比件信息",
    "申请方案卷号",
    "授权公告号",
    "授权公告日",
    "证书号",
    "公告二维码链接",
]
_PARSE_EXTENSION_HEADERS: list[str] = [
    "PDF解析状态",
    "PDF解析错误",
    "审查部门信息",
    "审查协作中心信息",
    "审查员姓名",
    "审查员电话",
    "合议组组长",
    "主审员",
    "参审员",
    "驳回理由",
    "对比件信息",
    "申请方案卷号",
    "授权公告号",
    "授权公告日",
    "证书号",
    "公告二维码链接",
]


def _is_xml_compatible_char(char: str) -> bool:
    code = ord(char)
    return code in (0x09, 0x0A, 0x0D) or (0x20 <= code <= 0xD7FF) or (0xE000 <= code <= 0xFFFD) or (0x10000 <= code <= 0x10FFFF)


def _clean_excel_text(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if _is_xml_compatible_char(ch))
    if len(text) > _EXCEL_CELL_MAX_LEN:
        text = text[:_EXCEL_CELL_MAX_LEN]
    return text


def _require_openpyxl():
    try:
        from openpyxl import Workbook

        return Workbook
    except Exception as e:
        raise RuntimeError(f"缺少 openpyxl，无法导出 Excel：{e}")


def _kind_label(kind: NoticeKind) -> str:
    if kind == "exam_opinion":
        return "审查意见"
    if kind == "rectification":
        return "补正"
    return "未知"


def _status_label(status: str) -> str:
    src = str(status or "").strip().lower()
    if src == "success":
        return "成功"
    if src == "skip":
        return "跳过"
    if src == "fail":
        return "失败"
    return str(status or "")


def _safe_join(items: Iterable[str], sep: str = ";") -> str:
    return sep.join([str(item or "").strip() for item in (items or []) if str(item or "").strip()])


def _build_business_headers() -> list[str]:
    headers = [str(col or "") for col in BUSINESS_FIELD_ORDER if str(col or "")]
    return headers


def _build_extra_business_headers(
    *,
    items: Iterable[ProcessItemResult],
    business_headers: list[str],
) -> list[str]:
    present: set[str] = set()
    for item in items:
        business_fields = item.business_fields if isinstance(item.business_fields, dict) else {}
        for key, value in business_fields.items():
            name = str(key or "").strip()
            if name and str(value or "").strip():
                present.add(name)

    base = set(_BASE_HEADERS)
    return [
        header
        for header in business_headers
        if header not in base and header != "专利类型(显示)" and header in present
    ]


def _build_headers(
    *,
    include_exam_pdf_columns: bool,
    business_headers: list[str] | None = None,
    extra_business_headers: list[str] | None = None,
) -> list[str]:
    if business_headers is None:
        business_headers = _build_business_headers()
    headers = list(_BASE_HEADERS)
    extras = [header for header in (extra_business_headers or []) if str(header or "").strip()]
    if extras:
        insert_at = headers.index("汇总PDF路径")
        headers[insert_at:insert_at] = extras
    if include_exam_pdf_columns:
        insert_at = headers.index(_PARSE_INSERT_HEADER) + 1
        headers[insert_at:insert_at] = list(_PARSE_CORE_HEADERS)
        headers.extend(_PARSE_EXTENSION_HEADERS)
    return headers


def _parse_value_map(item: ProcessItemResult) -> dict[str, str]:
    reject_reason = str(item.pdf_reject_reason or item.pdf_reject_reasons or "")
    return {
        "PDF解析状态": str(item.pdf_parse_status or ""),
        "PDF解析错误": str(item.pdf_parse_error or ""),
        "申请人信息": str(item.pdf_applicant or ""),
        "发明人信息": str(item.pdf_inventor or ""),
        "代理人信息": str(item.pdf_agent or ""),
        "代理机构信息": str(item.pdf_agency_raw or ""),
        "审查部门信息": str(item.pdf_department or ""),
        "审查协作中心信息": str(item.pdf_center or ""),
        "审查员姓名": str(item.pdf_examiner_name or ""),
        "审查员电话": str(item.pdf_examiner_phone or ""),
        "合议组组长": str(item.pdf_panel_head or ""),
        "主审员": str(item.pdf_panel_main or ""),
        "参审员": str(item.pdf_panel_member or ""),
        "驳回理由": reject_reason,
        "对比件信息": str(item.pdf_cn_pubnos or ""),
        "申请方案卷号": str(item.pdf_dossier_no or ""),
        "授权公告号": str(item.pdf_authorization_pub_no or ""),
        "授权公告日": str(item.pdf_authorization_pub_date or ""),
        "证书号": str(item.pdf_certificate_no or ""),
        "公告二维码链接": str(item.pdf_qrcode_link or ""),
    }


def build_dynamic_keys(items: Iterable[ProcessItemResult]) -> list[str]:
    _ = items
    return []


def _business_value(business_fields: dict[str, str], *headers: str) -> str:
    if not isinstance(business_fields, dict):
        return ""
    for header in headers:
        text = str(business_fields.get(header, "") or "").strip()
        if text:
            return text
    return ""


def write_excel_report(
    dest_path: str,
    *,
    items: list[ProcessItemResult],
    include_exam_pdf_columns: bool = False,
) -> str:
    Workbook = _require_openpyxl()
    wb = Workbook()
    ws = wb.active
    ws.title = "官文处理结果"

    report_items = list(items or [])
    business_headers = _build_business_headers()
    extra_business_headers = _build_extra_business_headers(
        items=report_items,
        business_headers=business_headers,
    )
    headers = _build_headers(
        include_exam_pdf_columns=bool(include_exam_pdf_columns),
        business_headers=business_headers,
        extra_business_headers=extra_business_headers,
    )
    append_text_row(ws, [_clean_excel_text(col) for col in headers])
    process_date = datetime.now().strftime("%Y-%m-%d")

    for item in report_items:
        business_fields = item.business_fields if isinstance(item.business_fields, dict) else {}
        parse_values = _parse_value_map(item)
        row_map: dict[str, str] = {
            "状态": _status_label(item.status),
            _PROCESS_DATE_HEADER: process_date,
            "发明名称": _business_value(business_fields, "发明名称"),
            "专利类型": _business_value(business_fields, "专利类型", "专利类型(显示)"),
            "通知书名称": _business_value(business_fields, "通知书名称"),
            "申请号": _business_value(business_fields, "申请号"),
            "申请日": _business_value(business_fields, "申请日"),
            "发文日": _business_value(business_fields, "发文日"),
            "逾期日": _business_value(business_fields, "逾期日"),
            "内部编号": _business_value(business_fields, "内部编号"),
            "输出PDF名称": str(item.output_pdf_name or ""),
            "申请人信息": _business_value(business_fields, "申请人信息") or str(parse_values.get("申请人信息", "") or ""),
            "通知书类型": _kind_label(item.notice_kind),
            "通知书代码": _business_value(business_fields, "通知书代码"),
            "期限天": _business_value(business_fields, "期限天"),
            "案卷号": _business_value(business_fields, "案卷号"),
            "汇总PDF路径": str(item.summary_pdf_path or ""),
            "归档PDF路径": str(item.archive_pdf_path or ""),
            "错误信息": str(item.reason or ""),
            "源ZIP": str(item.source_zip_path or ""),
        }
        if include_exam_pdf_columns:
            row_map["发明人信息"] = str(parse_values.get("发明人信息", "") or "")
            row_map["代理机构信息"] = str(parse_values.get("代理机构信息", "") or "")
            row_map["代理人信息"] = str(parse_values.get("代理人信息", "") or "")
            for header in _PARSE_EXTENSION_HEADERS:
                row_map[header] = str(parse_values.get(header, "") or "")
        for header in extra_business_headers:
            row_map[header] = _business_value(business_fields, header)

        append_text_row(ws, [_clean_excel_text(row_map.get(header, "")) for header in headers])

    wb.save(dest_path)
    return dest_path


def build_default_excel_name(now: datetime | None = None) -> str:
    ts = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    return f"官文处理结果_{ts}.xlsx"


__all__ = ["build_default_excel_name", "build_dynamic_keys", "write_excel_report"]
