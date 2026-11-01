from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from core.config import sanitize_filename

from .field_governance import build_notice_key
from .field_registry import FILENAME_FIELDS, RECEIPT_TYPE_KEY, get_type_tokens, normalize_notice_type
from .kind_detect import detect_notice_kind
from .models import NamingGroupConfig, NoticeAliasRule, NoticeKind, NoticeMeta, NoticeTypeNamingConfig, ProcessOptions
from .notice_name_rules import normalize_notice_name_for_meta

DEFAULT_FILENAME_FIELDS: tuple[str, ...] = ("专利类型", "发明名称", "申请号", "通知书名称", "发文日")
DEFAULT_RECEIPT_FILENAME_FIELDS: tuple[str, ...] = (
    "收据",
    "收据_缴费人",
    "收据_申请号",
    "收据_专利类型",
    "收据_缴费项目汇总",
    "收据_缴费金额元",
)

DEFAULT_ALIAS_RULES: dict[str, tuple[NoticeAliasRule, ...]] = {
    "exam_opinion": (
        NoticeAliasRule(notice_name="第一次审查意见通知书", short_name="一审", enabled=False),
    ),
    "rectification": (
        NoticeAliasRule(notice_name="第一次补正通知书", short_name="一补", enabled=False),
    ),
}

_INVALID_FILENAME_SEPARATOR_CHARS = set('\\/:*?"<>|')


@dataclass(frozen=True)
class NoticeNamingOutput:
    output_pdf_name: str
    archive_rel_dir: str
    naming_mode: str
    display_notice_name: str
    parts: list[str]


@dataclass(frozen=True)
class NoticeNamingPreviewOutput:
    preview_pdf_name: str
    naming_mode: str
    display_notice_name: str
    parts: list[str]


def default_alias_rules_for_type(notice_type: str | NoticeKind) -> list[NoticeAliasRule]:
    notice_key = normalize_notice_type(notice_type)
    return list(DEFAULT_ALIAS_RULES.get(notice_key, ()))


def default_naming_config_for_type(notice_type: str | NoticeKind) -> NoticeTypeNamingConfig:
    notice_key = normalize_notice_type(notice_type)
    filename_fields = list(DEFAULT_RECEIPT_FILENAME_FIELDS) if notice_key == RECEIPT_TYPE_KEY else list(DEFAULT_FILENAME_FIELDS)
    return NoticeTypeNamingConfig(
        naming_mode="default",
        filename_fields=filename_fields,
        alias_rules=default_alias_rules_for_type(notice_key),
    )


def _normalize_alias_rules(raw_rules: object) -> list[NoticeAliasRule]:
    normalized: list[NoticeAliasRule] = []
    for raw in raw_rules if isinstance(raw_rules, Iterable) else []:
        if isinstance(raw, NoticeAliasRule):
            notice_name = str(raw.notice_name or "").strip()
            short_name = str(raw.short_name or "").strip()
            if notice_name and short_name:
                normalized.append(NoticeAliasRule(notice_name=notice_name, short_name=short_name, enabled=bool(raw.enabled)))
            continue
        if not isinstance(raw, dict):
            continue
        notice_name = str(raw.get("notice_name", "") or "").strip()
        short_name = str(raw.get("short_name", "") or "").strip()
        enabled = bool(raw.get("enabled", False))
        if notice_name and short_name:
            normalized.append(NoticeAliasRule(notice_name=notice_name, short_name=short_name, enabled=enabled))
    return normalized


def _normalize_filename_fields(raw_fields: object, *, notice_type: str | NoticeKind) -> list[str]:
    allowed = set(get_type_tokens(notice_type))
    if not allowed:
        allowed = set(FILENAME_FIELDS)
    if normalize_notice_type(notice_type) == RECEIPT_TYPE_KEY:
        allowed.add("收据_缴费项目")
    legacy_aliases = {
        "发文日8": "发文日",
    }
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_fields if isinstance(raw_fields, Iterable) else []:
        token = str(raw or "").strip()
        token = str(legacy_aliases.get(token, token)).strip()
        if not token or token not in allowed:
            continue
        if token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def normalize_type_naming_config(raw_cfg: object, notice_type: str | NoticeKind) -> NoticeTypeNamingConfig:
    defaults = default_naming_config_for_type(notice_type)
    if isinstance(raw_cfg, NoticeTypeNamingConfig):
        naming_mode = str(raw_cfg.naming_mode or "default").strip().lower()
        if naming_mode not in ("default", "custom"):
            naming_mode = "default"
        filename_fields = _normalize_filename_fields(raw_cfg.filename_fields, notice_type=notice_type) or list(
            defaults.filename_fields
        )
        alias_rules = _normalize_alias_rules(raw_cfg.alias_rules) or list(defaults.alias_rules)
        return NoticeTypeNamingConfig(naming_mode=naming_mode, filename_fields=filename_fields, alias_rules=alias_rules)

    if not isinstance(raw_cfg, dict):
        return defaults

    naming_mode = str(raw_cfg.get("naming_mode", "default") or "default").strip().lower()
    if naming_mode not in ("default", "custom"):
        naming_mode = "default"
    filename_fields = _normalize_filename_fields(raw_cfg.get("filename_fields"), notice_type=notice_type) or list(
        defaults.filename_fields
    )
    alias_rules = _normalize_alias_rules(raw_cfg.get("alias_rules")) or list(defaults.alias_rules)
    return NoticeTypeNamingConfig(naming_mode=naming_mode, filename_fields=filename_fields, alias_rules=alias_rules)


def _explicit_alias_rules_from_config(raw_cfg: object) -> list[NoticeAliasRule]:
    if isinstance(raw_cfg, NoticeTypeNamingConfig):
        return _normalize_alias_rules(raw_cfg.alias_rules)
    if isinstance(raw_cfg, dict):
        return _normalize_alias_rules(raw_cfg.get("alias_rules"))
    return []


def _resolve_type_config(
    *,
    options: ProcessOptions,
    lookup_keys: list[str],
) -> tuple[NoticeTypeNamingConfig | object | None, str]:
    cfg_map = dict(options.type_naming_configs or {})
    seen: set[str] = set()
    for key in lookup_keys:
        name = str(key or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        if name in cfg_map:
            return cfg_map.get(name), name
    return None, ""


def _compose_effective_naming_config(
    *,
    options: ProcessOptions,
    notice_key: str,
    fallback_notice_kind: NoticeKind,
    notice_name: str,
) -> tuple[NoticeTypeNamingConfig, str]:
    lookup_keys = _lookup_notice_keys(
        notice_key=notice_key,
        notice_kind=fallback_notice_kind,
        notice_name=notice_name,
    )
    cfg, cfg_key = _resolve_effective_naming_config(
        options=options,
        notice_key=notice_key,
        fallback_notice_kind=fallback_notice_kind,
        notice_name=notice_name,
    )
    alias_cfg, alias_key = _resolve_type_config(options=options, lookup_keys=lookup_keys)
    effective_key = cfg_key or alias_key or normalize_notice_type(notice_key or fallback_notice_kind)
    naming_cfg = normalize_type_naming_config(cfg, effective_key)
    return (
        NoticeTypeNamingConfig(
            naming_mode=naming_cfg.naming_mode,
            filename_fields=list(naming_cfg.filename_fields or []),
            alias_rules=_explicit_alias_rules_from_config(alias_cfg),
        ),
        effective_key,
    )


def get_effective_type_naming_config(options: ProcessOptions, notice_type: str | NoticeKind) -> NoticeTypeNamingConfig:
    notice_key = normalize_notice_type(notice_type)
    cfg, _cfg_key = _compose_effective_naming_config(
        options=options,
        notice_key=notice_key,
        fallback_notice_kind=notice_key,
        notice_name="",
    )
    return cfg


def _lookup_notice_keys(*, notice_key: str, notice_kind: NoticeKind, notice_name: str) -> list[str]:
    lookup_keys: list[str] = []
    if notice_key and notice_key != "unknown":
        lookup_keys.append(notice_key)

    kind_key = str(notice_kind or "").strip()
    if kind_key:
        lookup_keys.append(kind_key)

    detected_kind, _kind_text, _round = detect_notice_kind(notice_name)
    detected_kind = str(detected_kind or "").strip()
    if detected_kind:
        lookup_keys.append(detected_kind)

    lookup_keys.append(normalize_notice_type(notice_kind))
    return lookup_keys


def _resolve_group_config(
    *,
    options: ProcessOptions,
    lookup_keys: list[str],
) -> tuple[NoticeTypeNamingConfig | object | None, str]:
    membership = {
        normalize_notice_type(str(raw_key or "").strip()): str(raw_group_id or "").strip()
        for raw_key, raw_group_id in dict(options.type_group_membership or {}).items()
        if normalize_notice_type(str(raw_key or "").strip()) and str(raw_group_id or "").strip()
    }
    raw_groups = dict(options.naming_groups or {})
    groups: dict[str, NamingGroupConfig | object] = {
        str(group_id or "").strip(): group_cfg
        for group_id, group_cfg in raw_groups.items()
        if str(group_id or "").strip()
    }

    seen: set[str] = set()
    for key in lookup_keys:
        type_key = normalize_notice_type(key)
        if not type_key or type_key in seen:
            continue
        seen.add(type_key)
        group_id = membership.get(type_key, "")
        if not group_id:
            continue
        group_cfg = groups.get(group_id)
        if group_cfg is None:
            continue
        if isinstance(group_cfg, NamingGroupConfig):
            return group_cfg.group_config, type_key
        if isinstance(group_cfg, dict):
            return group_cfg.get("group_config"), type_key
    return None, ""


def _resolve_effective_naming_config(
    *,
    options: ProcessOptions,
    notice_key: str,
    fallback_notice_kind: NoticeKind,
    notice_name: str,
) -> tuple[NoticeTypeNamingConfig | object | None, str]:
    cfg_map = dict(options.type_naming_configs or {})
    lookup_keys = _lookup_notice_keys(
        notice_key=notice_key,
        notice_kind=fallback_notice_kind,
        notice_name=notice_name,
    )

    group_cfg, group_cfg_key = _resolve_group_config(options=options, lookup_keys=lookup_keys)
    if group_cfg is not None:
        return group_cfg, group_cfg_key

    seen: set[str] = set()
    for key in lookup_keys:
        name = str(key or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        if name in cfg_map:
            return cfg_map.get(name), name

    fallback_key = notice_key if notice_key and notice_key != "unknown" else str(fallback_notice_kind or "").strip()
    return None, normalize_notice_type(fallback_key)


def _collapse_plus(name: str) -> str:
    cleaned = re.sub(r"\++", "+", str(name or "").strip())
    return cleaned.strip("+")


def validate_filename_separator(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    if any(ch in _INVALID_FILENAME_SEPARATOR_CHARS for ch in text):
        return '字段连接符不能包含 Windows 文件名非法字符：\\ / : * ? " < > |'
    if any(ord(ch) < 32 for ch in text):
        return "字段连接符不能包含控制字符或换行。"
    return ""


def normalize_filename_separator(value: object) -> str:
    text = str(value or "")
    if not text:
        return "+"
    if validate_filename_separator(text):
        return "+"
    return text


def _join_filename_parts(parts: list[str], options: ProcessOptions) -> str:
    separator = normalize_filename_separator(getattr(options, "filename_separator", "+"))
    if separator == "+":
        return _collapse_plus("+".join(parts))
    return separator.join(parts).strip()


def _sanitize_piece(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    cleaned = sanitize_filename(raw)
    cleaned = cleaned.strip(" +")
    if str(cleaned or "").strip().lower() == "output" and str(raw).strip().lower() != "output":
        return ""
    return cleaned


def mask_app_no_for_preview(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    chars = list(raw)
    alnum_positions = [idx for idx, ch in enumerate(chars) if ch.isalnum()]
    count = len(alnum_positions)
    if count <= 0:
        return raw

    if count <= 2:
        keep_prefix = 0
        keep_suffix = 0
    elif count <= 8:
        keep_prefix = 1
        keep_suffix = 1
    else:
        keep_prefix = 4
        keep_suffix = 4

    for pos, idx in enumerate(alnum_positions):
        keep = (pos < keep_prefix) or (pos >= count - keep_suffix)
        if not keep:
            chars[idx] = "*"
    return "".join(chars)


def _notice_name_with_alias(*, notice_name: str, alias_rules: list[NoticeAliasRule]) -> str:
    source = str(notice_name or "").strip()
    for rule in alias_rules:
        if not bool(rule.enabled):
            continue
        if str(rule.notice_name or "").strip() == source:
            short_name = str(rule.short_name or "").strip()
            if short_name:
                return short_name
    return source


def _token_values(
    meta: NoticeMeta,
    *,
    notice_kind: NoticeKind,
    display_notice_name: str,
    normalized_notice_name: str,
) -> dict[str, str]:
    _kind, kind_text, round_text = detect_notice_kind(normalized_notice_name or meta.notice_name)
    notice_type_text = kind_text if kind_text and kind_text != "未知" else _kind
    amount = str(meta.receipt_amount or "").strip()
    amount_yuan = f"{amount}元" if amount and not amount.endswith("元") else amount
    receipt_item_first = str(meta.receipt_fee_item_first or meta.receipt_fee_item or "").strip()
    receipt_item_summary = str(meta.receipt_fee_item_summary or receipt_item_first).strip()
    return {
        "专利类型": str(meta.patent_type or "").strip(),
        "申请号": str(meta.app_no or "").strip(),
        "申请号带点": str(meta.app_no_dotted or "").strip(),
        "通知书名称": str(display_notice_name or "").strip(),
        "发明名称": str(meta.invention_name or "").strip(),
        "申请人信息": str(meta.applicant or "").strip(),
        "通知书代码": str(meta.notice_code or "").strip(),
        "发文日": str(meta.issue_date or meta.issue_date_raw or "").strip().replace("-", ""),
        "发文日8": str(meta.issue_date8 or "").strip(),
        "内部编号": str(meta.internal_no or "").strip(),
        "逾期日": str(meta.due_date or "").strip(),
        "期限天": str(meta.limit_days or "").strip(),
        "发文序号": str(meta.doc_serial or "").strip(),
        "案卷号": str(meta.dossier_no or "").strip(),
        "申请日": str(meta.apply_date or "").strip(),
        "通知书类型": str(notice_type_text or notice_kind or "").strip(),
        "次数": str(meta.notice_round or round_text or "").strip(),
        "收据": "收据",
        "收据_缴费人": str(meta.receipt_payer or meta.applicant or "").strip(),
        "收据_申请号": str(meta.receipt_app_no or meta.app_no or "").strip(),
        "收据_专利类型": str(meta.receipt_patent_type or meta.patent_type or "").strip(),
        "收据_缴费项目": receipt_item_first,
        "收据_缴费项目首项": receipt_item_first,
        "收据_缴费项目汇总": receipt_item_summary,
        "收据_缴费项目明细": str(meta.receipt_fee_item_detail or "").strip(),
        "收据_缴费金额": amount,
        "收据_缴费金额元": amount_yuan,
        "收据_缴费日期": str(meta.receipt_payment_date or "").strip().replace("-", ""),
        "收据_缴费方式": str(meta.receipt_payment_method or "").strip(),
        "收据_订单号": str(meta.receipt_order_no or "").strip(),
        "收据_票据代码": str(meta.receipt_ticket_code or "").strip(),
        "收据_票据号码": str(meta.receipt_ticket_no or "").strip(),
        "收据_开票日期": str(meta.receipt_invoice_date or "").strip().replace("-", ""),
    }


def _default_fields_for_meta(meta: NoticeMeta) -> list[str]:
    if str(meta.notice_code or "").strip() == "10071" and str(meta.notice_name or "").strip() == "电子提交收据":
        return list(DEFAULT_RECEIPT_FILENAME_FIELDS)
    return list(DEFAULT_FILENAME_FIELDS)


def _resolve_naming_context(
    *,
    meta: NoticeMeta,
    notice_kind: NoticeKind,
    options: ProcessOptions,
) -> tuple[NoticeTypeNamingConfig, str, list[str], dict[str, str]]:
    notice_key = build_notice_key(meta)
    cfg, cfg_key = _compose_effective_naming_config(
        options=options,
        notice_key=notice_key,
        fallback_notice_kind=notice_kind,
        notice_name=meta.notice_name,
    )
    normalized_notice_name = normalize_notice_name_for_meta(meta) or str(meta.notice_name or "").strip()
    display_notice_name = _notice_name_with_alias(
        notice_name=normalized_notice_name,
        alias_rules=list(cfg.alias_rules or []),
    )
    values = _token_values(
        meta,
        notice_kind=notice_kind,
        display_notice_name=display_notice_name,
        normalized_notice_name=normalized_notice_name,
    )

    if str(cfg.naming_mode) == "custom":
        fields = list(cfg.filename_fields or [])
    else:
        fields = _default_fields_for_meta(meta)
    return cfg, display_notice_name, fields, values


def _build_parts(
    *,
    fields: list[str],
    values: dict[str, str],
    use_field_name_when_empty: bool = False,
) -> list[str]:
    parts: list[str] = []
    for raw_field_name in fields:
        field_name = str(raw_field_name or "").strip()
        if not field_name:
            continue
        if use_field_name_when_empty:
            raw_value = str(values.get(field_name, "") or "").strip()
            if raw_value:
                value = _sanitize_piece(raw_value)
                if value:
                    parts.append(value)
                continue
            placeholder = _sanitize_piece(field_name)
            if placeholder:
                parts.append(placeholder)
            continue

        value = _sanitize_piece(values.get(field_name, ""))
        if value:
            parts.append(value)
    return parts


def render_notice_output(*, meta: NoticeMeta, notice_kind: NoticeKind, options: ProcessOptions) -> NoticeNamingOutput:
    cfg, display_notice_name, fields, values = _resolve_naming_context(
        meta=meta,
        notice_kind=notice_kind,
        options=options,
    )
    parts = _build_parts(fields=fields, values=values, use_field_name_when_empty=False)

    if not parts:
        fallback = _sanitize_piece(meta.app_no) or _sanitize_piece(meta.notice_code) or _sanitize_piece(display_notice_name)
        if fallback:
            parts = [fallback]
        else:
            parts = ["notice"]

    base_name = _join_filename_parts(parts, options)
    if not base_name:
        base_name = "notice"
    output_pdf_name = f"{base_name}.pdf"

    app_no_segment = _sanitize_piece(meta.app_no)
    archive_rel_dir = app_no_segment if app_no_segment else "未命名申请号"

    return NoticeNamingOutput(
        output_pdf_name=output_pdf_name,
        archive_rel_dir=archive_rel_dir,
        naming_mode=str(cfg.naming_mode or "default"),
        display_notice_name=display_notice_name,
        parts=parts,
    )


def notice_output_uses_field(
    *,
    meta: NoticeMeta,
    notice_kind: NoticeKind,
    options: ProcessOptions,
    field_name: str,
) -> bool:
    target = str(field_name or "").strip()
    if not target:
        return False
    _cfg, _display_notice_name, fields, _values = _resolve_naming_context(
        meta=meta,
        notice_kind=notice_kind,
        options=options,
    )
    return target in {str(field or "").strip() for field in fields}


def render_notice_output_preview(
    *,
    meta: NoticeMeta,
    notice_kind: NoticeKind,
    options: ProcessOptions,
) -> NoticeNamingPreviewOutput:
    cfg, display_notice_name, fields, values = _resolve_naming_context(
        meta=meta,
        notice_kind=notice_kind,
        options=options,
    )
    values_for_preview = dict(values)
    values_for_preview["申请号"] = mask_app_no_for_preview(values_for_preview.get("申请号", ""))
    values_for_preview["申请号带点"] = mask_app_no_for_preview(values_for_preview.get("申请号带点", ""))
    parts = _build_parts(fields=fields, values=values_for_preview, use_field_name_when_empty=True)

    if not parts:
        fallback = (
            _sanitize_piece(mask_app_no_for_preview(meta.app_no))
            or _sanitize_piece(meta.notice_code)
            or _sanitize_piece(display_notice_name)
        )
        parts = [fallback or "notice"]

    base_name = _join_filename_parts(parts, options)
    preview_pdf_name = f"{base_name or 'notice'}.pdf"

    return NoticeNamingPreviewOutput(
        preview_pdf_name=preview_pdf_name,
        naming_mode=str(cfg.naming_mode or "default"),
        display_notice_name=display_notice_name,
        parts=parts,
    )


__all__ = [
    "DEFAULT_ALIAS_RULES",
    "DEFAULT_FILENAME_FIELDS",
    "NoticeNamingOutput",
    "NoticeNamingPreviewOutput",
    "default_alias_rules_for_type",
    "default_naming_config_for_type",
    "get_effective_type_naming_config",
    "notice_output_uses_field",
    "normalize_type_naming_config",
    "normalize_filename_separator",
    "render_notice_output",
    "render_notice_output_preview",
    "validate_filename_separator",
    "mask_app_no_for_preview",
]
