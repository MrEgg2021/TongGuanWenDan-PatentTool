from __future__ import annotations

import ast
import importlib
import unittest
from pathlib import Path

from gui.main_window.mixins import official_docs_mixin
from gui.main_window.mixins.official_docs_ops import type_list_ops


class OfficialDocsTypeOpsModularizationTests(unittest.TestCase):
    def test_type_list_ops_is_a_function_free_compatibility_entrypoint(self) -> None:
        source = Path(type_list_ops.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        function_names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]

        self.assertEqual([], function_names)

    def test_focused_modules_own_representative_exports(self) -> None:
        type_tree_ops = importlib.import_module(
            "gui.main_window.mixins.official_docs_ops.type_tree_ops"
        )
        naming_group_ops = importlib.import_module(
            "gui.main_window.mixins.official_docs_ops.naming_group_ops"
        )
        type_card_ops = importlib.import_module(
            "gui.main_window.mixins.official_docs_ops.type_card_ops"
        )

        expected_exports = {
            "_current_type_selection_context": type_tree_ops._current_type_selection_context,
            "_refresh_official_docs_type_list": type_tree_ops._refresh_official_docs_type_list,
            "_assign_entry_to_group": naming_group_ops._assign_entry_to_group,
            "on_official_docs_remove_type_from_group": naming_group_ops.on_official_docs_remove_type_from_group,
            "_load_type_cards_to_ui": type_card_ops._load_type_cards_to_ui,
            "_refresh_official_docs_settings_preview_line": type_card_ops._refresh_official_docs_settings_preview_line,
        }

        self.assertTrue(set(expected_exports).issubset(set(type_list_ops.__all__)))
        for name, implementation in expected_exports.items():
            with self.subTest(name=name):
                self.assertIs(getattr(type_list_ops, name), implementation)
                self.assertIs(getattr(official_docs_mixin.OfficialDocsMixin, name), implementation)


if __name__ == "__main__":
    unittest.main()
