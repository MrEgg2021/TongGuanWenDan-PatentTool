import unittest

from core.formal_review.marker_rules import build_marker_normalization_write_plan
from core.formal_review.models import ClaimItem, FormalReviewDocument


class FormalReviewMarkerOverlapTests(unittest.TestCase):
    def test_longer_name_wins_when_overlap_exists(self) -> None:
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="所述行星齿轮连接。", anchor_start=100, anchor_end=108)],
            description="",
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10", "行星齿轮": "10A"},
            description_segments=[],
        )
        self.assertEqual(plan.candidate_claims, 1)
        self.assertEqual(len(plan.commands), 1)
        self.assertEqual(plan.commands[0].name, "行星齿轮")
        self.assertEqual(plan.commands[0].replacement_text, "（10A）")

    def test_non_overlapping_hits_are_both_kept(self) -> None:
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="行星齿轮与齿轮配合。", anchor_start=0, anchor_end=10)],
            description="",
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10", "行星齿轮": "10A"},
            description_segments=[],
        )
        names = [item.name for item in plan.commands]
        self.assertEqual(plan.candidate_claims, 2)
        self.assertEqual(sorted(names), ["行星齿轮", "齿轮"])


if __name__ == "__main__":
    unittest.main()