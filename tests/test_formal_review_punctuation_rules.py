import unittest

from core.formal_review.models import ClaimItem
from core.formal_review.rules import check_abstract_word_count, check_claim_reference_rules, check_punctuation_issues


class FormalReviewRulesTests(unittest.TestCase):
    def test_abstract_word_count_exceeded(self) -> None:
        source = "字" * 301
        issues = check_abstract_word_count(source, threshold=300)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule_id, "abstract.word_count.exceeded")
        self.assertIsNotNone(issues[0].span_start)
        self.assertIsNotNone(issues[0].span_end)
        self.assertEqual(int(issues[0].span_start), 0)
        self.assertGreater(int(issues[0].span_end), 0)
        self.assertLessEqual(int(issues[0].span_end), len(source))

    def test_punctuation_issues_detected(self) -> None:
        issues = check_punctuation_issues("出现，，以及，；组合。", section="description")
        self.assertGreaterEqual(len(issues), 2)
        rule_ids = {item.rule_id for item in issues}
        self.assertIn("punctuation.repeated", rule_ids)
        self.assertIn("punctuation.invalid_combo", rule_ids)

    def test_claim_reference_rules(self) -> None:
        claims = [
            ClaimItem(num=1, text="一种装置。"),
            ClaimItem(num=2, text="根据权利要求3和4所述装置。"),
            ClaimItem(num=3, text="根据权利要求1所述装置。"),
        ]
        issues = check_claim_reference_rules(claims)
        rule_ids = {issue.rule_id for issue in issues}
        self.assertIn("claim.ref.future", rule_ids)
        self.assertIn("claim.ref.missing_target", rule_ids)
        self.assertIn("claim.ref.choice_word_missing", rule_ids)


if __name__ == "__main__":
    unittest.main()
