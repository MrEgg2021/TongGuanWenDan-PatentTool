from __future__ import annotations

import unittest

from core.document_parser.paragraph_mixin_impl import ParagraphTraversalMixin


class _CountHolder:
    def __init__(self, count: int) -> None:
        self.Count = int(count)


class _FakeTableRange:
    def __init__(self, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)


class _FakeTable:
    def __init__(self, *, start: int = 10, end: int = 20, rows: int = 2, cols: int = 2) -> None:
        self.Range = _FakeTableRange(start=start, end=end)
        self.Rows = _CountHolder(rows)
        self.Columns = _CountHolder(cols)


class _FakeTablesAccessor:
    def __init__(self, *, count: int, table: _FakeTable | None = None, error: Exception | None = None) -> None:
        self.Count = int(count)
        self._table = table
        self._error = error

    def __call__(self, idx: int):
        _ = idx
        if self._error is not None:
            raise self._error
        return self._table


class _FakeRange:
    def __init__(self, *, text: str, in_table: bool, tables: _FakeTablesAccessor, start: int = 100) -> None:
        self.Text = text
        self.Tables = tables
        self.ShapeRange = _CountHolder(0)
        self.InlineShapes = _CountHolder(0)
        self.Start = int(start)
        self.End = int(start + len(text))
        self._in_table = bool(in_table)

    def Information(self, _code: int) -> bool:
        return self._in_table


class _FakeParagraph:
    def __init__(self, rng: _FakeRange) -> None:
        self.Range = rng


class _FakeParagraphs(list):
    def __init__(self, paragraphs: list[_FakeParagraph]) -> None:
        super().__init__(paragraphs)
        self.Count = len(paragraphs)


class _FakeDoc:
    def __init__(self, paragraphs: list[_FakeParagraph]) -> None:
        self.Paragraphs = _FakeParagraphs(paragraphs)


class _FakeWord:
    def __init__(self, paragraphs: list[_FakeParagraph]) -> None:
        self.doc = _FakeDoc(paragraphs)
        self.opened_path: str | None = None

    def open_doc(self, path: str) -> None:
        self.opened_path = path


class _FakeXml:
    def __init__(self) -> None:
        self.paragraphs: list[tuple[object, str, bool]] = []

    def create_paragraph(self, parent, text=None, num=None, is_claim=False):
        _ = num
        node = {"parent": parent, "text": text, "is_claim": bool(is_claim), "num": "0001"}
        self.paragraphs.append((parent, str(text or ""), bool(is_claim)))
        return node


class _FakeParser(ParagraphTraversalMixin):
    description_paragraph_split_mode = "word"

    def __init__(
        self,
        *,
        paragraphs: list[_FakeParagraph],
        process_table_error: Exception | None = None,
        process_table_result: bool = False,
        process_failure_context: dict | None = None,
        section_key: str = "claims",
    ) -> None:
        self.word = _FakeWord(paragraphs)
        self.sections = {"claims": {"name": "claims"}, "description": {"name": "description"}}
        self.processed_tables = set()
        self._table_capture_success = {}
        self._table_placeholder_inserted = set()
        self._table_process_failure_context = process_failure_context
        self._process_table_error = process_table_error
        self._process_table_result = bool(process_table_result)
        self._process_failure_context = dict(process_failure_context or {})
        self._section_key = str(section_key)
        self.processed_paragraph_texts: list[str] = []
        self.claim_placeholder_texts: list[str] = []
        self.flush_called = False
        self.xml = _FakeXml()

    def _build_section_plan_from_headers(self, _doc):
        return {}

    def _get_section_key_for_paragraph(self, _para, _section_plan):
        return self._section_key

    def _detect_logical_section(self, _current_section_key, _text):
        return None

    def _sanitize_text(self, text: str) -> str:
        return text

    def _process_floating_shapes(self, _para, _parent_node, _current_section_key) -> bool:
        return False

    def process_paragraph_content(self, para, _parent_node, is_claim=False, section_key=None) -> None:
        _ = is_claim, section_key
        self.processed_paragraph_texts.append(str(para.Range.Text))

    def process_table(self, _table, _parent_node, _current_section_key):
        if self._process_table_error is not None:
            raise self._process_table_error
        return self._process_table_result

    def _consume_table_process_failure_context(self):
        ctx = dict(self._process_failure_context or {})
        self._process_failure_context = {}
        return ctx or None

    def _flush_pending_claim(self, _claims_root, force=False) -> None:
        _ = force
        self.flush_called = True

    def _append_claim_segments(self, _parent_node, segments, is_new_start=False, claim_num=None):
        _ = is_new_start, claim_num
        self.claim_placeholder_texts.extend(
            str(seg.get("text") or "")
            for seg in list(segments or [])
            if seg.get("kind") == "text"
        )

    def generate_output_files(self, case_id=None):
        return {"ok": True, "case_id": case_id}


class TableExceptionFallbackTests(unittest.TestCase):
    def test_tables_accessor_com_exception_does_not_abort_conversion(self) -> None:
        failing_para = _FakeParagraph(
            _FakeRange(
                text="table paragraph",
                in_table=True,
                tables=_FakeTablesAccessor(count=1, error=RuntimeError("com object disconnected")),
                start=10,
            )
        )
        normal_para = _FakeParagraph(
            _FakeRange(
                text="normal paragraph",
                in_table=False,
                tables=_FakeTablesAccessor(count=0),
                start=30,
            )
        )
        parser = _FakeParser(paragraphs=[failing_para, normal_para], process_table_result=True)

        result = parser.run("dummy.docx")

        self.assertTrue(result["ok"])
        self.assertEqual(parser.processed_paragraph_texts, ["normal paragraph"])
        self.assertEqual(len(parser.table_screenshot_failures), 1)
        failure = parser.table_screenshot_failures[0]
        self.assertEqual(failure.get("stage"), "get_table")
        self.assertEqual(failure.get("error_code"), "TABLE_COM_ERROR")

    def test_process_table_exception_records_failure_and_inserts_claim_placeholder(self) -> None:
        table_para = _FakeParagraph(
            _FakeRange(
                text="table text fallback",
                in_table=True,
                tables=_FakeTablesAccessor(count=1, table=_FakeTable(start=100, end=150)),
                start=100,
            )
        )
        parser = _FakeParser(
            paragraphs=[table_para],
            process_table_error=RuntimeError("table export failed"),
        )

        result = parser.run("dummy.docx")

        self.assertTrue(result["ok"])
        self.assertEqual(parser.processed_paragraph_texts, [])
        self.assertEqual(parser.claim_placeholder_texts, ["表格截图失败，未写入 XML，请人工核对原文。"])
        self.assertEqual(len(parser.table_screenshot_failures), 1)
        failure = parser.table_screenshot_failures[0]
        self.assertEqual(failure.get("stage"), "process_table")
        self.assertEqual(failure.get("error_code"), "TABLE_COM_ERROR")
        self.assertIn("table export failed", failure.get("error_message", ""))
        self.assertEqual(failure.get("resolution_code"), "placeholder_inserted")

    def test_failed_description_table_inserts_single_placeholder_and_keeps_failure_context(self) -> None:
        table = _FakeTable(start=100, end=150)
        paras = [
            _FakeParagraph(
                _FakeRange(
                    text="table row 1",
                    in_table=True,
                    tables=_FakeTablesAccessor(count=1, table=table),
                    start=100,
                )
            ),
            _FakeParagraph(
                _FakeRange(
                    text="table row 2",
                    in_table=True,
                    tables=_FakeTablesAccessor(count=1, table=table),
                    start=110,
                )
            ),
        ]
        parser = _FakeParser(
            paragraphs=paras,
            process_table_result=False,
            process_failure_context={
                "error_code": "fragment_measured_over_limit",
                "stage": "split.backoff_exhausted",
                "error_message": "all candidate fragments exceeded max height",
                "height_mm": 240.8,
                "safe_row": 31,
            },
            section_key="description",
        )

        result = parser.run("dummy.docx")

        self.assertTrue(result["ok"])
        self.assertEqual(parser.processed_paragraph_texts, [])
        self.assertEqual(
            parser.xml.paragraphs,
            [({"name": "description"}, "表格截图失败，未写入 XML，请人工核对原文。", False)],
        )
        self.assertEqual(len(parser.table_screenshot_failures), 1)
        failure = parser.table_screenshot_failures[0]
        self.assertEqual(failure.get("error_code"), "fragment_measured_over_limit")
        self.assertEqual(failure.get("stage"), "split.backoff_exhausted")
        self.assertEqual(failure.get("resolution_code"), "placeholder_inserted")
        self.assertEqual(failure.get("safe_row"), 31)
        self.assertEqual(failure.get("height_mm"), 240.8)


if __name__ == "__main__":
    unittest.main()
