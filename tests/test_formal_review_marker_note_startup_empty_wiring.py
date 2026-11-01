import unittest
from pathlib import Path


class FormalReviewMarkerNoteStartupEmptyWiringTests(unittest.TestCase):
    def test_state_init_clears_marker_note_once_and_no_longer_restores_from_pref(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "gui/main_window/mixins/formal_review_ops/state_ops.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("_formal_review_marker_note_initialized", source)
        self.assertIn("marker_edit.clear()", source)
        self.assertIn("set_pref(_MARKER_NOTE_PREF_KEY, \"\")", source)
        self.assertNotIn("marker_edit.setPlainText(str(get_pref(_MARKER_NOTE_PREF_KEY, \"\") or \"\"))", source)

    def test_mode_switch_clears_marker_note_and_pref(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "gui/main_window/mixins/formal_review_ops/workspace_ops.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def on_formal_review_mode_changed(self, _checked: bool = False) -> None:", source)
        self.assertIn("marker_edit.clear()", source)
        self.assertIn("set_pref(_MARKER_NOTE_PREF_KEY, \"\")", source)


if __name__ == "__main__":
    unittest.main()
