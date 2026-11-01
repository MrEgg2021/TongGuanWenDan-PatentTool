import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewChangedOnlyResetOnParseAndModeSwitchTests(unittest.TestCase):
    def test_parse_path_no_longer_resets_changed_only_flags(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _set_edit_segments(self, segments: list[EditableSegment] | None) -> None:", text)
        self.assertNotIn("_reset_changed_only_toggles", text)

    def test_file_switch_clears_document_without_changed_only_calls(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def on_formal_review_choose_file(self):", text)
        self.assertIn("self._formal_review_document = None", text)
        self.assertNotIn("_reset_changed_only_toggles", text)

    def test_mode_switch_clears_segments_and_views(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def on_formal_review_mode_changed(self, _checked: bool = False) -> None:", text)
        self.assertIn("self._clear_document_views()", text)
        self.assertIn("self._build_section_segments([])", text)
        self.assertNotIn("_set_diff_preview_mode(", text)


if __name__ == "__main__":
    unittest.main()
