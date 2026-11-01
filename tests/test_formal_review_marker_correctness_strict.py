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


def _build_segments(lines: list[str]) -> tuple[str, list[_Seg]]:
    text = "\n".join(lines)
    rows: list[_Seg] = []
    cursor = 0
    for index, line in enumerate(lines):
        start = cursor
        end = start + len(line)
        rows.append(_Seg(local_start=start, local_end=end, word_range_start=start, raw_text=line))
        cursor = end + (1 if index < len(lines) - 1 else 0)
    return text, rows


class FormalReviewMarkerCorrectnessStrictTests(unittest.TestCase):
    def test_claim_exact_fullwidth_format_is_treated_as_correct(self) -> None:
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="齿轮（10/10A）连接。", anchor_start=0, anchor_end=12)],
            description="",
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10/10A"},
            description_segments=[],
        )
        self.assertEqual(plan.command_count, 0)
        self.assertEqual(plan.skipped_correct_count, 1)

    def test_claim_halfwidth_bracket_is_replaced(self) -> None:
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="齿轮(10/10A)连接。", anchor_start=0, anchor_end=12)],
            description="",
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10/10A"},
            description_segments=[],
        )
        self.assertEqual(plan.command_count, 1)
        cmd = plan.commands[0]
        self.assertEqual(cmd.section, "claims")
        self.assertEqual(cmd.expected_old_fragment, "(10/10A)")
        self.assertEqual(cmd.replacement_text, "（10/10A）")

    def test_claim_square_bracket_is_replaced(self) -> None:
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="齿轮[10/10A]连接。", anchor_start=0, anchor_end=12)],
            description="",
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10/10A"},
            description_segments=[],
        )
        self.assertEqual(plan.command_count, 1)
        cmd = plan.commands[0]
        self.assertEqual(cmd.section, "claims")
        self.assertEqual(cmd.expected_old_fragment, "[10/10A]")
        self.assertEqual(cmd.replacement_text, "（10/10A）")

    def test_claim_bare_number_is_replaced(self) -> None:
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="齿轮56连接。", anchor_start=0, anchor_end=8)],
            description="",
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10/10A"},
            description_segments=[],
        )
        self.assertEqual(plan.command_count, 1)
        cmd = plan.commands[0]
        self.assertEqual(cmd.section, "claims")
        self.assertEqual(cmd.expected_old_fragment, "56")
        self.assertEqual(cmd.replacement_text, "（10/10A）")

    def test_description_bracketed_marker_is_replaced_with_plain_marker(self) -> None:
        description, segments = _build_segments(["背景技术。", "具体实施方式", "齿轮（10/10A）转动。"])
        document = FormalReviewDocument(claims=[], description=description)
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10/10A"},
            description_segments=segments,
        )
        desc_cmds = [item for item in plan.commands if item.section == "description"]
        self.assertEqual(len(desc_cmds), 1)
        self.assertEqual(desc_cmds[0].expected_old_fragment, "（10/10A）")
        self.assertEqual(desc_cmds[0].replacement_text, "10/10A")

    def test_description_exact_plain_format_is_treated_as_correct(self) -> None:
        description, segments = _build_segments(["具体实施方式", "齿轮10/10A转动。"])
        document = FormalReviewDocument(claims=[], description=description)
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10/10A"},
            description_segments=segments,
        )
        self.assertEqual(plan.command_count, 0)
        self.assertEqual(plan.skipped_correct_count, 1)


if __name__ == "__main__":
    unittest.main()
