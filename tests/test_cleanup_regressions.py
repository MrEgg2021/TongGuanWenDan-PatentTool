import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.quality import pyflakes_gate


def _module(path: str) -> ast.Module:
    return ast.parse(Path(path).read_text(encoding="utf-8"))


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function not found: {name}")


class CleanupRegressionTests(unittest.TestCase):
    def test_confirmed_private_dead_functions_are_removed(self) -> None:
        forbidden_by_path = {
            "core/document_parser/table_ops/render_pdf_ops.py": {
                "_row_dark_ratio",
                "_find_visual_slice_cut",
                "_visual_slice_pdf_fragment",
            },
            "core/formal_review/rules.py": {"_phrase_tail_end"},
            "core/formal_review/semantic_rules.py": {"_find_drawings_heading_line"},
            "core/app_preferences.py": {"_get_bool"},
            "core/manual_illustration_sync.py": {"_response_prefix_to_page_attr"},
            "core/official_docs/input_resolver.py": {"_list_inner_zip_infos"},
            "core/tgd_data_management_impl/excel_io_impl/text_utils.py": {
                "_split_uscc_or_id",
                "_parse_yes_no",
                "_parse_date_yyyy_mm_dd",
                "_parse_int01",
            },
            "gui/dialog_utils.py": {"_icon_to_standard_pixmap"},
            "gui/widgets_impl/request_form/tabs_impl.py": {
                "_calc_fixed_width_by_chars",
                "_calc_combo_width_by_text",
            },
            "gui/widgets_impl/tgd_zip_import_review_utils.py": {
                "_infer_inventor_id_type_text_from_id_no",
            },
            "gui/main_window/mixins/response_correction_mixin.py": {
                "_flow_requires_opinion",
                "_mark_staged_errors",
                "_scaled_progress_callback",
                "_refresh_uploaded_files_table",
            },
            "gui/widgets_impl/tgd_zip_import_review_dialog_impl/main_dialog_impl/dialog.py": {
                "_register_cpl",
                "_schedule_refresh_completer",
                "_refresh_completer_for_edit",
                "_prefill_agency_table",
                "_ensure_fact_editor_prefilled",
                "_update_fact_tab_layout",
                "_load_fact_editor_from_row",
                "_set_combo_text",
                "_refresh_fact_table_row",
                "_validate_fact_rows",
                "_collect_agency_rows",
                "_upsert_agency_agents",
            },
            "gui/main_window/mixins/batch_mixin.py": {
                "_update_batch_selection_stats",
                "_update_batch_file_list_height",
            },
            "gui/ui_modals.py": {"_apply_card_shadow"},
        }

        for path, forbidden_names in forbidden_by_path.items():
            with self.subTest(path=path):
                module = _module(path)
                function_names = {
                    node.name
                    for node in ast.walk(module)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                self.assertTrue(forbidden_names.isdisjoint(function_names))

    def test_noop_official_docs_checked_status_chain_is_removed(self) -> None:
        paths = (
            "gui/main_window/mixins/official_docs_mixin.py",
            "gui/main_window/mixins/official_docs_ops/type_list_ops.py",
            "gui/main_window/mixins/official_docs_ops/type_tree_ops.py",
            "gui/main_window/mixins/official_docs_ops/naming_group_ops.py",
            "gui/main_window/mixins/official_docs_ops/type_card_ops.py",
        )

        for path in paths:
            source = Path(path).read_text(encoding="utf-8")
            self.assertNotIn("_refresh_official_docs_checked_type_status", source, path)

    def test_pyflakes_gate_uses_current_python_interpreter(self) -> None:
        with patch("tools.quality.pyflakes_gate.subprocess.run") as run_mock:
            run_mock.return_value.stdout = ""
            run_mock.return_value.stderr = ""

            self.assertEqual([], pyflakes_gate._run_pyflakes(["core"]))

        self.assertEqual(
            [pyflakes_gate.sys.executable, "-m", "pyflakes", "core"],
            run_mock.call_args.args[0],
        )
        self.assertEqual("utf-8", run_mock.call_args.kwargs["encoding"])
        self.assertEqual("replace", run_mock.call_args.kwargs["errors"])
        self.assertEqual("1", run_mock.call_args.kwargs["env"]["PYTHONUTF8"])
        self.assertEqual("utf-8", run_mock.call_args.kwargs["env"]["PYTHONIOENCODING"])

    def test_legacy_formal_review_function_is_removed(self) -> None:
        module = _module("core/formal_review/rules.py")
        names = {node.name for node in ast.walk(module) if isinstance(node, ast.FunctionDef)}

        self.assertNotIn("_legacy_check_claim_reference_basis_issues", names)

    def test_table_row_safety_has_no_statements_after_return(self) -> None:
        module = _module("core/document_parser/table_topology_impl.py")
        function = _function(module, "_is_row_safe")
        return_indexes = [index for index, node in enumerate(function.body) if isinstance(node, ast.Return)]

        self.assertEqual([len(function.body) - 1], return_indexes)

    def test_unused_official_docs_status_panel_function_is_removed(self) -> None:
        module = _module("gui/main_window/mixins/official_docs_ops/type_list_ops.py")
        names = {node.name for node in ast.walk(module) if isinstance(node, ast.FunctionDef)}

        self.assertNotIn("_set_official_docs_group_status_panel", names)

    def test_request_form_event_filter_has_no_unused_super_callback(self) -> None:
        module = _module("gui/widgets_impl/request_form/dialog_impl/main_dialog_impl/event_filter_ops.py")
        function = _function(module, "event_filter")
        arg_names = [arg.arg for arg in function.args.args]

        self.assertEqual(["self", "obj", "event"], arg_names)

    def test_batch_drawings_quality_warning_dead_chain_is_removed(self) -> None:
        paths = (
            "gui/batch_run_impl/conversion_flow.py",
            "gui/batch_run_impl/finalize_flow.py",
            "gui/batch_run_impl/report.py",
        )

        for path in paths:
            source = Path(path).read_text(encoding="utf-8")
            self.assertNotIn("drawings_quality_warn_files", source, path)
            self.assertNotIn("_batch_drawings_quality_warn_files", source, path)

    def test_confirmed_unused_assignments_are_removed(self) -> None:
        forbidden_by_function = {
            "core/word_startup_health.py": "binding_progid = None",
            "core/word_engine_impl/start_app_steps/dispatch.py": "visible_pids =",
        }

        for path, forbidden in forbidden_by_function.items():
            source = Path(path).read_text(encoding="utf-8")
            self.assertNotIn(forbidden, source, path)

        preflight_module = _module("gui/single_run_impl/preflight_flow.py")
        prevalidate_function = _function(preflight_module, "prevalidate_single")
        prevalidate_assigned_names = {
            target.id
            for node in ast.walk(prevalidate_function)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        self.assertNotIn("request_form_prefill_available", prevalidate_assigned_names)

        module = _module("tools/quality/manual_retest_helper.py")
        collect_function = _function(module, "_collect")
        assigned_names = {
            target.id
            for node in ast.walk(collect_function)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        self.assertNotIn("root", assigned_names)

    def test_confirmed_write_only_state_and_orphan_config_keys_are_removed(self) -> None:
        forbidden_by_path = {
            "core/document_parser/document_parser.py": (
                "_desc_period_current_p",
                "_desc_period_last_node",
            ),
            "core/document_parser/table_topology_impl.py": (
                "wdActiveEndPageNumber",
                "wdBorderLeft",
                "wdBorderRight",
            ),
            "core/formal_review/extractor.py": ("_CLAIM_START_RE",),
            "core/formal_review/rules.py": ("_BRACKET_MARKER_RE",),
            "core/formal_review/write_commands.py": ("description_scope_start",),
            "core/manual_illustration_sync.py": ("_AUTO_BLOCK_RE_TEMPLATE",),
            "gui/main_window/mixins/tgd_data_management_ops_impl/zip_poa_mapping.py": (
                "_applicant_indices",
                "self._applicants",
                "self._source_path",
            ),
            "gui/ui_layout_impl/response_correction_page.py": ("self._prefix",),
            "gui/widgets_impl/formal_review/settings_dialog_parts/wordlist_tab.py": (
                "self._wordlist_splitter",
            ),
            "gui/widgets_impl/request_form/dialog_impl/main_dialog_impl/dialog.py": (
                "self._fact_selected_exact =",
            ),
            "gui/widgets_impl/tgd_fact_record_manager_dialog_impl/main_dialog.py": (
                "_edit_trigger_defaults",
            ),
            "resources/config.yaml": (
                "dtd_path",
                "max_output_width_px",
                "table_formula_max_width_px",
            ),
        }

        for path, forbidden_names in forbidden_by_path.items():
            with self.subTest(path=path):
                source = Path(path).read_text(encoding="utf-8")
                for name in forbidden_names:
                    self.assertNotIn(name, source, f"{path}: {name}")



if __name__ == "__main__":
    unittest.main()
