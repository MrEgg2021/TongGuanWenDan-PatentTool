import unittest

from core.formal_review.models import FormalReviewDocument
from core.formal_review.semantic_rules import check_drawings_cross_section_consistency_issues
from gui.main_window.mixins.formal_review_ops.shared import _issue_location_text


class FormalReviewCrossSectionIssueLocationTests(unittest.TestCase):
    def test_drawings_missing_in_description_rule_renders_location_as_description(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种设备\n"
                "附图说明\n"
                "图1为结构示意图。\n"
                "图2为分解示意图。\n"
                "具体实施方式\n"
                "如图1所示。"
            ),
            drawings="图1\n图2\n图3",
        )
        issues = check_drawings_cross_section_consistency_issues(doc)
        self.assertEqual(1, len(issues))
        issue = issues[0]
        self.assertEqual("drawings.figure.ref.missing_in_description_drawings", issue.rule_id)
        self.assertEqual("description", str(issue.section))
        self.assertEqual("说明书", _issue_location_text(issue))


if __name__ == "__main__":
    unittest.main()
