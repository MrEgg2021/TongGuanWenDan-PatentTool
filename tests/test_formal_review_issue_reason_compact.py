import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewIssueReasonCompactTests(unittest.TestCase):
    def test_reason_compact_covers_primary_rule_types(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _issue_reason_compact(issue: Issue) -> str:", text)
        for token in [
            "wordlist.claims.forbidden",
            "wordlist.description.forbidden",
            "wordlist.claims.sensitive",
            "wordlist.description.sensitive",
            "punctuation.repeated",
            "punctuation.invalid_combo",
            "text.repeated_word",
            "drawings.figure.ref.missing_in_impl",
            "drawings.figure.ref.duplicate_in_drawings_section",
            "description.drawings.figure.ref.missing_in_drawings_section",
            "drawings.figure.ref.missing_in_description_drawings",
            "description.impl_heading.missing_for_figure_check",
            "description.heading.missing.required",
            "description.title.missing",
            "description.title.length.exceeded",
            "theme.claim1.multi_subject",
            "theme.title_claim1.mismatch",
            "theme.title_abstract.mismatch",
            "theme.title.unrecognized",
            "claim.ref.self",
            "claim.ref.future",
            "claim.ref.missing_target",
            "claim.ref.choice_word_missing",
            "claim.ref.marker_basis.missing",
            "claim.ref.term_basis.missing",
            "claim.ref.multi_to_multi.recursive",
            "claim1.word_count.exceeded",
            "claim1.marker_count.exceeded",
            "claim.punctuation.period.extra",
            "claim.punctuation.period.tail_missing",
            "abstract.word_count.exceeded",
        ]:
            self.assertIn(token, text)
        self.assertIn('child.setToolTip(2, str(issue.message or ""))', text)
        self.assertIn("_CROSS_SECTION_REASON_PREFIX", text)
        self.assertIn('"description.drawings.figure.ref.missing_in_drawings_section": "\\u8bf4\\u660e\\u4e66\\u9644\\u56fe\\u7f3a\\u5c11\\u56fe\\u53f7"', text)
        self.assertIn('"drawings.figure.ref.missing_in_description_drawings": "\\u9644\\u56fe\\u8bf4\\u660e\\u7f3a\\u5c11\\u56fe\\u53f7"', text)
        self.assertIn("if rid in _CROSS_SECTION_REASON_PREFIX:", text)
        self.assertIn("\\u9644\\u56fe\\u56fe\\u53f7\\u91cd\\u590d", text)


if __name__ == "__main__":
    unittest.main()
