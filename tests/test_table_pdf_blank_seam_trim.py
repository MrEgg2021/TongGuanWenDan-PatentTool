from __future__ import annotations

import unittest

from PIL import Image

from core.document_parser.table_ops import render_pdf_ops as render_pdf_module


def _make_img(*, width: int = 20, height: int = 20, white_top: int = 0, white_bottom: int = 0) -> Image.Image:
    img = Image.new("RGB", (width, height), (0, 0, 0))
    px = img.load()
    for y in range(white_top):
        for x in range(width):
            px[x, y] = (255, 255, 255)
    for y in range(height - white_bottom, height):
        for x in range(width):
            px[x, y] = (255, 255, 255)
    return img


class TablePdfBlankSeamTrimTests(unittest.TestCase):
    def test_trim_blank_seam_between_pages_removes_shared_white_band(self) -> None:
        curr = _make_img(white_bottom=3)
        nxt = _make_img(white_top=4)

        curr2, nxt2, diag = render_pdf_module._trim_blank_seam_between_pages(curr, nxt, max_rows=12)

        self.assertEqual(curr2.size, curr.size)
        self.assertEqual(nxt2.size, (20, 17))
        self.assertEqual(diag["trim_top"], 3)
        self.assertTrue(diag["trimmed"])

    def test_trim_blank_seam_between_pages_keeps_images_when_no_blank_overlap(self) -> None:
        curr = _make_img(white_bottom=0)
        nxt = _make_img(white_top=0)

        curr2, nxt2, diag = render_pdf_module._trim_blank_seam_between_pages(curr, nxt, max_rows=12)

        self.assertEqual(curr2.size, curr.size)
        self.assertEqual(nxt2.size, nxt.size)
        self.assertEqual(diag["trim_top"], 0)
        self.assertFalse(diag["trimmed"])

    def test_prepare_processed_pages_drops_blank_pages_after_trim(self) -> None:
        content_page = _make_img(width=20, height=20, white_top=2, white_bottom=3)
        blank_page = Image.new("RGB", (20, 20), (255, 255, 255))

        processed = render_pdf_module._prepare_processed_pages([content_page, blank_page])

        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].size, (20, 15))


if __name__ == "__main__":
    unittest.main()
