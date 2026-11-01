import unittest

from core.formal_review.claim_refs import check_claim_reference_issues, parse_claim_references


class FormalReviewClaimRefParserTests(unittest.TestCase):
    def test_parse_refs_and_choice_word(self) -> None:
        source = "根据权利要求1至3任一项所述的装置。"
        parsed = parse_claim_references(source)
        self.assertEqual(parsed.refs, [1, 2, 3])
        self.assertTrue(parsed.has_choice_word)
        for ref in parsed.refs:
            self.assertIn(ref, parsed.ref_spans)
            span = parsed.ref_spans[ref]
            self.assertGreater(span[1], span[0])
            self.assertTrue(source[span[0] : span[1]].startswith("权利要求"))

    def test_detects_reference_issues(self) -> None:
        source = "根据权利要求2、4所述的装置。"
        parsed = parse_claim_references(source)
        issues = check_claim_reference_issues(
            claim_num=2,
            refs=parsed.refs,
            has_choice_word=parsed.has_choice_word,
            max_claim_num=3,
            source_text=source,
            ref_spans=parsed.ref_spans,
        )
        rule_ids = {issue.rule_id for issue in issues}
        self.assertIn("claim.ref.self", rule_ids)
        self.assertIn("claim.ref.missing_target", rule_ids)
        self.assertIn("claim.ref.choice_word_missing", rule_ids)
        for issue in issues:
            self.assertIsNotNone(issue.span_start)
            self.assertIsNotNone(issue.span_end)
            self.assertGreater(int(issue.span_end or 0), int(issue.span_start or 0))


if __name__ == "__main__":
    unittest.main()
