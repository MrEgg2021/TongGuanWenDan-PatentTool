from __future__ import annotations

import html
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFontMetrics, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidgetItem,
    QWidget,
)

from core.logging_utils import logger
from core.formal_review.edit_model import EditableSegment
from core.formal_review.extractor import extract_formal_review_document
from core.formal_review.annotator import TOOL_COMMENT_PREFIX
from core.formal_review.comment_sync import sync_comments_inplace
from core.formal_review.companion_client import (
    close_session,
    connect_active_word,
    detect_unsaved_source,
    get_dirty_state,
    get_document_snapshot,
    get_word_hwnd,
    inspect_doc_clean_state,
    normalize_word_window,
    open_or_attach_document,
)
from core.formal_review.marker_rules import build_marker_normalization_write_plan
from core.formal_review.models import ClaimItem, FormalReviewDocument, Issue
from core.formal_review.plain_text_parser import parse_plain_text_sections
from core.formal_review.range_resolver import check_com_find_ready
from core.formal_review.report import build_report_payload, write_report_docx, write_report_xlsx
from core.formal_review.claim_refs import parse_claim_references
from core.formal_review.rule_registry import RULE_REGISTRY, enabled_rule_id_set, load_rule_enabled, rule_items_for_ui, save_rule_enabled
from core.formal_review.rule_params import load_rule_params, save_rule_params
from core.formal_review.service import build_issue_id, run_formal_review
from core.formal_review.suppression import SuppressionStore, build_instance_fingerprint
from core.formal_review.text_utils import count_effective_chars, extract_figure_markers, parse_marker_note_map, parse_marker_note_payload
from core.formal_review.text_projection import ProjectionBundle
from core.formal_review.word_locator import locate_issue_in_word
from core.formal_review.window_docking import DockLayout, dock_app_and_word
from core.formal_review.write_commands import MarkerNormalizationWritePlan
from core.formal_review.write_executor import apply_write_commands
from core.formal_review.write_preflight import run_write_preflight
from core.formal_review.wordlists import (
    load_wordlist_profile_store,
    load_wordlists,
    save_wordlist_profile_store,
    set_active_wordlist_profile,
)
from core.user_prefs import get_pref, set_pref
from core.word_engine import WordEngine
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal
from gui.widgets_impl.formal_review import FormalReviewSettingsDialog

_COMMENT_AUTHOR_PREF_KEY = "formal_review.comment_author_name"
_MARKER_NOTE_PREF_KEY = "formal_review.marker_note"
_HIGHLIGHT_COLORS_PREF_KEY = "formal_review.highlight_colors.v1"
_COMMENT_COPY_PATH_PREF_KEY = "formal_review.comment_copy_path.v1"
_RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY = "formal_review.results_tree.column_widths.v1"
_TOOL_COMMENT_PREFIX = TOOL_COMMENT_PREFIX
_RESULTS_TREE_DEFAULT_WIDTHS = (120, 80, 220, 80)
_RESULTS_TREE_MIN_WIDTH = 36

_SECTION_LABELS = {
    "claims": "权利要求书",
    "description": "说明书",
    "abstract": "摘要",
    "drawings": "附图",
}
_SEVERITY_LABELS = {
    "fatal": "致命",
    "error": "错误",
    "high": "高危",
    "warning": "警告",
    "medium": "中等",
    "low": "提醒",
    "info": "提示",
}
_DEFAULT_HIGHLIGHT_COLORS = {
    "wordlist.claims.forbidden": "#FFF176",
    "wordlist.claims.sensitive": "#FFE082",
    "wordlist.description.forbidden": "#FFCCBC",
    "wordlist.description.sensitive": "#FFECB3",
    "punctuation.repeated": "#B3E5FC",
    "punctuation.invalid_combo": "#B2DFDB",
    "text.repeated_word": "#B2EBF2",
    "drawings.figure.ref.missing_in_impl": "#D1C4E9",
    "description.structure.error": "#FFCDD2",
    "description.title.length.exceeded": "#FFE0B2",
    "theme.consistency": "#DCEDC8",
    "claim.ref": "#F8BBD0",
    "claim.threshold": "#FFE082",
    "claim.punctuation.structure": "#CE93D8",
    "abstract.word_count.exceeded": "#FFCDD2",
    "level.forbid": "#FFCDD2",
    "level.warn": "#FFE082",
    "level.remind": "#C8E6C9",
    "default": "#E0E0E0",
    "selected": "#90CAF9",
}
_RULE_OPTIONS = [
    {
        "rule_id": str(item.get("rule_id") or ""),
        "label": str(item.get("label") or ""),
        "color_key": str(item.get("color_key") or "default"),
        "default_enabled": bool(item.get("default_enabled", True)),
        "ui_domain": str(item.get("ui_domain") or "general"),
        "ui_level": str(item.get("ui_level") or "warn"),
        "default_color": _DEFAULT_HIGHLIGHT_COLORS.get(
            str(item.get("color_key") or "default"),
            _DEFAULT_HIGHLIGHT_COLORS["default"],
        ),
    }
    for item in rule_items_for_ui()
]
_CONTEXT_RADIUS = 10
_CLAIM_HEADER_FONT_SIZE = 13
_CLAIM_BODY_MIN_HEIGHT = 56
_CLAIM_BODY_MAX_HEIGHT = 360
_CLAIM_BODY_HEIGHT_PADDING = 8
_CLAIM_MARKER_HEIGHT_PADDING = 4
_CLAIM_MARKER_HORIZONTAL_PADDING = 16
_WIDGET_SIZE_MAX = 16777215
_QUOTED_TERM_RE = re.compile(r"[\"“”]([^\"“”]+)[\"“”]")
_DIGIT_RE = re.compile(r"\d+")
_CROSS_SECTION_REASON_PREFIX: dict[str, str] = {
    "description.drawings.figure.ref.missing_in_drawings_section": "\u8bf4\u660e\u4e66\u9644\u56fe\u7f3a\u5c11\u56fe\u53f7",
    "drawings.figure.ref.missing_in_description_drawings": "\u9644\u56fe\u8bf4\u660e\u7f3a\u5c11\u56fe\u53f7",
}
_CROSS_SECTION_REASON_AUDITED = False
_TOKEN_RE = re.compile(r"\{OBJ:[^}]+\}")
_SUPPORTED_WORD_SUFFIXES = {".doc", ".docx"}


def _ask_continue_cancel_cn(
    self,
    title: str,
    text: str,
    *,
    default_continue: bool = False,
) -> bool:
    try:
        return bool(
            ask_continue_cancel(
                self,
                str(title or "确认"),
                str(text or ""),
                continue_text="继续",
                cancel_text="取消",
                default_continue=bool(default_continue),
            )
        )
    except Exception:
        pass

    box = QMessageBox(self)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(str(title or "确认"))
    box.setText(str(text or ""))
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.Yes if bool(default_continue) else QMessageBox.No)
    yes_btn = box.button(QMessageBox.Yes)
    no_btn = box.button(QMessageBox.No)
    if yes_btn is not None:
        yes_btn.setText("继续")
    if no_btn is not None:
        no_btn.setText("取消")
    try:
        return box.exec() == QMessageBox.Yes
    except Exception:
        return False


def _safe_int(value, default: int | None = None) -> int | None:
    try:
        return int(value)
    except Exception:
        return default


def _normalized_word_suffix(path: str) -> str:
    return str(Path(str(path or "").strip()).suffix or "").lower()


def _normalize_hex(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("#"):
        text = f"#{text}"
    if QColor(text).isValid():
        return text.upper()
    return str(fallback or "#E0E0E0")


def _normalize_highlight_colors(payload: dict[str, str] | None) -> dict[str, str]:
    source = dict(payload or {})
    normalized: dict[str, str] = {}
    for key, fallback in _DEFAULT_HIGHLIGHT_COLORS.items():
        normalized[key] = _normalize_hex(source.get(key, fallback), fallback)
    for row in _RULE_OPTIONS:
        rule_id = str(row.get("rule_id") or "")
        color_key = str(row.get("color_key") or "default")
        fallback = normalized.get(color_key, _DEFAULT_HIGHLIGHT_COLORS["default"])
        normalized[rule_id] = _normalize_hex(source.get(rule_id, fallback), fallback)
    return normalized


def _issue_type_key(issue: Issue) -> str:
    rid = str(issue.rule_id or "")
    if rid.startswith("wordlist."):
        return f"wordlist.{issue.section}.{issue.category}"
    if rid.startswith("claim1."):
        return "claim.threshold"
    if rid.startswith("claim.ref."):
        return "claim.ref"
    if rid in {"claim.punctuation.period.extra", "claim.punctuation.period.tail_missing"}:
        return "claim.punctuation.structure"
    if rid == "text.repeated_word":
        return "text.repeated_word"
    if rid in {
        "drawings.figure.ref.missing_in_impl",
        "drawings.figure.ref.missing_in_description_drawings",
        "drawings.figure.ref.duplicate_in_drawings_section",
    }:
        return "drawings.figure.ref.missing_in_impl"
    if rid.startswith("description.impl_heading.") or rid.startswith("description.heading.") or rid == "description.title.missing" or rid == "description.drawings.figure.ref.missing_in_drawings_section":
        return "description.structure.error"
    if rid == "description.title.length.exceeded":
        return "description.title.length.exceeded"
    if rid.startswith("theme."):
        return "theme.consistency"
    if rid == "punctuation.repeated":
        return "punctuation.repeated"
    if rid == "punctuation.invalid_combo":
        return "punctuation.invalid_combo"
    if rid == "abstract.word_count.exceeded":
        return "abstract.word_count.exceeded"
    return "default"


def _issue_group_label(issue: Issue) -> str:
    rid = str(issue.rule_id or "")
    if rid.startswith("wordlist."):
        section_text = _SECTION_LABELS.get(str(issue.section or ""), str(issue.section or ""))
        category_text = "禁用词" if str(issue.category or "") == "forbidden" else "敏感词"
        return f"{section_text}{category_text}"
    if rid == "text.repeated_word":
        return "\u8fde\u7eed\u91cd\u590d\u8bcd\u8bed"
    if rid in {
        "drawings.figure.ref.missing_in_impl",
        "drawings.figure.ref.missing_in_description_drawings",
        "drawings.figure.ref.duplicate_in_drawings_section",
    }:
        return "\u9644\u56fe\u56fe\u53f7\u6838\u5bf9"
    if rid.startswith("description.impl_heading.") or rid.startswith("description.heading.") or rid.startswith("description.title.") or rid == "description.drawings.figure.ref.missing_in_drawings_section":
        return "\u8bf4\u660e\u4e66\u7ed3\u6784\u4e0e\u6807\u9898"
    if rid.startswith("theme."):
        return "\u4e3b\u9898\u4e00\u81f4\u6027"
    if rid.startswith("claim1."):
        return "权利要求阈值"
    if rid.startswith("claim.ref."):
        return "权利要求引用"
    if rid.startswith("claim.punctuation.period."):
        return "权利要求标点结构"
    if rid.startswith("punctuation."):
        return "标点符号"
    if rid == "abstract.word_count.exceeded":
        return "摘要长度"
    return "规则检查"

def _issue_group_label_compact_for_list(issue: Issue) -> str:
    label = _issue_group_label(issue)
    if label == "权利要求引用":
        return "引用检查"
    if label.startswith("说明书"):
        return label.replace("说明书", "说明", 1)
    return label
def _issue_location_text(issue: Issue) -> str:
    section = str(issue.section or "")
    if section == "claims":
        claim_num = _safe_int(issue.claim_num, None)
        return f"权{claim_num}" if claim_num is not None and claim_num > 0 else "权利要求"
    if section == "description":
        return "说明书"
    if section == "abstract":
        return "摘要"
    if section == "drawings":
        return "附图"
    return _SECTION_LABELS.get(section, section)
def _issue_location_compact_for_list(issue: Issue) -> str:
    return _issue_location_text(issue)
def _extract_quoted_text(text: str) -> str:
    matched = _QUOTED_TERM_RE.search(str(text or ""))
    if not matched:
        return ""
    return str(matched.group(1) or "").strip()
def _extract_digits(text: str) -> list[int]:
    return [int(x) for x in _DIGIT_RE.findall(str(text or ""))]


def _extract_reason_tail(text: str) -> str:
    message = str(text or "")
    matched = re.search(r"[：:]\s*(.+)$", message)
    if not matched:
        return ""
    return str(matched.group(1) or "").strip()


def _audit_cross_section_reason_prefixes_once() -> None:
    global _CROSS_SECTION_REASON_AUDITED
    if bool(_CROSS_SECTION_REASON_AUDITED):
        return
    _CROSS_SECTION_REASON_AUDITED = True
    expected = {
        "description.drawings.figure.ref.missing_in_drawings_section": "\u8bf4\u660e\u4e66\u9644\u56fe\u7f3a\u5c11\u56fe\u53f7",
        "drawings.figure.ref.missing_in_description_drawings": "\u9644\u56fe\u8bf4\u660e\u7f3a\u5c11\u56fe\u53f7",
    }
    for rule_id, prefix in expected.items():
        current = str(_CROSS_SECTION_REASON_PREFIX.get(rule_id, "") or "")
        if current != prefix:
            logger.warning(
                "[formal_review][ui] compact_copy_mismatch rule_id=%s expected=%s actual=%s",
                rule_id,
                prefix,
                current,
            )


def _issue_reason_compact(issue: Issue) -> str:
    _audit_cross_section_reason_prefixes_once()
    rid = str(issue.rule_id or "")
    snippet = str(issue.snippet or "").strip()
    quoted = _extract_quoted_text(str(issue.message or ""))
    token = quoted or snippet
    if rid in {"wordlist.claims.forbidden", "wordlist.description.forbidden"}:
        return f"禁用词“{token}”" if token else "禁用词命中"
    if rid in {"wordlist.claims.sensitive", "wordlist.description.sensitive"}:
        return f"敏感词“{token}”" if token else "敏感词命中"
    if rid == "punctuation.repeated":
        return f"连续标点“{token}”" if token else "连续标点"
    if rid == "punctuation.invalid_combo":
        return f"不规范标点组合“{token}”" if token else "不规范标点组合"
    if rid == "text.repeated_word":
        return f"重复词语“{token}”" if token else "重复词语"
    if rid == "drawings.figure.ref.missing_in_impl":
        message = str(issue.message or "")
        tail = message.split("：", 1)[-1].strip() if "：" in message else ""
        return f"实施方式缺少图号：{tail}" if tail else "实施方式缺少图号"
    if rid == "drawings.figure.ref.duplicate_in_drawings_section":
        return f"\u9644\u56fe\u56fe\u53f7\u91cd\u590d\uff1a{token}" if token else "\u9644\u56fe\u56fe\u53f7\u91cd\u590d"
    if rid in _CROSS_SECTION_REASON_PREFIX:
        tail = _extract_reason_tail(str(issue.message or ""))
        prefix = str(_CROSS_SECTION_REASON_PREFIX.get(rid) or "")
        return f"{prefix}：{tail}" if tail else prefix
    if rid == "description.impl_heading.missing_for_figure_check":
        return "缺少实施方式标题"
    if rid == "description.heading.missing.required":
        message = str(issue.message or "")
        tail = message.split("：", 1)[-1].strip() if "：" in message else ""
        return f"必需小标题缺失：{tail}" if tail else "必需小标题缺失"
    if rid == "description.title.missing":
        return "说明书标题缺失"
    if rid == "description.title.length.exceeded":
        nums = _extract_digits(str(issue.message or ""))
        current = nums[0] if nums else None
        return f"说明书标题超长（{current}）" if current is not None else "说明书标题超长"
    if rid == "theme.claim1.multi_subject":
        return "权利要求1含多个主题"
    if rid == "theme.title_claim1.mismatch":
        return "标题与权利要求1主题不一致"
    if rid == "theme.title_abstract.mismatch":
        return "标题与摘要主题不一致"
    if rid == "theme.title.unrecognized":
        return "标题主题未识别"
    if rid == "claim.ref.self":
        claim_num = _safe_int(issue.claim_num, None)
        return f"权利要求{claim_num}自引用" if claim_num is not None else "自引用"
    if rid == "claim.ref.future":
        nums = _extract_digits(str(issue.message or ""))
        target = nums[-1] if nums else _safe_int(issue.claim_num, None)
        return f"引用了未来项{target}" if target is not None else "引用未来项"
    if rid == "claim.ref.missing_target":
        nums = _extract_digits(str(issue.message or ""))
        target = nums[-1] if nums else None
        return f"引用目标{target}不存在" if target is not None else "引用目标不存在"
    if rid == "claim.ref.choice_word_missing":
        claim_num = _safe_int(issue.claim_num, None)
        return f"权利要求{claim_num}缺少择一词" if claim_num is not None else "缺少择一词"
    if rid == "claim.ref.multi_to_multi.recursive":
        claim_num = _safe_int(issue.claim_num, None)
        return f"权利要求{claim_num}多引多递归" if claim_num is not None else "多引多递归"
    if rid == "claim.ref.marker_basis.missing":
        return "附图标记在被引链中无引用基础"
    if rid == "claim.ref.term_basis.missing":
        return "所述后术语未对应标号说明"
    if rid == "claim1.word_count.exceeded":
        return "权1字数超限"
    if rid == "claim1.marker_count.exceeded":
        return "权1附图标记数超限"
    if rid == "claim.punctuation.period.extra":
        return "句号重复（应仅保留末尾一个）"
    if rid == "claim.punctuation.period.tail_missing":
        return "末尾缺少句号"
    if rid == "abstract.word_count.exceeded":
        nums = _extract_digits(str(issue.message or ""))
        current = nums[-1] if nums else None
        return f"摘要字数{current}超限" if current is not None else "摘要字数超限"
    return str(issue.message or rid or "规则问题")
def _issue_matches_editor(issue: Issue, section: str, claim_num: int | None = None) -> bool:
    if str(getattr(issue, "section", "") or "") != str(section or ""):
        return False
    if str(section or "") != "claims":
        return True
    if claim_num is None:
        return True
    issue_claim_num = _safe_int(getattr(issue, "claim_num", None), None)
    target_claim_num = _safe_int(claim_num, None)
    return issue_claim_num is not None and target_claim_num is not None and int(issue_claim_num) == int(target_claim_num)
@dataclass(slots=True)
class _SectionSegment:
    section: str
    claim_num: int | None
    local_start: int
    local_end: int
    word_range_start: int
    raw_text: str = ""


__all__ = [
    "ClaimItem",
    "DockLayout",
    "EditableSegment",
    "FormalReviewDocument",
    "FormalReviewSettingsDialog",
    "Issue",
    "MarkerNormalizationWritePlan",
    "Path",
    "ProjectionBundle",
    "QColor",
    "QDialog",
    "QFileDialog",
    "QFontMetrics",
    "QHBoxLayout",
    "QHeaderView",
    "QLabel",
    "QMessageBox",
    "QPushButton",
    "QSignalBlocker",
    "QSize",
    "QSizePolicy",
    "QTableWidgetItem",
    "QTextCharFormat",
    "QTextCursor",
    "QTextEdit",
    "QTextFormat",
    "QTimer",
    "QTreeWidgetItem",
    "QWidget",
    "Qt",
    "RULE_REGISTRY",
    "SuppressionStore",
    "WordEngine",
    "_CLAIM_BODY_HEIGHT_PADDING",
    "_CLAIM_BODY_MAX_HEIGHT",
    "_CLAIM_BODY_MIN_HEIGHT",
    "_CLAIM_HEADER_FONT_SIZE",
    "_CLAIM_MARKER_HEIGHT_PADDING",
    "_CLAIM_MARKER_HORIZONTAL_PADDING",
    "_COMMENT_AUTHOR_PREF_KEY",
    "_COMMENT_COPY_PATH_PREF_KEY",
    "_CONTEXT_RADIUS",
    "_DEFAULT_HIGHLIGHT_COLORS",
    "_HIGHLIGHT_COLORS_PREF_KEY",
    "_MARKER_NOTE_PREF_KEY",
    "_RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY",
    "_RESULTS_TREE_DEFAULT_WIDTHS",
    "_RESULTS_TREE_MIN_WIDTH",
    "_RULE_OPTIONS",
    "_SEVERITY_LABELS",
    "_SUPPORTED_WORD_SUFFIXES",
    "_SectionSegment",
    "_TOKEN_RE",
    "_TOOL_COMMENT_PREFIX",
    "_WIDGET_SIZE_MAX",
    "_issue_group_label",
    "_issue_group_label_compact_for_list",
    "_issue_location_compact_for_list",
    "_issue_location_text",
    "_issue_matches_editor",
    "_issue_reason_compact",
    "_issue_type_key",
    "_normalize_highlight_colors",
    "_normalized_word_suffix",
    "_safe_int",
    "apply_write_commands",
    "build_instance_fingerprint",
    "build_issue_id",
    "build_marker_normalization_write_plan",
    "build_report_payload",
    "check_com_find_ready",
    "close_session",
    "connect_active_word",
    "count_effective_chars",
    "datetime",
    "detect_unsaved_source",
    "dock_app_and_word",
    "enabled_rule_id_set",
    "extract_figure_markers",
    "extract_formal_review_document",
    "get_dirty_state",
    "get_document_snapshot",
    "get_pref",
    "get_word_hwnd",
    "html",
    "inspect_doc_clean_state",
    "load_rule_enabled",
    "load_rule_params",
    "load_wordlist_profile_store",
    "load_wordlists",
    "locate_issue_in_word",
    "logger",
    "normalize_word_window",
    "open_or_attach_document",
    "parse_claim_references",
    "parse_marker_note_map",
    "parse_marker_note_payload",
    "parse_plain_text_sections",
    "run_formal_review",
    "run_write_preflight",
    "save_rule_enabled",
    "save_rule_params",
    "save_wordlist_profile_store",
    "set_active_wordlist_profile",
    "set_pref",
    "show_blocking_alert_modal",
    "shutil",
    "sync_comments_inplace",
    "write_report_docx",
    "write_report_xlsx",
]
