import unittest

from core.formal_review.models import ClaimItem, FormalReviewDocument
from core.formal_review.service import run_formal_review


class FormalReviewClaim1AnchorExpectedHitTests(unittest.TestCase):
    def test_claim1_threshold_issues_include_expected_hit_anchor(self) -> None:
        doc = FormalReviewDocument(
            claims=[
                ClaimItem(
                    num=1,
                    text="一种装置，包括第一模块(1)、第二模块(2)和第三模块(3)，用于执行复杂流程。",
                    markers=["1", "2", "3"],
                    anchor_start=100,
                )
            ],
            description="",
            abstract="",
            drawings="",
        )
        result = run_formal_review(
            doc,
            wordlists={"forbidden": [], "sensitive": []},
            ignored_issue_ids=set(),
            abstract_threshold=300,
            rule_params={"claim1_word_limit": 5, "claim1_marker_limit": 1},
        )
        issues = list(result.get("issues", []) or [])
        threshold_issues = [
            row
            for row in issues
            if str(getattr(row, "rule_id", "") or "")
            in {"claim1.word_count.exceeded", "claim1.marker_count.exceeded"}
        ]
        self.assertTrue(threshold_issues)
        for issue in threshold_issues:
            snippet = str(getattr(issue, "snippet", "") or "")
            anchor = getattr(issue, "anchor", None)
            self.assertIsInstance(anchor, dict)
            self.assertEqual(str(anchor.get("expected_hit", "") or ""), snippet)
            self.assertLessEqual(len(snippet), 10)
            self.assertNotIn("\n", snippet)


if __name__ == "__main__":
    unittest.main()
