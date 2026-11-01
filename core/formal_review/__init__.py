from .annotator import (
    TOOL_COMMENT_PREFIX,
    build_comment_plan,
    build_comment_text,
    clear_tool_comments,
    is_tool_comment,
)
from .comment_sync import CommentSyncResult, sync_comments_inplace, sync_comments_to_copy, sync_comments_to_doc
from .companion_client import (
    CompanionSession,
    activate_word_window,
    close_session,
    connect_active_word,
    detect_unsaved_source,
    get_dirty_state,
    get_document_snapshot,
    get_word_hwnd,
    normalize_word_window,
    open_or_attach_document,
)
from .edit_model import EditableSegment, TokenSpan
from .models import ClaimItem, FormalReviewDocument, Issue
from .plain_text_parser import parse_plain_text_sections
from .revision_writer import export_revised_annotated_copy
from .report import (
    build_report_markdown,
    build_report_payload,
    write_report_docx,
    write_report_json,
    write_report_markdown,
    write_report_xlsx,
)
from .rule_registry import (
    RULE_ENABLED_PREF_KEY,
    RULE_REGISTRY,
    default_rule_enabled_map,
    enabled_rule_id_set,
    load_rule_enabled,
    normalize_rule_enabled,
    rule_items_for_ui,
    save_rule_enabled,
)
from .rule_params import (
    RULE_PARAMS_PREF_KEY,
    default_rule_params,
    load_rule_params,
    merged_refer_words,
    normalize_rule_params,
    save_rule_params,
)
from .range_resolver import ResolveResult, resolve_issue_range
from .service import build_issue_id, run_formal_review
from .suppression import SuppressionStore, build_instance_fingerprint
from .text_utils import (
    count_effective_chars,
    extract_figure_markers,
    normalize_marker_token,
    parse_marker_note_map,
    parse_marker_note_payload,
)
from .text_projection import ParagraphProjection, ProjectionBundle, SectionProjection
from .word_locator import LocateResult, locate_issue_in_word
from .window_docking import DockLayout, DockResult, dock_app_and_word
from .word_highlight_sync import HighlightSyncResult, apply_issue_highlights, clear_tool_highlights_via_comments
from .wordlists import (
    DEFAULT_WORDLISTS_V2,
    WORDLIST_PREF_KEY_V1,
    WORDLIST_PREF_KEY_V2,
    load_wordlists,
    normalize_wordlists,
    save_wordlists,
)

__all__ = [
    "ClaimItem",
    "CompanionSession",
    "EditableSegment",
    "FormalReviewDocument",
    "Issue",
    "build_comment_plan",
    "build_comment_text",
    "clear_tool_comments",
    "build_instance_fingerprint",
    "CommentSyncResult",
    "TOOL_COMMENT_PREFIX",
    "activate_word_window",
    "DEFAULT_WORDLISTS_V2",
    "RULE_ENABLED_PREF_KEY",
    "RULE_REGISTRY",
    "RULE_PARAMS_PREF_KEY",
    "WORDLIST_PREF_KEY_V1",
    "WORDLIST_PREF_KEY_V2",
    "build_issue_id",
    "build_report_markdown",
    "build_report_payload",
    "write_report_docx",
    "count_effective_chars",
    "close_session",
    "connect_active_word",
    "detect_unsaved_source",
    "default_rule_enabled_map",
    "default_rule_params",
    "enabled_rule_id_set",
    "export_revised_annotated_copy",
    "extract_figure_markers",
    "get_dirty_state",
    "get_document_snapshot",
    "get_word_hwnd",
    "normalize_marker_token",
    "normalize_word_window",
    "open_or_attach_document",
    "parse_marker_note_map",
    "parse_marker_note_payload",
    "load_rule_enabled",
    "load_rule_params",
    "load_wordlists",
    "normalize_rule_enabled",
    "normalize_rule_params",
    "normalize_wordlists",
    "parse_plain_text_sections",
    "rule_items_for_ui",
    "run_formal_review",
    "save_rule_enabled",
    "save_rule_params",
    "save_wordlists",
    "SuppressionStore",
    "sync_comments_to_copy",
    "sync_comments_inplace",
    "sync_comments_to_doc",
    "is_tool_comment",
    "locate_issue_in_word",
    "LocateResult",
    "ResolveResult",
    "DockLayout",
    "DockResult",
    "HighlightSyncResult",
    "apply_issue_highlights",
    "clear_tool_highlights_via_comments",
    "dock_app_and_word",
    "resolve_issue_range",
    "TokenSpan",
    "ParagraphProjection",
    "SectionProjection",
    "ProjectionBundle",
    "write_report_json",
    "write_report_markdown",
    "write_report_xlsx",
    "merged_refer_words",
]
