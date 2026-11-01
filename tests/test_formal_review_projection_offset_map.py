import unittest

from core.formal_review.text_projection import ParagraphProjection, map_span_to_word_range


class FormalReviewProjectionOffsetMapTests(unittest.TestCase):
    def test_map_span_prefers_explicit_offset_map(self) -> None:
        row = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=4,
            word_start=100,
            word_end=110,
            text="ABCD",
            offset_map_start=[101, 103, 105, 108],
            offset_map_end=[102, 104, 106, 109],
        )
        mapped = map_span_to_word_range([row], 1, 3)
        self.assertEqual(mapped, (103, 106))

    def test_map_span_falls_back_to_linear_without_map(self) -> None:
        row = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=4,
            word_start=20,
            word_end=24,
            text="ABCD",
        )
        mapped = map_span_to_word_range([row], 1, 3)
        self.assertEqual(mapped, (21, 23))


if __name__ == "__main__":
    unittest.main()

