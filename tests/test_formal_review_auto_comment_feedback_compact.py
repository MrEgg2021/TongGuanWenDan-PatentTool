import unittest

from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewAutoCommentFeedbackCompactTests(unittest.TestCase):
    def test_auto_sync_success_publishes_non_blocking_summary(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _publish_auto_comment_sync_summary(self, result, output_path: str, trigger: str) -> None:", text)
        self.assertIn("self._publish_auto_comment_sync_summary(result, resolved_output, trigger)", text)

    def test_auto_sync_success_no_longer_uses_completion_modal(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn('QMessageBox.information(self, "批注同步完成"', text)

    def test_auto_sync_digest_includes_failed_reason_sample_wiring(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("failed_reason_codes", text)
        self.assertIn("reason_sample", text)


if __name__ == "__main__":
    unittest.main()
