from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .field_policy import get_naming_blocked_fields, get_naming_whitelist_from_levels
from .models import NoticeKind
from .notice_name_rules import normalize_notice_name
from .resource_mirror import get_resource_mirror_paths, sync_embedded_resource_to_mirror


NoticeTypeCode = str

FORBIDDEN_NAMING_FIELDS: tuple[str, ...] = tuple(sorted(get_naming_blocked_fields()))

FILENAME_FIELDS: tuple[str, ...] = (
    "专利类型",
    "申请号",
    "申请号带点",
    "通知书名称",
    "发明名称",
    "申请人信息",
    "通知书代码",
    "发文日",
    "内部编号",
    "逾期日",
    "期限天",
    "发文序号",
    "案卷号",
    "申请日",
    "通知书类型",
    "次数",
)

RECEIPT_TYPE_KEY = "10071|电子提交收据"
RECEIPT_FILENAME_FIELDS: tuple[str, ...] = (
    "收据",
    "收据_缴费人",
    "收据_申请号",
    "收据_专利类型",
    "收据_缴费项目首项",
    "收据_缴费项目汇总",
    "收据_缴费项目明细",
    "收据_缴费金额",
    "收据_缴费金额元",
    "收据_缴费日期",
    "收据_缴费方式",
    "收据_订单号",
    "收据_票据代码",
    "收据_票据号码",
    "收据_开票日期",
)

TYPE_TOKENS: dict[str, tuple[str, ...]] = {
    "exam_opinion": FILENAME_FIELDS,
    "rectification": FILENAME_FIELDS,
    RECEIPT_TYPE_KEY: RECEIPT_FILENAME_FIELDS,
}

TYPE_DISPLAY_NAMES: dict[str, str] = {
    "exam_opinion": "审查意见通知书",
    "rectification": "补正通知书",
}

_SUPPORTED_TYPES_RESOURCE_FILE = "official_doc_supported_types.json"
PATENT_GROUP_INVENTION = "发明专利"
PATENT_GROUP_UTILITY = "实用新型专利"
PATENT_GROUP_DESIGN = "外观专利"
PATENT_GROUP_UNKNOWN = "未知"
_DEFAULT_SUPPORTED_TYPE_CATALOG: dict[str, Any] = {
    "version": 1,
    "types": [
        {
            "key": "exam_opinion",
            "display_name": "审查意见通知书",
            "processable": True,
            "disabled_reason": "",
        },
        {
            "key": "rectification",
            "display_name": "补正通知书",
            "processable": True,
            "disabled_reason": "",
        },
    ],
}


@dataclass(frozen=True)
class SupportedTypeCatalogHealth:
    healthy: bool
    source: str
    path: str
    warning: str
    error: str
    embedded_path: str
    mirror_path: str


_CATALOG_HEALTH = SupportedTypeCatalogHealth(
    healthy=False,
    source="uninitialized",
    path="",
    warning="",
    error="catalog not loaded",
    embedded_path="",
    mirror_path="",
)


def clear_supported_type_catalog_cache() -> None:
    """清空支持类型目录缓存与健康状态；主要用于测试隔离。"""
    _load_supported_type_catalog.cache_clear()
    _set_catalog_health(
        SupportedTypeCatalogHealth(
            healthy=False,
            source="uninitialized",
            path="",
            warning="",
            error="catalog not loaded",
            embedded_path="",
            mirror_path="",
        )
    )


def normalize_notice_type(code: str | NoticeKind) -> NoticeTypeCode:
    value = str(code or "").strip()
    return value or "exam_opinion"


def _default_display_name(type_key: str) -> str:
    notice_type = normalize_notice_type(type_key)
    preset = str(TYPE_DISPLAY_NAMES.get(notice_type, "") or "").strip()
    if preset:
        return preset
    if "|" in notice_type:
        code_part, name_part = notice_type.split("|", 1)
        notice_name = str(name_part or "").strip()
        notice_code = str(code_part or "").strip()
        if notice_name and notice_code:
            normalized_name = normalize_notice_name(
                notice_code=notice_code,
                notice_name=notice_name,
                patent_type_label="",
                force_by_code=True,
            )
            return f"{normalized_name or notice_name}（{notice_code}）"
        if notice_name:
            return normalize_notice_name(
                notice_code="",
                notice_name=notice_name,
                patent_type_label="",
                force_by_code=True,
            ) or notice_name
        if notice_code:
            return notice_code
    return notice_type or "未命名通知书类型"


def infer_patent_group_from_label(patent_type_label: str) -> str:
    text = str(patent_type_label or "").strip()
    if not text:
        return PATENT_GROUP_UNKNOWN
    if "外观" in text:
        return PATENT_GROUP_DESIGN
    if "实用新型" in text:
        return PATENT_GROUP_UTILITY
    if "发明" in text:
        return PATENT_GROUP_INVENTION
    return PATENT_GROUP_UNKNOWN


def infer_patent_group_from_type_key(type_key: str | NoticeKind, *, display_name: str = "") -> str:
    notice_type = normalize_notice_type(type_key)
    if notice_type in ("exam_opinion", "rectification"):
        return PATENT_GROUP_UNKNOWN

    code_part = ""
    name_part = ""
    if "|" in notice_type:
        code_part, name_part = notice_type.split("|", 1)
    code = str(code_part or "").strip()
    name = str(display_name or "").strip() or str(name_part or "").strip()

    if "外观" in name:
        return PATENT_GROUP_DESIGN
    if "实用新型" in name:
        return PATENT_GROUP_UTILITY
    if "发明" in name:
        return PATENT_GROUP_INVENTION

    if code.startswith("23") or code in {"400003"}:
        return PATENT_GROUP_DESIGN
    if code.startswith("22") or code in {"400002", "200305"}:
        return PATENT_GROUP_UTILITY
    if code.startswith("21") or code in {"400001", "210407"}:
        return PATENT_GROUP_INVENTION
    return PATENT_GROUP_UNKNOWN


def _normalize_supported_type_entry(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    key = normalize_notice_type(str(raw.get("key", "") or "").strip())
    if not key:
        return None
    display_name_raw = str(raw.get("display_name", "") or "").strip() or _default_display_name(key)
    if "|" in key:
        code_part, _name_part = key.split("|", 1)
        code_text = str(code_part or "").strip()
    else:
        code_text = ""
    display_name = normalize_notice_name(
        notice_code=code_text,
        notice_name=display_name_raw,
        patent_type_label="",
        force_by_code=True,
    ) or display_name_raw
    processable = bool(raw.get("processable", True))
    disabled_reason = str(raw.get("disabled_reason", "") or "").strip()
    patent_group = str(raw.get("patent_group", "") or "").strip()
    if not patent_group:
        patent_group = infer_patent_group_from_type_key(key, display_name=display_name)
    if processable:
        disabled_reason = ""
    return {
        "key": key,
        "display_name": display_name,
        "processable": processable,
        "disabled_reason": disabled_reason,
        "patent_group": patent_group,
    }


def _clone_default_supported_catalog() -> dict[str, Any]:
    return json.loads(json.dumps(_DEFAULT_SUPPORTED_TYPE_CATALOG, ensure_ascii=False))


def _load_catalog_json(path: str) -> dict[str, Any]:
    if not path:
        raise FileNotFoundError("empty catalog path")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"catalog payload must be JSON object: {path}")
    return raw


def _set_catalog_health(health: SupportedTypeCatalogHealth) -> None:
    global _CATALOG_HEALTH
    _CATALOG_HEALTH = health


@lru_cache(maxsize=1)
def _load_supported_type_catalog() -> list[dict[str, Any]]:
    base = _clone_default_supported_catalog()
    merged_by_key: dict[str, dict[str, Any]] = {}

    for item in base.get("types", []):
        normalized = _normalize_supported_type_entry(item)
        if normalized is not None:
            merged_by_key[str(normalized["key"])] = normalized

    mirror_paths = get_resource_mirror_paths(_SUPPORTED_TYPES_RESOURCE_FILE)
    raw: dict[str, Any] | None = None
    source = "missing"
    path = ""
    warning = ""
    error = ""

    if os.path.exists(mirror_paths.embedded_path):
        try:
            raw = _load_catalog_json(mirror_paths.embedded_path)
            source = "embedded"
            path = mirror_paths.embedded_path
            sync_warning = sync_embedded_resource_to_mirror(mirror_paths)
            if sync_warning:
                warning = sync_warning
        except Exception as exc:
            warning = f"embedded catalog load failed: {exc}"

    if raw is None and os.path.exists(mirror_paths.mirror_path):
        try:
            raw = _load_catalog_json(mirror_paths.mirror_path)
            source = "mirror"
            path = mirror_paths.mirror_path
        except Exception as exc:
            error = f"mirror catalog load failed: {exc}"

    if raw is None:
        if not error:
            error = (
                "catalog resource unavailable: "
                f"embedded={mirror_paths.embedded_path}, mirror={mirror_paths.mirror_path}"
            )
        _set_catalog_health(
            SupportedTypeCatalogHealth(
                healthy=False,
                source=source,
                path=path,
                warning=warning,
                error=error,
                embedded_path=mirror_paths.embedded_path,
                mirror_path=mirror_paths.mirror_path,
            )
        )
        catalog = list(merged_by_key.values())
        catalog.sort(key=lambda item: (str(item.get("display_name", "") or ""), str(item.get("key", "") or "")))
        return catalog

    if not isinstance(raw, dict):
        _set_catalog_health(
            SupportedTypeCatalogHealth(
                healthy=False,
                source=source,
                path=path,
                warning=warning,
                error=f"catalog payload is not a JSON object: {path}",
                embedded_path=mirror_paths.embedded_path,
                mirror_path=mirror_paths.mirror_path,
            )
        )
        catalog = list(merged_by_key.values())
        catalog.sort(key=lambda item: (str(item.get("display_name", "") or ""), str(item.get("key", "") or "")))
        return catalog

    raw_items = raw.get("types", []) if isinstance(raw, dict) else []
    for item in raw_items if isinstance(raw_items, list) else []:
        normalized = _normalize_supported_type_entry(item)
        if normalized is not None:
            merged_by_key[str(normalized["key"])] = normalized

    catalog = list(merged_by_key.values())
    catalog.sort(key=lambda item: (str(item.get("display_name", "") or ""), str(item.get("key", "") or "")))
    _set_catalog_health(
        SupportedTypeCatalogHealth(
            healthy=True,
            source=source,
            path=path,
            warning=warning,
            error="",
            embedded_path=mirror_paths.embedded_path,
            mirror_path=mirror_paths.mirror_path,
        )
    )
    return catalog


def get_supported_type_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in _load_supported_type_catalog()]


def get_supported_type_catalog_health() -> SupportedTypeCatalogHealth:
    _load_supported_type_catalog()
    return _CATALOG_HEALTH


def get_supported_type_keys(*, include_unprocessable: bool = True) -> list[str]:
    keys: list[str] = []
    for item in _load_supported_type_catalog():
        key = normalize_notice_type(str(item.get("key", "") or "").strip())
        if not key:
            continue
        if (not include_unprocessable) and (not bool(item.get("processable", True))):
            continue
        keys.append(key)
    return keys


def _get_catalog_item(type_key: str | NoticeKind) -> dict[str, Any] | None:
    notice_type = normalize_notice_type(type_key)
    for item in _load_supported_type_catalog():
        if normalize_notice_type(str(item.get("key", "") or "")) == notice_type:
            return item
    return None


def is_type_processable(type_key: str | NoticeKind) -> bool:
    item = _get_catalog_item(type_key)
    if item is None:
        return True
    return bool(item.get("processable", True))


def get_type_disabled_reason(type_key: str | NoticeKind) -> str:
    item = _get_catalog_item(type_key)
    if item is None:
        return ""
    return str(item.get("disabled_reason", "") or "").strip()


def is_notice_key_processable(notice_key: str | NoticeKind) -> tuple[bool, str]:
    """Return processability for a concrete notice key.

    Rules:
    1) If key is present in supported-type catalog, follow catalog `processable` + `disabled_reason`.
    2) Unknown PCT-like keys are blocked by default (whitelist strategy).
    3) Other unknown keys are allowed by default to avoid over-blocking non-PCT future types.
    """

    key = normalize_notice_type(notice_key)
    item = _get_catalog_item(key)
    if item is not None:
        processable = bool(item.get("processable", True))
        if processable:
            return True, ""
        reason = str(item.get("disabled_reason", "") or "").strip()
        if not reason:
            reason = f"通知书类型不纳入处理：{key}"
        return False, reason

    if "PCT" in key.upper():
        return False, "PCT相关通知书未纳入处理白名单"
    return True, ""


def get_type_tokens(code: str | NoticeKind) -> list[str]:
    notice_type = normalize_notice_type(code)
    base_tokens = list(TYPE_TOKENS.get(notice_type, FILENAME_FIELDS))
    whitelist = get_naming_whitelist_from_levels(candidate_fields=base_tokens)
    if not whitelist:
        forbidden = {str(token or "").strip() for token in FORBIDDEN_NAMING_FIELDS if str(token or "").strip()}
        return [token for token in base_tokens if token not in forbidden]
    return [token for token in base_tokens if token in whitelist]


def get_type_display_name(code: str | NoticeKind) -> str:
    notice_type = normalize_notice_type(code)
    catalog_item = _get_catalog_item(notice_type)
    if catalog_item is not None:
        display_name = str(catalog_item.get("display_name", "") or "").strip()
        if display_name:
            return display_name
    return _default_display_name(notice_type)


__all__ = [
    "FILENAME_FIELDS",
    "RECEIPT_FILENAME_FIELDS",
    "RECEIPT_TYPE_KEY",
    "PATENT_GROUP_DESIGN",
    "PATENT_GROUP_INVENTION",
    "PATENT_GROUP_UNKNOWN",
    "PATENT_GROUP_UTILITY",
    "TYPE_DISPLAY_NAMES",
    "TYPE_TOKENS",
    "FORBIDDEN_NAMING_FIELDS",
    "SupportedTypeCatalogHealth",
    "infer_patent_group_from_label",
    "infer_patent_group_from_type_key",
    "clear_supported_type_catalog_cache",
    "get_supported_type_catalog",
    "get_supported_type_catalog_health",
    "get_supported_type_keys",
    "get_type_disabled_reason",
    "get_type_display_name",
    "get_type_tokens",
    "is_notice_key_processable",
    "is_type_processable",
    "normalize_notice_type",
]
