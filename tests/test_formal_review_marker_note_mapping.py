import unittest

from core.formal_review.text_utils import parse_marker_note_map


class FormalReviewMarkerNoteMappingTests(unittest.TestCase):
    def test_parse_marker_note_map_supports_common_separators(self) -> None:
        text = "1、壳体；2、固定架\n201:滑槽\n202) 扣件。"
        mapping = parse_marker_note_map(text)
        self.assertEqual(mapping.get("1"), "壳体")
        self.assertEqual(mapping.get("2"), "固定架")
        self.assertEqual(mapping.get("201"), "滑槽")
        self.assertEqual(mapping.get("202"), "扣件")

    def test_parse_marker_note_map_ignores_invalid_rows(self) -> None:
        text = "壳体；abc、固定架"
        mapping = parse_marker_note_map(text)
        self.assertEqual(mapping, {})


if __name__ == "__main__":
    unittest.main()