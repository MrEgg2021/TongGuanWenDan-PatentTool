from __future__ import annotations

import re
from typing import Any, Dict, Optional

from core.regions_cn import CITIES_BY_PROVINCE, PROVINCES


def _extract_known_code(text: Any, valid_codes: set[str]) -> Optional[str]:
    if text is None:
        return None
    try:
        s = str(text)
    except Exception:
        return None
    candidates = re.findall(r"\d{6}", s)
    for code in candidates:
        if code in valid_codes:
            return code
    return None


def _normalize_province_name(name: Any) -> str:
    if not name:
        return ""
    s = re.sub(r"\s+", "", str(name))
    if not s:
        return ""
    suffixes = [
        "特别行政区",
        "回族自治区",
        "壮族自治区",
        "维吾尔自治区",
        "自治区",
        "省",
        "市",
    ]
    for suf in suffixes:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return s


def _normalize_city_name(name: Any) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", "", str(name))


def _infer_province_code_from_text(value: Any) -> Optional[str]:
    if not value:
        return None

    prov_codes = {p.get("code") for p in PROVINCES if p.get("code")}
    code = _extract_known_code(value, prov_codes)
    if code:
        return code

    full_norm = _normalize_province_name(value)
    if not full_norm:
        return None

    # 
    matched: Optional[str] = None
    for p in PROVINCES:
        name = p.get("name")
        p_code = p.get("code")
        if not name or not p_code:
            continue
        cand_norm = _normalize_province_name(name)
        if not cand_norm:
            continue
        if cand_norm == full_norm:
            if matched is not None and matched != p_code:
                # 
                return None
            matched = p_code
    if matched:
        return matched

    # 
    candidates: set[str] = set()
    for p in PROVINCES:
        name = p.get("name")
        p_code = p.get("code")
        if not name or not p_code:
            continue
        cand_norm = _normalize_province_name(name)
        if not cand_norm:
            continue
        if cand_norm in full_norm:
            candidates.add(p_code)

    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _infer_city_code_from_text(province_code: Optional[str], value: Any) -> Optional[str]:
    if not value:
        return None

    user_norm = _normalize_city_name(value)
    if not user_norm:
        return None

    candidates: list[tuple[str, str]] = []
    if province_code and province_code in CITIES_BY_PROVINCE:
        for item in CITIES_BY_PROVINCE[province_code]:
            code = item.get("code")
            name = item.get("name")
            if not code or not name:
                continue
            candidates.append((code, _normalize_city_name(name)))
    else:
        for items in CITIES_BY_PROVINCE.values():
            for item in items:
                code = item.get("code")
                name = item.get("name")
                if not code or not name:
                    continue
                candidates.append((code, _normalize_city_name(name)))

    if not candidates:
        return None

    valid_codes = {code for code, _ in candidates}
    code = _extract_known_code(value, valid_codes)
    if code:
        return code

    matches: set[str] = set()
    for cand_code, cand_norm in candidates:
        if not cand_norm:
            continue
        if user_norm == cand_norm:
            matches.add(cand_code)
            continue
        if user_norm.endswith(cand_norm):
            matches.add(cand_code)
            continue
        if cand_norm.endswith(user_norm) and len(cand_norm) - len(user_norm) <= 1:
            if cand_norm[-1] in "市区县旗":
                matches.add(cand_code)
                continue
        # 
        if cand_norm in user_norm:
            matches.add(cand_code)

    if len(matches) == 1:
        return next(iter(matches))
    return None


def _infer_region_from_single_address(record: Dict[str, Any], addr_key: str) -> None:
    """在未显式填写省/市时，尝试从单行详细地址中拆出省、市和剩余详细地址，并补全代码。

    仅在 record["province"] / record["city"] 目前均为空时生效，以避免覆盖用户已明确填写的内容。
    """
    if not isinstance(record, dict):
        return

    # 若已经有省/市文本，则尊重用户输入，不再尝试自动拆分
    if (record.get("province") or "").strip() or (record.get("city") or "").strip():
        return

    full = record.get(addr_key)
    if not full:
        return
    try:
        full_text = str(full)
    except Exception:
        return
    full_text = full_text.strip()
    if not full_text:
        return

    # 先基于整行地址推断省份代码和城市/地区代码
    prov_code = _infer_province_code_from_text(full_text)
    if prov_code:
        city_code = _infer_city_code_from_text(prov_code, full_text)
    else:
        city_code = _infer_city_code_from_text(None, full_text)

    prov_name = ""
    city_name = ""
    if prov_code:
        for p in PROVINCES:
            if p.get("code") == prov_code:
                prov_name = p.get("name") or ""
                break

    found_prov_code = None
    if city_code:
        for p_code, items in CITIES_BY_PROVINCE.items():
            for item in items:
                if item.get("code") == city_code:
                    city_name = item.get("name") or ""
                    found_prov_code = p_code
                    break
            if city_name:
                break

    # 若仅根据城市反推到所属省份，则一并补全省份代码和名称
    if not prov_code and found_prov_code:
        prov_code = found_prov_code
        for p in PROVINCES:
            if p.get("code") == prov_code:
                prov_name = p.get("name") or ""
                break

    # 根据识别到的省/市名称，从原始地址字符串中裁剪前缀，剩余部分视为详细地址/街道
    detail = full_text
    changed = False
    if prov_name and prov_name in detail:
        idx = detail.find(prov_name) + len(prov_name)
        detail = detail[idx:]
        changed = True
    if city_name and city_name in detail:
        idx = detail.find(city_name) + len(city_name)
        detail = detail[idx:]
        changed = True
    detail = detail.lstrip(" ,，。；;")

    if prov_name and not (record.get("province") or "").strip():
        record["province"] = prov_name
    if city_name and not (record.get("city") or "").strip():
        record["city"] = city_name

    # 仅在确实裁剪掉了省/市前缀时，才回写剩余详细地址，避免无意义覆盖
    if changed and detail:
        record[addr_key] = detail

    if prov_code and "province_code" not in record:
        record["province_code"] = prov_code
    if city_code and "city_code" not in record:
        record["city_code"] = city_code


def _attach_region_codes(request_info: Dict[str, Any]) -> None:
    # 先处理仅填写了单行地址/街道而省/市留空的情况，尽量从整行地址中自动拆出省/市
    applicants = request_info.get("applicants") or []
    for app in applicants:
        if not isinstance(app, dict):
            continue
        if app.get("address"):
            _infer_region_from_single_address(app, "address")

    contact = request_info.get("contact") or {}
    if isinstance(contact, dict) and contact.get("street"):
        _infer_region_from_single_address(contact, "street")

    # 在自动拆分之后，再根据中文省/市名称补全行政区划代码（兼容已填写省/市的场景）
    applicants = request_info.get("applicants") or []
    for app in applicants:
        if not isinstance(app, dict):
            continue
        prov_text = app.get("province")
        city_text = app.get("city")
        district_text = app.get("district")

        prov_code = _infer_province_code_from_text(prov_text)
        if prov_code and "province_code" not in app:
            app["province_code"] = prov_code

        city_code = _infer_city_code_from_text(prov_code, city_text) if city_text else None
        if city_code and "city_code" not in app:
            app["city_code"] = city_code

        district_code = _infer_city_code_from_text(prov_code, district_text) if district_text else None
        if district_code and "district_code" not in app:
            app["district_code"] = district_code

    contact = request_info.get("contact") or {}
    if isinstance(contact, dict):
        c_prov_text = contact.get("province")
        c_city_text = contact.get("city")

        c_prov_code = _infer_province_code_from_text(c_prov_text)
        if c_prov_code and "province_code" not in contact:
            contact["province_code"] = c_prov_code

        c_city_code = _infer_city_code_from_text(c_prov_code, c_city_text) if c_city_text else None
        if c_city_code and "city_code" not in contact:
            contact["city_code"] = c_city_code


__all__ = [
    "_attach_region_codes",
    "_extract_known_code",
    "_infer_city_code_from_text",
    "_infer_province_code_from_text",
    "_infer_region_from_single_address",
    "_normalize_city_name",
    "_normalize_province_name",
]
