import unittest
from pathlib import Path


class FormalReviewResultPopupTriggerWiringTests(unittest.TestCase):
    def test_review_summary_dialog_helper_only_allows_start_check(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _show_formal_review_cycle_summary_dialog(self, *, trigger: str, auto_sync_comments: bool) -> None:", source)
        self.assertIn("if str(trigger or \"\") != \"start_check\":", source)
        self.assertIn("QMessageBox.information(self, \"审查结果摘要\", \"\\n\".join(lines))", source)

    def test_run_cycle_calls_summary_dialog_with_trigger_and_sync_flag(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(encoding="utf-8")
        self.assertIn("self._show_formal_review_cycle_summary_dialog(", source)
        self.assertIn("trigger=str(trigger or \"\")", source)
        self.assertIn("auto_sync_comments=bool(auto_sync_comments)", source)
        self.assertIn("if bool(auto_sync_comments) and isinstance(sync_summary, dict):", source)


if __name__ == "__main__":
    unittest.main()
