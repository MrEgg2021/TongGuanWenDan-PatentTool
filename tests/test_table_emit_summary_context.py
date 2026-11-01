from __future__ import annotations

import unittest

from core.document_parser.table_mixin import TableProcessingMixin


class _DummyXml:
    def create_paragraph(self, parent, text=None, num=None, is_claim=False):
        _ = parent, text, num, is_claim
        return {}

    def create_image_node(self, parent, img_filename, width_mm, height_mm, img_type='desc', inline=True):
        _ = parent, img_filename, width_mm, height_mm, img_type, inline
        return {}


class _DummyTableEmitter(TableProcessingMixin):
    def __init__(self) -> None:
        self.xml = _DummyXml()

    def _guard_table_fragment_height(self, filename, height_mm, *, stage, section, remove_file=False):
        _ = filename, height_mm, stage, section, remove_file
        return True

    def _append_claim_segments(self, parent_node, segments, is_new_start=False, claim_num=None):
        _ = parent_node, segments, is_new_start, claim_num
        return None


class TableEmitSummaryContextTests(unittest.TestCase):
    def test_emit_final_table_image_records_emit_summary_context(self) -> None:
        emitter = _DummyTableEmitter()
        emitter._clear_table_emit_summary_context()

        ok = emitter._emit_final_table_image({}, 'description', 'tbl_demo.jpg', 165.0, 210.0, object(), False)
        summary = emitter._consume_table_emit_summary_context()

        self.assertTrue(ok)
        self.assertEqual(
            summary,
            [
                {
                    'file': 'tbl_demo.jpg',
                    'width_mm': 165.0,
                    'height_mm': 210.0,
                    'section': 'description',
                }
            ],
        )


if __name__ == '__main__':
    unittest.main()
