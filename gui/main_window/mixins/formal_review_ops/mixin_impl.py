from __future__ import annotations

from .shared import _ask_continue_cancel_cn
from . import state_ops, workspace_ops, edit_ops, issue_view_ops, companion_ops, marker_ops, settings_export_ops, interaction_ops

_STATICMETHOD_NAMES = ['_claim_num_from_item_token', '_clean_gate_bool_label', '_clean_gate_count_label', '_format_claim_refs', '_format_markers_with_mapping', '_set_splitter_order', '_strip_obj_tokens', '_truncate_dialog_text']

class FormalReviewMixin:
    pass


FormalReviewMixin._ask_continue_cancel_cn = _ask_continue_cancel_cn


def _bind_ops_symbols(module) -> None:
    for name, value in vars(module).items():
        if not callable(value):
            continue
        if not (name.startswith("_") or name.startswith("on_formal_review_")):
            continue
        member = staticmethod(value) if name in _STATICMETHOD_NAMES else value
        globals()[name] = member
        setattr(FormalReviewMixin, name, member)

for _module in (state_ops, workspace_ops, edit_ops, issue_view_ops, companion_ops, marker_ops, settings_export_ops, interaction_ops):
    _bind_ops_symbols(_module)

__all__ = ["FormalReviewMixin"]
