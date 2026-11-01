import unittest

from core.formal_review.models import ClaimItem, FormalReviewDocument
from core.formal_review.rule_registry import default_rule_enabled_map
from core.formal_review.service import run_formal_review


class FormalReviewServiceNewClaimRulesIntegrationTests(unittest.TestCase):
    def _build_doc(self) -> FormalReviewDocument:
        claims = [
            ClaimItem(num=1, text="一种冷媒分配器。其特征在于，包括分配管。", anchor_start=100),
            ClaimItem(num=2, text="根据权利要求1所述的冷媒分配器。", anchor_start=200),
            ClaimItem(num=3, text="根据权利要求1所述的冷媒分配器。", anchor_start=300),
            ClaimItem(num=4, text="根据权利要求1和2所述的冷媒分配器。", anchor_start=400),
            ClaimItem(num=5, text="根据权利要求4所述的冷媒分配器。", anchor_start=500),
            ClaimItem(num=6, text="根据权利要求2-3任一项所述的冷媒分配器。", anchor_start=600),
            ClaimItem(num=7, text="根据权利要求4和6所述的冷媒分配器。", anchor_start=700),
            ClaimItem(num=8, text="根据权利要求1-3任一项所述的冷媒分配器", anchor_start=800),
            ClaimItem(num=9, text="根据权利要求1-8任一项所述的冷媒分配器。", anchor_start=900),
        ]
        return FormalReviewDocument(
            claims=claims,
            description="说明书正文。",
            abstract="摘要正文。",
            drawings="",
        )

    def test_service_emits_three_new_claim_rule_ids(self) -> None:
        result = run_formal_review(self._build_doc(), wordlists={}, ignored_issue_ids=set(), abstract_threshold=300)
        issues = list(result.get("issues", []) or [])
        rule_ids = {str(issue.rule_id or "") for issue in issues}
        self.assertIn("claim.ref.multi_to_multi.recursive", rule_ids)
        self.assertIn("claim.punctuation.period.extra", rule_ids)
        self.assertIn("claim.punctuation.period.tail_missing", rule_ids)

    def test_service_respects_enabled_rule_filter_for_new_rules(self) -> None:
        enabled = {rule_id for rule_id, is_enabled in default_rule_enabled_map().items() if is_enabled}
        enabled.discard("claim.ref.multi_to_multi.recursive")
        enabled.discard("claim.punctuation.period.extra")
        enabled.discard("claim.punctuation.period.tail_missing")

        result = run_formal_review(
            self._build_doc(),
            wordlists={},
            ignored_issue_ids=set(),
            abstract_threshold=300,
            enabled_rule_ids=enabled,
        )
        issues = list(result.get("issues", []) or [])
        rule_ids = {str(issue.rule_id or "") for issue in issues}
        self.assertNotIn("claim.ref.multi_to_multi.recursive", rule_ids)
        self.assertNotIn("claim.punctuation.period.extra", rule_ids)
        self.assertNotIn("claim.punctuation.period.tail_missing", rule_ids)


if __name__ == "__main__":
    unittest.main()
