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
        self.FullName = r"D:\tmp\atomic.docx"
        self.saved = 0

    def Save(self) -> None:
        self.saved += 1


class FormalReviewCommentSyncAtomicTests(unittest.TestCase):
    def test_preflight_failure_returns_zero_commit(self) -> None:
        doc = _FakeDoc()
        failure = type("Failure", (), {"issue_id": "i-1"})()
        with (
            patch("core.formal_review.comment_sync.build_comment_plan", return_value=[]),
            patch(
                "core.formal_review.comment_sync.preflight_comment_targets",
                return_value={"targets": [], "failures": [failure], "skipped_ignored": 2},
            ),
            patch("core.formal_review.comment_sync.clear_tool_comments_in_doc") as clear_mock,
            patch("core.formal_review.comment_sync.apply_comments_to_doc") as apply_mock,
        ):
            result = sync_comments_to_doc(doc, [], author_name="", clear_tool_comments=True)
        clear_mock.assert_not_called()
        apply_mock.assert_not_called()
        self.assertEqual(result.written, 0)
        self.assertEqual(result.skipped, 3)
        self.assertEqual(result.failed_issue_count, 1)
        self.assertEqual(result.failed_issue_ids, ["i-1"])
        self.assertEqual(doc.saved, 0)


if __name__ == "__main__":
    unittest.main()

