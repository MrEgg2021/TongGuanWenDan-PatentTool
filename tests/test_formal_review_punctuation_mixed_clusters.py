import unittest

from core.formal_review.rules import check_punctuation_issues


class FormalReviewPunctuationMixedClustersTests(unittest.TestCase):
    def test_mixed_and_repeated_clusters_are_detected(self) -> None:
        issues = check_punctuation_issues("A；。B，，C， ；D。 。E", section="description")
        self.assertGreaterEqual(len(issues), 4)
        rule_ids = [row.rule_id for row in issues]
        self.assertIn("punctuation.invalid_combo", rule_ids)
        self.assertIn("punctuation.repeated", rule_ids)

    def test_claims_and_abstract_sections_emit_punctuation_issues(self) -> None:
        claim_rows = check_punctuation_issues("所述部件；。连接", section="claims", claim_num=1)
        abstract_rows = check_punctuation_issues("摘要内容，，并且稳定。", section="abstract")
        self.assertTrue(any(row.section == "claims" for row in claim_rows))
        self.assertTrue(any(row.section == "abstract" for row in abstract_rows))
        self.assertTrue(any(row.rule_id == "punctuation.invalid_combo" for row in claim_rows))
        self.assertTrue(any(row.rule_id == "punctuation.repeated" for row in abstract_rows))


if __name__ == "__main__":
    unittest.main()
