from __future__ import annotations

from .official_docs_ops import detail_ops as _detail_ops
from .official_docs_ops import process_ops as _process_ops
from .official_docs_ops import shared as _shared
from .official_docs_ops import settings_ops as _settings_ops
from .official_docs_ops import state_ops as _state_ops
from .official_docs_ops import task_tree_ops as _task_tree_ops
from .official_docs_ops import type_list_ops as _type_list_ops

_SHARED_EXPORTS = tuple(_shared.__all__)
_OFFICIAL_DOCS_OP_MODULES = (
    _detail_ops,
    _process_ops,
    _settings_ops,
    _state_ops,
    _task_tree_ops,
    _type_list_ops,
)
_OFFICIAL_DOCS_METHOD_NAMES = (
    "_init_official_docs_state",
    "_ensure_official_docs_temp_root",
    "_cleanup_official_docs_temp",
    "_serialize_type_cfg",
    "_default_group_cfg_payload",
    "_serialize_naming_group",
    "_normalize_naming_groups_payload",
    "_normalize_official_doc_settings",
    "_get_official_docs_settings_snapshot",
    "_type_key_from_parsed",
    "_collect_available_type_entries",
    "_current_type_selection_context",
    "_set_type_selection_context",
    "_build_type_tree_payload",
    "_type_tree_context_from_item",
    "_collect_checked_type_tree_targets",
    "_clear_checked_type_tree_targets",
    "_remember_checked_type_tree_state_from_tree",
    "_checked_or_focused_group_contexts",
    "_checked_or_focused_type_contexts",
    "_refresh_official_docs_type_action_buttons",
    "_set_official_docs_naming_scope",
    "_refresh_official_docs_type_list",
    "_resolve_type_group_member_keys",
    "_pick_group_name",
    "_create_naming_group",
    "_pick_target_group_id",
    "_assign_entry_to_group",
    "_official_docs_cards_widget",
    "_list_widget_to_cards",
    "_card_to_item",
    "_set_cards_to_widget",
    "_set_filename_fields_card_editable",
    "_pdf_parse_field_widgets",
    "_set_pdf_parse_field_checks_enabled",
    "_current_type_alias_notice_options",
    "_set_alias_notice_item",
    "_alias_notice_name_from_row",
    "_sync_current_type_cards_from_ui",
    "_load_type_cards_to_ui",
    "_sample_meta_for_type",
    "_find_selected_meta_for_type",
    "_refresh_official_docs_settings_preview_line",
    "_update_official_docs_settings_dirty_ui",
    "_set_official_docs_settings_message",
    "_refresh_official_docs_naming_mode_labels",
    "_collect_official_docs_naming_splitter_sizes",
    "_apply_official_docs_naming_splitter_sizes",
    "_persist_official_docs_naming_splitter_sizes",
    "on_official_docs_naming_splitter_moved",
    "_apply_official_docs_settings_to_ui",
    "_refresh_official_docs_page_from_state",
    "_confirm_leave_official_docs_if_dirty",
    "on_official_docs_tab_changed",
    "_ensure_archive_consent",
    "on_official_docs_archive_checkbox_toggled",
    "on_official_docs_settings_changed",
    "on_official_docs_type_selection_changed",
    "on_official_docs_type_search_changed",
    "on_official_docs_type_tree_item_changed",
    "on_official_docs_type_tree_context_menu",
    "on_official_docs_create_naming_group",
    "on_official_docs_rename_naming_group",
    "on_official_docs_delete_naming_group",
    "on_official_docs_add_group_member",
    "on_official_docs_move_type_to_group",
    "on_official_docs_remove_type_from_group",
    "_append_card_to_target",
    "on_official_docs_insert_field_card",
    "on_official_docs_move_field_up",
    "on_official_docs_move_field_down",
    "on_official_docs_remove_selected_field",
    "on_official_docs_clear_fields",
    "on_official_docs_alias_table_changed",
    "on_official_docs_add_alias_rule",
    "on_official_docs_remove_alias_rule",
    "_validate_official_docs_settings",
    "on_official_docs_save_settings",
    "on_official_docs_browse_summary_root",
    "on_official_docs_browse_archive_root",
    "_ensure_node_exists",
    "_add_official_docs_inputs",
    "on_official_docs_choose_zips",
    "on_official_docs_choose_folder",
    "on_official_docs_paths_dropped",
    "on_official_docs_clear_items",
    "_parse_official_docs_leaf_if_needed",
    "_leaf_search_payload",
    "_sync_official_docs_list_detail_toggle_text",
    "_set_official_docs_list_detail_visible",
    "on_official_docs_toggle_task_details_visibility",
    "on_official_docs_search_changed",
    "_create_leaf_tree_item",
    "_refresh_official_docs_tree_column_width",
    "_render_official_docs_tree",
    "on_official_docs_item_check_changed",
    "on_official_docs_item_expanded",
    "on_official_docs_item_collapsed",
    "on_official_docs_selection_changed",
    "_iter_leaf_ids_in_order",
    "_iter_checked_leaf_ids",
    "_build_official_docs_options",
    "_build_preview_paths",
    "_refresh_official_docs_detail",
    "_extract_pdf_to_temp",
    "_open_pdf_source_for_leaf",
    "_build_collision_resolver",
    "_find_leaf_id_by_zip_path",
    "_build_confirm_callback",
    "_collect_done_dirs",
    "_cache_official_docs_process_results",
    "on_official_docs_start_processing",
)
_OFFICIAL_DOCS_STATIC_METHOD_NAMES = {"_type_tree_context_from_item"}


def _resolve_official_docs_op(name: str):
    matches = [
        getattr(module, name)
        for module in _OFFICIAL_DOCS_OP_MODULES
        if callable(getattr(module, name, None))
    ]
    if len(matches) != 1:
        raise RuntimeError(f"官文 Mixin 方法来源异常：{name}，匹配数={len(matches)}")
    return matches[0]


def __getattr__(name: str):
    if name in _SHARED_EXPORTS:
        return getattr(_shared, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class OfficialDocsMixin:
    pass


for _method_name in _OFFICIAL_DOCS_METHOD_NAMES:
    _method = _resolve_official_docs_op(_method_name)
    if _method_name in _OFFICIAL_DOCS_STATIC_METHOD_NAMES:
        _method = staticmethod(_method)
    setattr(OfficialDocsMixin, _method_name, _method)

__all__ = ["OfficialDocsMixin", *_SHARED_EXPORTS]
