from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class StaticCleanupContractTests(unittest.TestCase):
    def test_gui_app_declares_only_stable_entrypoint_exports(self) -> None:
        source = (REPO_ROOT / "gui_app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        exported_names: list[str] | None = None

        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                continue
            exported_names = [
                element.value
                for element in node.value.elts
                if isinstance(node.value, ast.List)
                and isinstance(element, ast.Constant)
                and isinstance(element.value, str)
            ]

        self.assertEqual(["MainWindow", "main"], exported_names)

    def test_layout_sources_do_not_use_single_line_compound_statements(self) -> None:
        paths = (
            REPO_ROOT / "gui/ui_layout.py",
            REPO_ROOT / "gui/ui_layout_impl/modern_shell_impl.py",
            REPO_ROOT / "gui/widgets_impl/tgd_fact_record_manager_utils.py",
        )
        violations: list[str] = []

        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                    continue
                if node.body and node.body[0].lineno == node.lineno:
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")

        self.assertEqual([], violations)

    def test_zip_import_module_keeps_imports_before_function_definitions(self) -> None:
        path = REPO_ROOT / "gui/main_window/mixins/tgd_data_management_ops_impl/zip_import_batch.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        first_definition_line = min(
            node.lineno
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        )
        late_imports = [
            node.lineno
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno > first_definition_line
        ]

        self.assertEqual([], late_imports)


if __name__ == "__main__":
    unittest.main()
