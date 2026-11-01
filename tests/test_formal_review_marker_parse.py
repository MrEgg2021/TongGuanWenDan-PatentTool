import unittest

from core.formal_review.text_utils import parse_marker_note_map, parse_marker_note_payload


class FormalReviewMarkerParseTests(unittest.TestCase):
    def test_parse_supports_alnum_and_slash_markers(self) -> None:
        payload = parse_marker_note_payload("10、齿轮；10a、行星齿轮；10/10a、壳体")
        self.assertEqual(payload.name_to_marker.get("齿轮"), "10")
        self.assertEqual(payload.name_to_marker.get("行星齿轮"), "10A")
        self.assertEqual(payload.name_to_marker.get("壳体"), "10/10A")
        self.assertEqual(payload.errors, [])

    def test_same_name_with_multiple_markers_is_blocking_error(self) -> None:
        payload = parse_marker_note_payload("10、齿轮；11、齿轮")
        self.assertTrue(payload.errors)
        self.assertIn("齿轮", payload.errors[0])

    def test_same_marker_with_multiple_names_warns_and_keeps_first(self) -> None:
        payload = parse_marker_note_payload("10、齿轮；10、行星齿轮")
        self.assertEqual(payload.marker_to_name.get("10"), "齿轮")
        self.assertTrue(payload.warnings)
        self.assertIn("10", payload.warnings[0])
        mapping = parse_marker_note_map("10、齿轮；10、行星齿轮")
        self.assertEqual(mapping.get("10"), "齿轮")


if __name__ == "__main__":
    unittest.main()