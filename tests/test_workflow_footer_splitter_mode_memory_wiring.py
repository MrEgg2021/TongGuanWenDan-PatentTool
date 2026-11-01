import unittest
from pathlib import Path


class WorkflowFooterSplitterModeMemoryWiringTests(unittest.TestCase):
    def test_mode_switch_restores_footer_splitter_sizes_for_current_mode(self) -> None:
        mode_source = Path("gui/app_impl/mode.py").read_text(encoding="utf-8")
        self.assertIn("restore_workflow_footer_splitter_for_mode", mode_source)
        self.assertIn("restore_workflow_footer_splitter_for_mode(window)", mode_source)

    def test_splitter_pref_module_has_mode_specific_keys_and_binding(self) -> None:
        prefs_source = Path("gui/app_impl/layout_splitter_prefs.py").read_text(encoding="utf-8")
        self.assertIn(
            'WORKFLOW_FOOTER_SPLITTER_SINGLE_KEY = "layout.workflow.footer_splitter_single_sizes.v1"',
            prefs_source,
        )
        self.assertIn(
            'WORKFLOW_FOOTER_SPLITTER_BATCH_KEY = "layout.workflow.footer_splitter_batch_sizes.v1"',
            prefs_source,
        )
        self.assertIn("def bind_workflow_footer_splitter_prefs(window) -> None:", prefs_source)
        self.assertIn("def restore_workflow_footer_splitter_for_mode(window) -> None:", prefs_source)
        self.assertIn('timers["workflow_footer_splitter"] = timer', prefs_source)


if __name__ == "__main__":
    unittest.main()
