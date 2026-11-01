import unittest

from core.formal_review.models import ClaimItem
from core.formal_review.rules import check_claim_recursive_multi_reference_issues


class FormalReviewClaimMultiToMultiRecursiveTests(unittest.TestCase):
    def test_recursive_multi_reference_hits_expected_claims(self) -> None:
        claims = [
            ClaimItem(num=1, text="一种冷媒分配器。"),
            ClaimItem(num=2, text="根据权利要求1所述的冷媒分配器。"),
            ClaimItem(num=3, text="根据权利要求1所述的冷媒分配器。"),
            ClaimItem(num=4, text="根据权利要求1和2所述的冷媒分配器。"),
            ClaimItem(num=5, text="根据权利要求4所述的冷媒分配器。"),
            ClaimItem(num=6, text="根据权利要求2-3任一项所述的冷媒分配器。"),
            ClaimItem(num=7, text="根据权利要求4和6所述的冷媒分配器。"),
            ClaimItem(num=8, text="根据权利要求1-3任一项所述的冷媒分配器。"),
            ClaimItem(num=9, text="根据权利要求1-8任一项所述的冷媒分配器。"),
        ]

        issues = check_claim_recursive_multi_reference_issues(claims)
        issue_by_claim = {int(issue.claim_num or 0): issue for issue in issues}

        self.assertIn(7, issue_by_claim)
        self.assertIn(9, issue_by_claim)
        self.assertNotIn(4, issue_by_claim)

        self.assertEqual("claim.ref.multi_to_multi.recursive", issue_by_claim[7].rule_id)
        self.assertIn("递归命中", str(issue_by_claim[7].message or ""))
        self.assertIn("4", str(issue_by_claim[7].message or ""))
        self.assertIn("6", str(issue_by_claim[7].message or ""))


if __name__ == "__main__":
    unittest.main()
