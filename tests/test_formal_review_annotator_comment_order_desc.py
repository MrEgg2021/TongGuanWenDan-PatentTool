import unittest

from core.formal_review.annotator import apply_comments_to_doc, build_comment_plan
from core.formal_review.models import Issue
from core.formal_review.text_projection import ParagraphProjection, ProjectionBundle, SectionProjection


class _FakeRange:
    def __init__(self, doc, start: int, end: int) -> None:
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = doc.text[self.Start : self.End]


class _FakeComments:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def Add(self, rng, _text):  # noqa: N802 - COM style
        self.calls.append((int(rng.Start), int(rng.End)))


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self.text = text
        self.Comments = _FakeComments()

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeRange(self, start, end)


class FormalReviewAnnotatorCommentOrderTests(unittest.TestCase):
    def test_comments_added_in_descending_start_order(self) -> None:
        text = "abcdef"
        issues = [
            Issue(
                rule_id="wordlist.description.forbidden",
                severity="high",
                category="forbidden",
                section="description",
                message="test1",
                span_start=0,
                span_end=1,
                anchor={"expected_hit": "a", "word_range_start": 0},
                issue_id="i-1",
                ignored=False,
            ),
            Issue(
                rule_id="wordlist.description.forbidden",
                severity="high",
                category="forbidden",
                section="description",
                message="test2",
                span_start=4,
                span_end=6,
                anchor={"expected_hit": "ef", "word_range_start": 0},
                issue_id="i-2",
                ignored=False,
            ),
        ]
        para = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=len(text),
            word_start=0,
            word_end=len(text),
            text=text,
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para])},
        )
        doc = _FakeDoc(text)
        plan = build_comment_plan(list(issues))
        stats = apply_comments_to_doc(doc, issues=list(issues), comment_plan=plan, projections=projections)

        self.assertEqual(int(stats.get("written", 0)), 2)
        self.assertEqual(doc.Comments.calls, [(4, 6), (0, 1)])


if __name__ == "__main__":
    unittest.main()

