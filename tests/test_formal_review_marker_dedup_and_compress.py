import unittest
from unittest.mock import patch

from core.formal_review.marker_rules import _detect_marker_action, build_marker_normalization_write_plan
from core.formal_review.models import ClaimItem, FormalReviewDocument
from core.formal_review.write_commands import WriteCommand


class FormalReviewMarkerDedupAndCompressTests(unittest.TestCase):
    def test_detect_marker_action_compresses_duplicate_runs(self) -> None:
        status, old_frag, repl = _detect_marker_action("claims", "（3）（3）后续", "3")
        self.assertEqual(status, "replace")
        self.assertEqual(old_frag, "（3）（3）")
        self.assertEqual(repl, "（3）")

        status, old_frag, repl = _detect_marker_action("description", "33的侧壁", "3")
        self.assertEqual(status, "replace")
        self.assertEqual(old_frag, "33")
        self.assertEqual(repl, "3")

        status, old_frag, repl = _detect_marker_action("description", "3的侧壁", "3")
        self.assertEqual(status, "correct")
        self.assertEqual(old_frag, "3")
        self.assertEqual(repl, "3")

    def test_plan_deduplicates_identical_commands_and_blocks_conflicts(self) -> None:
        doc = FormalReviewDocument(claims=[ClaimItem(num=1, text="X")], description="", abstract="", drawings="")
        mapping = {"X": "3"}

        def fake_append_claim(_claim, *, rows, plan, cmd_seq):  # noqa: ARG001
            cmd_seq[0] += 1
            plan.commands.append(
                WriteCommand(
                    cmd_id=f"c-{cmd_seq[0]}",
                    action_kind="insert_after_name",
                    section="claims",
                    claim_num=1,
                    name="X",
                    marker="3",
                    local_start=0,
                    local_end=0,
                    word_start=100,
                    word_end=100,
                    expected_old_fragment="",
                    replacement_text="（3）",
                )
            )
            cmd_seq[0] += 1
            plan.commands.append(
                WriteCommand(
                    cmd_id=f"c-{cmd_seq[0]}",
                    action_kind="insert_after_name",
                    section="claims",
                    claim_num=1,
                    name="X",
                    marker="3",
                    local_start=0,
                    local_end=0,
                    word_start=100,
                    word_end=100,
                    expected_old_fragment="",
                    replacement_text="（3）",
                )
            )
            plan.inserted_count += 2

        with (
            patch("core.formal_review.marker_rules._append_commands_for_claim", side_effect=fake_append_claim),
            patch("core.formal_review.marker_rules._append_commands_for_description", return_value=None),
        ):
            plan = build_marker_normalization_write_plan(
                document=doc,
                name_to_marker=mapping,
                description_segments=[],
                doc=None,
                projections=None,
            )
        self.assertEqual(plan.command_count, 1)
        self.assertEqual(plan.inserted_count, 1)
        self.assertTrue(any("去重" in str(msg) for msg in list(plan.warnings or [])))

        def fake_append_conflict(_claim, *, rows, plan, cmd_seq):  # noqa: ARG001
            cmd_seq[0] += 1
            plan.commands.append(
                WriteCommand(
                    cmd_id=f"c-{cmd_seq[0]}",
                    action_kind="replace_marker_after_name",
                    section="claims",
                    claim_num=1,
                    name="X",
                    marker="3",
                    local_start=0,
                    local_end=2,
                    word_start=200,
                    word_end=202,
                    expected_old_fragment="(9)",
                    replacement_text="（3）",
                )
            )
            cmd_seq[0] += 1
            plan.commands.append(
                WriteCommand(
                    cmd_id=f"c-{cmd_seq[0]}",
                    action_kind="replace_marker_after_name",
                    section="claims",
                    claim_num=1,
                    name="X",
                    marker="3",
                    local_start=0,
                    local_end=2,
                    word_start=200,
                    word_end=202,
                    expected_old_fragment="(9)",
                    replacement_text="（3）（3）",
                )
            )

        with (
            patch("core.formal_review.marker_rules._append_commands_for_claim", side_effect=fake_append_conflict),
            patch("core.formal_review.marker_rules._append_commands_for_description", return_value=None),
        ):
            plan = build_marker_normalization_write_plan(
                document=doc,
                name_to_marker=mapping,
                description_segments=[],
                doc=None,
                projections=None,
            )
        self.assertTrue(plan.errors)


if __name__ == "__main__":
    unittest.main()

