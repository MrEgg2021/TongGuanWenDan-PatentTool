import unittest

from core.formal_review.text_projection import (
    ParagraphProjection,
    all_occurrences,
    locate_occurrence_in_projection,
    map_span_to_word_range,
    projection_text,
)


class FormalReviewTextProjectionTests(unittest.TestCase):
    def test_projection_text_joins_paragraphs_with_newline(self) -> None:
        paragraphs = [
            ParagraphProjection("description", None, 1, 0, 4, 10, 14, "abcd"),
            ParagraphProjection("description", None, 2, 5, 8, 30, 33, "xyz"),
        ]
        self.assertEqual(projection_text(paragraphs), "abcd\nxyz")

    def test_map_span_to_word_range_in_single_paragraph(self) -> None:
        paragraphs = [ParagraphProjection("description", None, 1, 0, 8, 100, 108, "connect.")]
        self.assertEqual(map_span_to_word_range(paragraphs, 2, 5), (102, 105))

    def test_map_span_to_word_range_rejects_cross_paragraph_span(self) -> None:
        paragraphs = [
            ParagraphProjection("description", None, 1, 0, 4, 10, 14, "abcd"),
            ParagraphProjection("description", None, 2, 5, 8, 30, 33, "xyz"),
        ]
        self.assertIsNone(map_span_to_word_range(paragraphs, 3, 6))

    def test_locate_occurrence_in_projection_by_index(self) -> None:
        paragraphs = [ParagraphProjection("description", None, 1, 0, 20, 0, 20, "connect and connect")]
        self.assertEqual(all_occurrences("connect and connect", "connect"), [0, 12])
        self.assertEqual(locate_occurrence_in_projection(paragraphs, "connect", 1), (12, 19))


if __name__ == "__main__":
    unittest.main()
