import unittest
from pathlib import Path


class FormalReviewRevisionWriterFallbackCommentTests(unittest.TestCase):
    def test_failed_or_non_text_segments_are_downgraded_to_comment(self) -> None:
        text = Path("core/formal_review/revision_writer.py").read_text(encoding="utf-8")
        self.assertIn("downgraded_rows.append((segment, reason))", text)
        self.assertIn("downgraded_rows.append((segment, \"Word 定位区间无效\"))", text)
        self.assertIn("downgraded_rows.append((segment, \"Word 回写失败，已降级为批注\"))", text)
        self.assertIn("_add_comment_to_doc(", text)
        self.assertIn("\"downgraded_comment_written\": downgraded_comment_written", text)


if __name__ == "__main__":
    unittest.main()
