import unittest

from core.formal_review.extractor import extract_formal_review_document_from_doc
from core.formal_review.rules import check_punctuation_issues


class _FakeCollection:
    def __init__(self, items):
        self._items = list(items or [])
        self.Count = len(self._items)

    def __call__(self, idx):
        return self._items[int(idx) - 1]


class _FakeHeaderRange:
    def __init__(self, text: str):
        self.Text = str(text or "")


class _FakeHeader:
    def __init__(self, text: str):
        self.Range = _FakeHeaderRange(text)


class _FakeRange:
    def __init__(self, start: int, text: str):
        self.Start = int(start)
        self.Text = str(text or "")
        self.End = int(self.Start + len(self.Text))


class _FakeInlineItem:
    def __init__(self, start: int, end: int):
        self.Range = _FakeRange(int(start), "X" * max(0, int(end) - int(start)))


class _FakeParagraphRange(_FakeRange):
    def __init__(
        self,
        start: int,
        text: str,
        *,
        inline_ranges: list[tuple[int, int]] | None = None,
        omath_ranges: list[tuple[int, int]] | None = None,
    ):
        super().__init__(start, text)
        self.InlineShapes = _FakeCollection([_FakeInlineItem(s, e) for s, e in list(inline_ranges or [])])
        self.OMaths = _FakeCollection([_FakeInlineItem(s, e) for s, e in list(omath_ranges or [])])


class _FakeParagraph:
    def __init__(
        self,
        start: int,
        text: str,
        *,
        inline_ranges: list[tuple[int, int]] | None = None,
        omath_ranges: list[tuple[int, int]] | None = None,
    ):
        self.Range = _FakeParagraphRange(
            int(start),
            str(text or ""),
            inline_ranges=list(inline_ranges or []),
            omath_ranges=list(omath_ranges or []),
        )


class _FakeHeaders:
    def __init__(self, primary_text: str):
        self._primary_text = str(primary_text or "")

    def __call__(self, idx):
        if int(idx) == 1:
            return _FakeHeader(self._primary_text)
        return _FakeHeader("")


class _FakeSection:
    def __init__(self, start: int, end: int, header_text: str):
        self.Range = _FakeRange(int(start), "X" * max(0, int(end) - int(start)))
        self.Headers = _FakeHeaders(str(header_text or ""))


class _FakeDoc:
    def __init__(self, paragraphs, *, header_text: str = "说明书", section_specs=None):
        paragraph_rows = list(paragraphs or [])
        self.Paragraphs = _FakeCollection(paragraph_rows)
        if section_specs is not None:
            self.Sections = _FakeCollection(
                [_FakeSection(start, end, text) for start, end, text in list(section_specs or [])]
            )
        elif paragraph_rows:
            sec_start = int(paragraph_rows[0].Range.Start)
            sec_end = int(paragraph_rows[-1].Range.End + 10)
            self.Sections = _FakeCollection([_FakeSection(sec_start, sec_end, header_text)])
        else:
            sec_start = 0
            sec_end = 1
            self.Sections = _FakeCollection([_FakeSection(sec_start, sec_end, header_text)])


class FormalReviewExtractorNonTextFilterTests(unittest.TestCase):
    def test_omath_content_removed_and_breakpoint_inserted(self) -> None:
        start = 100
        text = "A：x/y，B\r"
        # x/y -> [start+2, start+5)
        paragraph = _FakeParagraph(start, text, omath_ranges=[(start + 2, start + 5)])
        doc = _FakeDoc([paragraph], header_text="说明书")

        document, _anchors, editable_segments, projections = extract_formal_review_document_from_doc(doc)
        self.assertEqual(document.description, "A：\n，B")

        segment = [row for row in editable_segments if str(getattr(row, "section", "")) == "description"][0]
        self.assertTrue(bool(getattr(segment, "has_non_text", False)))
        self.assertGreaterEqual(len(list(getattr(segment, "token_spans", []) or [])), 1)

        row = projections.sections["description"].paragraphs[0]
        self.assertEqual(len(row.text), len(row.offset_map_start))
        self.assertEqual(len(row.text), len(row.offset_map_end))
        newline_index = row.text.index("\n")
        self.assertEqual(int(row.offset_map_start[newline_index]), start + 5)
        self.assertEqual(int(row.offset_map_end[newline_index]), start + 5)

    def test_inline_shape_content_removed_and_breakpoint_inserted(self) -> None:
        start = 200
        text = "甲：P，乙\r"
        paragraph = _FakeParagraph(start, text, inline_ranges=[(start + 2, start + 3)])
        doc = _FakeDoc([paragraph], header_text="说明书")

        document, _anchors, _editable_segments, _projections = extract_formal_review_document_from_doc(doc)
        self.assertEqual(document.description, "甲：\n，乙")

    def test_formula_like_text_no_longer_triggers_invalid_combo_after_filter(self) -> None:
        start = 300
        text = "序列：x/y，后续\r"
        paragraph = _FakeParagraph(start, text, omath_ranges=[(start + 3, start + 6)])
        doc = _FakeDoc([paragraph], header_text="说明书")

        document, _anchors, _editable_segments, _projections = extract_formal_review_document_from_doc(doc)
        issues = check_punctuation_issues(document.description, section="description")
        self.assertFalse(any(str(getattr(item, "rule_id", "")) == "punctuation.invalid_combo" for item in issues))

    def test_request_meta_section_is_not_extracted_into_formal_review_text(self) -> None:
        paragraphs = [
            _FakeParagraph(100, "申请信息确认页\r"),
            _FakeParagraph(130, "专利名称：一种装置\r"),
            _FakeParagraph(220, "一种装置\r"),
            _FakeParagraph(240, "技术领域\r"),
            _FakeParagraph(260, "本申请涉及装置。\r"),
        ]
        doc = _FakeDoc(
            paragraphs,
            section_specs=[
                (100, 200, "申请信息确认页"),
                (220, 320, "说明书"),
            ],
        )

        document, _anchors, _editable_segments, _projections = extract_formal_review_document_from_doc(doc)

        self.assertNotIn("申请信息确认页", document.description)
        self.assertNotIn("专利名称", document.description)
        self.assertIn("一种装置", document.description)


if __name__ == "__main__":
    unittest.main()

