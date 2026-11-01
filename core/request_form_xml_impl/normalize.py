from __future__ import annotations


def _normalize_applicant_type_code(raw_code, raw_text, default_code):
    code = ""
    if raw_code is not None:
        code = str(raw_code).strip()
    if code and not code.isdigit():
        tmp = ""
        for ch in code:
            if ch.isdigit():
                tmp = ch
                break
        if tmp:
            code = tmp
    if not code and raw_text:
        t = str(raw_text).strip()
        if "工矿" in t:
            code = "3"
        elif "个人" in t:
            code = "1"
        elif ("事业" in t and "单位" in t) or ("科研" in t and "机构" in t):
            code = "2"
        if not code:
            tmp = ""
            for ch in t:
                if ch.isdigit():
                    tmp = ch
                    break
            if tmp:
                code = tmp
    if not code and default_code is not None:
        code = str(default_code).strip()
    return code


def _normalize_id_type_code(raw_code, raw_text, default_code):
    code = ""
    if raw_code is not None:
        code = str(raw_code).strip().upper()
    if code in ("F", "I", "O"):
        return code
    if not code and raw_text:
        t = str(raw_text).strip()
        t_upper = t.upper()
        if "统一社会信用代码" in t or "社会信用代码" in t or "统一社会信用" in t:
            code = "F"
        elif t_upper.startswith("F-") or t_upper.startswith("F ") or t_upper == "F":
            code = "F"
        elif "身份证" in t or "居民" in t:
            code = "I"
        elif t_upper.startswith("I-") or t_upper == "I":
            code = "I"
        elif "其他" in t:
            code = "0"
        elif t_upper.startswith("O-") or t_upper == "O":
            code = "0"
    if not code and default_code is not None:
        code = str(default_code).strip().upper()
    if code and code not in ("F", "I", "O"):
        ch = code[0].upper()
        if ch in ("F", "I", "O"):
            code = ch
    return code


__all__ = ["_normalize_applicant_type_code", "_normalize_id_type_code"]
