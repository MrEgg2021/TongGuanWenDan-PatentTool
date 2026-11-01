import unittest

from core.formal_review.text_projection import ParagraphProjection, ProjectionBundle, SectionProjection
from core.formal_review.word_locator import locate_issue_in_word


class _FakeSelectionRange:
    def __init__(self) -> None:
        self.scrolled = False

    def ScrollIntoView(self):  # noqa: N802
        self.scrolled = True


class _FakeSelection:
    def __init__(self) -> None:
        self.Range = _FakeSelectionRange()

    def SetRange(self, _start, _end):  # noqa: N802
        return None


class _FakeApp:
    def __init__(self) -> None:
        self.Selection = _FakeSelection()


class _FakeRange:
    def __init__(self, doc, start: int, end: int):
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = doc.text[self.Start : self.End]
        self.Application = doc.Application

    def Select(self):  # noqa: N802
        self._doc.selected = (self.Start, self.End)


class _FakeDoc:
    def __init__(self, text: str):
        self.text = text
        self.selected = None
        self.Application = _FakeApp()

    def Range(self, start: int, end: int):  # noqa: N802
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeRange(self, start, end)


class _FakeSession:
    def __init__(self, doc):
        self.doc = doc
        self.word_hwnd = None


class _FakeIssue:
    def __init__(self, *, section: str, span_start: int, span_end: int, snippet: str, anchor: dict):
        self.section = section
        self.claim_num = None
        self.span_start = span_start
        self.span_end = span_end
        self.snippet = snippet
        self.message = ""
        self.anchor = anchor


class FormalReviewLocatorScrollAndReasonTests(unittest.TestCase):
    def test_locate_success_scrolls_into_view(self) -> None:
        text = "gear connect mechanism"
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
        issue = _FakeIssue(section="description", span_start=5, span_end=12, snippet="connect", anchor={"expected_hit": "connect"})
        doc = _FakeDoc(text)
        result = locate_issue_in_word(_FakeSession(doc), issue, projections=projections)
        self.assertTrue(result.ok)
        self.assertEqual(doc.selected, (5, 12))
        self.assertTrue(doc.Application.Selection.Range.scrolled)

    def test_locate_failure_exposes_reason_code(self) -> None:
        issue = _FakeIssue(section="description", span_start=0, span_end=4, snippet="gear", anchor={"expected_hit": "gear"})
        doc = _FakeDoc("gear")
        result = locate_issue_in_word(_FakeSession(doc), issue, projections=None)
        self.assertFalse(result.ok)
        self.assertIn("projection_missing", result.message)


if __name__ == "__main__":
    unittest.main()

