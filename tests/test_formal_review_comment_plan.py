import unittest

from core.formal_review.annotator import build_comment_plan
from core.formal_review.models import Issue


class FormalReviewCommentPlanTests(unittest.TestCase):
    def test_build_comment_plan_skips_no_range_mapping(self) -> None:
        issues = [
            Issue(
                rule_id="wordlist.forbidden",
                severity="high",
                category="forbidden",
                section="description",
                message="命中禁用词：绝对",
                span_start=5,
                span_end=7,
                snippet="绝对",
                anchor={"word_range_start": 100},
                issue_id="x1",
            ),
            Issue(
                rule_id="punctuation.repeated",
                severity="warning",
                category="rule",
                section="claims",
                claim_num=2,
                message="连续标点",
                issue_id="x2",
                ignored=True,
            ),
        ]
        plan = build_comment_plan(issues)
        self.assertEqual(plan[0].range_start, 105)
        self.assertEqual(plan[0].range_end, 107)
        self.assertIn("@说明书", plan[0].comment_text)
        self.assertTrue(plan[1].ignored)


if __name__ == "__main__":
    unittest.main()
