from __future__ import annotations

from typing import Literal

from core.official_docs.kind_detect import detect_notice_kind

from .models import NoticeMeta

ResponseCorrectionNoticeKind = Literal["exam_opinion", "rectification", "unknown"]

_EXAM_OPINION_CODES = frozenset({"210401", "210403", "220301", "230302"})
_RECTIFICATION_CODES = frozenset({"210302", "230301"})


def infer_response_correction_notice_kind(notice: NoticeMeta) -> ResponseCorrectionNoticeKind:
    kind, _kind_text, _round_text = detect_notice_kind(str(notice.notice_name or "").strip())
    if kind in ("exam_opinion", "rectification"):
        return kind

    code = str(notice.notice_code or "").strip()
    if code in _EXAM_OPINION_CODES:
        return "exam_opinion"
    if code in _RECTIFICATION_CODES:
        return "rectification"
    return "unknown"


__all__ = ["ResponseCorrectionNoticeKind", "infer_response_correction_notice_kind"]
