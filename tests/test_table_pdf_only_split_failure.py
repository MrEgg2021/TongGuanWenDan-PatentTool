from __future__ import annotations

import unittest

from core.document_parser.table_ops.process_steps.split_flow import process_table_split_flow


class _FakeRows:
    Count = 2


class _FakeColumns:
    Count = 3


class _FakeRange:
    Start = 10
    End = 20


class _FakeTable:
    Rows = _FakeRows()
    Columns = _FakeColumns()
    Range = _FakeRange()


class _FakeParser:
    word = None

    def __init__(self) -> None:
        self.failure_contexts: list[dict] = []

    def _get_table_splitting_max_height_cm(self):
        return 24.0

    def _get_table_width_point(self, _table):
        return 321.0

    def _set_table_process_failure_context(self, **kwargs) -> None:
        self.failure_contexts.append(dict(kwargs))


class TablePdfOnlySplitFailureTests(unittest.TestCase):
    def test_split_failure_needs_no_legacy_screenshot_method(self) -> None:
        parser = _FakeParser()

        result = process_table_split_flow(parser, _FakeTable(), {}, "description")

        self.assertFalse(result)
        self.assertEqual("split.missing_word_engine", parser.failure_contexts[-1]["stage"])
        self.assertFalse(hasattr(parser, "_screenshot_table_range"))


if __name__ == "__main__":
    unittest.main()
