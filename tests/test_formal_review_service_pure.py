import unittest

from core.formal_review.models import ClaimItem, FormalReviewDocument
from core.formal_review.service import run_formal_review
from core.formal_review.wordlists import DEFAULT_WORDLISTS_V2


class FormalReviewServicePureTests(unittest.TestCase):
    def test_run_formal_review_generates_issues(self) -> None:
        doc = FormalReviewDocument(
            claims=[
                ClaimItem(num=1, text="一种设备，其特征在于，包含模块（1）。", anchor_start=100),
                ClaimItem(num=2, text="根据权利要求3和4所述设备。", anchor_start=200),
                ClaimItem(num=3, text="根据权利要求1所述设备。", anchor_start=300),
            ],
            description="说明书中保证系统稳定，，并且绝对可靠。",
            abstract="字" * 320,
            drawings="图1为结构示意图。",
        )
        wordlists = {"forbidden": ["绝对"], "sensitive": ["保证"]}
        result = run_formal_review(doc, wordlists=wordlists, ignored_issue_ids=set(), abstract_threshold=300)
        issues = result["issues"]
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(issue.rule_id == "abstract.word_count.exceeded" for issue in issues))
        self.assertTrue(any(issue.rule_id == "wordlist.description.forbidden" for issue in issues))
        self.assertTrue(any(issue.rule_id == "claim.ref.missing_target" for issue in issues))

    def test_slim_default_wordlists_do_not_flag_legacy_broad_terms(self) -> None:
        doc = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="一种装置，可以包括优选模块。", anchor_start=0)],
            description="该装置约为矩形，并且绝对可靠。",
            abstract="",
            drawings="",
        )
        result = run_formal_review(
            doc,
            wordlists=DEFAULT_WORDLISTS_V2,
            ignored_issue_ids=set(),
            abstract_threshold=300,
        )
        issues = list(result.get("issues", []) or [])
        self.assertFalse(any(str(issue.rule_id).startswith("wordlist.") for issue in issues))


if __name__ == "__main__":
    unittest.main()
