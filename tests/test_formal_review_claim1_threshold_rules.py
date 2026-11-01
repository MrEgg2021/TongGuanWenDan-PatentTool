import unittest

from core.formal_review.models import ClaimItem
from core.formal_review.rules import check_claim1_threshold_issues


class FormalReviewClaim1ThresholdRuleTests(unittest.TestCase):
    def test_claim1_word_count_exceeded(self) -> None:
        claims = [ClaimItem(num=1, text="一种冷媒分配器，其特征在于包括多个结构单元。", markers=["1"])]
        issues = check_claim1_threshold_issues(claims, word_limit=8, marker_limit=20)
        rule_ids = {issue.rule_id for issue in issues}
        self.assertIn("claim1.word_count.exceeded", rule_ids)
        self.assertNotIn("claim1.marker_count.exceeded", rule_ids)
        target = next((issue for issue in issues if issue.rule_id == "claim1.word_count.exceeded"), None)
        self.assertIsNotNone(target)
        snippet = str(getattr(target, "snippet", "") or "")
        self.assertGreater(len(snippet), 0)
        self.assertLessEqual(len(snippet), 10)
        self.assertNotIn("\n", snippet)

    def test_claim1_marker_count_exceeded_with_dedup(self) -> None:
        claims = [ClaimItem(num=1, text="一种冷媒分配器。", markers=["1", "2", "2", "3"])]
        issues = check_claim1_threshold_issues(claims, word_limit=500, marker_limit=2)
        target = next((issue for issue in issues if issue.rule_id == "claim1.marker_count.exceeded"), None)
        self.assertIsNotNone(target)
        self.assertEqual("warning", str(getattr(target, "severity", "") or ""))
        snippet = str(getattr(target, "snippet", "") or "")
        self.assertGreater(len(snippet), 0)
        self.assertLessEqual(len(snippet), 10)
        self.assertNotIn("\n", snippet)

    def test_claim1_marker_count_uses_text_extraction_when_marker_field_empty(self) -> None:
        claims = [ClaimItem(num=1, text="一种装置，包括喷嘴（1）、导流板（2）及壳体（2）。")]
        issues = check_claim1_threshold_issues(claims, word_limit=500, marker_limit=1)
        self.assertTrue(any(issue.rule_id == "claim1.marker_count.exceeded" for issue in issues))

    def test_within_limits_should_not_report(self) -> None:
        claims = [ClaimItem(num=1, text="一种装置。", markers=["1"])]
        issues = check_claim1_threshold_issues(claims, word_limit=20, marker_limit=5)
        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
