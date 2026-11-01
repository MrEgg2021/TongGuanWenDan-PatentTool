import unittest

from core.formal_review.models import ClaimItem
from core.formal_review.rules import check_claim_period_structure_issues


class FormalReviewClaimPeriodStructureTests(unittest.TestCase):
    def test_single_tail_period_is_valid(self) -> None:
        claim = ClaimItem(num=1, text="一种冷媒分配器，其特征在于，包括射流出口。")
        issues = check_claim_period_structure_issues(claim)
        self.assertEqual([], issues)

    def test_extra_period_is_reported(self) -> None:
        claim = ClaimItem(num=1, text="一种冷媒分配器。其特征在于，射流出口。")
        issues = check_claim_period_structure_issues(claim)
        target = next((issue for issue in issues if issue.rule_id == "claim.punctuation.period.extra"), None)
        self.assertIsNotNone(target)
        self.assertEqual("。", str(getattr(target, "snippet", "") or ""))
        self.assertEqual(1, int(getattr(target, "span_end", 0) or 0) - int(getattr(target, "span_start", 0) or 0))

    def test_tail_missing_period_is_reported(self) -> None:
        claim = ClaimItem(num=1, text="一种冷媒分配器，其特征在于，包括射流出口")
        issues = check_claim_period_structure_issues(claim)
        self.assertTrue(any(issue.rule_id == "claim.punctuation.period.tail_missing" for issue in issues))

    def test_extra_and_tail_missing_can_coexist(self) -> None:
        claim = ClaimItem(num=1, text="一种冷媒分配器。其特征在于，包括射流出口。并且连接腔贯通")
        issues = check_claim_period_structure_issues(claim)
        rule_ids = {issue.rule_id for issue in issues}
        self.assertIn("claim.punctuation.period.extra", rule_ids)
        self.assertIn("claim.punctuation.period.tail_missing", rule_ids)

    def test_decimal_dots_do_not_count_as_extra_period(self) -> None:
        claim = ClaimItem(num=1, text="一种方法，其特征在于，阈值=0.84，间距=0.90。")
        issues = check_claim_period_structure_issues(claim)
        rule_ids = {issue.rule_id for issue in issues}
        self.assertNotIn("claim.punctuation.period.extra", rule_ids)
        self.assertNotIn("claim.punctuation.period.tail_missing", rule_ids)

    def test_ascii_tail_dot_only_triggers_tail_missing(self) -> None:
        claim = ClaimItem(num=1, text="一种方法，其特征在于，阈值=0.84，间距=0.90.")
        issues = check_claim_period_structure_issues(claim)
        rule_ids = {issue.rule_id for issue in issues}
        self.assertNotIn("claim.punctuation.period.extra", rule_ids)
        self.assertIn("claim.punctuation.period.tail_missing", rule_ids)

    def test_fullwidth_tail_dot_only_triggers_tail_missing(self) -> None:
        claim = ClaimItem(num=1, text="一种方法，其特征在于，阈值=0.84，间距=0.90．")
        issues = check_claim_period_structure_issues(claim)
        rule_ids = {issue.rule_id for issue in issues}
        self.assertNotIn("claim.punctuation.period.extra", rule_ids)
        self.assertIn("claim.punctuation.period.tail_missing", rule_ids)

    def test_multiple_ascii_dots_with_single_cn_period_has_no_extra(self) -> None:
        claim = ClaimItem(num=1, text="一种方法，其特征在于，步骤S4.计算样本；步骤S5.判定。")
        issues = check_claim_period_structure_issues(claim)
        rule_ids = {issue.rule_id for issue in issues}
        self.assertNotIn("claim.punctuation.period.extra", rule_ids)
        self.assertNotIn("claim.punctuation.period.tail_missing", rule_ids)


if __name__ == "__main__":
    unittest.main()
