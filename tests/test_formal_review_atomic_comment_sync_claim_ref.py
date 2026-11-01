import unittest

from core.formal_review.annotator import TOOL_COMMENT_PREFIX
from core.formal_review.claim_refs import parse_claim_references
from core.formal_review.comment_sync import sync_comments_to_doc
from core.formal_review.models import Issue
from core.formal_review.text_projection import ParagraphProjection, ProjectionBundle, SectionProjection


class _FakeApp:
    def __init__(self) -> None:
        self.UserName = "orig"
        self.UserInitials = "OR"


class _FakeDocRange:
    def __init__(self, doc: "_FakeDoc", start: int, end: int) -> None:
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = doc.text[self.Start : self.End]


class _FakeCommentRange:
    def __init__(self, text: str) -> None:
        self.Text = str(text or "")


class _FakeComment:
    def __init__(self, text: str, owner: "_FakeComments") -> None:
        self.Range = _FakeCommentRange(text)
        self._owner = owner

    def Delete(self) -> None:
        self._owner._rows.remove(self)


class _FakeComments:
    def __init__(self) -> None:
        self._rows: list[_FakeComment] = []

    @property
    def Count(self) -> int:
        return len(self._rows)

    def __call__(self, idx: int) -> _FakeComment:
        return self._rows[int(idx) - 1]

    def Add(self, rng, text):  # noqa: N802 - COM style
        row = _FakeComment(str(text or ""), self)
        self._rows.append(row)
        return row


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self.Application = _FakeApp()
        self.FullName = r"D:\tmp\claim_ref_atomic.docx"
        self.text = text
        self.Comments = _FakeComments()
        self.saved = 0

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeDocRange(self, start, end)

    def Save(self) -> None:
        self.saved += 1


class FormalReviewAtomicCommentSyncClaimRefTests(unittest.TestCase):
    def test_claim_ref_issues_do_not_block_atomic_comment_sync(self) -> None:
        source = "根据权利要求2、4所述的完全装置。"
        parsed = parse_claim_references(source)
        span_start, span_end = parsed.ref_spans[4]

        claim_ref_issue = Issue(
            rule_id="claim.ref.missing_target",
            severity="error",
            category="rule",
            section="claims",
            claim_num=2,
            message="test",
            span_start=int(span_start),
            span_end=int(span_end),
            anchor={"expected_hit": source[span_start:span_end], "word_range_start": 0},
            issue_id="i-claim-ref",
        )

        term = "完全"
        term_start = source.index(term)
        wordlist_issue = Issue(
            rule_id="wordlist.claims.forbidden",
            severity="high",
            category="forbidden",
            section="claims",
            claim_num=2,
            message='权利要求书中不得出现禁用词："完全"',
            span_start=int(term_start),
            span_end=int(term_start + len(term)),
            snippet=term,
            anchor={"expected_hit": term, "word_range_start": 0},
            issue_id="i-wordlist",
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
        result = sync_comments_to_doc(
            doc,
            [claim_ref_issue, wordlist_issue],
            author_name="",
            clear_tool_comments=True,
            tool_prefix=TOOL_COMMENT_PREFIX,
            projections=projections,
        )

        self.assertEqual(result.failed_issue_count, 0)
        self.assertEqual(result.written, 2)
        self.assertEqual(doc.saved, 1)
        self.assertEqual(doc.Comments.Count, 2)


if __name__ == "__main__":
    unittest.main()

