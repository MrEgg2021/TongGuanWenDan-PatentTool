import unittest

from core.formal_review.models import FormalReviewDocument
from core.formal_review.semantic_rules import check_drawings_duplicate_figure_issues


class FormalReviewDrawingsDuplicateFigureRefsTests(unittest.TestCase):
    def test_reports_second_occurrence_as_duplicate(self) -> None:
        doc = FormalReviewDocument(
            drawings="\u56fe1\n\u56fe2\n\u56fe1\n",
        )
        issues = check_drawings_duplicate_figure_issues(doc)
        self.assertEqual(1, len(issues))
        issue = issues[0]
        self.assertEqual("drawings.figure.ref.duplicate_in_drawings_section", issue.rule_id)
        self.assertEqual("error", issue.severity)
        self.assertEqual("drawings", issue.section)
        self.assertEqual("\u56fe1", str(issue.snippet or ""))
        self.assertIn("\u7b2c2\u6b21\u51fa\u73b0", str(issue.message or ""))
        span_text = str(doc.drawings[int(issue.span_start) : int(issue.span_end)] or "")
        self.assertEqual("\u56fe1", span_text)
        anchor = dict(getattr(issue, "anchor", {}) or {})
        self.assertEqual("\u56fe1", str(anchor.get("expected_hit", "") or ""))
        candidates = list(anchor.get("expected_hit_candidates", []) or [])
        self.assertTrue(candidates)
        self.assertEqual("\u56fe1", str(candidates[0] or ""))

    def test_reports_each_duplicate_occurrence(self) -> None:
        doc = FormalReviewDocument(
            drawings="\u56fe1\n\u56fe1\n\u56fe1\n",
        )
        issues = check_drawings_duplicate_figure_issues(doc)
        self.assertEqual(2, len(issues))
        messages = [str(issue.message or "") for issue in issues]
        self.assertTrue(any("\u7b2c2\u6b21\u51fa\u73b0" in message for message in messages))
        self.assertTrue(any("\u7b2c3\u6b21\u51fa\u73b0" in message for message in messages))

    def test_does_not_treat_different_suffixes_as_duplicate(self) -> None:
        doc = FormalReviewDocument(
            drawings="\u56fe1A\n\u56fe1B\n",
        )
        self.assertEqual([], check_drawings_duplicate_figure_issues(doc))

    def test_keeps_suffix_case_sensitive_for_duplicate_key(self) -> None:
        doc = FormalReviewDocument(
            drawings="\u56fe1A\n\u56fe1a\n",
        )
        self.assertEqual([], check_drawings_duplicate_figure_issues(doc))

    def test_ignores_non_leading_figure_mentions(self) -> None:
        doc = FormalReviewDocument(
            drawings="\u53c2\u89c1\u56fe1\n\u56fe1\n\u56fe2\n",
        )
        self.assertEqual([], check_drawings_duplicate_figure_issues(doc))

    def test_scope_is_drawings_only(self) -> None:
        doc = FormalReviewDocument(
            description="\u9644\u56fe\u8bf4\u660e\n\u56fe1\n\u56fe1\n",
            drawings="\u56fe1\n\u56fe2\n",
        )
        self.assertEqual([], check_drawings_duplicate_figure_issues(doc))


if __name__ == "__main__":
    unittest.main()
