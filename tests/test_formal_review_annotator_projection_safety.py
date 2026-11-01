import unittest

from core.formal_review.annotator import apply_comments_to_doc, build_comment_plan
from core.formal_review.models import Issue
from core.formal_review.text_projection import ParagraphProjection, ProjectionBundle, SectionProjection


class _FakeRange:
    def __init__(self, doc, start: int, end: int):
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = doc.text[self.Start : self.End]


class _FakeComments:
    def __init__(self):
        self.rows = []

    def Add(self, rng, text):  # noqa: N802 - COM style
        self.rows.append((int(rng.Start), int(rng.End), str(text or "")))


class _FakeDoc:
    def __init__(self, text: str):
        self.text = text
        self.Comments = _FakeComments()

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeRange(self, start, end)


class FormalReviewAnnotatorProjectionSafetyTests(unittest.TestCase):
    def test_no_anchor_fallback_when_projection_is_present(self) -> None:
        doc = _FakeDoc("abcde")
        issue = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=0,
            span_end=1,
            snippet="x",
            anchor={"expected_hit": "x", "word_range_start": 2},
            issue_id="i1",
            ignored=False,
        )
        para = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=5,
            word_start=0,
            word_end=5,
            text="abcde",
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para])},
        )

        plan = build_comment_plan([issue])
        stats = apply_comments_to_doc(
            doc,
            issues=[issue],
            comment_plan=plan,
            projections=projections,
        )

        self.assertEqual(stats["written"], 0)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(len(doc.Comments.rows), 0)


if __name__ == "__main__":
    unittest.main()
