from __future__ import annotations

import re
from dataclasses import dataclass

import fitz


_REASON_KEYWORDS: tuple[str, ...] = (
    "不符合",
    "不具备",
    "不能授予专利权",
    "被驳回",
    "驳回",
    "缺陷",
)

_CLAUSE_RE = re.compile(
    r"(专利法(?:实施细则)?第[0-9一二三四五六七八九十百零〇]+条(?:第[0-9一二三四五六七八九十百零〇]+款)?)"
)
_CN_PUB_RE = re.compile(r"CN\d{6,12}[A-Z]?")
_PHONE_RE = re.compile(r"(?<!\d)(\d{3,4}-\d{7,8}|\d{7,12})(?!\d)")
_CLAIM_ID_RE = re.compile(r"权利要求[0-9一二三四五六七八九十百零〇,\-，、至和]+")


@dataclass(frozen=True)
class ExamPdfExtractResult:
    status: str = "失败"
    error: str = ""
    reject_reasons: str = ""
    clauses: str = ""
    cn_pubnos: str = ""
    examiner_name: str = ""
    examiner_phone: str = ""


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").strip())


def _normalize_line(text: str) -> str:
    line = str(text or "").replace("\u3000", " ").replace("\r", " ").replace("\t", " ").strip()
    line = re.sub(r"\s+", " ", line)
    return line


def _dedup_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = _compact(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _is_valid_reason_line(line: str) -> bool:
    compact = _compact(line)
    if not compact:
        return False
    if not any(keyword in compact for keyword in _REASON_KEYWORDS):
        return False
    if compact.startswith("权利要求"):
        if _CLAIM_ID_RE.search(compact) is None:
            return False
    return True


def _extract_reason_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if _is_valid_reason_line(line):
            out.append(line)
    return _dedup_keep_order(out)


def _extract_clauses(reason_lines: list[str]) -> list[str]:
    clauses: list[str] = []
    for line in reason_lines:
        compact = _compact(line)
        for matched in _CLAUSE_RE.findall(compact):
            if matched:
                clauses.append(matched)
    return _dedup_keep_order(clauses)


def _extract_cn_pubnos(text: str) -> list[str]:
    compact = _compact(text)
    return _dedup_keep_order([match.group(0) for match in _CN_PUB_RE.finditer(compact)])


def _extract_examiner_name(lines: list[str]) -> str:
    for raw in lines:
        compact = _compact(raw)
        if not compact:
            continue
        if "审查员" not in compact:
            continue
        if "代码" in compact:
            continue
        if "电话" in compact:
            continue
        match = re.search(r"(?:审查员姓名|审查员)[:：]?([\u4e00-\u9fff]{2,8})", compact)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def _extract_examiner_phone(lines: list[str]) -> str:
    for raw in lines:
        compact = _compact(raw)
        if not compact:
            continue
        if ("联系电话" not in compact) and ("审查员电话" not in compact):
            continue
        match = _PHONE_RE.search(compact)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def extract_exam_pdf_fields(pdf_bytes: bytes) -> ExamPdfExtractResult:
    if not pdf_bytes:
        return ExamPdfExtractResult(status="失败", error="主PDF为空")
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        return ExamPdfExtractResult(status="失败", error=f"打开PDF失败：{exc}")

    try:
        text = "\n".join(doc[page_index].get_text("text") for page_index in range(doc.page_count))
    except Exception as exc:
        return ExamPdfExtractResult(status="失败", error=f"提取文本失败：{exc}")
    finally:
        doc.close()

    lines = [_normalize_line(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line]

    reason_lines = _extract_reason_lines(lines)
    clauses = _extract_clauses(reason_lines)
    cn_pubnos = _extract_cn_pubnos(text)
    examiner_name = _extract_examiner_name(lines)
    examiner_phone = _extract_examiner_phone(lines)

    return ExamPdfExtractResult(
        status="成功",
        reject_reasons="；".join(reason_lines),
        clauses="；".join(clauses),
        cn_pubnos="；".join(cn_pubnos),
        examiner_name=examiner_name,
        examiner_phone=examiner_phone,
    )


__all__ = ["ExamPdfExtractResult", "extract_exam_pdf_fields"]
