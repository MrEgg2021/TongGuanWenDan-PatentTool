from __future__ import annotations

import unittest
from unittest.mock import patch

from core.document_parser.table_ops.process_ops import process_table


class TableProcessOpsWrapperTests(unittest.TestCase):
    def test_process_table_uses_split_flow_when_short_path_not_handled(self) -> None:
        owner = object()
        table = object()
        parent_node = {"k": "v"}

        with (
            patch("core.document_parser.table_ops.process_ops.build_table_process_context") as mock_ctx,
            patch("core.document_parser.table_ops.process_ops.try_short_table_direct_path", return_value=None) as mock_short,
            patch("core.document_parser.table_ops.process_ops.process_table_split_flow", return_value={"ok": True}) as mock_split,
            patch("core.document_parser.table_ops.process_ops.finalize_table_process_result", side_effect=lambda x: x) as mock_fin,
        ):
            class _Ctx:
                def __init__(self):
                    self.owner = owner
                    self.table = table
                    self.parent_node = parent_node
                    self.current_section_key = "claims"

            mock_ctx.return_value = _Ctx()

            out = process_table(owner, table, parent_node, "claims")

        self.assertEqual(out, {"ok": True})
        mock_ctx.assert_called_once_with(owner, table, parent_node, "claims")
        mock_short.assert_called_once()
        mock_split.assert_called_once()
        mock_fin.assert_called_once_with({"ok": True})

    def test_process_table_returns_short_path_result_when_available(self) -> None:
        owner = object()
        table = object()
        parent_node = {}

        with (
            patch("core.document_parser.table_ops.process_ops.build_table_process_context") as mock_ctx,
            patch("core.document_parser.table_ops.process_ops.try_short_table_direct_path", return_value=123) as mock_short,
            patch("core.document_parser.table_ops.process_ops.process_table_split_flow") as mock_split,
            patch("core.document_parser.table_ops.process_ops.finalize_table_process_result", side_effect=lambda x: x) as mock_fin,
        ):
            class _Ctx:
                def __init__(self):
                    self.owner = owner
                    self.table = table
                    self.parent_node = parent_node
                    self.current_section_key = "description"

            mock_ctx.return_value = _Ctx()
            out = process_table(owner, table, parent_node, "description")

        self.assertEqual(out, 123)
        mock_short.assert_called_once()
        mock_split.assert_not_called()
        mock_fin.assert_called_once_with(123)

    def test_process_table_returns_false_when_split_flow_raises(self) -> None:
        owner = object()
        table = object()
        parent_node = {}

        with (
            patch("core.document_parser.table_ops.process_ops.build_table_process_context") as mock_ctx,
            patch("core.document_parser.table_ops.process_ops.try_short_table_direct_path", return_value=None) as mock_short,
            patch(
                "core.document_parser.table_ops.process_ops.process_table_split_flow",
                side_effect=RuntimeError("split flow failed"),
            ) as mock_split,
            patch("core.document_parser.table_ops.process_ops.finalize_table_process_result") as mock_fin,
        ):
            class _Ctx:
                def __init__(self):
                    self.owner = owner
                    self.table = table
                    self.parent_node = parent_node
                    self.current_section_key = "description"

            mock_ctx.return_value = _Ctx()
            out = process_table(owner, table, parent_node, "description")

        self.assertFalse(out)
        mock_short.assert_called_once()
        mock_split.assert_called_once()
        mock_fin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
