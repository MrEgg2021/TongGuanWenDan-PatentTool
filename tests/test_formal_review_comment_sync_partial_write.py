import unittest
from unittest.mock import patch

from core.formal_review.comment_sync import sync_comments_to_doc


class _FakeApp:
    def __init__(self) -> None:
        self.UserName = "orig"
        self.UserInitials = "OR"


class _FakeDoc:
    def __init__(self) -> None:
        self.Application = _FakeApp()
        self.FullName = r"D:\tmp\partial_write.docx"
        self.saved = 0

    def Save(self) -> None:
        self.saved += 1


class FormalReviewCommentSyncPartialWriteTests(unittest.TestCase):
    def test_preflight_partial_mode_writes_targets_and_preserves_failed_ranges(self) -> None:
        doc = _FakeDoc()
        preflight_failure = type(
            "Failure",
            (),
            {"issue_id": "i-fail", "reason_code": "word_find_candidate_not_found", "detail": ""},
        )()
        target = type("Target", (), {"issue_id": "i-ok", "start": 10, "end": 20})()

        with (
            patch("core.formal_review.comment_sync.build_comment_plan", return_value=[]),
            patch(
                "core.formal_review.comment_sync.preflight_comment_targets",
                return_value={
                    "targets": [target],
                    "failures": [preflight_failure],
                    "skipped_ignored": 0,
                    "strict_failed": 1,
                    "loose_rescued": 0,
                    "final_failed": 1,
                    "strict_level_hist": {},
                    "loose_level_hist": {},
                    "resolver_path_hist": {},
                    "resolver_reason_hist": {"word_find_candidate_not_found": 1},
                },
            ),
            patch("core.formal_review.comment_sync.clear_tool_highlights_via_comments", return_value=2) as clear_hl_mock,
            patch("core.formal_review.comment_sync.clear_tool_comments_in_doc", return_value=3) as clear_cm_mock,
            patch(
                "core.formal_review.comment_sync.apply_comments_to_doc",
                return_value={
                    "written": 1,
                    "skipped": 1,
                    "failed_issue_count": 1,
                    "failed_issue_ids": ["i-fail"],
                    "failed_items": [{"issue_id": "i-fail", "reason_code": "word_find_candidate_not_found"}],
                },
            ) as apply_mock,
        ):
            result = sync_comments_to_doc(
                doc,
                [],
                author_name="",
                clear_tool_comments=True,
                allow_partial_on_preflight_failure=True,
                preserve_failed_existing_comments=True,
            )

        clear_hl_mock.assert_called_once()
        clear_cm_mock.assert_called_once()
        self.assertEqual(clear_hl_mock.call_args.kwargs.get("target_ranges"), {(10, 20)})
        self.assertEqual(clear_cm_mock.call_args.kwargs.get("target_ranges"), {(10, 20)})
        apply_mock.assert_called_once()
        self.assertTrue(bool(apply_mock.call_args.kwargs.get("allow_partial_preflight_failures")))
        self.assertEqual(result.written, 1)
        self.assertEqual(result.failed_issue_count, 1)
        self.assertEqual(result.failed_issue_ids, ["i-fail"])
        self.assertEqual(result.failed_reason_codes, ["word_find_candidate_not_found"])
        self.assertEqual(result.cleared_tool_comments, 3)
        self.assertEqual(result.cleared_tool_highlights, 2)
        self.assertEqual(doc.saved, 1)

    def test_preflight_failure_without_targets_remains_no_mutation(self) -> None:
        doc = _FakeDoc()
        preflight_failure = type("Failure", (), {"issue_id": "i-fail", "reason_code": "candidate_missing", "detail": ""})()
        with (
            patch("core.formal_review.comment_sync.build_comment_plan", return_value=[]),
            patch(
                "core.formal_review.comment_sync.preflight_comment_targets",
                return_value={
                    "targets": [],
                    "failures": [preflight_failure],
                    "skipped_ignored": 0,
                    "strict_failed": 1,
                    "loose_rescued": 0,
                    "final_failed": 1,
                    "strict_level_hist": {},
                    "loose_level_hist": {},
                    "resolver_path_hist": {},
                    "resolver_reason_hist": {"candidate_missing": 1},
                },
            ),
            patch("core.formal_review.comment_sync.clear_tool_highlights_via_comments") as clear_hl_mock,
            patch("core.formal_review.comment_sync.clear_tool_comments_in_doc") as clear_cm_mock,
            patch("core.formal_review.comment_sync.apply_comments_to_doc") as apply_mock,
        ):
            result = sync_comments_to_doc(
                doc,
                [],
                author_name="",
                clear_tool_comments=True,
                allow_partial_on_preflight_failure=True,
                preserve_failed_existing_comments=True,
            )

        clear_hl_mock.assert_not_called()
        clear_cm_mock.assert_not_called()
        apply_mock.assert_not_called()
        self.assertEqual(result.written, 0)
        self.assertEqual(result.failed_issue_count, 1)
        self.assertEqual(result.failed_issue_ids, ["i-fail"])
        self.assertEqual(doc.saved, 0)


if __name__ == "__main__":
    unittest.main()
