from __future__ import annotations

import unittest

from core.document_parser.table_mixin import TableProcessingMixin
from core.document_parser.table_ops.process_steps.types import TableCaptureResult, TablePdfFragment


class _FakeRange:
    pass


class _FakeTable:
    Range = _FakeRange()


class _ProbeCaptureParser(TableProcessingMixin):
    def __init__(self, result: TableCaptureResult) -> None:
        self.config = {
            'table_capture': {
            },
            'paths': {
                'temp_dir': '.',
            },
        }
        self._result = result
        self.removed: list[str] = []

    def _capture_table_pdf_first_result(self, rng, *, current_section_key, width_point):
        _ = rng, current_section_key, width_point
        return self._result

    def _remove_temp_image_if_exists(self, filename):
        if filename:
            self.removed.append(str(filename))


class TableCanvasProbeCaptureTests(unittest.TestCase):
    def test_capture_table_in_canvas_preserves_pdf_first_failure_instead_of_legacy_screenshot_success(self) -> None:
        parser = _ProbeCaptureParser(
            TableCaptureResult(
                fragments=[],
                used_blank_doc_fallback=False,
                hard_table=True,
                failure_code='selection_export_failed',
                diagnostic_code='pdf_page_invalid',
            )
        )

        filename, width_mm, height_mm = parser._capture_table_in_canvas(
            _FakeTable(),
            parent_node={},
            current_section_key='description',
            width_point=321.0,
        )

        self.assertIsNone(filename)
        self.assertEqual((width_mm, height_mm), (0.0, 0.0))
        failure = parser._peek_table_process_failure_context()
        self.assertIsNotNone(failure)
        self.assertEqual(failure['error_code'], 'selection_export_failed')
        self.assertEqual(failure['diagnostic_code'], 'pdf_page_invalid')

    def test_capture_table_in_canvas_payload_preserves_legal_multi_fragment_pdf_first_result(self) -> None:
        parser = _ProbeCaptureParser(
            TableCaptureResult(
                fragments=[
                    TablePdfFragment('probe_p1.jpg', 1, 1000, 1200, 100.0, 120.0, 'selection'),
                    TablePdfFragment('probe_p2.jpg', 2, 1000, 1180, 100.0, 118.0, 'selection'),
                ],
                used_blank_doc_fallback=False,
                hard_table=True,
                failure_code=None,
            )
        )

        payload = parser._capture_table_in_canvas_payload(
            _FakeTable(),
            parent_node={},
            current_section_key='description',
            width_point=321.0,
        )

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['fragment_count'], 2)
        self.assertEqual(
            payload['fragments'],
            [('probe_p1.jpg', 100.0, 120.0), ('probe_p2.jpg', 100.0, 118.0)],
        )
        self.assertIsNone(parser._peek_table_process_failure_context())

    def test_capture_table_in_canvas_marks_multi_fragment_result_as_contract_rejection_for_legacy_single_fragment_call(self) -> None:
        parser = _ProbeCaptureParser(
            TableCaptureResult(
                fragments=[
                    TablePdfFragment('probe_p1.jpg', 1, 1000, 1200, 100.0, 120.0, 'selection'),
                    TablePdfFragment('probe_p2.jpg', 2, 1000, 1180, 100.0, 118.0, 'selection'),
                ],
                used_blank_doc_fallback=False,
                hard_table=True,
                failure_code=None,
            )
        )

        filename, width_mm, height_mm = parser._capture_table_in_canvas(
            _FakeTable(),
            parent_node={},
            current_section_key='description',
            width_point=321.0,
        )

        self.assertIsNone(filename)
        self.assertEqual((width_mm, height_mm), (0.0, 0.0))
        self.assertEqual(parser.removed, ['probe_p1.jpg', 'probe_p2.jpg'])
        failure = parser._peek_table_process_failure_context()
        self.assertIsNotNone(failure)
        self.assertEqual(failure['error_code'], 'probe_contract_rejected_multi_fragment')
        self.assertEqual(failure['classification'], 'probe_contract_rejected_multi_fragment')
        self.assertEqual(failure['fragment_count'], 2)


if __name__ == '__main__':
    unittest.main()
