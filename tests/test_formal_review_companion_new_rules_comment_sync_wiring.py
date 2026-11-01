import unittest
from pathlib import Path

from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewCompanionNewRulesCommentSyncWiringTests(unittest.TestCase):
    def test_new_rules_are_present_in_formal_review_mixin_source(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("claim.ref.multi_to_multi.recursive", text)
        self.assertIn("claim.punctuation.period.extra", text)
        self.assertIn("claim.punctuation.period.tail_missing", text)

    def test_comment_sync_uses_issue_list_without_rule_id_filtering(self) -> None:
        companion_path = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py")
        text = companion_path.read_text(encoding="utf-8")
        self.assertIn("def _auto_sync_comments_to_copy(self, *, trigger: str, notify_failure: bool = True) -> bool:", text)
        self.assertIn('issues = list(getattr(self, "_formal_review_issues", []) or [])', text)
        self.assertIn("if self._ignore_enabled():", text)
        self.assertIn('issues = [row for row in issues if not bool(getattr(row, "ignored", False))]', text)
        self.assertNotIn("claim.punctuation.period.extra", text)
        self.assertNotIn("claim.punctuation.period.tail_missing", text)
        self.assertNotIn("claim.ref.multi_to_multi.recursive", text)


if __name__ == "__main__":
    unittest.main()
