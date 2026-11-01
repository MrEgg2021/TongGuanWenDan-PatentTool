import unittest
from pathlib import Path


class FormalReviewCommentSyncCrossSectionObservabilityTests(unittest.TestCase):
    def test_comment_sync_logs_cross_section_rule_counts(self) -> None:
        text = Path("core/formal_review/comment_sync.py").read_text(encoding="utf-8")
        self.assertIn("cross_desc=%s cross_drawings=%s", text)
        self.assertIn("_RULE_ID_DESC_MISSING_IN_DRAWINGS", text)
        self.assertIn("_RULE_ID_DRAWINGS_MISSING_IN_DESC", text)


if __name__ == "__main__":
    unittest.main()
