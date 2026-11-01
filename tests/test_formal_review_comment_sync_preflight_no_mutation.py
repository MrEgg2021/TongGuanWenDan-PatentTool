import unittest
from unittest.mock import patch

from core.formal_review.comment_sync import sync_comments_to_doc


class _FakeUndoRecord:
    def __init__(self) -> None:
        self.started = 0
        self.ended = 0

    def StartCustomRecord(self, _name: str) -> None:  # noqa: N802 - COM style
        self.started += 1

    def EndCustomRecord(self) -> None:  # noqa: N802 - COM style
        self.ended += 1


class _FakeApp:
    def __init__(self) -> None:
        self.UserName = "orig"
        self.UserInitials = "OR"
        self.UndoRecord = _FakeUndoRecord()
        self.undo_called = 0

    def Undo(self) -> None:  # noqa: N802 - COM style
        self.undo_called += 1


class _FakeDoc:
    def __init__(self) -> None:
        self.Application = _FakeApp()
        self.FullName = r"D:\tmp\preflight.docx"
        self.saved = 0

    def Save(self) -> None:  # noqa: N802 - COM style
        self.saved += 1


class FormalReviewCommentSyncPreflightNoMutationTests(unittest.TestCase):
    def test_preflight_failure_does_not_mutate_even_when_undo_available(self) -> None:
        doc = _FakeDoc()
        failure = type("Failure", (), {"issue_id": "i-1", "reason_code": "candidate_missing"})()
        with (
            patch("core.formal_review.comment_sync.build_comment_plan", return_value=[]),
            patch(
                "core.formal_review.comment_sync.preflight_comment_targets",
                return_value={"targets": [], "failures": [failure], "skipped_ignored": 0},
            ),
            patch("core.formal_review.comment_sync.clear_tool_highlights_via_comments") as clear_hl_mock,
            patch("core.formal_review.comment_sync.clear_tool_comments_in_doc") as clear_mock,
            patch("core.formal_review.comment_sync.apply_comments_to_doc") as apply_mock,
        ):
            result = sync_comments_to_doc(doc, [], author_name="", clear_tool_comments=True)

        # Preflight failure must be strictly "no mutation": no clearing, no writing, no save.
        clear_hl_mock.assert_not_called()
        clear_mock.assert_not_called()
        apply_mock.assert_not_called()
        self.assertEqual(doc.saved, 0)

        # Preflight failure should not start UndoRecord, and should not call app.Undo().
        self.assertEqual(doc.Application.UndoRecord.started, 0)
        self.assertEqual(doc.Application.UndoRecord.ended, 0)
        self.assertEqual(doc.Application.undo_called, 0)

        self.assertEqual(result.written, 0)
        self.assertEqual(result.failed_issue_count, 1)
        self.assertEqual(result.failed_issue_ids, ["i-1"])


if __name__ == "__main__":
    unittest.main()

