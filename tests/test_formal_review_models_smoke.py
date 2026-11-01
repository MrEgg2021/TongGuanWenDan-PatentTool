import unittest

from core.formal_review.models import ClaimItem, FormalReviewDocument, Issue


class FormalReviewModelsSmokeTests(unittest.TestCase):
    def test_models_can_serialize(self) -> None:
        claim = ClaimItem(num=1, text="一种装置。", word_count=4, markers=["1"], refs=[1])
        issue = Issue(
            rule_id="punctuation.repeated",
            severity="warning",
            category="rule",
            section="claims",
            claim_num=1,
            message="存在连续标点",
            span_start=10,
            span_end=12,
            snippet="，，",
            anchor={"word_range_start": 120},
            issue_id="abc123",
        )
        doc = FormalReviewDocument(claims=[claim], description="说明书", abstract="摘要", drawings="附图")

        self.assertEqual(claim.to_dict()["num"], 1)
        self.assertEqual(issue.to_dict()["issue_id"], "abc123")
        payload = doc.to_dict()
        self.assertEqual(payload["claims"][0]["text"], "一种装置。")
        self.assertEqual(payload["description"], "说明书")


if __name__ == "__main__":
    unittest.main()
