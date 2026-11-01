import unittest

from core.formal_review.rules import check_punctuation_issues


class FormalReviewPunctuationBridgeExemptionTests(unittest.TestCase):
    def test_bridge_clusters_are_exempt(self) -> None:
        samples = [
            "A\u201d \uff0c \u201cB",
            "A\uff09 \uff0c \u201cB",
            "A\u300b \u3002 \u201cB",
            "A\u201d\t\uff0c\t\u201cB",
            "A\uff09\uff09\uff0c\u201c\u201cB",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                issues = check_punctuation_issues(sample, section="description")
                self.assertEqual(issues, [])

    def test_invalid_clusters_still_report(self) -> None:
        repeated = check_punctuation_issues("A\uff0c\uff0cB", section="description")
        mixed = check_punctuation_issues("A\uff0c\uff1bB", section="description")
        wrappers_only = check_punctuation_issues("A\uff09\uff09B", section="description")
        wrapper_then_multi = check_punctuation_issues("A\uff09\u3002\u3002B", section="description")
        adjacent_quotes = check_punctuation_issues("\u201c\u7532\u201d\u201c\u4e59\u201d", section="description")

        self.assertTrue(any(row.rule_id == "punctuation.repeated" for row in repeated))
        self.assertTrue(any(row.rule_id == "punctuation.invalid_combo" for row in mixed))
        self.assertTrue(any(row.rule_id == "punctuation.repeated" for row in wrappers_only))
        self.assertTrue(any(row.rule_id == "punctuation.invalid_combo" for row in wrapper_then_multi))
        self.assertTrue(any(row.rule_id == "punctuation.invalid_combo" for row in adjacent_quotes))

    def test_newline_boundary_is_not_bridged(self) -> None:
        rows = check_punctuation_issues("A\uff09\n\u3002B", section="description")
        self.assertEqual(rows, [])

    def test_bridge_exemption_is_consistent_across_sections(self) -> None:
        claim_rows = check_punctuation_issues(
            "\u6743\u5229\u8981\u6c42\u4e2d\u201d\uff0c\u201c\u4e0a\u4e00\u90e8\u5206",
            section="claims",
            claim_num=1,
        )
        desc_rows = check_punctuation_issues(
            "\u8bf4\u660e\u4e66\u4e2d\uff09\uff0c\u201c\u4e0b\u4e00\u6bb5",
            section="description",
        )
        abstract_rows = check_punctuation_issues(
            "\u6458\u8981\u4e2d\u300b\u3002\u201c\u7ed3\u8bba",
            section="abstract",
        )
        self.assertEqual(claim_rows, [])
        self.assertEqual(desc_rows, [])
        self.assertEqual(abstract_rows, [])


if __name__ == "__main__":
    unittest.main()
