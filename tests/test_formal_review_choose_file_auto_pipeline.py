import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewChooseFileAutoPipelineTests(unittest.TestCase):
    def test_choose_file_forces_word_mode_and_checks_gate_without_auto_review(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("word_radio = getattr(self, \"formal_review_mode_word_radio\", None)", text)
        self.assertIn("self._formal_review_input_mode = \"word\"", text)
        self.assertIn("if not self._connect_or_attach_companion():", text)
        self.assertIn("self._formal_review_companion_docked_once = False", text)
        self.assertIn("self._dock_companion_windows_once()", text)
        self.assertIn("if not self._ensure_companion_doc_clean_or_prompt(trigger=\"choose_file\", allow_retry=False):", text)
        self.assertIn("self._reset_companion_selection_after_gate_block()", text)
        self.assertIn("def _ensure_com_find_ready_or_prompt(self, *, context: str) -> bool:", text)
        self.assertNotIn("self._run_companion_review_cycle(trigger=\"choose_file\", auto_sync_comments=True, redock=True)", text)


if __name__ == "__main__":
    unittest.main()
