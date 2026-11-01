import unittest

from core.formal_review.semantic_rules import check_repeated_word_issues


class FormalReviewRepeatedWordRuleTests(unittest.TestCase):
    def test_detects_adjacent_repeated_word_in_multiple_forms(self) -> None:
        text = "所述所述模块与所述\t所述接口连接。"
        issues = check_repeated_word_issues(text, section="description")
        self.assertEqual(2, len(issues))
        self.assertTrue(all(issue.rule_id == "text.repeated_word" for issue in issues))
        self.assertTrue(all(issue.section == "description" for issue in issues))

    def test_skips_cross_punctuation_and_newline(self) -> None:
        text = "所述，所述\n所述\n所述"
        issues = check_repeated_word_issues(text, section="abstract")
        self.assertEqual([], issues)

    def test_claim_section_preserves_claim_num(self) -> None:
        issues = check_repeated_word_issues("模块模块", section="claims", claim_num=1)
        self.assertEqual(1, len(issues))
        self.assertEqual("claims", issues[0].section)
        self.assertEqual(1, issues[0].claim_num)


if __name__ == "__main__":
    unittest.main()

