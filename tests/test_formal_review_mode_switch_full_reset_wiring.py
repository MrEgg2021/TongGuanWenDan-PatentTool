import unittest
from pathlib import Path


class FormalReviewModeSwitchFullResetWiringTests(unittest.TestCase):
    def test_mode_switch_compares_previous_mode_and_triggers_full_reset(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/workspace_ops.py").read_text(encoding="utf-8")
        marker = "def on_formal_review_mode_changed(self, _checked: bool = False) -> None:"
        self.assertIn(marker, source)
        block = source.split(marker, 1)[1].split("\ndef ", 1)[0]
        self.assertIn('previous_mode = str(getattr(self, "_formal_review_input_mode", "word") or "word")', block)
        self.assertIn("self._ensure_formal_review_state()", block)
        self.assertIn("if mode == previous_mode:", block)
        self.assertIn("self._formal_review_input_mode = mode", block)
        self.assertIn("self._reset_formal_review_runtime_state(full_reset=True)", block)

        prev_idx = block.find("previous_mode =")
        ensure_idx = block.find("self._ensure_formal_review_state()")
        check_idx = block.find("if mode == previous_mode:")
        reset_idx = block.find("self._reset_formal_review_runtime_state(full_reset=True)")
        self.assertTrue(0 <= prev_idx < ensure_idx < check_idx < reset_idx)

    def test_full_reset_helper_clears_runtime_artifacts(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/workspace_ops.py").read_text(encoding="utf-8")
        marker = "def _reset_formal_review_runtime_state(self, *, full_reset: bool = True) -> None:"
        self.assertIn(marker, source)
        block = source.split(marker, 1)[1].split("def on_formal_review_mode_changed", 1)[0]
        self.assertIn('set_pref(_MARKER_NOTE_PREF_KEY, "")', block)
        self.assertIn('self._formal_review_current_file = ""', block)
        self.assertIn("self._formal_review_document = None", block)
        self.assertIn("store.clear_all()", block)
        self.assertIn("self._build_section_segments([])", block)
        self.assertIn("self._clear_document_views()", block)
        self.assertIn("self._reset_issue_views(clear_ignore=True)", block)
        self.assertIn("self._set_needs_parse(False)", block)


if __name__ == "__main__":
    unittest.main()
