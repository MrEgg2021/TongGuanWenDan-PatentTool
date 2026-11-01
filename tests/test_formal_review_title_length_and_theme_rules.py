import unittest

from core.formal_review.models import ClaimItem, FormalReviewDocument
from core.formal_review.semantic_rules import check_description_title_issues, check_theme_consistency_issues


class FormalReviewTitleLengthAndThemeRuleTests(unittest.TestCase):
    def test_reports_missing_title_when_first_line_is_heading(self) -> None:
        doc = FormalReviewDocument(description="技术领域\n本申请涉及检测技术。")
        issues = check_description_title_issues(doc)
        self.assertEqual(1, len(issues))
        self.assertEqual("description.title.missing", issues[0].rule_id)
        self.assertEqual("error", issues[0].severity)

    def test_reports_title_length_exceeded(self) -> None:
        doc = FormalReviewDocument(description=f"{'超' * 26}\n技术领域\n本申请涉及检测技术。")
        issues = check_description_title_issues(doc)
        self.assertEqual(1, len(issues))
        self.assertEqual("description.title.length.exceeded", issues[0].rule_id)
        self.assertEqual("warning", issues[0].severity)

    def test_reports_theme_mismatch_and_claim1_multi_subject(self) -> None:
        doc = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="一种数据处理方法系统，其特征在于包括采集模块。")],
            description="一种数据处理装置\n技术领域\n本申请涉及检测技术。",
            abstract="本摘要公开一种计算机程序产品。",
        )
        issues = check_theme_consistency_issues(doc)
        issue_ids = {issue.rule_id for issue in issues}
        self.assertIn("theme.claim1.multi_subject", issue_ids)
        self.assertIn("theme.title_claim1.mismatch", issue_ids)
        self.assertIn("theme.title_abstract.mismatch", issue_ids)

    def test_reports_unrecognized_title_theme(self) -> None:
        doc = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="一种设备，其特征在于包括壳体。")],
            description="一种改进方案\n技术领域\n本申请涉及机械领域。",
            abstract="本摘要公开一种改进方案。",
        )
        issues = check_theme_consistency_issues(doc)
        issue_ids = {issue.rule_id for issue in issues}
        self.assertIn("theme.title.unrecognized", issue_ids)


if __name__ == "__main__":
    unittest.main()

