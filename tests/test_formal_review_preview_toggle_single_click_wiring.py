import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewPreviewToggleSingleClickWiringTests(unittest.TestCase):
    def test_preview_toggle_state_method_removed(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn("def _set_diff_preview_mode(self, enabled: bool, *, sync_toggle: bool = False) -> None:", text)
        self.assertNotIn("_formal_review_diff_preview_enabled", text)
        self.assertNotIn("formal_review_diff_preview_toggle", text)


if __name__ == "__main__":
    unittest.main()
