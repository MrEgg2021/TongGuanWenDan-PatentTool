from __future__ import annotations

from dataclasses import dataclass

from .field_policy import (
    get_business_field_order,
    get_patent_type_mapping,
    get_uncertain_field_order,
)
from .field_registry import is_notice_key_processable
from .models import NoticeMeta
from .notice_name_rules import normalize_notice_name_for_meta


BUSINESS_FIELD_ORDER: tuple[str, ...] = tuple(get_business_field_order())
UNCERTAIN_FIELD_ORDER: tuple[str, ...] = tuple(get_uncertain_field_order())


def extract_patent_type_code_from_app_no(app_no: str) -> str:
    src = str(app_no or "").strip()
    if not src:
        return ""
    upper = src.upper()
    if "PCT/" in upper:
        return ""

    main = src.split(".", 1)[0]
    digits = "".join(ch for ch in main if ch.isdigit())
    if len(digits) >= 12:
        return digits[4]
    if len(digits) >= 8:
        return digits[2]
    return ""


def map_patent_type_display(type_code: str) -> str:
    code = str(type_code or "").strip()
    if not code:
        return ""
    mapping = get_patent_type_mapping()
    return str(mapping.get(code, "") or "")


def infer_patent_type_from_app_no(app_no: str) -> tuple[str, str]:
    code = extract_patent_type_code_from_app_no(app_no)
    label = map_patent_type_display(code)
    return code, label


def build_notice_key(meta: NoticeMeta) -> str:
    code = str(meta.notice_code or "").strip()
    name = str(meta.notice_name or "").strip()
    app_no = str(meta.app_no or "").strip()
    internal_no = str(meta.internal_no or "").strip()

    if code and name:
        return f"{code}|{name}"
    if app_no and name:
        return f"{app_no}|{name}"
    if internal_no and name:
        return f"{internal_no}|{name}"
    if code:
        return code
    if app_no:
        return app_no
    if internal_no:
        return internal_no
    if name:
        return name
    return "unknown"


def _pick_value(raw_fields: dict[str, str], *candidates: str) -> str:
    if not raw_fields:
        return ""
    normalized_items = [
        (str(key or "").strip(), str(value or "").strip())
        for key, value in (raw_fields or {}).items()
        if str(key or "").strip()
    ]
    exact: dict[str, str] = {key: value for key, value in normalized_items}
    upper_items = [(key.upper(), value) for key, value in normalized_items]

    for candidate in candidates:
        lookup = str(candidate or "").strip()
        if not lookup:
            continue
        direct = str(exact.get(lookup, "") or "").strip()
        if direct:
            return direct

    for candidate in candidates:
        lookup = str(candidate or "").strip().upper()
        if not lookup:
            continue
        for key_upper, value in upper_items:
            if key_upper == lookup or key_upper.endswith(f"/{lookup}"):
                text = str(value or "").strip()
                if text:
                    return text
    return ""


def _collect_attachment_yewulx(raw_fields: dict[str, str]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for key, value in (raw_fields or {}).items():
        key_upper = str(key or "").strip().upper()
        if not key_upper:
            continue
        if not key_upper.endswith("/YEWULX"):
            continue
        if "/FUJIAN" not in key_upper:
            continue
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return ";".join(values)


def _normalize_date(raw: str) -> str:
    digits = "".join(ch for ch in str(raw or "").strip() if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return str(raw or "").strip()


def should_skip_by_filter(*, meta: NoticeMeta, raw_fields: dict[str, str]) -> str:
    reasons: list[str] = []
    notice_name = str(meta.notice_name or "").strip()
    notice_key = build_notice_key(meta)
    is_processable, processable_reason = is_notice_key_processable(notice_key)
    if not is_processable:
        reasons.append(str(processable_reason or f"通知书类型不纳入处理：{notice_key}"))

    if "回执" in notice_name and not any("回执" in str(r) for r in reasons):
        reasons.append("通知书名称包含“回执”")

    has_pct = "PCT" in notice_name.upper()
    if not has_pct:
        for key, value in (raw_fields or {}).items():
            key_text = str(key or "").upper()
            if "PCT" in key_text:
                has_pct = True
                break
            value_text = str(value or "").strip().upper()
            if value_text and "PCT" in value_text and (
                "通知书名称" in key_text or key_text.endswith("TONGZHISMC")
            ):
                has_pct = True
                break
    if has_pct and (not is_processable):
        if not any("PCT" in str(r).upper() for r in reasons):
            reasons.append("PCT相关通知书未纳入处理白名单")

    if not reasons:
        return ""
    return "按过滤口径跳过：" + "；".join(reasons)


@dataclass(frozen=True)
class FieldLayers:
    notice_key: str
    business_fields: dict[str, str]
    uncertain_fields: dict[str, str]
    raw_fields: dict[str, str]


def build_field_layers(*, meta: NoticeMeta, raw_fields: dict[str, str]) -> FieldLayers:
    raw_map: dict[str, str] = {}
    for key, value in (raw_fields or {}).items():
        key_text = str(key or "").strip()
        if not key_text:
            continue
        raw_map[key_text] = str(value or "").strip()

    app_no = str(meta.app_no or "").strip() or _pick_value(raw_map, "SHUXINGXX/SHENQINGH", "SHENQINGH")
    _type_code, type_label = infer_patent_type_from_app_no(app_no)
    faminglx_raw = _pick_value(raw_map, "SHUXINGXX/FAMINGLX", "FAMINGLX")
    patent_type_display = type_label or ""
    notice_name_display = normalize_notice_name_for_meta(meta)
    issue_date = str(meta.issue_date or "").strip() or _normalize_date(_pick_value(raw_map, "SHUXINGXX/FAWENR", "FAWENR"))
    apply_date = str(meta.apply_date or "").strip() or _normalize_date(_pick_value(raw_map, "SHUXINGXX/SHENQINGR", "SHENQINGR"))
    applicant = (
        str(meta.applicant or "").strip()
        or _pick_value(
            raw_map,
            "SHUXINGXX/SHENQINGRMC",
            "SHENQINGRMC",
            "SHUXINGXX/SHENQINGREN",
            "SHENQINGREN",
            "SHUXINGXX/SHENQINGRXM",
            "SHENQINGRXM",
            "SHUXINGXX/APPLICANT",
            "APPLICANT",
        )
    )

    all_business_fields = {
        "申请号": app_no,
        "申请日": apply_date,
        "内部编号": str(meta.internal_no or "").strip() or _pick_value(raw_map, "SHUXINGXX/NEIBUBH", "NEIBUBH"),
        "案卷号": str(meta.dossier_no or "").strip() or _pick_value(raw_map, "SHUXINGXX/ANJUANH", "ANJUANH"),
        "通知书名称": notice_name_display
        or _pick_value(raw_map, "SHUXINGXX/TONGZHISMC", "TONGZHISMC"),
        "发文日": issue_date,
        "通知书代码": str(meta.notice_code or "").strip() or _pick_value(raw_map, "SHUXINGXX/TONGZHISBM", "TONGZHISBM"),
        "专利类型": patent_type_display,
        "专利类型(显示)": patent_type_display,
        "期限天": str(meta.limit_days or "").strip() or _pick_value(raw_map, "SHUXINGXX/QIXIAN", "QIXIAN"),
        "逾期日": str(meta.due_date or "").strip() or _pick_value(raw_map, "SHUXINGXX/YUQIRQ", "YUQIRQ"),
        "发明名称": str(meta.invention_name or "").strip() or _pick_value(raw_map, "SHUXINGXX/FAMINGMC", "FAMINGMC"),
        "申请人信息": applicant,
        "收据_缴费人": str(meta.receipt_payer or "").strip(),
        "收据_申请号": str(meta.receipt_app_no or "").strip(),
        "收据_专利类型": str(meta.receipt_patent_type or "").strip(),
        "收据_缴费项目": str(meta.receipt_fee_item or "").strip(),
        "收据_缴费项目首项": str(meta.receipt_fee_item_first or meta.receipt_fee_item or "").strip(),
        "收据_缴费项目汇总": str(meta.receipt_fee_item_summary or meta.receipt_fee_item_first or meta.receipt_fee_item or "").strip(),
        "收据_缴费项目明细": str(meta.receipt_fee_item_detail or "").strip(),
        "收据_缴费金额": str(meta.receipt_amount or "").strip(),
        "收据_缴费金额元": f"{meta.receipt_amount}元" if str(meta.receipt_amount or "").strip() and not str(meta.receipt_amount).strip().endswith("元") else str(meta.receipt_amount or "").strip(),
        "收据_缴费日期": str(meta.receipt_payment_date or "").strip(),
        "收据_缴费方式": str(meta.receipt_payment_method or "").strip(),
        "收据_订单号": str(meta.receipt_order_no or "").strip(),
        "收据_票据代码": str(meta.receipt_ticket_code or "").strip(),
        "收据_票据号码": str(meta.receipt_ticket_no or "").strip(),
        "收据_开票日期": str(meta.receipt_invoice_date or "").strip(),
        "收据_交款人统一社会信用代码": str(meta.receipt_payer_credit_code or "").strip(),
        "收据_校验码": str(meta.receipt_check_code or "").strip(),
        "收据_收款单位": str(meta.receipt_payee_unit or "").strip(),
        "收据_复核人": str(meta.receipt_reviewer or "").strip(),
        "收据_收款人": str(meta.receipt_collector or "").strip(),
    }

    business_order = get_business_field_order()
    business_fields = {
        field_name: str(all_business_fields.get(field_name, "") or "")
        for field_name in business_order
    }
    if ("专利类型" in business_fields) and ("专利类型(显示)" not in business_fields):
        business_fields["专利类型(显示)"] = str(business_fields.get("专利类型", "") or "")

    all_uncertain_fields = {
        "DMHFLAG_raw": _pick_value(raw_map, "SHUXINGXX/DMHFLAG", "DMHFLAG"),
        "FAMINGLX_raw": faminglx_raw,
        "附件YEWULX_raw_set": _collect_attachment_yewulx(raw_map),
    }
    uncertain_order = get_uncertain_field_order()
    uncertain_fields = {
        field_name: str(all_uncertain_fields.get(field_name, "") or "")
        for field_name in uncertain_order
    }

    return FieldLayers(
        notice_key=build_notice_key(meta),
        business_fields=business_fields,
        uncertain_fields=uncertain_fields,
        raw_fields=raw_map,
    )


__all__ = [
    "BUSINESS_FIELD_ORDER",
    "FieldLayers",
    "UNCERTAIN_FIELD_ORDER",
    "build_field_layers",
    "build_notice_key",
    "extract_patent_type_code_from_app_no",
    "infer_patent_type_from_app_no",
    "map_patent_type_display",
    "should_skip_by_filter",
]
