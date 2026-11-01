from __future__ import annotations

import unittest

from core.document_parser.table_ops.process_steps.short_probe import try_short_table_direct_path
from core.document_parser.table_ops.process_steps.types import TableCaptureResult, TablePdfFragment, TableProcessContext


class _FakeRange:
    Start = 10
    End = 20


class _FakeTable:
    Range = _FakeRange()


class _FakeOwner:
    def __init__(self, capture_result: TableCaptureResult | None, *, emit_result=True) -> None:
        self.capture_result = capture_result
        self.emit_result = emit_result
        self.calls: list[tuple] = []
        self.failure_contexts: list[dict] = []
        self.config = {'table_capture': {'pipeline': 'obsolete-value-must-be-ignored'}}

    def _get_table_width_point(self, _table):
        self.calls.append(('get_width',))
        return 321.0

    def _capture_table_pdf_first_result(self, rng, *, current_section_key, width_point):
        self.calls.append(('capture', rng.Start, rng.End, str(current_section_key), float(width_point)))
        return self.capture_result

    def _emit_fragments(self, fragments, parent_node, section, table_obj):
        self.calls.append(('emit_fragments', list(fragments), parent_node, str(section), table_obj))
        return bool(self.emit_result)

    def _set_table_process_failure_context(self, **kwargs):
        self.failure_contexts.append(dict(kwargs))


class TablePdfFirstRouteTests(unittest.TestCase):
    def test_try_short_table_direct_path_emits_pdf_fragments_when_capture_succeeds(self) -> None:
        owner = _FakeOwner(
            TableCaptureResult(
                fragments=[
                    TablePdfFragment('tbl_p1.jpg', 1, 1000, 1200, 113.25, 135.90, 'selection'),
                    TablePdfFragment('tbl_p2.jpg', 2, 1000, 900, 113.25, 101.93, 'selection'),
                ],
                used_blank_doc_fallback=False,
                hard_table=True,
                failure_code=None,
            )
        )
        ctx = TableProcessContext(owner=owner, table=_FakeTable(), parent_node={'k': 'v'}, current_section_key='description')

        out = try_short_table_direct_path(ctx)

        self.assertTrue(out)
        self.assertEqual(owner.calls[0], ('get_width',))
        self.assertEqual(owner.calls[1], ('capture', 10, 20, 'description', 321.0))
        self.assertEqual(
            owner.calls[2][1],
            [('tbl_p1.jpg', 113.25, 135.9), ('tbl_p2.jpg', 113.25, 101.93)],
        )
        self.assertEqual(owner.failure_contexts, [])

    def test_try_short_table_direct_path_returns_none_for_overlimit_pdf_fragment_failure(self) -> None:
        owner = _FakeOwner(
            TableCaptureResult(
                fragments=[],
                used_blank_doc_fallback=False,
                hard_table=True,
                failure_code='fragment_still_over_limit',
            )
        )
        ctx = TableProcessContext(owner=owner, table=_FakeTable(), parent_node={}, current_section_key='description')

        out = try_short_table_direct_path(ctx)

        self.assertIsNone(out)
        self.assertEqual(owner.failure_contexts[-1]['error_code'], 'fragment_still_over_limit')
        self.assertEqual(owner.failure_contexts[-1]['stage'], 'pdf_first.capture')
