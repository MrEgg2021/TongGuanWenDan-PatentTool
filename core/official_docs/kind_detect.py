from __future__ import annotations

import re

from .models import NoticeKind


_RE_ROUND_CN = re.compile(r"第([一二三四五六七八九十百千]+)次")
_RE_ROUND_NUM = re.compile(r"第([0-9]+)次")
_RE_ROUND_N = re.compile(r"第([Nn])次")


def _extract_round_text(notice_name: str) -> str:
    text = str(notice_name or "").strip()
    if not text:
        return ""
    if "第一次" in text:
        return "一"

    m = _RE_ROUND_N.search(text)
    if m:
        return "N"

    m = _RE_ROUND_NUM.search(text)
    if m:
        return str(m.group(1) or "").strip()

    m = _RE_ROUND_CN.search(text)
    if m:
        return str(m.group(1) or "").strip()

    return ""


def detect_notice_kind(notice_name: str) -> tuple[NoticeKind, str, str]:
    """Return (kind, kind_text, round_text)."""

    name = str(notice_name or "").strip()
    kind: NoticeKind = "unknown"

    if "审查意见" in name and "通知书" in name:
        kind = "exam_opinion"
    elif "补正" in name and "通知书" in name:
        kind = "rectification"

    round_text = _extract_round_text(name)
    if kind in ("exam_opinion", "rectification") and not round_text:
        # Common default: when round isn't explicit, treat as first.
        round_text = "一"

    if kind == "exam_opinion":
        kind_text = "审查意见"
    elif kind == "rectification":
        kind_text = "补正"
    else:
        kind_text = "未知"

    return kind, kind_text, round_text


__all__ = ["detect_notice_kind"]

