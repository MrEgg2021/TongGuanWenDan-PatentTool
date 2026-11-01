import unittest

from core.formal_review.plain_text_parser import parse_plain_text_sections


class FormalReviewPlainTextParserTests(unittest.TestCase):
    def test_split_claims_by_period_and_fill_number(self) -> None:
        document, anchors, editable_segments = parse_plain_text_sections(
            "1、一种装置，包括模块A。根据权利要求1所述装置，进一步包括模块B。",
            "说明书正文。",
            "摘要。",
            "附图说明。",
        )
        self.assertEqual(len(document.claims), 2)
        self.assertEqual(document.claims[0].num, 1)
        self.assertEqual(document.claims[1].num, 2)
        self.assertTrue(document.claims[0].text.endswith("。"))
        self.assertTrue(document.claims[1].text.endswith("。"))
        self.assertGreaterEqual(len(anchors), 4)
        self.assertIn("claims:1", {item.segment_id for item in editable_segments})
        self.assertIn("description:0", {item.segment_id for item in editable_segments})

    def test_preserve_explicit_claim_numbers(self) -> None:
        document, _anchors, editable_segments = parse_plain_text_sections(
            "3、一种系统。7、根据权利要求3所述系统。",
            "",
            "",
            "",
        )
        self.assertEqual([claim.num for claim in document.claims], [3, 7])
        self.assertEqual([item.segment_id for item in editable_segments], ["claims:3", "claims:7"])


if __name__ == "__main__":
    unittest.main()
