from __future__ import annotations

from .shared import (
    Any,
    NAMING_ALIAS_SPLITTER_DEFAULT,
    NAMING_ALIAS_SPLITTER_KEY,
    OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION,
    OFFICIAL_DOC_BASE_TYPES,
    OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS,
    OFFICIAL_DOC_SETTINGS_VERSION,
    PDF_PARSE_FIELD_FLAGS_DEFAULT,
    ParsedNotice,
    NoticeTypeNamingConfig,
    QTimer,
    TYPE_NODE_KIND_UNGROUPED_TYPE,
    _build_type_display_groups,
    _canonical_notice_name_for_display,
    _default_naming_groups_payload,
    _default_settings,
    _explicit_alias_rows_from_raw_cfg,
    _group_config_notice_type_hint,
    _normalize_naming_alias_splitter_sizes,
    _notice_key_from_meta,
    copy,
    get_official_doc_settings,
    get_supported_type_catalog,
    get_type_disabled_reason,
    get_type_display_name,
    is_type_processable,
    normalize_filename_separator,
    normalize_notice_type,
    normalize_type_naming_config,
    os,
    set_official_doc_settings,
    shutil,
    tempfile,
)


def _init_official_docs_state(self) -> None:
    if bool(getattr(self, "_official_docs_state_ready", False)):
        return

    self._official_docs_state_ready = True
    self._official_docs_temp_root = ""
    self._official_docs_temp_files: list[str] = []

    self._official_docs_nodes: list[dict[str, Any]] = []
    self._official_docs_bundles: dict[str, dict[str, Any]] = {}
    self._official_docs_leaves: dict[str, dict[str, Any]] = {}
    self._official_docs_bundle_expanded: dict[str, bool] = {}
    self._official_docs_search_text = ""
    self._official_docs_selected_leaf_id = ""
    self._official_docs_last_import_ignored = []
    self._official_docs_last_process_leaf_ids: list[str] = []

    self._official_docs_tree_rebuilding = False
    self._official_docs_signals_blocked = False
    self._official_docs_alias_loading = False
    self._official_docs_tab_switching = False
    self._official_docs_last_tab_index = 0
    self._official_docs_type_search_text = ""
    self._official_docs_type_members_by_primary: dict[str, list[str]] = {}
    self._official_docs_type_tree_rebuilding = False
    self._official_docs_naming_splitter_sizes_pending: list[int] | None = None
    self._official_docs_naming_splitter_syncing = False

    if not hasattr(self, "_official_docs_naming_splitter_save_timer"):
        try:
            timer = QTimer(self)
        except Exception:
            timer = QTimer()
        timer.setSingleShot(True)
        timer.setInterval(250)
        timer.timeout.connect(self._persist_official_docs_naming_splitter_sizes)
        self._official_docs_naming_splitter_save_timer = timer

    self._official_docs_collision_policy_cache: tuple[str, bool] | None = None

    saved = self._normalize_official_doc_settings(get_official_doc_settings())
    self._official_docs_saved_settings = saved
    self._official_docs_working_settings = copy.deepcopy(saved)
    self._official_docs_current_type = "exam_opinion"
    self._official_docs_type_selection_context = {
        "node_kind": TYPE_NODE_KIND_UNGROUPED_TYPE,
        "group_id": "",
        "type_key": "exam_opinion",
        "member_keys": ["exam_opinion"],
        "display_name": get_type_display_name("exam_opinion"),
    }
    self._official_docs_dirty = False

    self._apply_official_docs_settings_to_ui()
    self._render_official_docs_tree()
    self._refresh_official_docs_detail()

def _ensure_official_docs_temp_root(self) -> str:
    path = str(getattr(self, "_official_docs_temp_root", "") or "").strip()
    if path and os.path.isdir(path):
        return path
    root = tempfile.mkdtemp(prefix="official_docs_")
    self._official_docs_temp_root = root
    return root

def _cleanup_official_docs_temp(self) -> None:
    files = list(getattr(self, "_official_docs_temp_files", []) or [])
    for file_path in files:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
    self._official_docs_temp_files = []

    root = str(getattr(self, "_official_docs_temp_root", "") or "").strip()
    if root:
        try:
            shutil.rmtree(root, ignore_errors=True)
        except Exception:
            pass
    self._official_docs_temp_root = ""

def _serialize_type_cfg(self, cfg: NoticeTypeNamingConfig) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rule in cfg.alias_rules or []:
        notice_name = str(rule.notice_name or "").strip()
        short_name = str(rule.short_name or "").strip()
        if not notice_name or not short_name:
            continue
        rows.append(
            {
                "notice_name": notice_name,
                "short_name": short_name,
                "enabled": bool(rule.enabled),
            }
        )
    return {
        "naming_mode": str(cfg.naming_mode or "default"),
        "filename_fields": [str(token or "").strip() for token in (cfg.filename_fields or []) if str(token or "").strip()],
        "alias_rules": rows,
    }

def _persist_official_doc_settings_safely(data: dict[str, Any]) -> None:
    # 历史契约保留：set_official_doc_settings(defaults)
    try:
        set_official_doc_settings(data)
    except Exception:
        return

def _normalize_group_member_keys(raw_members: Any) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    if not isinstance(raw_members, (list, tuple)):
        return normalized
    for raw_key in raw_members:
        key = normalize_notice_type(str(raw_key or "").strip())
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized

def _default_group_cfg_payload(self, notice_type_hint: str = "exam_opinion") -> dict[str, Any]:
    normalized_hint = normalize_notice_type(notice_type_hint) or "exam_opinion"
    payload = self._serialize_type_cfg(normalize_type_naming_config(None, normalized_hint))
    payload["alias_rules"] = []
    return payload

def _serialize_naming_group(
    self,
    *,
    group_id: str,
    name: str,
    member_type_keys: list[str],
    raw_group_config: Any,
) -> dict[str, Any]:
    notice_type_hint = _group_config_notice_type_hint(group_id, member_type_keys, "exam_opinion")
    group_cfg = normalize_type_naming_config(raw_group_config, notice_type_hint)
    payload = self._serialize_type_cfg(group_cfg)
    payload["alias_rules"] = []
    return {
        "id": str(group_id or "").strip(),
        "name": str(name or "").strip(),
        "member_type_keys": list(member_type_keys),
        "group_config": payload,
    }


def _alias_notice_options_for_member_key(self, member_key: str) -> list[str]:
    normalized_key = normalize_notice_type(member_key)
    if not normalized_key:
        return []

    options: list[str] = []
    for entry in _build_type_display_groups(self._collect_available_type_entries()):
        primary_key = normalize_notice_type(str(entry.get("primary_key", "") or "").strip())
        member_keys = [
            normalize_notice_type(str(raw_key or "").strip())
            for raw_key in list(entry.get("member_keys", []) or [])
            if normalize_notice_type(str(raw_key or "").strip())
        ]
        if normalized_key != primary_key and normalized_key not in member_keys:
            continue
        candidates = [
            str(entry.get("display_name", "") or "").strip(),
            *[str(get_type_display_name(raw_key) or "").strip() for raw_key in member_keys],
        ]
        for candidate in candidates:
            canonical = _canonical_notice_name_for_display(candidate)
            if canonical and canonical not in options:
                options.append(canonical)
        break

    if not options:
        fallback = _canonical_notice_name_for_display(str(get_type_display_name(normalized_key) or "").strip())
        if fallback:
            options.append(fallback)
    return options


def _migrate_group_alias_rules_to_type_configs(
    self,
    *,
    raw_groups: Any,
    raw_membership: Any,
    normalized_type_configs: dict[str, dict[str, Any]],
) -> None:
    membership_by_group: dict[str, list[str]] = {}
    if isinstance(raw_membership, dict):
        for raw_type_key, raw_group_id in raw_membership.items():
            type_key = normalize_notice_type(str(raw_type_key or "").strip())
            group_id = str(raw_group_id or "").strip()
            if not type_key or not group_id:
                continue
            membership_by_group.setdefault(group_id, [])
            if type_key not in membership_by_group[group_id]:
                membership_by_group[group_id].append(type_key)

    for raw_group in raw_groups if isinstance(raw_groups, (list, tuple)) else []:
        if not isinstance(raw_group, dict):
            continue
        group_id = str(raw_group.get("id", "") or "").strip()
        member_keys = _normalize_group_member_keys(raw_group.get("member_type_keys"))
        for member_key in membership_by_group.get(group_id, []):
            if member_key not in member_keys:
                member_keys.append(member_key)
        if not member_keys:
            continue

        group_alias_rows = _explicit_alias_rows_from_raw_cfg(raw_group.get("group_config"))
        if not group_alias_rows:
            continue

        for member_key in member_keys:
            member_options = set(_alias_notice_options_for_member_key(self, member_key))
            if not member_options:
                continue
            matched_rows = [
                dict(row)
                for row in group_alias_rows
                if _canonical_notice_name_for_display(str(row.get("notice_name", "") or "").strip()) in member_options
            ]
            payload = dict(normalized_type_configs.get(member_key) or self._default_group_cfg_payload(member_key))
            explicit_rows = list(payload.get("alias_rules", []) or [])
            if explicit_rows:
                continue
            payload["alias_rules"] = matched_rows
            normalized_type_configs[member_key] = payload

def _normalize_naming_groups_payload(
    self,
    raw_groups: Any,
    raw_membership: Any,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    normalized_groups: list[dict[str, Any]] = []
    member_order_by_group: dict[str, list[str]] = {}
    member_owner: dict[str, str] = {}
    seen_group_ids: set[str] = set()

    for raw_group in raw_groups if isinstance(raw_groups, (list, tuple)) else []:
        if not isinstance(raw_group, dict):
            continue
        group_id = str(raw_group.get("id", "") or "").strip()
        group_name = str(raw_group.get("name", "") or "").strip()
        if not group_id or not group_name or group_id in seen_group_ids:
            continue

        member_keys = _normalize_group_member_keys(raw_group.get("member_type_keys"))
        normalized_group = self._serialize_naming_group(
            group_id=group_id,
            name=group_name,
            member_type_keys=member_keys,
            raw_group_config=raw_group.get("group_config"),
        )
        normalized_groups.append(normalized_group)
        seen_group_ids.add(group_id)
        member_order_by_group[group_id] = []
        for key in member_keys:
            if key in member_owner:
                continue
            member_owner[key] = group_id
            member_order_by_group[group_id].append(key)

    if isinstance(raw_membership, dict):
        for raw_type_key, raw_group_id in raw_membership.items():
            type_key = normalize_notice_type(str(raw_type_key or "").strip())
            group_id = str(raw_group_id or "").strip()
            if not type_key or not group_id or group_id not in seen_group_ids or type_key in member_owner:
                continue
            member_owner[type_key] = group_id
            member_order_by_group.setdefault(group_id, []).append(type_key)

    for group in normalized_groups:
        group_id = str(group.get("id", "") or "").strip()
        group["member_type_keys"] = list(member_order_by_group.get(group_id, []))

    return normalized_groups, member_owner


def _migrate_untouched_legacy_default_groups(
    self,
    raw_groups: Any,
    raw_membership: Any,
) -> tuple[Any, Any]:
    current_groups, current_membership = _default_naming_groups_payload()
    legacy_groups = copy.deepcopy(current_groups)
    legacy_membership = dict(current_membership)
    added_keys = set(OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS)

    for group in legacy_groups:
        if str(group.get("id", "") or "").strip() != "review_rectification":
            continue
        group["member_type_keys"] = [
            key
            for key in list(group.get("member_type_keys", []) or [])
            if normalize_notice_type(str(key or "").strip()) not in added_keys
        ]
    for key in added_keys:
        legacy_membership.pop(key, None)

    normalized_existing = self._normalize_naming_groups_payload(raw_groups, raw_membership)
    normalized_legacy = self._normalize_naming_groups_payload(legacy_groups, legacy_membership)
    if normalized_existing != normalized_legacy:
        return raw_groups, raw_membership
    return current_groups, current_membership


def _normalize_official_doc_settings(self, raw: Any) -> dict[str, Any]:
    defaults = _default_settings()
    if not isinstance(raw, dict):
        _persist_official_doc_settings_safely(defaults)
        return copy.deepcopy(defaults)
    if int((raw or {}).get("version", 0) or 0) != OFFICIAL_DOC_SETTINGS_VERSION:
        _persist_official_doc_settings_safely(defaults)
        return copy.deepcopy(defaults)

    normalized = copy.deepcopy(defaults)
    normalized["write_summary"] = bool(raw.get("write_summary", normalized["write_summary"]))
    normalized["write_archive"] = bool(raw.get("write_archive", normalized["write_archive"]))
    normalized["confirm_each"] = bool(raw.get("confirm_each", normalized["confirm_each"]))
    normalized["enable_exam_pdf_parse"] = bool(raw.get("enable_exam_pdf_parse", normalized["enable_exam_pdf_parse"]))
    normalized["filename_separator"] = normalize_filename_separator(
        raw.get("filename_separator", normalized["filename_separator"])
    )
    mode_value = str(raw.get("no_list_multi_pdf_mode", normalized["no_list_multi_pdf_mode"]) or "").strip().lower()
    normalized["no_list_multi_pdf_mode"] = "merge_all" if mode_value == "merge_all" else "split_each_pdf"
    normalized["pdf_parse_enable_notice_suppressed"] = bool(
        raw.get("pdf_parse_enable_notice_suppressed", normalized["pdf_parse_enable_notice_suppressed"])
    )
    raw_pdf_flags = raw.get("pdf_parse_field_flags", {})
    normalized_pdf_flags = dict(PDF_PARSE_FIELD_FLAGS_DEFAULT)
    if isinstance(raw_pdf_flags, dict):
        legacy_alias = {
            "reject_clauses": "reject_reason",
            "reject_reasons": "reject_reason",
        }
        for old_key, new_key in legacy_alias.items():
            if bool(raw_pdf_flags.get(old_key, False)):
                normalized_pdf_flags[new_key] = True
        for field_key in normalized_pdf_flags.keys():
            if field_key in raw_pdf_flags:
                normalized_pdf_flags[field_key] = bool(raw_pdf_flags.get(field_key, normalized_pdf_flags[field_key]))
    normalized["pdf_parse_field_flags"] = normalized_pdf_flags

    summary_root = str(raw.get("summary_root_dir", normalized["summary_root_dir"]) or "").strip()
    archive_root = str(raw.get("archive_root_dir", normalized["archive_root_dir"]) or "").strip()
    if summary_root:
        normalized["summary_root_dir"] = summary_root
    if archive_root:
        normalized["archive_root_dir"] = archive_root

    normalized["archive_consent_doc_version"] = int(
        raw.get("archive_consent_doc_version", OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION)
        or OFFICIAL_DOC_ARCHIVE_CONSENT_DOC_VERSION
    )
    normalized["archive_consent_accepted_version"] = max(
        0,
        int(raw.get("archive_consent_accepted_version", 0) or 0),
    )
    splitter_sizes = _normalize_naming_alias_splitter_sizes(raw.get(NAMING_ALIAS_SPLITTER_KEY))
    if splitter_sizes is None:
        splitter_sizes = list(NAMING_ALIAS_SPLITTER_DEFAULT)
    normalized[NAMING_ALIAS_SPLITTER_KEY] = splitter_sizes

    raw_type_configs = raw.get("type_configs", {})
    if not isinstance(raw_type_configs, dict):
        raw_type_configs = {}

    normalized_type_configs: dict[str, dict[str, Any]] = {}
    type_keys: list[str] = []
    for base_key in OFFICIAL_DOC_BASE_TYPES:
        key = normalize_notice_type(base_key)
        if key and key not in type_keys:
            type_keys.append(key)
    for raw_key in raw_type_configs.keys():
        key = normalize_notice_type(str(raw_key or "").strip())
        if key and key not in type_keys:
            type_keys.append(key)
    for key in type_keys:
        parsed_cfg = normalize_type_naming_config(raw_type_configs.get(key), key)
        payload = self._serialize_type_cfg(parsed_cfg)
        payload["alias_rules"] = _explicit_alias_rows_from_raw_cfg(raw_type_configs.get(key))
        normalized_type_configs[key] = payload
    normalized["type_configs"] = normalized_type_configs

    raw_groups = raw.get("naming_groups", [])
    raw_membership = raw.get("type_group_membership", {})
    _migrate_group_alias_rules_to_type_configs(
        self,
        raw_groups=raw_groups,
        raw_membership=raw_membership,
        normalized_type_configs=normalized["type_configs"],
    )
    if not raw_groups and not raw_membership:
        raw_groups, raw_membership = _default_naming_groups_payload()
    else:
        raw_groups, raw_membership = _migrate_untouched_legacy_default_groups(
            self,
            raw_groups,
            raw_membership,
        )
    normalized_groups, normalized_membership = self._normalize_naming_groups_payload(raw_groups, raw_membership)
    normalized["naming_groups"] = normalized_groups
    normalized["type_group_membership"] = normalized_membership

    if normalized != raw:
        _persist_official_doc_settings_safely(normalized)
    return normalized

def _get_official_docs_settings_snapshot(self, *, sync_current_type: bool = True) -> dict[str, Any]:
    self._init_official_docs_state()
    snapshot = copy.deepcopy(getattr(self, "_official_docs_working_settings", _default_settings()))
    if sync_current_type:
        self._sync_current_type_cards_from_ui()
        snapshot = copy.deepcopy(getattr(self, "_official_docs_working_settings", _default_settings()))
    return snapshot

def _type_key_from_parsed(self, parsed: ParsedNotice) -> str:
    key = _notice_key_from_meta(parsed.meta)
    if key and key != "unknown":
        return key
    fallback = str(parsed.notice_kind or "").strip()
    return normalize_notice_type(fallback)

def _collect_available_type_entries(self) -> list[dict[str, Any]]:
    entries_by_key: dict[str, dict[str, Any]] = {}
    catalog_order: list[str] = []
    extra_order: list[str] = []

    for raw_entry in get_supported_type_catalog():
        key = normalize_notice_type(str(raw_entry.get("key", "") or "").strip())
        if not key:
            continue
        display_name = str(raw_entry.get("display_name", "") or "").strip() or get_type_display_name(key)
        entry = {
            "key": key,
            "display_name": display_name,
            "processable": bool(raw_entry.get("processable", True)),
            "disabled_reason": str(raw_entry.get("disabled_reason", "") or "").strip(),
            "is_new": False,
        }
        entries_by_key[key] = entry
        catalog_order.append(key)

    def _append_dynamic(key: str, *, mark_new: bool) -> None:
        type_key = normalize_notice_type(key)
        if not type_key or type_key in entries_by_key:
            return
        display_name = get_type_display_name(type_key)
        entries_by_key[type_key] = {
            "key": type_key,
            "display_name": display_name,
            "processable": bool(is_type_processable(type_key)),
            "disabled_reason": get_type_disabled_reason(type_key),
            "is_new": bool(mark_new),
        }
        extra_order.append(type_key)

    settings = getattr(self, "_official_docs_working_settings", {})
    if isinstance(settings, dict):
        raw_type_configs = settings.get("type_configs", {})
        if isinstance(raw_type_configs, dict):
            for raw_key in raw_type_configs.keys():
                _append_dynamic(str(raw_key or "").strip(), mark_new=True)

    leaves = getattr(self, "_official_docs_leaves", {})
    if isinstance(leaves, dict):
        for leaf in leaves.values():
            if not isinstance(leaf, dict):
                continue
            parsed = leaf.get("parsed")
            if not isinstance(parsed, ParsedNotice):
                continue
            _append_dynamic(self._type_key_from_parsed(parsed), mark_new=True)

    for base_key in OFFICIAL_DOC_BASE_TYPES:
        key = normalize_notice_type(base_key)
        if key in entries_by_key:
            continue
        entries_by_key[key] = {
            "key": key,
            "display_name": get_type_display_name(key),
            "processable": bool(is_type_processable(key)),
            "disabled_reason": get_type_disabled_reason(key),
            "is_new": False,
        }
        catalog_order.append(key)

    ordered_keys: list[str] = []
    seen: set[str] = set()
    for key in catalog_order + extra_order:
        name = normalize_notice_type(key)
        if not name or name in seen or name not in entries_by_key:
            continue
        seen.add(name)
        ordered_keys.append(name)

    return [dict(entries_by_key[key]) for key in ordered_keys]

