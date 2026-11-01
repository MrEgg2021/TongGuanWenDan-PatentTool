import unittest
from pathlib import Path


class FormalReviewEditSegmentExtractionTests(unittest.TestCase):
    def test_extractor_returns_editable_segments(self) -> None:
        text = Path("core/formal_review/extractor.py").read_text(encoding="utf-8")
        self.assertIn("def extract_formal_review_document(", text)
        self.assertIn("-> tuple[FormalReviewDocument, list[TextAnchor], list[EditableSegment], ProjectionBundle]", text)
        self.assertIn("segment_id=f\"claims:{int(current_claim_num)}\"", text)
        self.assertIn("segment_id=f\"{section}:0\"", text)
        self.assertIn("return document, anchors, editable_segments, projections", text)


if __name__ == "__main__":
    unittest.main()
