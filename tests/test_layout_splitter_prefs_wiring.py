import unittest
from pathlib import Path


class LayoutSplitterPrefsWiringTests(unittest.TestCase):
    def test_splitter_pref_module_defines_required_keys_and_bindings(self) -> None:
        source = Path("gui/app_impl/layout_splitter_prefs.py").read_text(encoding="utf-8")
        self.assertIn('SINGLE_MAIN_SPLITTER_KEY = "layout.single.main_splitter_sizes.v1"', source)
        self.assertIn('BATCH_MAIN_SPLITTER_KEY = "layout.batch.main_splitter_sizes.v1"', source)
        self.assertIn(
            'OFFICIAL_DOCS_TASK_VERTICAL_SPLITTER_KEY = "layout.official_docs.task_vertical_splitter_sizes.v1"',
            source,
        )
        self.assertIn('PREVIEW_TOP_BOTTOM_SPLITTER_KEY = "layout.preview.top_bottom_splitter_sizes.v1"', source)
        self.assertIn('PREVIEW_LEFT_RIGHT_SPLITTER_KEY = "layout.preview.left_right_splitter_sizes.v1"', source)
        self.assertIn('RESPONSE_PROCESSING_UPPER_HEIGHT_KEY = "layout.response.processing_upper_height.v1"', source)
        self.assertIn('CORRECTION_PROCESSING_UPPER_HEIGHT_KEY = "layout.correction.processing_upper_height.v1"', source)
        self.assertIn('ACTIVE_RESPONSE_PROCESSING_UPPER_HEIGHT_KEY = "layout.active_response.processing_upper_height.v1"', source)
        self.assertIn('ACTIVE_CORRECTION_PROCESSING_UPPER_HEIGHT_KEY = "layout.active_correction.processing_upper_height.v1"', source)
        self.assertIn("SPLITTER_DEBOUNCE_MS = 300", source)
        self.assertIn('def bind_layout_splitter_prefs(window) -> None:', source)
        self.assertIn('_bind_splitter(window, "single_main_splitter", SINGLE_MAIN_SPLITTER_KEY, [7, 3])', source)
        self.assertIn('_bind_splitter(window, "batch_main_splitter", BATCH_MAIN_SPLITTER_KEY, [3, 7])', source)
        self.assertIn('"official_docs_task_vertical_splitter"', source)
        self.assertIn('_bind_splitter(window, "preview_main_vertical_splitter", PREVIEW_TOP_BOTTOM_SPLITTER_KEY, [3, 7])', source)
        self.assertIn(
            '_bind_splitter(window, "preview_main_horizontal_splitter", PREVIEW_LEFT_RIGHT_SPLITTER_KEY, [2, 1])',
            source,
        )
        self.assertIn(
            'WORKFLOW_HOME_SPLITTER_SINGLE_KEY = "layout.workflow.home_splitter_single_sizes.v1"',
            source,
        )
        self.assertIn(
            'WORKFLOW_HOME_SPLITTER_BATCH_KEY = "layout.workflow.home_splitter_batch_sizes.v1"',
            source,
        )
        self.assertIn(
            'WORKFLOW_FOOTER_SPLITTER_SINGLE_KEY = "layout.workflow.footer_splitter_single_sizes.v1"',
            source,
        )
        self.assertIn(
            'WORKFLOW_FOOTER_SPLITTER_BATCH_KEY = "layout.workflow.footer_splitter_batch_sizes.v1"',
            source,
        )
        self.assertIn("def bind_workflow_home_splitter_prefs(window) -> None:", source)
        self.assertIn("def restore_workflow_home_splitter_for_mode(window) -> None:", source)
        self.assertIn("def bind_workflow_footer_splitter_prefs(window) -> None:", source)
        self.assertIn("def restore_workflow_footer_splitter_for_mode(window) -> None:", source)
        self.assertIn('def _bind_response_correction_height(window, attr_name: str, key: str, default_height: int, legacy_splitter_key: str) -> None:', source)
        self.assertIn('_bind_response_correction_height(window, "response_processing_pane", RESPONSE_PROCESSING_UPPER_HEIGHT_KEY, 520, RESPONSE_PROCESSING_SPLITTER_KEY)', source)
        self.assertIn('_bind_response_correction_height(window, "correction_processing_pane", CORRECTION_PROCESSING_UPPER_HEIGHT_KEY, 560, CORRECTION_PROCESSING_SPLITTER_KEY)', source)
        self.assertIn('_bind_response_correction_height(window, "active_response_processing_pane", ACTIVE_RESPONSE_PROCESSING_UPPER_HEIGHT_KEY, 520, ACTIVE_RESPONSE_PROCESSING_SPLITTER_KEY)', source)
        self.assertIn('_bind_response_correction_height(window, "active_correction_processing_pane", ACTIVE_CORRECTION_PROCESSING_UPPER_HEIGHT_KEY, 560, ACTIVE_CORRECTION_PROCESSING_SPLITTER_KEY)', source)

    def test_main_window_setup_calls_splitter_pref_binding(self) -> None:
        source = Path("gui_app.py").read_text(encoding="utf-8")
        self.assertIn("bind_layout_splitter_prefs", source)
        self.assertIn("bind_layout_splitter_prefs(self)", source)
        self.assertIn("bind_workflow_home_splitter_prefs", source)
        self.assertIn("bind_workflow_home_splitter_prefs(self)", source)
        self.assertIn("bind_workflow_footer_splitter_prefs", source)
        self.assertIn("bind_workflow_footer_splitter_prefs(self)", source)


if __name__ == "__main__":
    unittest.main()
