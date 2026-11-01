import unittest

from core.formal_review.matcher import match_terms


class FormalReviewWordlistMatcherTests(unittest.TestCase):
    def test_longest_match_wins(self) -> None:
        result = match_terms(
            "abcd abc",
            ["abc", "abcd"],
            category="forbidden",
            severity="high",
            section="description",
        )
        terms = [item["term"] for item in result["occurrences"]]
        self.assertEqual(terms, ["abcd", "abc"])

    def test_case_insensitive_for_ascii(self) -> None:
        result = match_terms(
            "MaxValue maxvalue MAXVALUE",
            ["maxvalue"],
            category="sensitive",
            severity="medium",
            section="claims",
            claim_num=1,
        )
        self.assertEqual(len(result["occurrences"]), 3)
        summary = result["summary"][0]
        self.assertEqual(summary["term"], "maxvalue")
        self.assertEqual(summary["count"], 3)


if __name__ == "__main__":
    unittest.main()
