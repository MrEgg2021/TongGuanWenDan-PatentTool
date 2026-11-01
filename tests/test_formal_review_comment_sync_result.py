import unittest
from unittest.mock import patch

from core.formal_review.comment_sync import CommentSyncResult, sync_comments_to_doc


class _FakeApp:
    def __init__(self) -> None:
        self.UserName = "orig"
        self.UserInitials = "OR"


class _FakeDoc:
    def __init__(self) -> None:
        self.Application = _FakeApp()
        self.FullName = r"D:\tmp\demo.docx"
        self.saved = 0

    def Save(self) -> None:
        self.saved += 1


class FormalReviewCommentSyncResultTests(unittest.TestCase):
    def test_result_dataclass_fields(self) -> None:
        row = CommentSyncResult(
            output_path="a.docx",
            written=1,
            skipped=2,
            cleared_tool_comments=3,
            cleared_tool_highlights=0,
            used_existing_doc=True,
        )
        self.assertEqual(row.output_path, "a.docx")
        self.assertEqual(row.written, 1)
        self.assertEqual(row.skipped, 2)
        self.assertEqual(row.cleared_tool_comments, 3)
        self.assertEqual(row.cleared_tool_highlights, 0)
        self.assertTrue(row.used_existing_doc)

    def test_sync_comments_to_doc_returns_structured_counts(self) -> None:
        doc = _FakeDoc()
        with (
            patch("core.formal_review.comment_sync.clear_tool_comments_in_doc", return_value=4),
            patch("core.formal_review.comment_sync.build_comment_plan", return_value=[]),
            patch("core.formal_review.comment_sync.apply_comments_to_doc", return_value={"written": 7, "skipped": 1}),
        ):
            result = sync_comments_to_doc(
                doc,
                [],
                author_name="Tester",
                clear_tool_comments=True,
            )
        self.assertEqual(result.output_path, doc.FullName)
        self.assertEqual(result.written, 7)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.cleared_tool_comments, 4)
        self.assertEqual(result.cleared_tool_highlights, 0)
        self.assertTrue(result.used_existing_doc)
        self.assertEqual(doc.saved, 1)
        self.assertEqual(doc.Application.UserName, "orig")
        self.assertEqual(doc.Application.UserInitials, "OR")


if __name__ == "__main__":
    unittest.main()
