from __future__ import annotations

import unittest

from core.formal_review.marker_rules import build_marker_normalization_write_plan
from core.formal_review.models import ClaimItem, FormalReviewDocument


class FormalReviewMarkerRulesSnapshotTests(unittest.TestCase):
    def test_claim_path_snapshot_is_stable(self) -> None:
        document = FormalReviewDocument(
            claims=[
                ClaimItem(num=1, text="gear connected", anchor_start=10),
                ClaimItem(num=2, text="gear（10）connected", anchor_start=100),
                ClaimItem(num=3, text="gear10connected", anchor_start=200),
            ],
            description="",
            abstract="",
            drawings="",
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"gear": "10"},
            description_segments=[],
            doc=None,
            projections=None,
        )

        snapshot = {
            "candidate_claims": int(plan.candidate_claims),
            "candidate_description": int(plan.candidate_description),
            "inserted_count": int(plan.inserted_count),
            "replaced_count": int(plan.replaced_count),
            "skipped_correct_count": int(plan.skipped_correct_count),
            "skipped_unsupported_count": int(plan.skipped_unsupported_count),
            "command_count": int(plan.command_count),
            "commands": [
                (
                    int(cmd.claim_num or 0),
                    str(cmd.action_kind),
                    int(cmd.local_start),
                    int(cmd.local_end),
                    int(cmd.word_start),
                    int(cmd.word_end),
                )
                for cmd in list(plan.commands or [])
            ],
        }
        expected = {
            "candidate_claims": 3,
            "candidate_description": 0,
            "inserted_count": 1,
            "replaced_count": 1,
            "skipped_correct_count": 1,
            "skipped_unsupported_count": 0,
            "command_count": 2,
            "commands": [
                (3, "replace_marker_after_name", 4, 7, 204, 207),
                (1, "insert_after_name", 4, 4, 14, 14),
            ],
        }
        self.assertEqual(snapshot, expected)


if __name__ == "__main__":
    unittest.main()
