from __future__ import annotations

import re

from core.regions_cn import CITIES_BY_PROVINCE, PROVINCES

_USCC_RE = re.compile(r"^[0-9A-HJ-NP-RT-Y]{18}$")

_FACT_SHEET_NAME = "申请信息"
_AGENCY_SHEET_NAME = "代理机构信息"

_FACT_HEADERS = [
    "申请人名称",
    "申请人类型",
    "申请人证件类型",
    "申请人证件号码",
    "申请人电话",
    "申请人电子邮箱",
    "申请人地址（省/市/区+详细地址）",
    "申请人邮编",
    "发明人姓名",
    "发明人证件类型",
    "发明人证件号码",
    "发明人国籍代码",
    "联系人姓名",
    "联系人电话",
    "联系人电子邮箱",
    "联系人地址（省/市/区+街道门牌号）",
    "联系人邮编",
    "分组名称",
    "总委托书编号",
    "关联代理机构名称",
    "关联代理机构代码",
]

_AGENCY_HEADERS = [
    "代理机构名称",
    "代理机构代码",
    "代理师姓名",
    "代理师资格证号",
    "代理师电话",
]

_REGION_CODES_6: set[str] = set()
for _p in PROVINCES:
    try:
        _code = _p.get("code")
        if _code:
            _REGION_CODES_6.add(str(_code))
    except Exception:
        pass
for _items in CITIES_BY_PROVINCE.values():
    for _it in _items:
        try:
            _code = _it.get("code")
            if _code:
                _REGION_CODES_6.add(str(_code))
        except Exception:
            pass
