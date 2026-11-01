import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewIgnoreResyncWiringTests(unittest.TestCase):
    def test_ignore_toggle_schedules_debounced_resync(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _schedule_companion_comment_resync(", text)
        self.assertIn('self._schedule_companion_comment_resync("ignore", notify_failure=False)', text)
        self.assertIn("[formal_review][ignore] toggle:", text)
        self.assertIn("[formal_review][ignore] resync_begin:", text)

    def test_ignore_resync_failure_does_not_force_modal_dialog(self) -> None:
        text = read_formal_review_mixin_source()
        # Ensure warning dialog remains gated by notify_failure,
        # so ignore-triggered resync can run with notify_failure=False.
        self.assertIn("if bool(notify_failure):", text)
        self.assertIn("QMessageBox.warning(", text)

    def test_start_check_runs_review_then_syncs_in_word_mode(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn('self._run_companion_review_cycle(trigger="start_check", auto_sync_comments=True, redock=False)', text)


if __name__ == "__main__":
    unittest.main()
