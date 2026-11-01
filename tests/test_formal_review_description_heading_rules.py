import unittest

from core.formal_review.models import FormalReviewDocument
from core.formal_review.semantic_rules import check_description_heading_issues


class FormalReviewDescriptionHeadingRuleTests(unittest.TestCase):
    def test_reports_missing_required_headings_with_drawings(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种装置\n"
                "技术领域 本申请涉及检测技术。\n"
                "具体实施方式 本申请提供一种实现方式。"
            ),
            drawings="图1为结构示意图。",
        )
        issues = check_description_heading_issues(doc)
        self.assertEqual(1, len(issues))
        self.assertEqual("description.heading.missing.required", issues[0].rule_id)
        self.assertIn("背景技术", str(issues[0].message))
        self.assertIn("附图说明", str(issues[0].message))

    def test_does_not_require_drawings_heading_when_drawings_absent(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种装置\n"
                "技术领域 本申请涉及检测技术。\n"
                "背景技术 现有方案存在效率低的问题。\n"
                "发明内容 提出一种改进方案。\n"
                "实施例 下面结合实施例说明。"
            ),
            drawings="",
        )
        issues = check_description_heading_issues(doc)
        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()

