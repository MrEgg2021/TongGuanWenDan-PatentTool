from __future__ import annotations

import unittest

from core.document_parser.table_ops.process_ops import process_table
from core.document_parser.table_ops.process_steps.types import TableCaptureResult, TablePdfFragment


class _FakeRows:
    Count = 0


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
    description_paragraph_split_mode = 'word'

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.config = {
            'table_capture': {
                'pipeline': 'pdf_first',
            }
        }

    def _get_table_width_point(self, table):
        _ = table
        self.calls.append(('get_width',))
        return 321.0

    def _capture_table_pdf_first_result(self, table_range, *, current_section_key, width_point):
        self.calls.append(('capture_pdf_first', table_range.Start, table_range.End, str(current_section_key), float(width_point)))
        return TableCaptureResult(
            fragments=[TablePdfFragment('mock_table_p1.png', 1, 1200, 800, 113.25, 75.5, 'selection')],
            used_blank_doc_fallback=False,
            hard_table=False,
            failure_code=None,
        )

    def _emit_fragments(self, fragments, parent_node, section, table_obj):
        self.calls.append(('emit_fragments', list(fragments), parent_node, str(section), table_obj))
        return {
            'section': str(section),
            'fragments': list(fragments),
        }


class TableProcessOpsSnapshotTests(unittest.TestCase):
    def test_pdf_first_snapshot_path(self) -> None:
        parser = _FakeParser()
        result = process_table(parser, _FakeTable(), parent_node={}, current_section_key='claims')

        self.assertEqual(
            result,
            {
                'section': 'claims',
                'fragments': [('mock_table_p1.png', 113.25, 75.5)],
            },
        )
        self.assertEqual(parser.calls[0], ('get_width',))
        self.assertEqual(parser.calls[1], ('capture_pdf_first', 10, 20, 'claims', 321.0))
        self.assertEqual(parser.calls[2][0], 'emit_fragments')
        self.assertEqual(parser.calls[2][1], [('mock_table_p1.png', 113.25, 75.5)])
        self.assertEqual(parser.calls[2][2], {})
        self.assertEqual(parser.calls[2][3], 'claims')


if __name__ == '__main__':
    unittest.main()