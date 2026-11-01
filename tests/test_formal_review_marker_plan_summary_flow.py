import unittest
from pathlib import Path


class FormalReviewMarkerPlanSummaryFlowTests(unittest.TestCase):
    def test_partial_commit_summary_and_logging_keywords_exist(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/marker_ops.py").read_text(encoding="utf-8")
        self.assertIn("[formal_review][marker_apply]", source)
        self.assertIn("atomic_commit=False", source)
        self.assertIn("claim_resolve_strict_failed_count", source)
        self.assertIn("claim_resolve_loose_rescued_count", source)
        self.assertIn("claim_resolve_projection_count", source)
        self.assertIn("claim_resolve_word_find_com_count", source)
        self.assertIn("claim_resolve_word_find_legacy_count", source)


if __name__ == "__main__":
    unittest.main()
