import unittest

from core.formal_review.models import ClaimItem
from core.formal_review.rules import check_claim_reference_basis_issues


REFER_WORD = "\u6240\u8ff0"


class FormalReviewClaimReferenceBasisRuleTests(unittest.TestCase):
    def test_only_adjacent_term_after_refer_word_is_checked(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u88c5\u7f6e\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u6240\u8ff0A\u8bbe\u7f6e\u4e8e\u58f3\u4f53\u3002"),
            ClaimItem(num=3, text="\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u88c5\u7f6e\uff0c\u6240\u8ff0A\u4e0a\u8fd8\u8bbe\u7f6e\u6709B\u3002"),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"1": "A", "2": "B"},
        )
        claim3_issues = [issue for issue in issues if int(issue.claim_num or 0) == 3]
        self.assertEqual([], claim3_issues)

    def test_marker_basis_missing_is_reported_from_adjacent_term(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u88c5\u7f6e\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u6240\u8ff0\u55b7\u5634\u8bbe\u7f6e\u4e8e\u58f3\u4f53\u3002"),
            ClaimItem(num=2, text="\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u88c5\u7f6e\uff0c\u6240\u8ff0\u5bfc\u6d41\u55b7\u5634\uff082\uff09\u8fde\u63a5\u4e8e\u7ba1\u8def\u3002"),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"1": "\u55b7\u5634", "2": "\u5bfc\u6d41\u55b7\u5634"},
        )
        claim2_issues = [issue for issue in issues if int(issue.claim_num or 0) == 2]
        rule_ids = {issue.rule_id for issue in claim2_issues}
        self.assertIn("claim.ref.marker_basis.missing", rule_ids)
        self.assertNotIn("claim.ref.term_basis.missing", rule_ids)

    def test_term_basis_missing_is_reported_without_marker(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u88c5\u7f6e\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u6240\u8ff0\u55b7\u5634\u8bbe\u7f6e\u4e8e\u58f3\u4f53\u3002"),
            ClaimItem(num=2, text="\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u88c5\u7f6e\uff0c\u6240\u8ff0\u5bfc\u6d41\u5b54\u4e0e\u58f3\u4f53\u8fde\u901a\u3002"),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"1": "\u55b7\u5634"},
        )
        claim2_issues = [issue for issue in issues if int(issue.claim_num or 0) == 2]
        rule_ids = {issue.rule_id for issue in claim2_issues}
        self.assertIn("claim.ref.term_basis.missing", rule_ids)
        self.assertNotIn("claim.ref.marker_basis.missing", rule_ids)

    def test_recursive_reference_chain_can_provide_basis(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u88c5\u7f6e\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u6240\u8ff0\u55b7\u5634\u8bbe\u7f6e\u4e8e\u58f3\u4f53\u3002"),
            ClaimItem(num=2, text="\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u88c5\u7f6e\uff0c\u6240\u8ff0\u55b7\u5634\u4e0e\u58f3\u4f53\u8fde\u63a5\u3002"),
            ClaimItem(num=3, text="\u6839\u636e\u6743\u5229\u8981\u6c422\u6240\u8ff0\u7684\u88c5\u7f6e\uff0c\u6240\u8ff0\u55b7\u5634\u8fde\u63a5\u5728\u5bfc\u6d41\u901a\u9053\u3002"),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"1": "\u55b7\u5634"},
        )
        claim3_issues = [issue for issue in issues if int(issue.claim_num or 0) == 3]
        self.assertEqual([], claim3_issues)

    def test_multiple_refer_words_generate_independent_units(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u88c5\u7f6e\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u6240\u8ff0A\u8bbe\u7f6e\u4e8e\u58f3\u4f53\u3002"),
            ClaimItem(num=2, text="\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u88c5\u7f6e\uff0c\u6240\u8ff0A\u4e0a\u8fd8\u8bbe\u7f6e\u6709B\uff0c\u4e14\u6240\u8ff0C\u8fde\u63a5\u6240\u8ff0A\u3002"),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"1": "A", "2": "B", "3": "C"},
        )
        claim2_issues = [issue for issue in issues if int(issue.claim_num or 0) == 2]
        self.assertTrue(
            any(
                issue.rule_id == "claim.ref.marker_basis.missing" and "C" in str(issue.message)
                for issue in claim2_issues
            )
        )
        self.assertFalse(
            any(
                issue.rule_id == "claim.ref.marker_basis.missing" and "B" in str(issue.message)
                for issue in claim2_issues
            )
        )

    def test_preamble_refer_word_is_skipped_when_characterizing_phrase_exists(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u88c5\u7f6e\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0cA\u8fde\u63a5\u58f3\u4f53\u3002"),
            ClaimItem(num=2, text="\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u88c5\u7f6e\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u6240\u8ff0A\u4e0a\u8fd8\u8bbe\u7f6e\u6709B\u3002"),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"1": "A", "2": "B"},
        )
        claim2_issues = [issue for issue in issues if int(issue.claim_num or 0) == 2]
        self.assertEqual([], claim2_issues)

    def test_preamble_refer_word_is_skipped_by_first_delimiter_fallback(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u88c5\u7f6e\uff0cA\u8fde\u63a5\u58f3\u4f53\u3002"),
            ClaimItem(num=2, text="\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u88c5\u7f6e\uff0c\u6240\u8ff0A\u56fa\u5b9a\u3002"),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"1": "A"},
        )
        claim2_issues = [issue for issue in issues if int(issue.claim_num or 0) == 2]
        self.assertEqual([], claim2_issues)

    def test_local_prefix_in_same_claim_provides_marker_basis(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u8bbe\u5907\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u58f3\u4f53\u8fde\u63a5\u5e95\u5ea7\u3002"),
            ClaimItem(
                num=2,
                text=(
                    "\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u8bbe\u5907\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c"
                    "\u652f\u67b6\u8bbe\u7f6e\u5728\u58f3\u4f53\u4e0a\u3002\u6240\u8ff0\u652f\u67b6\uff0810\uff09\u8fde\u63a5\u4f20\u611f\u5668\u3002"
                ),
            ),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"10": "\u652f\u67b6"},
        )
        claim2_issues = [issue for issue in issues if int(issue.claim_num or 0) == 2]
        self.assertFalse(any(issue.rule_id == "claim.ref.marker_basis.missing" for issue in claim2_issues))

    def test_preamble_term_before_scan_start_is_not_local_basis(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u8bbe\u5907\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u58f3\u4f53\u8fde\u63a5\u5e95\u5ea7\u3002"),
            ClaimItem(
                num=2,
                text=(
                    "\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u652f\u67b6\u68c0\u6d4b\u8bbe\u5907\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c"
                    "\u6240\u8ff0\u652f\u67b6\uff0810\uff09\u8fde\u63a5\u4f20\u611f\u5668\u3002"
                ),
            ),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"10": "\u652f\u67b6"},
        )
        claim2_issues = [issue for issue in issues if int(issue.claim_num or 0) == 2]
        self.assertTrue(any(issue.rule_id == "claim.ref.marker_basis.missing" for issue in claim2_issues))

    def test_cross_sentence_local_prefix_still_provides_basis(self) -> None:
        claims = [
            ClaimItem(num=1, text="\u4e00\u79cd\u8bbe\u5907\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c\u58f3\u4f53\u8fde\u63a5\u5e95\u5ea7\u3002"),
            ClaimItem(
                num=2,
                text=(
                    "\u6839\u636e\u6743\u5229\u8981\u6c421\u6240\u8ff0\u7684\u8bbe\u5907\uff0c\u5176\u7279\u5f81\u5728\u4e8e\uff0c"
                    "\u652f\u67b6\u7528\u4e8e\u652f\u6491\u4f20\u611f\u5668\u3002\u6240\u8ff0\u652f\u67b6\u8fde\u63a5\u5728\u5b89\u88c5\u677f\u4e0a\u3002"
                ),
            ),
        ]
        issues = check_claim_reference_basis_issues(
            claims,
            refer_words=[REFER_WORD],
            marker_note_map={"10": "\u652f\u67b6"},
        )
        claim2_issues = [issue for issue in issues if int(issue.claim_num or 0) == 2]
        self.assertFalse(any(issue.rule_id == "claim.ref.marker_basis.missing" for issue in claim2_issues))


if __name__ == "__main__":
    unittest.main()
