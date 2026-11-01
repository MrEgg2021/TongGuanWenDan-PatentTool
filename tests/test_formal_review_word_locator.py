import unittest
from dataclasses import dataclass

from core.formal_review.text_projection import ParagraphProjection, ProjectionBundle, SectionProjection
from core.formal_review.word_locator import locate_issue_in_word


class _FakeRange:
    def __init__(self, doc, start: int, end: int):
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = doc.text[self.Start : self.End]

    def Select(self):  # noqa: N802 - COM style
        self._doc.selected = (self.Start, self.End)


class _FakeDoc:
    def __init__(self, text: str):
        self.text = text
        self.selected = None

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeRange(self, start, end)


@dataclass
class _FakeIssue:
    rule_id: str
    section: str
    claim_num: int | None
    span_start: int
    span_end: int
    snippet: str
    message: str
    anchor: dict


class _FakeSession:
    def __init__(self, doc):
        self.doc = doc


def _build_projection(text: str) -> ProjectionBundle:
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
    return ProjectionBundle(
        sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para])},
        claims={},
    )


class FormalReviewWordLocatorTests(unittest.TestCase):
    def test_anchor_locate_success(self) -> None:
        text = "gear connect mechanism"
        doc = _FakeDoc(text)
        issue = _FakeIssue(
            rule_id="wordlist.description.forbidden",
            section="description",
            claim_num=None,
            span_start=0,
            span_end=4,
            snippet="gear",
            message="",
            anchor={"expected_hit": "gear", "pre_context": "", "post_context": " connect"},
        )
        result = locate_issue_in_word(_FakeSession(doc), issue, projections=_build_projection(text))
        self.assertTrue(result.ok)
        self.assertEqual(result.level, "projection")
        self.assertIn("wordlist.description.forbidden", result.message)
        self.assertIn("[projection]", result.message)
        self.assertEqual(doc.selected, (0, 4))

    def test_context_fallback_for_repeated_term(self) -> None:
        text = "gear connect and connect"
        doc = _FakeDoc(text)
        issue = _FakeIssue(
            rule_id="wordlist.description.forbidden",
            section="description",
            claim_num=None,
            span_start=200,
            span_end=210,
            snippet="connect",
            message="",
            anchor={"expected_hit": "connect", "pre_context": " and ", "post_context": ""},
        )
        result = locate_issue_in_word(_FakeSession(doc), issue, projections=_build_projection(text))
        self.assertTrue(result.ok)
        self.assertEqual(result.level, "context")
        self.assertEqual(doc.selected, (17, 24))

    def test_fail_when_projection_missing(self) -> None:
        text = "gear connect mechanism"
        doc = _FakeDoc(text)
        issue = _FakeIssue(
            rule_id="wordlist.description.forbidden",
            section="description",
            claim_num=None,
            span_start=0,
            span_end=4,
            snippet="gear",
            message="",
            anchor={"expected_hit": "gear"},
        )
        result = locate_issue_in_word(_FakeSession(doc), issue, projections=None)
        self.assertFalse(result.ok)
        self.assertEqual(result.level, "fail")


if __name__ == "__main__":
    unittest.main()
