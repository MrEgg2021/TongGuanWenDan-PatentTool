from __future__ import annotations

import copy
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Iterable

from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidgetItem,
)

from core.app_preferences import get_official_doc_settings, set_official_doc_settings
from core.official_docs import (
    NoticeInputBundle,
    NoticeInputLeaf,
    NamingGroupConfig,
    NoticeAliasRule,
    NoticeMeta,
    NoticeTypeNamingConfig,
    ParsedNotice,
    PdfSource,
    ProcessOptions,
    ProcessSummary,
    default_naming_config_for_type,
    normalize_filename_separator,
    normalize_notice_input_paths,
    normalize_type_naming_config,
    parse_official_notice_archive,
    process_official_notice_archives,
    render_notice_output,
    render_notice_output_preview,
    resolve_notice_inputs,
    validate_filename_separator,
    normalize_notice_name_for_meta,
)
from core.official_docs.field_registry import (
    RECEIPT_TYPE_KEY,
    get_supported_type_catalog,
    get_type_disabled_reason,
    get_type_display_name,
    get_type_tokens,
    is_type_processable,
    normalize_notice_type,
)
from core.tgd_data_management_impl.pinyin_utils import get_pinyin_full, get_pinyin_initials
from core.official_docs.image_to_pdf import image_bytes_to_pdf_bytes
from core.official_docs.zip_reader import NoticeZipReader
from gui.dialog_utils import show_blocking_alert_modal
from gui.official_docs_dialogs import (
    show_official_docs_archive_consent_dialog,
    show_official_docs_collision_dialog,
    show_official_docs_confirm_dialog,
    show_official_docs_done_dialog,
    show_official_docs_pdf_parse_enable_notice_dialog,
)


OFFICIAL_DOC_SETTINGS_VERSION = 3
OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION = 1
OFFICIAL_DOC_BASE_TYPES: tuple[str, ...] = ("exam_opinion", "rectification")
OFFICIAL_DOC_UNGROUPED_ROOT_LABEL = "其他（未分组）"
OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS: tuple[str, ...] = (
    "210326|向外国申请专利保密审查意见通知书",
    "200029|办理手续补正通知书",
)
TREE_DATA_ROLE = Qt.UserRole
TREE_NODE_LEAF = "leaf"
TREE_NODE_BUNDLE = "bundle"
TYPE_KEY_ROLE = Qt.UserRole
TYPE_PROCESSABLE_ROLE = Qt.UserRole + 100
TYPE_IS_NEW_ROLE = Qt.UserRole + 101
TYPE_DISABLED_REASON_ROLE = Qt.UserRole + 102
TYPE_MEMBER_KEYS_ROLE = Qt.UserRole + 103
TYPE_NODE_KIND_ROLE = Qt.UserRole + 104
TYPE_GROUP_ID_ROLE = Qt.UserRole + 105
TYPE_DISPLAY_NAME_ROLE = Qt.UserRole + 106
FILENAME_TOKEN_ROLE = Qt.UserRole
TYPE_NODE_KIND_GROUP = "group"
TYPE_NODE_KIND_UNGROUPED_ROOT = "ungrouped_root"
TYPE_NODE_KIND_UNGROUPED_TYPE = "ungrouped_type"
TYPE_NODE_KIND_GROUP_MEMBER = "group_member"
CONFIG_TAB_INDEXES = {1, 2}
PDF_PARSE_FIELD_FLAGS_DEFAULT: dict[str, bool] = {
    "applicant": False,
    "inventor": False,
    "agent": False,
    "agency_raw": False,
    "department": False,
    "center": False,
    "examiner": False,
    "panel": False,
    "reject_reason": False,
    "prior_art": False,
    "dossier_no": False,
    "authorization_pub_no": False,
    "authorization_pub_date": False,
    "certificate_no": False,
    "qrcode_link": False,
    "qrcode_image": False,
}
NAMING_ALIAS_SPLITTER_KEY = "naming_alias_splitter_sizes_v1"
NAMING_ALIAS_SPLITTER_DEFAULT = [3, 2]
NAMING_ALIAS_SPLITTER_MIN_SIZE = 96
OFFICIAL_DOC_PRESET_NAMING_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "review_rectification",
        "审查/补正",
        (
            "exam_opinion",
            *OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS[:1],
            "rectification",
            "210403|第N次审查意见通知书",
            "230302|第N次审查意见通知书",
            "230301|第N次补正通知书",
            "210401|第一次审查意见通知书",
            "220301|第一次审查意见通知书",
            "220301|第二次审查意见通知书",
            "210302|补正通知书",
            *OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS[1:],
            "201510|审查业务专用函（非正常）",
        ),
    ),
    (
        "certificate",
        "证书",
        (
            "400001|发明专利证书",
            "400002|实用新型专利证书",
            "400003|外观设计专利证书",
        ),
    ),
    ("receipt", "收据", ("10071|电子提交收据",)),
    (
        "fee_notice",
        "费用通知",
        (
            "PCT/RO/102C|关于缴纳规定费用的通知书",
            "200103|缴纳申请费通知书",
            "200701|缴费通知书",
            "200021|收费减缴审批通知书",
            "200027|退款审批通知书",
        ),
    ),
    (
        "application_flow",
        "申请流程",
        (
            "200101|专利申请受理通知书",
            "210305|发明专利申请公布通知书",
            "210304|发明专利申请初步审查合格通知书",
            "210307|发明专利申请进入实质审查阶段通知书",
            "200602|办理登记手续通知书",
        ),
    ),
    (
        "rights_procedure",
        "权利/手续",
        (
            "200702|专利权终止通知书",
            "200022|视为撤回通知书",
            "200601|视为放弃取得专利权通知书",
            "200023|视为未提出通知书（著录项目变更）",
            "200028|手续合格通知书（撤回专利申请）",
            "200028|手续合格通知书（著录项目变更）",
            "200916|延长期限审批通知书",
            "201013|转送文件通知书（专利权人）",
        ),
    ),
    (
        "reexam_invalidation",
        "复审/无效",
        (
            "200905|复审请求受理通知书",
            "200908|复审通知书(首页)",
            "200912|复审决定书（首页）",
            "200913|复审案件结案通知书",
            "201004|无效宣告请求受理通知书（专利权人）",
            "201014|无效宣告请求口头审理通知书",
            "201019|无效宣告请求审查决定书",
        ),
    ),
    (
        "pct_international",
        "PCT/国际",
        (
            "PCT/ISA/210C|国际检索报告",
            "PCT/ISA/237C|国际检索单位书面意见",
            "PCT/ISA/220C|传送国际检索报告和国际检索单位书面意见或宣布的通知书",
            "PCT/RO/105C|国际申请号和国际申请日通知书",
            "PCT/ISA/202C|收到检索本的通知书",
            "PCT/ISA/224C|无其他可适用表格时的通知书",
        ),
    ),
    ("rejection", "驳回", ("210407|驳回决定", "200305|驳回决定通知书")),
)


def _extract_notice_code(type_key: str) -> str:
    text = str(type_key or "").strip()
    if "|" in text:
        return str(text.split("|", 1)[0] or "").strip()
    return ""


def _build_type_search_terms(entry: dict[str, Any]) -> dict[str, str]:
    display_name = str(entry.get("display_name", "") or "").strip()
    key = normalize_notice_type(str(entry.get("key", "") or "").strip())
    code = _extract_notice_code(key)
    return {
        "display_name": display_name,
        "code": code,
        "pinyin_full": get_pinyin_full(display_name),
        "pinyin_initials": get_pinyin_initials(display_name),
    }


def _match_type_search(entry: dict[str, Any], query: str) -> bool:
    key = str(query or "").strip().lower()
    if not key:
        return True
    terms = _build_type_search_terms(entry)
    targets: set[str] = {
        str(terms.get("display_name", "") or "").lower(),
        str(terms.get("code", "") or "").lower(),
        str(terms.get("pinyin_full", "") or "").lower(),
        str(terms.get("pinyin_initials", "") or "").lower(),
    }

    member_keys = entry.get("member_keys")
    if isinstance(member_keys, (list, tuple)):
        for member_key in member_keys:
            member_text = normalize_notice_type(str(member_key or "").strip())
            if not member_text:
                continue
            targets.add(member_text.lower())
            member_code = _extract_notice_code(member_text)
            if member_code:
                targets.add(member_code.lower())

    members = entry.get("members")
    if isinstance(members, list):
        for member in members:
            if not isinstance(member, dict):
                continue
            m_terms = _build_type_search_terms(member)
            targets.add(str(m_terms.get("display_name", "") or "").lower())
            targets.add(str(m_terms.get("code", "") or "").lower())
            targets.add(str(m_terms.get("pinyin_full", "") or "").lower())
            targets.add(str(m_terms.get("pinyin_initials", "") or "").lower())

    return any(key in target for target in targets if target)


def _canonical_display_name_for_type(display_name: str) -> str:
    text = str(display_name or "").strip()
    if not text:
        return ""
    synonym_map = {
        "驳回决定": "驳回决定通知书",
        "驳回决定通知书": "驳回决定通知书",
    }
    return str(synonym_map.get(text, text))


def _canonical_notice_name_for_display(notice_name: str) -> str:
    text = str(notice_name or "").strip()
    if not text:
        return ""
    normalized = _canonical_display_name_for_type(text)
    return str(normalized or text).strip()


def _build_type_display_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups_by_bucket: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for raw_entry in entries:
        entry = dict(raw_entry or {})
        type_key = normalize_notice_type(str(entry.get("key", "") or "").strip())
        if not type_key:
            continue
        display_name = str(entry.get("display_name", "") or "").strip() or get_type_display_name(type_key)
        canonical_name = _canonical_display_name_for_type(display_name) or display_name or type_key
        bucket_key = canonical_name

        group = groups_by_bucket.get(bucket_key)
        if group is None:
            group = {
                "display_name": canonical_name,
                "member_keys": [],
                "members": [],
                "processable": False,
                "disabled_reason": "",
                "is_new": False,
                "primary_key": "",
            }
            groups_by_bucket[bucket_key] = group
            order.append(bucket_key)

        member_keys = group.setdefault("member_keys", [])
        if type_key not in member_keys:
            member_keys.append(type_key)

        members = group.setdefault("members", [])
        members.append(entry)

        if bool(entry.get("processable", True)):
            group["processable"] = True
        if bool(entry.get("is_new", False)):
            group["is_new"] = True

    groups: list[dict[str, Any]] = []
    for bucket in order:
        group = groups_by_bucket[bucket]
        members = list(group.get("members", []) or [])
        processable_members = [m for m in members if bool(m.get("processable", True))]
        primary_pool = processable_members if processable_members else members
        primary_key = ""
        if primary_pool:
            primary_key = normalize_notice_type(str(primary_pool[0].get("key", "") or "").strip())
        if not primary_key:
            keys = [normalize_notice_type(str(k or "").strip()) for k in list(group.get("member_keys", []) or [])]
            keys = [k for k in keys if k]
            if keys:
                primary_key = keys[0]
        group["primary_key"] = primary_key

        if not bool(group.get("processable", False)):
            reasons: list[str] = []
            for m in members:
                reason = str(m.get("disabled_reason", "") or "").strip()
                if reason and reason not in reasons:
                    reasons.append(reason)
            group["disabled_reason"] = "；".join(reasons)
        else:
            group["disabled_reason"] = ""

        groups.append(group)
    return groups


def _default_kind_cards(kind: str) -> list[str]:
    cfg = default_naming_config_for_type(kind)
    return [str(token or "").strip() for token in (cfg.filename_fields or []) if str(token or "").strip()]


def _default_alias_rows(kind: str) -> list[dict[str, Any]]:
    cfg = default_naming_config_for_type(kind)
    rows: list[dict[str, Any]] = []
    for rule in cfg.alias_rules or []:
        notice_name = str(rule.notice_name or "").strip()
        short_name = str(rule.short_name or "").strip()
        if notice_name and short_name:
            rows.append(
                {
                    "notice_name": notice_name,
                    "short_name": short_name,
                    "enabled": bool(rule.enabled),
                }
            )
    return rows


def _group_config_notice_type_hint(group_id: str, member_type_keys: list[str], fallback: str = "exam_opinion") -> str:
    normalized_members = [
        normalize_notice_type(str(member_key or "").strip())
        for member_key in list(member_type_keys or [])
        if normalize_notice_type(str(member_key or "").strip())
    ]
    if str(group_id or "").strip() == "receipt" and RECEIPT_TYPE_KEY in normalized_members:
        return RECEIPT_TYPE_KEY
    if normalized_members:
        return normalized_members[0]
    return normalize_notice_type(fallback) or "exam_opinion"


def _default_group_config(kind: str) -> dict[str, Any]:
    return {
        "naming_mode": "default",
        "filename_fields": _default_kind_cards(kind),
        "alias_rules": [],
    }


def _default_naming_groups_payload() -> tuple[list[dict[str, Any]], dict[str, str]]:
    groups: list[dict[str, Any]] = []
    membership: dict[str, str] = {}
    for group_id, group_name, raw_members in OFFICIAL_DOC_PRESET_NAMING_GROUPS:
        member_keys = [normalize_notice_type(item) for item in raw_members if normalize_notice_type(item)]
        groups.append(
            {
                "id": group_id,
                "name": group_name,
                "member_type_keys": list(member_keys),
                "group_config": _default_group_config(member_keys[0] if member_keys else "exam_opinion"),
            }
        )
        for member_key in member_keys:
            membership[member_key] = group_id
    return groups, membership


def _explicit_alias_rows_from_raw_cfg(raw_cfg: Any) -> list[dict[str, Any]]:
    if isinstance(raw_cfg, NoticeTypeNamingConfig):
        raw_rules = raw_cfg.alias_rules
    elif isinstance(raw_cfg, dict):
        raw_rules = raw_cfg.get("alias_rules")
    else:
        raw_rules = []

    rows: list[dict[str, Any]] = []
    for raw_rule in raw_rules if isinstance(raw_rules, Iterable) else []:
        if isinstance(raw_rule, NoticeAliasRule):
            notice_name = _canonical_notice_name_for_display(str(raw_rule.notice_name or "").strip())
            short_name = str(raw_rule.short_name or "").strip()
            enabled = bool(raw_rule.enabled)
        elif isinstance(raw_rule, dict):
            notice_name = _canonical_notice_name_for_display(str(raw_rule.get("notice_name", "") or "").strip())
            short_name = str(raw_rule.get("short_name", "") or "").strip()
            enabled = bool(raw_rule.get("enabled", False))
        else:
            continue
        if not notice_name or not short_name:
            continue
        rows.append(
            {
                "notice_name": notice_name,
                "short_name": short_name,
                "enabled": enabled,
            }
        )
    return rows


def _normalize_naming_alias_splitter_sizes(raw: Any) -> list[int] | None:
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return None
    values: list[int] = []
    for item in raw[:2]:
        try:
            value = int(item)
        except Exception:
            return None
        values.append(max(NAMING_ALIAS_SPLITTER_MIN_SIZE, value))
    return values


def _default_settings() -> dict[str, Any]:
    default_root = os.path.abspath(os.path.join(os.getcwd(), "output"))
    default_groups, default_membership = _default_naming_groups_payload()
    return {
        "version": OFFICIAL_DOC_SETTINGS_VERSION,
        "write_summary": True,
        "write_archive": False,
        "confirm_each": False,
        "enable_exam_pdf_parse": False,
        "no_list_multi_pdf_mode": "split_each_pdf",
        "filename_separator": "+",
        "pdf_parse_enable_notice_suppressed": False,
        "pdf_parse_field_flags": dict(PDF_PARSE_FIELD_FLAGS_DEFAULT),
        "summary_root_dir": default_root,
        "archive_root_dir": default_root,
        "archive_consent_doc_version": OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION,
        "archive_consent_accepted_version": 0,
        NAMING_ALIAS_SPLITTER_KEY: list(NAMING_ALIAS_SPLITTER_DEFAULT),
        "type_configs": {
            "exam_opinion": {
                "naming_mode": "default",
                "filename_fields": _default_kind_cards("exam_opinion"),
                "alias_rules": _default_alias_rows("exam_opinion"),
            },
            "rectification": {
                "naming_mode": "default",
                "filename_fields": _default_kind_cards("rectification"),
                "alias_rules": _default_alias_rows("rectification"),
            },
        },
        "naming_groups": default_groups,
        "type_group_membership": default_membership,
    }


def _notice_key_from_meta(meta: NoticeMeta) -> str:
    code = str(meta.notice_code or "").strip()
    name = str(meta.notice_name or "").strip()
    key = f"{code}|{name}".strip("|")
    return key or "unknown"


def _leaf_display_name(leaf_item: dict[str, Any]) -> str:
    inner_zip_name = str(leaf_item.get("inner_zip_name", "") or "").strip()
    if inner_zip_name:
        base = os.path.basename(inner_zip_name.replace("\\", "/"))
        return base or inner_zip_name
    display_name = str(leaf_item.get("display_name", "") or "").strip()
    if display_name:
        return display_name
    source_zip = str(leaf_item.get("source_path", "") or "").strip()
    if source_zip:
        return os.path.basename(source_zip)
    zip_path = str(leaf_item.get("zip_path", "") or "").strip()
    return os.path.basename(zip_path) if zip_path else "未命名通知书"

def _leaf_source_label(leaf_item: dict[str, Any]) -> str:
    label = str(leaf_item.get("source_label", "") or "").strip()
    if label:
        return label
    source_path = str(leaf_item.get("source_path", "") or "").strip()
    inner_zip_name = str(leaf_item.get("inner_zip_name", "") or "").strip()
    if source_path and inner_zip_name:
        inner_base = os.path.basename(inner_zip_name.replace("\\", "/")) or inner_zip_name
        return f"{os.path.basename(source_path)} > {inner_base}"
    return source_path




__all__ = [
    "annotations",
    "copy",
    "os",
    "shutil",
    "subprocess",
    "tempfile",
    "asdict",
    "replace",
    "Path",
    "Any",
    "Iterable",
    "QSignalBlocker",
    "Qt",
    "QTimer",
    "QApplication",
    "QComboBox",
    "QFileDialog",
    "QInputDialog",
    "QListWidget",
    "QListWidgetItem",
    "QMessageBox",
    "QTableWidget",
    "QTableWidgetItem",
    "QTreeWidgetItem",
    "get_official_doc_settings",
    "set_official_doc_settings",
    "NoticeInputBundle",
    "NoticeInputLeaf",
    "NamingGroupConfig",
    "NoticeMeta",
    "NoticeTypeNamingConfig",
    "ParsedNotice",
    "PdfSource",
    "ProcessOptions",
    "ProcessSummary",
    "default_naming_config_for_type",
    "normalize_filename_separator",
    "normalize_notice_input_paths",
    "normalize_type_naming_config",
    "parse_official_notice_archive",
    "process_official_notice_archives",
    "render_notice_output",
    "render_notice_output_preview",
    "resolve_notice_inputs",
    "validate_filename_separator",
    "normalize_notice_name_for_meta",
    "get_supported_type_catalog",
    "get_type_disabled_reason",
    "get_type_display_name",
    "get_type_tokens",
    "is_type_processable",
    "normalize_notice_type",
    "RECEIPT_TYPE_KEY",
    "get_pinyin_full",
    "get_pinyin_initials",
    "image_bytes_to_pdf_bytes",
    "NoticeZipReader",
    "show_official_docs_archive_consent_dialog",
    "show_official_docs_collision_dialog",
    "show_official_docs_confirm_dialog",
    "show_blocking_alert_modal",
    "show_official_docs_done_dialog",
    "show_official_docs_pdf_parse_enable_notice_dialog",
    "OFFICIAL_DOC_SETTINGS_VERSION",
    "OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION",
    "OFFICIAL_DOC_BASE_TYPES",
    "OFFICIAL_DOC_UNGROUPED_ROOT_LABEL",
    "OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS",
    "OFFICIAL_DOC_PRESET_NAMING_GROUPS",
    "TREE_DATA_ROLE",
    "TREE_NODE_LEAF",
    "TREE_NODE_BUNDLE",
    "TYPE_KEY_ROLE",
    "TYPE_PROCESSABLE_ROLE",
    "TYPE_IS_NEW_ROLE",
    "TYPE_DISABLED_REASON_ROLE",
    "TYPE_MEMBER_KEYS_ROLE",
    "TYPE_NODE_KIND_ROLE",
    "TYPE_GROUP_ID_ROLE",
    "TYPE_DISPLAY_NAME_ROLE",
    "TYPE_NODE_KIND_GROUP",
    "TYPE_NODE_KIND_UNGROUPED_ROOT",
    "TYPE_NODE_KIND_UNGROUPED_TYPE",
    "TYPE_NODE_KIND_GROUP_MEMBER",
    "FILENAME_TOKEN_ROLE",
    "CONFIG_TAB_INDEXES",
    "PDF_PARSE_FIELD_FLAGS_DEFAULT",
    "NAMING_ALIAS_SPLITTER_KEY",
    "NAMING_ALIAS_SPLITTER_DEFAULT",
    "NAMING_ALIAS_SPLITTER_MIN_SIZE",
    "_extract_notice_code",
    "_build_type_search_terms",
    "_match_type_search",
    "_canonical_display_name_for_type",
    "_canonical_notice_name_for_display",
    "_build_type_display_groups",
    "_default_kind_cards",
    "_default_alias_rows",
    "_group_config_notice_type_hint",
    "_default_naming_groups_payload",
    "_explicit_alias_rows_from_raw_cfg",
    "_normalize_naming_alias_splitter_sizes",
    "_default_settings",
    "_notice_key_from_meta",
    "_leaf_display_name",
    "_leaf_source_label",
]
