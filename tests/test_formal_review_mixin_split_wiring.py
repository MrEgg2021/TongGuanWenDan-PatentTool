import unittest

from gui.main_window.mixins.formal_review_mixin import FormalReviewMixin


class FormalReviewMixinSplitWiringTests(unittest.TestCase):
    def test_key_handlers_exist_after_split(self) -> None:
        required = [
            "_run_companion_review_cycle",
            "_ensure_companion_doc_clean_or_prompt",
            "_auto_sync_comments_to_copy",
            "_apply_input_mode_to_ui",
            "_toggle_issue_ignore",
            "_build_combined_write_plan",
            "on_formal_review_open_settings",
            "on_formal_review_start_check",
            "on_formal_review_apply_marker_revision_direct",
            "on_formal_review_export_report",
        ]
        for name in required:
            self.assertTrue(hasattr(FormalReviewMixin, name), f"missing method: {name}")
            self.assertTrue(callable(getattr(FormalReviewMixin, name)), f"not callable: {name}")


if __name__ == "__main__":
    unittest.main()

