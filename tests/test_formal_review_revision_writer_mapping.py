import unittest
from pathlib import Path


class FormalReviewRevisionWriterMappingTests(unittest.TestCase):
    def test_revision_writer_enables_track_revisions_and_reverse_apply(self) -> None:
        text = Path("core/formal_review/revision_writer.py").read_text(encoding="utf-8")
        self.assertIn("doc2.TrackRevisions = True", text)
        self.assertIn("sorted(writable_segments, key=lambda item: int(item.get(\"word_start\") or 0), reverse=True)", text)
        self.assertIn("target_range = doc2.Range(start, end)", text)
        self.assertIn("target_range.Text = replacement", text)


if __name__ == "__main__":
    unittest.main()
