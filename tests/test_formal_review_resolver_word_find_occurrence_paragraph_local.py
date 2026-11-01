import unittest

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


class _FakeReplacement:
    def ClearFormatting(self) -> None:  # noqa: N802 - COM style
        return None


class _FakeFind:
    def __init__(self, rng) -> None:
        self._range = rng
        self.Text = ""
        self.Forward = True
        self.Wrap = 0
        self.Format = False
        self.MatchCase = False
        self.MatchWholeWord = False
        self.MatchWildcards = False
        self.MatchSoundsLike = False
        self.MatchAllWordForms = False
        self.Replacement = _FakeReplacement()

    def ClearFormatting(self) -> None:  # noqa: N802 - COM style
        return None

    def Execute(self, *args, **kwargs):  # noqa: N802 - COM style
        needle = str(self.Text or "")
        if not needle:
            return False
        source = str(self._range._doc.text or "")
        start = int(self._range.Start)
        end = int(self._range.End)
        idx = source.find(needle, start, end)
        if idx < 0:
            return False
        self._range.Start = int(idx)
        self._range.End = int(idx + len(needle))
        self._range.Text = source[self._range.Start : self._range.End]
        return True


class _FakeFindRange(_FakeRange):
    def __init__(self, doc, start: int, end: int) -> None:
        super().__init__(doc, start, end)
        self.Find = _FakeFind(self)


class _FakeDocWithFind(_FakeDoc):
    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeFindRange(self, start, end)


class FormalReviewResolverWordFindParagraphOccurrenceTests(unittest.TestCase):
    def test_word_find_uses_paragraph_local_occurrence(self) -> None:
        # Two paragraphs, same candidate appears across section. Span points to a later occurrence in paragraph 2.
        review_p1 = "foo AAA"
        review_p2 = "foo BBB foo"
        # Insert a hidden marker inside paragraph 2 so linear projection mapping mismatches and forces word_find.
        word_p1 = review_p1
        word_p2 = "foo BBB \x05foo"
        word_text = word_p1 + word_p2

        # Section-local offsets include an implicit newline between paragraphs.
        p1 = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=len(review_p1),
            word_start=0,
            word_end=len(word_p1),
            text=review_p1,
        )
        p2_local_start = len(review_p1) + 1
        p2 = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=2,
            local_start=p2_local_start,
            local_end=p2_local_start + len(review_p2),
            word_start=len(word_p1),
            word_end=len(word_p1) + len(word_p2),
            text=review_p2,
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[p1, p2])},
        )

        # Span anchors to the second "foo" in paragraph 2 (within section-local projection_text).
        second_foo_in_p2 = review_p2.rfind("foo")
        span_start = p2_local_start + int(second_foo_in_p2)
        span_end = span_start + 3
        issue = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=int(span_start),
            span_end=int(span_end),
            anchor={"expected_hit": "foo", "word_range_start": 0},
            issue_id="i-para-occ",
            ignored=False,
        )

        doc = _FakeDoc(word_text)
        resolved = resolve_issue_range(doc, issue, projections, strict=True, allow_legacy_fallback=True)
        self.assertTrue(resolved.ok)
        self.assertEqual(resolved.level, "word_find_legacy")
        # The second "foo" in paragraph 2 starts at absolute index 16 and ends at 19 in word_text.
        self.assertEqual(int(-1 if resolved.start is None else resolved.start), 16)
        self.assertEqual(int(-1 if resolved.end is None else resolved.end), 19)

    def test_com_find_uses_paragraph_local_occurrence(self) -> None:
        review_p1 = "foo AAA"
        review_p2 = "foo BBB foo"
        word_p1 = review_p1
        word_p2 = "foo BBB \x05foo"
        word_text = word_p1 + word_p2

        p1 = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=len(review_p1),
            word_start=0,
            word_end=len(word_p1),
            text=review_p1,
        )
        p2_local_start = len(review_p1) + 1
        p2 = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=2,
            local_start=p2_local_start,
            local_end=p2_local_start + len(review_p2),
            word_start=len(word_p1),
            word_end=len(word_p1) + len(word_p2),
            text=review_p2,
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[p1, p2])},
        )

        second_foo_in_p2 = review_p2.rfind("foo")
        span_start = p2_local_start + int(second_foo_in_p2)
        span_end = span_start + 3
        issue = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=int(span_start),
            span_end=int(span_end),
            anchor={"expected_hit": "foo", "word_range_start": 0},
            issue_id="i-para-occ-com",
            ignored=False,
        )

        doc = _FakeDocWithFind(word_text)
        resolved = resolve_issue_range(doc, issue, projections, strict=True)
        self.assertTrue(resolved.ok)
        self.assertEqual(resolved.level, "word_find_com")
        self.assertEqual(int(-1 if resolved.start is None else resolved.start), 16)
        self.assertEqual(int(-1 if resolved.end is None else resolved.end), 19)


if __name__ == "__main__":
    unittest.main()
