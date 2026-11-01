from __future__ import annotations

from .types import TableProcessContext


def build_table_process_context(owner, table, parent_node, current_section_key) -> TableProcessContext:
    return TableProcessContext(
        owner=owner,
        table=table,
        parent_node=parent_node,
        current_section_key=str(current_section_key),
    )
