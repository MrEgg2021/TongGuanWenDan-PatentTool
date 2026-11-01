import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewAutoCommentCopySyncTests(unittest.TestCase):
    def test_auto_sync_flow_uses_inplace_sync_on_working_copy(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _create_timestamp_working_copy(self, source_path: str) -> str:", text)
        self.assertIn("if detect_unsaved_source(next_source):", text)
        self.assertIn("working_copy = self._create_timestamp_working_copy(next_source)", text)
        self.assertIn("result = sync_comments_inplace(", text)
        self.assertNotIn("result = sync_comments_to_copy(", text)

    def test_start_check_and_connect_use_auto_sync_cycle(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn('self._run_companion_review_cycle(trigger="connect_word", auto_sync_comments=True, redock=True)', text)
        self.assertIn('self._run_companion_review_cycle(trigger="start_check", auto_sync_comments=True, redock=False)', text)
        self.assertIn('failed = int(getattr(result, "failed_issue_count", 0) or 0)', text)
        self.assertIn("if failed > 0:", text)
        self.assertIn("allow_partial_on_preflight_failure=True", text)
        self.assertIn("preserve_failed_existing_comments=True", text)
        self.assertIn("批注同步已部分完成", text)


if __name__ == "__main__":
    unittest.main()
