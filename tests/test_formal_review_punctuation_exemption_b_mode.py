import unittest

from core.formal_review.rules import check_punctuation_issues


class FormalReviewPunctuationExemptionBModeTests(unittest.TestCase):
    def test_close_wrapper_plus_single_punct_is_exempt(self) -> None:
        samples = [
            "A）。B",
            "A））。B",
            "A”。B",
            "A””。B",
            "A》》。B",
            "A）   。B",
            "A”\t。B",
            "A] .B",
            "A'' .B",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                issues = check_punctuation_issues(sample, section="description")
                self.assertEqual(issues, [])

    def test_normal_repeated_or_invalid_clusters_still_report(self) -> None:
        repeated = check_punctuation_issues("A，，B", section="description")
        invalid = check_punctuation_issues("A，；B", section="description")
        wrappers_only = check_punctuation_issues("A））B", section="description")
        wrapper_then_multi = check_punctuation_issues("A）。。B", section="description")

        self.assertTrue(any(row.rule_id == "punctuation.repeated" for row in repeated))
        self.assertTrue(any(row.rule_id == "punctuation.invalid_combo" for row in invalid))
        self.assertTrue(any(row.rule_id == "punctuation.repeated" for row in wrappers_only))
        self.assertTrue(any(row.rule_id == "punctuation.invalid_combo" for row in wrapper_then_multi))

    def test_newline_boundary_is_not_inline_exemption(self) -> None:
        no_cluster = check_punctuation_issues("A）\n。B", section="description")
        self.assertEqual(no_cluster, [])

        second_line_cluster = check_punctuation_issues("A）\n。！B", section="description")
        self.assertTrue(any(row.rule_id == "punctuation.invalid_combo" for row in second_line_cluster))

    def test_exemption_is_consistent_across_sections(self) -> None:
        claim_rows = check_punctuation_issues("所述部件）。连接", section="claims", claim_num=1)
        desc_rows = check_punctuation_issues("描述中”。用于收尾。", section="description")
        abstract_rows = check_punctuation_issues("摘要》》。", section="abstract")
        self.assertEqual(claim_rows, [])
        self.assertEqual(desc_rows, [])
        self.assertEqual(abstract_rows, [])


if __name__ == "__main__":
    unittest.main()
