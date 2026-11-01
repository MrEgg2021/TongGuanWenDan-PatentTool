import unittest

from core.formal_review.models import Issue
from core.formal_review.service import build_issue_id


class FormalReviewIssueIdTests(unittest.TestCase):
    def test_issue_id_contains_anchor_and_span(self) -> None:
        issue = Issue(
            rule_id="wordlist.forbidden",
            severity="high",
            category="forbidden",
            section="claims",
            claim_num=3,
            span_start=12,
            span_end=16,
            snippet="绝对",
            message="命中禁用词",
            anchor={"word_range_start": 230},
        )
        issue_id = build_issue_id(issue)
        self.assertIn("wordlist.forbidden|claims|3|230|12|16|", issue_id)


if __name__ == "__main__":
    unittest.main()
