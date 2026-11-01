from __future__ import annotations

import re


_USCC_CHARSET = "0123456789ABCDEFGHJKLMNPQRTUWXY"
# 权重 W_i = (3^i) mod 31, i=0..16（GB 32100-2015）
_USCC_WEIGHTS = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]
_ID18_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_ID18_CHECK_MAP = "10X98765432"


def _normalize(s: str) -> str:
    return re.sub(r"\s+|-", "", s).upper()


def validate_uscc(code: str) -> bool:
    s = _normalize(code)
    if len(s) != 18:
        return False
    # 严格字符集校验：仅允许 0-9 + A-H J-N P Q R T U W X Y（禁用 I/O/S/V/Z）
    if not re.match(r"^[0-9A-HJ-NP-RT-Y]{18}$", s):
        return False
    try:
        values = [
            _USCC_CHARSET.index(ch)
            for ch in s
        ]
    except ValueError:
        return False
    total = 0
    for v, w in zip(values[:17], _USCC_WEIGHTS):
        total += v * w
    check_value = (31 - total % 31) % 31
    return _USCC_CHARSET[check_value] == s[17]


def validate_cn_id(code: str) -> bool:
    s = _normalize(code)
    if len(s) == 18:
        if not (s[:17].isdigit() and (s[17].isdigit() or s[17] == "X")):
            return False
        total = 0
        for ch, w in zip(s[:17], _ID18_WEIGHTS):
            total += int(ch) * w
        m = total % 11
        return _ID18_CHECK_MAP[m] == s[17]
    if len(s) == 15:
        return s.isdigit()
    return False
