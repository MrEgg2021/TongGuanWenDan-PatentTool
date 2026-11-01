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
    result: list[_Seg] = []
    cursor = 0
    for idx, line in enumerate(lines):
        start = cursor
        end = start + len(line)
        result.append(_Seg(local_start=start, local_end=end, word_range_start=start, raw_text=line))
        cursor = end + (1 if idx < len(lines) - 1 else 0)
    return text, result


class FormalReviewMarkerScopeImplSectionTests(unittest.TestCase):
    def test_description_hits_before_impl_heading_are_ignored(self) -> None:
        description, segs = _segments(["齿轮在背景技术中。", "具体实施方式", "齿轮用于传动。"])
        document = FormalReviewDocument(claims=[], description=description)
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10"},
            description_segments=segs,
        )
        desc_cmds = [item for item in plan.commands if item.section == "description"]
        self.assertEqual(plan.candidate_description, 1)
        self.assertEqual(len(desc_cmds), 1)
        self.assertEqual(desc_cmds[0].expected_old_fragment, "")

    def test_missing_impl_heading_blocks_description_but_keeps_claim_commands(self) -> None:
        description, segs = _segments(["齿轮在背景技术中。", "齿轮用于传动。"])
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="齿轮连接。", anchor_start=200, anchor_end=205)],
            description=description,
        )
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10"},
            description_segments=segs,
        )
        self.assertFalse(plan.description_scope_found)
        self.assertTrue(plan.errors)
        claim_cmds = [item for item in plan.commands if item.section == "claims"]
        desc_cmds = [item for item in plan.commands if item.section == "description"]
        self.assertEqual(len(claim_cmds), 1)
        self.assertEqual(len(desc_cmds), 0)

    def test_impl_example_heading_is_treated_as_description_scope_start(self) -> None:
        description, segs = _segments(["背景技术。", "实施例", "齿轮用于传动。"])
        document = FormalReviewDocument(claims=[], description=description)
        plan = build_marker_normalization_write_plan(
            document=document,
            name_to_marker={"齿轮": "10"},
            description_segments=segs,
        )
        self.assertTrue(plan.description_scope_found)
        desc_cmds = [item for item in plan.commands if item.section == "description"]
        self.assertEqual(plan.candidate_description, 1)
        self.assertEqual(len(desc_cmds), 1)


if __name__ == "__main__":
    unittest.main()
