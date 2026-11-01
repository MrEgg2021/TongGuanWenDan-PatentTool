from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from core.paths_utils import get_resource_path


DEFAULT_FIELD_POLICY: dict[str, Any] = {
    "version": 1,
    "levels": {
        "L1": {"label": "确定语义", "allow_naming": True},
        "L2": {"label": "半确定语义", "allow_naming": False},
        "L3": {"label": "未确认语义", "allow_naming": False},
        "L4": {"label": "系统追踪ID", "allow_naming": False},
    },
    "patent_type": {
        "mapping": {
            "1": "发明专利",
            "2": "实用新型专利",
            "3": "外观专利",
            "6": "海牙外观",
            "8": "PCT发明",
            "9": "PCT实用新型",
        },
    },
    "zones": {
        "business_order": [
            "发明名称",
            "专利类型",
            "通知书名称",
            "申请号",
            "申请日",
            "发文日",
            "逾期日",
            "内部编号",
            "申请人信息",
            "通知书代码",
            "期限天",
            "案卷号",
            "收据_缴费人",
            "收据_申请号",
            "收据_专利类型",
            "收据_缴费项目",
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
            "收据_交款人统一社会信用代码",
            "收据_校验码",
            "收据_收款单位",
            "收据_复核人",
            "收据_收款人",
        ],
        "uncertain_order": [
            "DMHFLAG_raw",
            "FAMINGLX_raw",
            "附件YEWULX_raw_set",
        ],
    },
    "naming": {
        "allowed_levels": ["L1"],
        "blocked_fields": [
            "DMHFLAG",
            "DMHFLAG_raw",
            "FAMINGLX_raw",
            "YEWULX",
            "附件YEWULX_raw_set",
        ],
    },
    "field_levels": {
        "专利类型": "L1",
        "申请号": "L1",
        "申请号带点": "L1",
        "通知书名称": "L1",
        "发明名称": "L1",
        "申请人信息": "L1",
        "通知书代码": "L1",
        "发文日": "L1",
        "内部编号": "L1",
        "逾期日": "L1",
        "期限天": "L1",
        "发文序号": "L1",
        "案卷号": "L1",
        "申请日": "L1",
        "通知书类型": "L2",
        "次数": "L2",
        "收据": "L1",
        "收据_缴费人": "L1",
        "收据_申请号": "L1",
        "收据_专利类型": "L1",
        "收据_缴费项目": "L1",
        "收据_缴费项目首项": "L1",
        "收据_缴费项目汇总": "L1",
        "收据_缴费项目明细": "L1",
        "收据_缴费金额": "L1",
        "收据_缴费金额元": "L1",
        "收据_缴费日期": "L1",
        "收据_缴费方式": "L1",
        "收据_订单号": "L1",
        "收据_票据代码": "L1",
        "收据_票据号码": "L1",
        "收据_开票日期": "L1",
        "收据_交款人统一社会信用代码": "L1",
        "收据_校验码": "L1",
        "收据_收款单位": "L1",
        "收据_复核人": "L1",
        "收据_收款人": "L1",
        "DMHFLAG_raw": "L3",
        "FAMINGLX_raw": "L3",
        "附件YEWULX_raw_set": "L3",
        "ZIPBID": "L4",
    },
}

_RESOURCE_FILE = "official_doc_field_policy.json"


def _normalize_str_list(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values if isinstance(values, list) else []:
        text = str(value or "").strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _normalize_dict_str_str(values: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(values, dict):
        return out
    for key, value in values.items():
        key_text = str(key or "").strip()
        if not key_text:
            continue
        out[key_text] = str(value or "").strip()
    return out


def _deep_copy_default() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_FIELD_POLICY, ensure_ascii=False))


@lru_cache(maxsize=1)
def load_field_policy() -> dict[str, Any]:
    policy = _deep_copy_default()
    path = get_resource_path(_RESOURCE_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        return policy

    try:
        policy["version"] = int(raw.get("version", policy["version"]))
    except Exception:
        pass

    raw_levels = raw.get("levels")
    if isinstance(raw_levels, dict):
        for level_key in ("L1", "L2", "L3", "L4"):
            level_data = raw_levels.get(level_key)
            if not isinstance(level_data, dict):
                continue
            label = str(level_data.get("label", policy["levels"][level_key]["label"]) or "").strip()
            allow_naming = bool(level_data.get("allow_naming", policy["levels"][level_key]["allow_naming"]))
            if label:
                policy["levels"][level_key]["label"] = label
            policy["levels"][level_key]["allow_naming"] = allow_naming

    raw_patent = raw.get("patent_type")
    if isinstance(raw_patent, dict):
        mapping = _normalize_dict_str_str(raw_patent.get("mapping"))
        if mapping:
            policy["patent_type"]["mapping"] = mapping

    raw_zones = raw.get("zones")
    if isinstance(raw_zones, dict):
        business = _normalize_str_list(raw_zones.get("business_order"))
        uncertain = _normalize_str_list(raw_zones.get("uncertain_order"))
        if business:
            policy["zones"]["business_order"] = business
        if uncertain:
            policy["zones"]["uncertain_order"] = uncertain

    raw_naming = raw.get("naming")
    if isinstance(raw_naming, dict):
        allowed_levels = _normalize_str_list(raw_naming.get("allowed_levels"))
        blocked_fields = _normalize_str_list(raw_naming.get("blocked_fields"))
        if allowed_levels:
            policy["naming"]["allowed_levels"] = allowed_levels
        if blocked_fields:
            policy["naming"]["blocked_fields"] = blocked_fields

    raw_field_levels = raw.get("field_levels")
    if isinstance(raw_field_levels, dict):
        field_levels = _normalize_dict_str_str(raw_field_levels)
        if field_levels:
            policy["field_levels"] = field_levels

    return policy


def get_business_field_order() -> list[str]:
    return list(load_field_policy()["zones"]["business_order"])


def get_uncertain_field_order() -> list[str]:
    return list(load_field_policy()["zones"]["uncertain_order"])


def get_patent_type_mapping() -> dict[str, str]:
    return dict(load_field_policy()["patent_type"]["mapping"])


def get_field_levels() -> dict[str, str]:
    return dict(load_field_policy()["field_levels"])


def get_naming_allowed_levels() -> set[str]:
    return set(load_field_policy()["naming"]["allowed_levels"])


def get_naming_blocked_fields() -> set[str]:
    return set(load_field_policy()["naming"]["blocked_fields"])


def get_naming_whitelist_from_levels(*, candidate_fields: list[str]) -> set[str]:
    levels = get_field_levels()
    allowed_levels = get_naming_allowed_levels()
    allowed: set[str] = set()
    for field in candidate_fields or []:
        name = str(field or "").strip()
        if not name:
            continue
        level = str(levels.get(name, "") or "").strip()
        if level and level not in allowed_levels:
            continue
        allowed.add(name)
    allowed -= {str(item or "").strip() for item in get_naming_blocked_fields()}
    return allowed


__all__ = [
    "DEFAULT_FIELD_POLICY",
    "get_business_field_order",
    "get_field_levels",
    "get_naming_allowed_levels",
    "get_naming_blocked_fields",
    "get_naming_whitelist_from_levels",
    "get_patent_type_mapping",
    "get_uncertain_field_order",
    "load_field_policy",
]
