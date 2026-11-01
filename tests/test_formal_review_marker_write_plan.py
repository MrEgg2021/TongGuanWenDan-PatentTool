import unittest
from dataclasses import dataclass

from core.formal_review.marker_rules import build_marker_normalization_write_plan
from core.formal_review.models import ClaimItem, FormalReviewDocument


@dataclass(slots=True)
class _Seg:
    local_start: int
    local_end: int
    word_range_start: int
    raw_text: str


def _segments(lines: list[str]) -> tuple[str, list[_Seg]]:
    text = "\n".join(lines)
    rows: list[_Seg] = []
    cursor = 0
    for idx, line in enumerate(lines):
        start = cursor
        end = start + len(line)
        rows.append(_Seg(local_start=start, local_end=end, word_range_start=start, raw_text=line))
        cursor = end + (1 if idx < len(lines) - 1 else 0)
    return text, rows


class FormalReviewMarkerWritePlanTests(unittest.TestCase):
    def test_plan_counts_and_command_order(self) -> None:
        description, description_segments = _segments(["具体实施方式", "齿轮10连接，齿轮（10）啮合。"])
        document = FormalReviewDocument(
            claims=[
                ClaimItem(num=1, text="齿轮连接。", anchor_start=10, anchor_end=15),
                ClaimItem(num=2, text="齿轮（10）连接。", anchor_start=100, anchor_end=108),
                ClaimItem(num=3, text="齿轮(10)连接。", anchor_start=200, anchor_end=208),
            ],
            description=description,
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10"},
            description_segments=description_segments,
        )

        self.assertEqual(plan.candidate_claims, 3)
        self.assertEqual(plan.candidate_description, 2)
        self.assertEqual(plan.inserted_count, 1)
        self.assertEqual(plan.replaced_count, 2)
        self.assertEqual(plan.skipped_correct_count, 2)
        self.assertEqual(plan.command_count, 3)

        word_starts = [item.word_start for item in plan.commands]
        self.assertEqual(word_starts, sorted(word_starts, reverse=True))
        action_kinds = sorted(item.action_kind for item in plan.commands)
        self.assertEqual(action_kinds, ["insert_after_name", "replace_marker_after_name", "replace_marker_after_name"])

    def test_claim_mixed_legacy_formats_all_become_replace_commands(self) -> None:
        description, description_segments = _segments(["具体实施方式", "齿轮10连接。"])
        document = FormalReviewDocument(
            claims=[
                ClaimItem(num=1, text="齿轮(10)连接。", anchor_start=0, anchor_end=9),
                ClaimItem(num=2, text="齿轮[10]连接。", anchor_start=20, anchor_end=29),
                ClaimItem(num=3, text="齿轮【10】连接。", anchor_start=40, anchor_end=50),
                ClaimItem(num=4, text="齿轮10连接。", anchor_start=60, anchor_end=68),
                ClaimItem(num=5, text="齿轮１０连接。", anchor_start=80, anchor_end=88),
            ],
            description=description,
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10"},
            description_segments=description_segments,
        )
        claim_cmds = [item for item in list(plan.commands or []) if str(getattr(item, "section", "")) == "claims"]
        self.assertEqual(len(claim_cmds), 5)
        self.assertTrue(all(str(getattr(item, "replacement_text", "")) == "（10）" for item in claim_cmds))
        self.assertEqual(int(getattr(plan, "replaced_count", 0) or 0), 5)


if __name__ == "__main__":
    unittest.main()
