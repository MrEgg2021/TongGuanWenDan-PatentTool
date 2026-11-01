from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import FormalReviewDocument, Issue
from .rule_registry import RULE_REGISTRY

_SEVERITY_LABELS = {
    "fatal": "致命",
    "error": "错误",
    "high": "高危",
    "warning": "警告",
    "medium": "中等",
    "low": "提醒",
    "info": "提示",
}
_SECTION_LABELS = {
    "claims": "权利要求书",
    "description": "说明书",
    "abstract": "摘要",
    "drawings": "附图",
}


def build_report_payload(
    *,
    source_file: str,
    document: FormalReviewDocument,
    issues: list[Issue],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": source_file,
        "summary": {
            "claims_count": len(document.claims),
            "issues_total": len(issues),
            "issues_ignored": len([issue for issue in issues if issue.ignored]),
            "issues_effective": len([issue for issue in issues if not issue.ignored]),
        },
        "document": document.to_dict(),
        "issues": [issue.to_dict() for issue in issues],
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def write_report_json(path: str, payload: dict[str, Any]) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(out)


def _require_python_docx():
    try:
        from docx import Document  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"缺少依赖 python-docx，无法导出 DOCX 报告：{exc}") from exc
    return Document


def _require_openpyxl():
    try:
        from openpyxl import Workbook  # type: ignore
        from openpyxl.utils import get_column_letter  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"缺少依赖 openpyxl，无法导出 XLSX 报告：{exc}") from exc
    return Workbook, get_column_letter


def _issue_location(issue: dict[str, Any]) -> str:
    section = _localize_section(issue.get("section", ""))
    claim_num = issue.get("claim_num")
    if claim_num is None:
        return section
    return f"{section}/权利要求{claim_num}"


def _localize_severity(value: Any) -> str:
    raw = str(value or "")
    return _SEVERITY_LABELS.get(raw.lower(), raw)


def _localize_section(value: Any) -> str:
    raw = str(value or "")
    return _SECTION_LABELS.get(raw, raw)


def _localize_rule_label(value: Any) -> str:
    rule_id = str(value or "")
    row = RULE_REGISTRY.get(rule_id, {}) if isinstance(RULE_REGISTRY, dict) else {}
    label = str(row.get("label") or "").strip() if isinstance(row, dict) else ""
    return label or rule_id


def write_report_docx(path: str, payload: dict[str, Any]) -> str:
    Document = _require_python_docx()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    summary = dict(payload.get("summary", {}) or {})
    issues = list(payload.get("issues", []) or [])

    doc = Document()
    doc.add_heading("形式审查报告", level=1)
    doc.add_paragraph(f"生成时间：{payload.get('generated_at', '')}")
    source = payload.get('source_file', '')
    doc.add_paragraph(f"来源：{'纯文本输入' if source == 'plain_text_input' else source}")
    doc.add_paragraph(f"权利要求数量：{summary.get('claims_count', 0)}")
    doc.add_paragraph(f"问题总数：{summary.get('issues_total', 0)}")
    doc.add_paragraph(f"已忽略：{summary.get('issues_ignored', 0)}")
    doc.add_paragraph(f"有效问题：{summary.get('issues_effective', 0)}")

    doc.add_heading("问题明细", level=2)
    headers = ["序号", "严重度", "检查项目", "位置", "原因", "片段", "忽略"]
    table = doc.add_table(rows=1, cols=len(headers))
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = str(label)

    for idx, issue in enumerate(issues, start=1):
        row = table.add_row().cells
        row[0].text = str(idx)
        row[1].text = _localize_severity(issue.get("severity", ""))
        row[2].text = _localize_rule_label(issue.get("rule_id", ""))
        row[3].text = _issue_location(dict(issue or {}))
        row[4].text = str(issue.get("message", "") or "")
        row[5].text = str(issue.get("snippet", "") or "")
        row[6].text = "是" if bool(issue.get("ignored", False)) else "否"

    doc.save(out)
    return str(out)


def write_report_xlsx(path: str, payload: dict[str, Any], *, include_ignored_column: bool = True) -> str:
    Workbook, get_column_letter = _require_openpyxl()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    issues = list(payload.get("issues", []) or [])
    headers = ["序号", "严重度", "检查项目", "分区", "权利要求号", "原因", "片段"]
    if include_ignored_column:
        headers.append("忽略")

    wb = Workbook()
    ws = wb.active
    ws.title = "问题明细"
    ws.append(headers)
    ws.freeze_panes = "A2"

    for idx, issue in enumerate(issues, start=1):
        issue_dict = dict(issue or {})
        row = [
            idx,
            _localize_severity(issue_dict.get("severity", "")),
            _localize_rule_label(issue_dict.get("rule_id", "")),
            _localize_section(issue_dict.get("section", "")),
            issue_dict.get("claim_num"),
            str(issue_dict.get("message", "") or ""),
            str(issue_dict.get("snippet", "") or ""),
        ]
        if include_ignored_column:
            row.append("是" if bool(issue_dict.get("ignored", False)) else "否")
        ws.append(row)

    for col_idx in range(1, len(headers) + 1):
        letter = get_column_letter(col_idx)
        max_len = len(str(headers[col_idx - 1]))
        for row_idx in range(2, int(ws.max_row) + 1):
            text = str(ws.cell(row=row_idx, column=col_idx).value or "")
            max_len = max(max_len, len(text))
        ws.column_dimensions[letter].width = min(max_len + 2, 80)

    wb.save(out)
    return str(out)


def build_report_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# 形式审查报告",
        "",
        f"- 生成时间：{payload.get('generated_at', '')}",
        f"- 源文件：{'纯文本输入' if payload.get('source_file') == 'plain_text_input' else payload.get('source_file', '')}",
        f"- 权利要求数量：{summary.get('claims_count', 0)}",
        f"- 问题总数：{summary.get('issues_total', 0)}",
        f"- 已忽略：{summary.get('issues_ignored', 0)}",
        f"- 有效问题：{summary.get('issues_effective', 0)}",
        "",
        "## 问题明细",
        "",
    ]
    for idx, issue in enumerate(payload.get("issues", []), start=1):
        lines.append(
            f"{idx}. [{_localize_severity(issue.get('severity', ''))}] {_localize_rule_label(issue.get('rule_id', ''))} "
            f"@ {_localize_section(issue.get('section', ''))}"
            + (f"/权利要求{issue.get('claim_num')}" if issue.get("claim_num") is not None else "")
            + (" [已忽略]" if issue.get("ignored") else "")
        )
        lines.append(f"   - {issue.get('message', '')}")
    lines.append("")
    return "\n".join(lines)


def write_report_markdown(path: str, payload: dict[str, Any]) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report_markdown(payload), encoding="utf-8")
    return str(out)
