import unittest

from core.formal_review.claim_refs import parse_claim_references
from core.formal_review.models import Issue
from core.formal_review.range_resolver import resolve_issue_range
from core.formal_review.text_projection import ParagraphProjection, ProjectionBundle, SectionProjection


class _FakeRange:
    def __init__(self, doc, start: int, end: int) -> None:
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = doc.text[self.Start : self.End]


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self.text = text

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeRange(self, start, end)


class FormalReviewClaimRefLocatableTests(unittest.TestCase):
    def test_claim_ref_issue_resolves_via_projection(self) -> None:
        source = "根据权利要求2、4所述的装置。"
        parsed = parse_claim_references(source)
        span_start, span_end = parsed.ref_spans[4]

        issue = Issue(
            rule_id="claim.ref.missing_target",
            severity="error",
            category="rule",
            section="claims",
            claim_num=2,
            message="test",
            span_start=int(span_start),
            span_end=int(span_end),
            anchor={"expected_hit": source[span_start:span_end], "word_range_start": 0},
            issue_id="i-1",
            ignored=False,
        )

        para = ParagraphProjection(
            section="claims",
            claim_num=2,
            paragraph_index=1,
            local_start=0,
            local_end=len(source),
            word_start=0,
            word_end=len(source),
            text=source,
        )
        projections = ProjectionBundle(
            claims={2: SectionProjection(section="claims", claim_num=2, paragraphs=[para])},
            sections={},
        )

        doc = _FakeDoc(source)
        resolved = resolve_issue_range(doc, issue, projections, strict=True)
        self.assertTrue(resolved.ok)
        self.assertEqual(int(resolved.start or -1), int(span_start))
        self.assertEqual(int(resolved.end or -1), int(span_end))


if __name__ == "__main__":
    unittest.main()

