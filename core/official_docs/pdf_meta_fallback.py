from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field

import fitz

from .field_governance import infer_patent_type_from_app_no
from .field_registry import (
    PATENT_GROUP_UNKNOWN,
    RECEIPT_TYPE_KEY,
    get_supported_type_catalog,
    infer_patent_group_from_label,
    infer_patent_group_from_type_key,
)
from .kind_detect import detect_notice_kind
from .models import NoticeMeta, ReceiptFeeLineItem
from .notice_name_rules import normalize_notice_name
from .template_render import build_meta_from_list_fields
from .zip_reader import NoticeZipReader, ZipEntry


_APP_NO_LABEL_RE = re.compile(
    r"(?:申请号|专利号|国际申请号|国际申请日和国际申请号通知书)\s*[:：]?\s*([A-Za-z0-9./-]{8,})",
    re.IGNORECASE,
)
_APP_NO_RE = re.compile(r"\b\d{12,13}(?:[Xx]|\.[0-9Xx])?\b")
_PCT_APP_NO_RE = re.compile(r"PCT/[A-Z]{2}\d{4}/\d{4,}", re.IGNORECASE)
_DATE_BODY_RE = r"20\d{2}\s*(?:[.\-/年月]\s*\d{1,2}\s*){2}\s*日?"
_ISSUE_DATE_LABEL_RE = re.compile(
    rf"(?:发文日|发文日期|日期)\s*[:：]?\s*((?<!\d){_DATE_BODY_RE}(?!\d))"
)
_DATE_RE = re.compile(rf"(?<!\d)({_DATE_BODY_RE})(?!\d)")
_DOC_SERIAL_BODY_RE = r"[0-9]{14,20}"
_DOC_SERIAL_LABEL_RE = re.compile(
    rf"(?:发文序号|发文编号|Serial)\s*[:：]?\s*((?<!\d){_DOC_SERIAL_BODY_RE}(?!\d))",
    re.IGNORECASE,
)
_DOC_SERIAL_RE = re.compile(rf"(?<!\d)({_DOC_SERIAL_BODY_RE})(?!\d)")
_INVENTION_LABEL_RE = re.compile(r"(?:发明名称或实用新型名称|发明创造名称|发明名称)\s*[:：]?\s*(.+)")
_HEADER_NOTICE_CODE_RE = re.compile(r"^\d{5,6}$")
_TITLE_KEYWORDS: tuple[str, ...] = ("通知书", "决定书", "证书", "报告", "回执", "收据")
_INVENTION_LABELS: tuple[str, ...] = ("发明名称或实用新型名称", "发明创造名称", "发明名称")
_ISSUE_DATE_LABELS: tuple[str, ...] = ("发文日", "发文日期", "日期")
_DOC_SERIAL_LABELS: tuple[str, ...] = ("发文序号", "发文编号", "Serial")
_LABEL_LEADING_NOISE_RE = re.compile(r"^[\s:：=\-—_~*·•,.;；、\[{(<（【《]+")
_RECEIPT_TITLE = "中央非税收入统一票据（电子）"
_RECEIPT_APP_INFO_RE = re.compile(
    r"申请号[:：]\s*(?P<apps>[^_\n]+)_缴费日期[:：]\s*(?P<pay_date>[^_\n]+)_"
    r"缴费方式[:：]\s*(?P<method>[^_\n]+)_订单号[:：]\s*(?P<order>[0-9A-Za-z-]+)"
)
_RECEIPT_APP_NO_RE = re.compile(r"\b\d{12}[0-9Xx]?(?:\.\d)?\b")
_MONEY_RE = re.compile(r"^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})$")
_TICKET_CODE_RE = re.compile(r"^\d{8}$")
_TICKET_NO_RE = re.compile(r"^\d{10,12}$")
_RECEIPT_ITEM_CODE_RE = re.compile(r"^(?P<code>\d{10,12})(?:\s+(?P<name>.+))?$")


def _build_label_only_re(labels: tuple[str, ...]):
    escaped = [re.escape(str(label or "")) for label in labels if str(label or "").strip()]
    if not escaped:
        return re.compile(r"$^")
    return re.compile(r"(?:%s)" % "|".join(escaped), re.IGNORECASE)


_ISSUE_DATE_LABEL_ONLY_RE = _build_label_only_re(_ISSUE_DATE_LABELS)
_DOC_SERIAL_LABEL_ONLY_RE = _build_label_only_re(_DOC_SERIAL_LABELS)


@dataclass(frozen=True)
class PdfFallbackCandidate:
    entry: ZipEntry
    meta: NoticeMeta
    notice_kind: str
    matched_type_key: str = ""
    score: int = 0
    title_line: str = ""


@dataclass(frozen=True)
class PdfFallbackParseResult:
    ok: bool
    meta: NoticeMeta = field(default_factory=NoticeMeta)
    notice_kind: str = "unknown"
    matched_type_key: str = ""
    flat_fields: dict[str, str] = field(default_factory=dict)
    main_pdf_raw_name: str = ""
    error: str = ""


def _compact(text: str) -> str:
    return "".join(re.findall(r"[0-9A-Za-z\u4e00-\u9fff]+", str(text or "").strip())).lower()


def _normalize_app_no(value: str) -> str:
    raw = str(value or "").strip().replace(" ", "")
    if not raw:
        return ""
    pct = _PCT_APP_NO_RE.search(raw.upper())
    if pct:
        return str(pct.group(0) or "").strip().upper()
    matched = _APP_NO_RE.search(raw)
    if matched:
        return str(matched.group(0) or "").strip()
    return raw


def _normalize_receipt_date(raw: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(raw or "").strip())
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return str(raw or "").strip()


def _extract_text_lines(pdf_bytes: bytes) -> list[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        lines: list[str] = []
        for index in range(doc.page_count):
            page = doc[index]
            page_text = str(page.get_text("text") or "")
            for raw_line in page_text.splitlines():
                line = str(raw_line or "").replace("\u3000", " ").strip()
                line = re.sub(r"\s+", " ", line)
                if line:
                    lines.append(line)
        return lines
    finally:
        doc.close()


def _extract_app_no(lines: list[str]) -> str:
    for line in lines:
        pct = _PCT_APP_NO_RE.search(line.upper())
        if pct:
            return _normalize_app_no(pct.group(0))
        labeled = _APP_NO_LABEL_RE.search(line)
        if labeled:
            return _normalize_app_no(labeled.group(1))
    for line in lines:
        matched = _APP_NO_RE.search(line)
        if matched:
            return _normalize_app_no(matched.group(0))
    return ""


def _normalize_labeled_tail(text: str) -> str:
    return _LABEL_LEADING_NOISE_RE.sub("", str(text or "").strip())


def _extract_labeled_match(
    lines: list[str],
    *,
    label_re,
    value_re,
    search_limit: int,
    lookahead: int = 3,
) -> str:
    limited_lines = list(lines[:search_limit])
    for index, raw_line in enumerate(limited_lines):
        line = str(raw_line or "").strip()
        matched_label = label_re.search(line)
        if not matched_label:
            continue

        tail = _normalize_labeled_tail(line[matched_label.end() :])
        matched_value = value_re.search(tail)
        if matched_value:
            return str(matched_value.group(1) or matched_value.group(0) or "").strip()

        for next_line in limited_lines[index + 1 : index + 1 + max(1, int(lookahead))]:
            next_candidate = _normalize_labeled_tail(next_line)
            matched_value = value_re.search(next_candidate)
            if matched_value:
                return str(matched_value.group(1) or matched_value.group(0) or "").strip()
    return ""


def _extract_issue_date(lines: list[str]) -> str:
    labeled_value = _extract_labeled_match(
        lines,
        label_re=_ISSUE_DATE_LABEL_ONLY_RE,
        value_re=_DATE_RE,
        search_limit=20,
        lookahead=3,
    )
    if labeled_value:
        return labeled_value
    for line in lines[:20]:
        labeled = _ISSUE_DATE_LABEL_RE.search(line)
        if labeled:
            return str(labeled.group(1) or "").strip()
    for line in lines[:20]:
        matched = _DATE_RE.search(line)
        if matched:
            return str(matched.group(0) or "").strip()
    return ""


def extract_issue_date_from_pdf_lines(lines: list[str]) -> str:
    return _extract_issue_date(lines)


def _extract_doc_serial(lines: list[str]) -> str:
    labeled_value = _extract_labeled_match(
        lines,
        label_re=_DOC_SERIAL_LABEL_ONLY_RE,
        value_re=_DOC_SERIAL_RE,
        search_limit=30,
        lookahead=3,
    )
    if labeled_value:
        return labeled_value
    for line in lines[:30]:
        labeled = _DOC_SERIAL_LABEL_RE.search(line)
        if labeled:
            return str(labeled.group(1) or "").strip()
    return ""


def extract_doc_serial_from_pdf_lines(lines: list[str]) -> str:
    return _extract_doc_serial(lines)


def _extract_invention_name(lines: list[str]) -> str:
    for index, line in enumerate(lines[:80]):
        labeled = _INVENTION_LABEL_RE.search(line)
        if labeled:
            value = str(labeled.group(1) or "").strip()
            if value:
                return value

        compact = str(line or "").strip().rstrip("：:")
        if compact in _INVENTION_LABELS:
            next_index = index + 1
            if next_index < len(lines):
                value = str(lines[next_index] or "").strip()
                if value and value not in _INVENTION_LABELS:
                    return value
    return ""


def _title_candidates(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines[:20]:
        if any(keyword in line for keyword in _TITLE_KEYWORDS):
            out.append(line)
    return out or lines[:5]


def _extract_notice_type(
    *,
    lines: list[str],
    app_no: str,
) -> tuple[str, str, str]:
    text_full = _compact("\n".join(lines[:80]))
    titles = _title_candidates(lines)
    titles_compact = [_compact(line) for line in titles]
    patent_type_code, patent_type_label = infer_patent_type_from_app_no(app_no)
    app_group = infer_patent_group_from_label(patent_type_label)

    best: tuple[int, int, str, str, str] | None = None
    for item in get_supported_type_catalog():
        display_name = str(item.get("display_name", "") or "").strip()
        type_key = str(item.get("key", "") or "").strip()
        if not display_name or not type_key:
            continue
        code_part = type_key.split("|", 1)[0] if "|" in type_key else ""
        normalized_name = normalize_notice_name(
            notice_code=code_part,
            notice_name=display_name,
            patent_type_label=patent_type_label,
            force_by_code=True,
        )
        name_key = _compact(normalized_name or display_name)
        if not name_key:
            continue

        score = -1
        title_line = ""
        exact_title = next((line for line, key in zip(titles, titles_compact) if key == name_key), "")
        if exact_title:
            score = 320
            title_line = exact_title
        else:
            partial_title = next((line for line, key in zip(titles, titles_compact) if name_key in key), "")
            if partial_title:
                score = 260
                title_line = partial_title
            elif name_key in text_full:
                score = 220

        if score < 0:
            continue

        type_group = infer_patent_group_from_type_key(type_key, display_name=display_name)
        if app_group and app_group != PATENT_GROUP_UNKNOWN:
            if type_group == app_group:
                score += 35
            elif type_group != PATENT_GROUP_UNKNOWN:
                score -= 25

        if patent_type_code and code_part and code_part.startswith(("21", "22", "23", "40")):
            if code_part.startswith(f"2{patent_type_code}") or code_part.startswith(f"4{patent_type_code}"):
                score += 20

        score += 5 if bool(item.get("processable", True)) else 0
        candidate = (score, len(name_key), type_key, normalized_name or display_name, title_line)
        if best is None or candidate > best:
            best = candidate

    if best is None:
        return "", "", ""
    return best[2], best[3], best[4]


def _extract_header_notice_code(lines: list[str]) -> str:
    for line in lines[:5]:
        compact = re.sub(r"\s+", "", str(line or ""))
        if _HEADER_NOTICE_CODE_RE.fullmatch(compact):
            return compact
    return ""


def _build_flat_fields(meta: NoticeMeta) -> dict[str, str]:
    fields: dict[str, str] = {}

    def _put(*keys: str, value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        for key in keys:
            key_text = str(key or "").strip()
            if key_text:
                fields[key_text] = text

    _put("SHENQINGH", "SHUXINGXX/SHENQINGH", value=meta.app_no)
    _put("TONGZHISMC", "SHUXINGXX/TONGZHISMC", value=meta.notice_name)
    _put("FAMINGMC", "SHUXINGXX/FAMINGMC", value=meta.invention_name)
    _put("TONGZHISBM", "SHUXINGXX/TONGZHISBM", value=meta.notice_code)
    _put("FAWENR", "SHUXINGXX/FAWENR", value=meta.issue_date_raw or meta.issue_date)
    _put("FAWENXLH", "SHUXINGXX/FAWENXLH", value=meta.doc_serial)
    _put("NEIBUBH", "SHUXINGXX/NEIBUBH", value=meta.internal_no)
    _put("ANJUANH", "SHUXINGXX/ANJUANH", value=meta.dossier_no)
    _put("SHENQINGR", "SHUXINGXX/SHENQINGR", value=meta.apply_date)
    _put("收据_缴费人", value=meta.receipt_payer)
    _put("收据_申请号", value=meta.receipt_app_no)
    _put("收据_专利类型", value=meta.receipt_patent_type)
    _put("收据_缴费项目", value=meta.receipt_fee_item)
    _put("收据_缴费项目首项", value=meta.receipt_fee_item_first)
    _put("收据_缴费项目汇总", value=meta.receipt_fee_item_summary)
    _put("收据_缴费项目明细", value=meta.receipt_fee_item_detail)
    _put("收据_缴费金额", value=meta.receipt_amount)
    if meta.receipt_amount:
        amount_yuan = meta.receipt_amount if str(meta.receipt_amount).endswith("元") else f"{meta.receipt_amount}元"
        _put("收据_缴费金额元", value=amount_yuan)
    _put("收据_缴费日期", value=meta.receipt_payment_date)
    _put("收据_缴费方式", value=meta.receipt_payment_method)
    _put("收据_订单号", value=meta.receipt_order_no)
    _put("收据_票据代码", value=meta.receipt_ticket_code)
    _put("收据_票据号码", value=meta.receipt_ticket_no)
    _put("收据_开票日期", value=meta.receipt_invoice_date)
    _put("收据_交款人统一社会信用代码", value=meta.receipt_payer_credit_code)
    _put("收据_校验码", value=meta.receipt_check_code)
    _put("收据_收款单位", value=meta.receipt_payee_unit)
    _put("收据_复核人", value=meta.receipt_reviewer)
    _put("收据_收款人", value=meta.receipt_collector)
    return fields


def _unique_keep_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip().upper()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _receipt_tail_after_app_info(lines: list[str], app_info_line: str) -> tuple[list[str], list[str]]:
    try:
        index = next(idx for idx, line in enumerate(lines) if str(line or "").strip() == app_info_line)
    except StopIteration:
        return lines, []
    return lines[:index], lines[index + 1 :]


def _extract_receipt_ticket_code(preceding: list[str]) -> str:
    for line in reversed(preceding):
        text = str(line or "").strip()
        if _TICKET_CODE_RE.match(text):
            return text
    return ""


def _extract_receipt_ticket_no(preceding: list[str]) -> str:
    for line in reversed(preceding):
        text = str(line or "").strip()
        if _TICKET_NO_RE.match(text) and not _TICKET_CODE_RE.match(text):
            return text
    return ""


def _find_receipt_ticket_code_index(preceding: list[str]) -> int:
    for index in range(len(preceding) - 1, -1, -1):
        text = str(preceding[index] or "").strip()
        if _TICKET_CODE_RE.match(text):
            return index
    return -1


def _extract_receipt_payer_credit_code(preceding: list[str]) -> str:
    index = _find_receipt_ticket_code_index(preceding)
    if index >= 2:
        return str(preceding[index - 2] or "").strip()
    return ""


def _extract_receipt_check_code(preceding: list[str]) -> str:
    index = _find_receipt_ticket_code_index(preceding)
    if index >= 1:
        return str(preceding[index - 1] or "").strip()
    return ""


def _extract_receipt_amount(preceding: list[str], tail: list[str]) -> str:
    for source in (preceding, tail):
        for line in source:
            text = str(line or "").strip()
            if _MONEY_RE.match(text):
                return text
    return ""


def _extract_receipt_parties(tail: list[str]) -> tuple[str, str, str, str, int]:
    for index, line in enumerate(tail):
        unit = str(line or "").strip()
        if not unit or "国家知识产权局" not in unit:
            continue
        payer = str(tail[index + 1] or "").strip() if index + 1 < len(tail) else ""
        reviewer = str(tail[index + 2] or "").strip() if index + 2 < len(tail) else ""
        collector = str(tail[index + 3] or "").strip() if index + 3 < len(tail) else ""
        return unit, payer, reviewer, collector, index + 4

    for index, line in enumerate(tail):
        text = str(line or "").strip()
        if not text or "国家知识产权局" in text:
            continue
        if re.search(r"[\u4e00-\u9fff]", text) and not any(word in text for word in ("专利", "元整")):
            return "", text, "", "", index + 1
    return "", "", "", "", 0


def _normalize_receipt_item_name(raw: str) -> str:
    return str(raw or "").strip(" ：:")


def _extract_receipt_fee_items(tail: list[str], *, start_index: int) -> list[ReceiptFeeLineItem]:
    items: list[ReceiptFeeLineItem] = []
    index = max(0, int(start_index))
    while index < len(tail):
        text = str(tail[index] or "").strip()
        if not text:
            index += 1
            continue

        code_match = _RECEIPT_ITEM_CODE_RE.match(text)
        if not code_match:
            index += 1
            continue

        code = str(code_match.group("code") or "").strip()
        inline_name = _normalize_receipt_item_name(str(code_match.group("name") or ""))
        if inline_name:
            amount_index = index + 1
            amount = str(tail[amount_index] or "").strip() if amount_index < len(tail) else ""
            if _MONEY_RE.match(amount):
                items.append(ReceiptFeeLineItem(code=code, name=inline_name, amount=amount))
                index = amount_index + 1
                continue

        name_index = index + 1
        amount_index = index + 2
        name = _normalize_receipt_item_name(str(tail[name_index] or "")) if name_index < len(tail) else ""
        amount = str(tail[amount_index] or "").strip() if amount_index < len(tail) else ""
        if name and _MONEY_RE.match(amount):
            items.append(ReceiptFeeLineItem(code=code, name=name, amount=amount))
            index = amount_index + 1
            continue

        index += 1
    return items


def _receipt_item_summary(items: list[ReceiptFeeLineItem]) -> str:
    return "+".join([str(item.name or "").strip() for item in items if str(item.name or "").strip()])


def _receipt_item_detail(items: list[ReceiptFeeLineItem]) -> str:
    parts: list[str] = []
    for item in items:
        name = str(item.name or "").strip()
        if not name:
            continue
        amount = str(item.amount or "").strip()
        if amount:
            parts.append(f"{name}{amount if amount.endswith('元') else amount + '元'}")
        else:
            parts.append(name)
    return "+".join(parts)


def _extract_receipt_invoice_date(tail: list[str]) -> str:
    for line in reversed(tail):
        text = str(line or "").strip()
        matched = _DATE_RE.search(text)
        if matched:
            return str(matched.group(0) or "").strip()
    return ""


def _extract_receipt_candidate(entry: ZipEntry, lines: list[str]) -> PdfFallbackCandidate | None:
    full_text = "\n".join(lines)
    if _RECEIPT_TITLE not in full_text:
        return None
    matched = _RECEIPT_APP_INFO_RE.search(full_text)
    if not matched:
        return None

    app_numbers = _unique_keep_order(_RECEIPT_APP_NO_RE.findall(str(matched.group("apps") or "")))
    if not app_numbers:
        return None

    app_no = "+".join(app_numbers)
    patent_types = _unique_keep_order([infer_patent_type_from_app_no(app)[1] for app in app_numbers])
    patent_type = "+".join([item for item in patent_types if item])
    app_info_line = str(matched.group(0) or "").strip()
    preceding, tail = _receipt_tail_after_app_info(lines, app_info_line)
    ticket_code = _extract_receipt_ticket_code(preceding)
    ticket_no = _extract_receipt_ticket_no(preceding)
    amount = _extract_receipt_amount(preceding, tail)
    payer_credit_code = _extract_receipt_payer_credit_code(preceding)
    check_code = _extract_receipt_check_code(preceding)
    payee_unit, payer, reviewer, collector, item_start_index = _extract_receipt_parties(tail)
    fee_items = _extract_receipt_fee_items(tail, start_index=item_start_index)
    fee_item_first = str(fee_items[0].name or "").strip() if fee_items else ""
    fee_item_summary = _receipt_item_summary(fee_items)
    fee_item_detail = _receipt_item_detail(fee_items)
    fee_item = fee_item_first
    invoice_date_raw = _extract_receipt_invoice_date(tail)
    invoice_date = _normalize_receipt_date(invoice_date_raw)
    pay_date_raw = str(matched.group("pay_date") or "").strip()
    pay_date = _normalize_receipt_date(pay_date_raw)

    if not (ticket_no or fee_item):
        return None

    meta = NoticeMeta(
        notice_code="10071",
        notice_name="电子提交收据",
        app_no=app_no,
        patent_type=patent_type,
        applicant=payer,
        issue_date_raw=pay_date_raw,
        issue_date=pay_date,
        receipt_payer=payer,
        receipt_app_no=app_no,
        receipt_patent_type=patent_type,
        receipt_fee_item=fee_item,
        receipt_fee_items=tuple(fee_items),
        receipt_fee_item_first=fee_item_first,
        receipt_fee_item_summary=fee_item_summary,
        receipt_fee_item_detail=fee_item_detail,
        receipt_amount=amount,
        receipt_payment_date=pay_date,
        receipt_payment_method=str(matched.group("method") or "").strip(),
        receipt_order_no=str(matched.group("order") or "").strip(),
        receipt_ticket_code=ticket_code,
        receipt_ticket_no=ticket_no,
        receipt_invoice_date=invoice_date,
        receipt_payer_credit_code=payer_credit_code,
        receipt_check_code=check_code,
        receipt_payee_unit=payee_unit,
        receipt_reviewer=reviewer,
        receipt_collector=collector,
    )
    score = 400 + (20 if payer else 0) + (20 if fee_item else 0) + (20 if amount else 0)
    return PdfFallbackCandidate(
        entry=entry,
        meta=meta,
        notice_kind=RECEIPT_TYPE_KEY,
        matched_type_key=RECEIPT_TYPE_KEY,
        score=score,
        title_line=_RECEIPT_TITLE,
    )


def _is_minimal_meta(meta: NoticeMeta) -> bool:
    app_no = str(meta.app_no or "").strip()
    hint = str(meta.notice_name or "").strip() or str(meta.notice_code or "").strip() or str(meta.issue_date_raw or "").strip()
    return bool(app_no and hint)


def _extract_candidate(entry: ZipEntry, pdf_bytes: bytes) -> PdfFallbackCandidate | None:
    lines = _extract_text_lines(pdf_bytes)
    if not lines:
        return None

    receipt = _extract_receipt_candidate(entry, lines)
    if receipt is not None:
        return receipt

    app_no = _extract_app_no(lines)
    issue_date_raw = _extract_issue_date(lines)
    doc_serial = _extract_doc_serial(lines)
    invention_name = _extract_invention_name(lines)
    matched_type_key, matched_notice_name, title_line = _extract_notice_type(lines=lines, app_no=app_no)
    notice_name = str(title_line or matched_notice_name or "").strip()
    notice_code = ""
    if "|" in matched_type_key:
        notice_code = str(matched_type_key.split("|", 1)[0] or "").strip()
    header_code = _extract_header_notice_code(lines)
    if matched_notice_name and header_code:
        notice_code = header_code
        matched_type_key = f"{header_code}|{notice_name or matched_notice_name}"

    _kind, _kind_text, round_text = detect_notice_kind(notice_name)
    meta = build_meta_from_list_fields(
        {
            "SHENQINGH": app_no,
            "TONGZHISMC": notice_name,
            "FAMINGMC": invention_name,
            "TONGZHISBM": notice_code,
            "FAWENR": issue_date_raw,
            "FAWENXLH": doc_serial,
        },
        notice_round=round_text,
    )
    if not _is_minimal_meta(meta):
        return None

    score = 0
    if meta.app_no:
        score += 140
    if meta.notice_name:
        score += 150
    if meta.notice_code:
        score += 40
    if meta.issue_date_raw:
        score += 20
    if meta.doc_serial:
        score += 20
    if title_line:
        score += 30

    return PdfFallbackCandidate(
        entry=entry,
        meta=meta,
        notice_kind=_kind,
        matched_type_key=matched_type_key,
        score=score,
        title_line=title_line,
    )


def resolve_pdf_fallback_notice(zip_reader: NoticeZipReader) -> PdfFallbackParseResult:
    pdfs = list(zip_reader.iter_pdfs())
    if not pdfs:
        return PdfFallbackParseResult(
            ok=False,
            error="缺少 list.xml 且 ZIP 内未找到可用于命名的 PDF",
        )

    candidates: list[PdfFallbackCandidate] = []
    for entry in pdfs:
        try:
            pdf_bytes = zip_reader.read_bytes(entry.raw_name)
            candidate = _extract_candidate(entry, pdf_bytes)
        except Exception:
            candidate = None
        if candidate is not None:
            candidates.append(candidate)

    if not candidates:
        return PdfFallbackParseResult(
            ok=False,
            error="缺少 list.xml 且 PDF 未识别出最小命名字段",
        )

    candidates.sort(
        key=lambda item: (
            int(item.score),
            1 if str(item.meta.notice_code or "").strip() else 0,
            -len(str(item.entry.raw_name or "")),
            str(item.entry.display_name or item.entry.raw_name or ""),
        ),
        reverse=True,
    )
    best = candidates[0]
    return PdfFallbackParseResult(
        ok=True,
        meta=best.meta,
        notice_kind=best.notice_kind,
        matched_type_key=best.matched_type_key,
        flat_fields=_build_flat_fields(best.meta),
        main_pdf_raw_name=best.entry.raw_name,
    )


def parse_pdf_fallback_bytes(
    pdf_bytes: bytes,
    *,
    raw_name: str = "standalone.pdf",
    display_name: str = "standalone.pdf",
) -> PdfFallbackParseResult:
    if not pdf_bytes:
        return PdfFallbackParseResult(ok=False, error="PDF 字节为空")
    entry_name = str(raw_name or "standalone.pdf").strip() or "standalone.pdf"
    entry = ZipEntry(
        raw_name=entry_name,
        display_name=str(display_name or entry_name).strip() or entry_name,
        info=zipfile.ZipInfo(entry_name),
    )
    try:
        candidate = _extract_candidate(entry, pdf_bytes)
    except Exception as exc:
        return PdfFallbackParseResult(ok=False, error=str(exc))
    if candidate is None:
        return PdfFallbackParseResult(ok=False, error="PDF 未识别出可用通知书元数据")
    return PdfFallbackParseResult(
        ok=True,
        meta=candidate.meta,
        notice_kind=candidate.notice_kind,
        matched_type_key=candidate.matched_type_key,
        flat_fields=_build_flat_fields(candidate.meta),
        main_pdf_raw_name=candidate.entry.raw_name,
    )


__all__ = [
    "PdfFallbackCandidate",
    "PdfFallbackParseResult",
    "extract_doc_serial_from_pdf_lines",
    "extract_issue_date_from_pdf_lines",
    "parse_pdf_fallback_bytes",
    "resolve_pdf_fallback_notice",
]
