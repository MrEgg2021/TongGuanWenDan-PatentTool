from __future__ import annotations

import re


PATENT_TYPE_DISCLOSURE_HEADINGS = {
    "invention": "发明内容",
    "utility_model": "实用新型内容",
}

PATENT_TYPE_DISPLAY_LABELS = {
    "invention": "发明",
    "utility_model": "实用新型",
}


def _strip_heading_prefix(text: str) -> str:
    """去掉常见段首编号/序号前缀，保留后续正文。"""
    if not text:
        return ""

    patterns = [
        r"^[\s\u3000]*[\[\(（【]?\s*[0-9０-９]{1,4}\s*[\]\)）】]?\s*[\.．、]?\s*",
        r"^[\s\u3000]*[一二三四五六七八九十]+[\.．、]\s*",
        r"^[\s\u3000]*（[一二三四五六七八九十]+）\s*",
    ]
    stripped = str(text or "")
    for pat in patterns:
        new_val = re.sub(pat, "", stripped, count=1)
        if new_val != stripped:
            stripped = new_val
            break
    return stripped.lstrip(" \t\u3000")


def detect_direct_patent_type_heading(text: str) -> tuple[str | None, str | None]:
    """仅识别直接命中的“发明内容 / 实用新型内容”标题。"""
    norm = _strip_heading_prefix(str(text or "").strip())
    for patent_type, heading in PATENT_TYPE_DISCLOSURE_HEADINGS.items():
        if norm.startswith(heading):
            return patent_type, heading
    return None, None


def is_patent_type_disclosure_heading(heading_text: str | None) -> bool:
    return str(heading_text or "").strip() in PATENT_TYPE_DISCLOSURE_HEADINGS.values()


def get_default_disclosure_heading(patent_type: str | None) -> str:
    if patent_type == "utility_model":
        return PATENT_TYPE_DISCLOSURE_HEADINGS["utility_model"]
    return PATENT_TYPE_DISCLOSURE_HEADINGS["invention"]


def get_patent_type_display_label(patent_type: str | None) -> str:
    return str(PATENT_TYPE_DISPLAY_LABELS.get(str(patent_type or "").strip(), "") or "")


__all__ = [
    "PATENT_TYPE_DISCLOSURE_HEADINGS",
    "PATENT_TYPE_DISPLAY_LABELS",
    "detect_direct_patent_type_heading",
    "get_default_disclosure_heading",
    "get_patent_type_display_label",
    "is_patent_type_disclosure_heading",
]
