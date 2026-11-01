from __future__ import annotations

import unittest

from PIL import Image

from core.document_parser.table_ops import render_pdf_ops as render_pdf_module


class TablePdfFragmentNormalizationTests(unittest.TestCase):
    def test_calculate_width_variance_ratio_uses_median_width(self) -> None:
        ratio = render_pdf_module._calculate_width_variance_ratio([100, 108, 92])

        self.assertAlmostEqual(ratio, 0.08, places=4)

    def test_pad_pages_to_common_width_expands_narrow_page_to_batch_width(self) -> None:
        wide = Image.new('RGB', (10, 4), (255, 255, 255))
        narrow = Image.new('RGB', (6, 4), (0, 0, 0))

        normalized = render_pdf_module._pad_pages_to_common_width([wide, narrow])

        self.assertEqual([img.size for img in normalized], [(10, 4), (10, 4)])
        self.assertEqual(normalized[1].getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(normalized[1].getpixel((2, 0)), (0, 0, 0))

    def test_page_batch_is_invalid_when_width_variance_exceeds_threshold(self) -> None:
        self.assertTrue(render_pdf_module._page_batch_has_invalid_width_variance([100, 118], 0.08))
        self.assertFalse(render_pdf_module._page_batch_has_invalid_width_variance([100, 107], 0.08))