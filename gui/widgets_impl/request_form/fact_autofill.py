from __future__ import annotations

# Keep explicit gate import for static wiring checks.

from .fact_autofill_impl.activation_ops import _on_inline_fact_combo_activated
from .fact_autofill_impl.anchor_ops import (
    _clear_contact_fields_if_match_old_unique,
    _clear_inventor_fields_if_match_old_unique,
    _on_applicant_anchor_committed,
    _on_applicant_anchor_editing_finished,
)
from .fact_autofill_impl.common_ops import (
    _clear_combo_value,
    _clear_line_edit_text,
    _collect_all_applicant_anchor_groups_with_old_value,
    _get_line_edit_text,
    _query_fact_records_with_anchor_groups,
)
from .fact_autofill_impl.prefill_ops import (
    _auto_prefill_current_scope,
    _auto_prefill_current_scope_for_tab,
    _trigger_all_inventor_autofill,
)

__all__ = [
    "_clear_combo_value",
    "_auto_prefill_current_scope",
    "_on_inline_fact_combo_activated",
    "_collect_all_applicant_anchor_groups_with_old_value",
    "_query_fact_records_with_anchor_groups",
    "_clear_line_edit_text",
    "_get_line_edit_text",
    "_clear_inventor_fields_if_match_old_unique",
    "_clear_contact_fields_if_match_old_unique",
    "_trigger_all_inventor_autofill",
    "_auto_prefill_current_scope_for_tab",
    "_on_applicant_anchor_committed",
    "_on_applicant_anchor_editing_finished",
]
