from __future__ import annotations

import os
import tempfile
import unittest

from PIL import Image

from core.img_processor import ImageProcessor


class TableCenteringKeepHeightTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _make_image(self, name: str, size: tuple[int, int]) -> str:
        path = os.path.join(self._tmp.name, name)
        Image.new('RGB', size, (32, 32, 32)).save(path, quality=95, subsampling=0, dpi=(300, 300))
        return path

    def test_pad_table_for_centering_keep_height_only_changes_width(self) -> None:
        processor = ImageProcessor(
            {
                'jpeg_quality': 95,
                'jpeg_subsampling': 0,
                'bg_color': '#FFFFFF',
            }
        )
        image_path = self._make_image('table.jpg', (100, 50))

        new_width_mm, new_height_mm = processor.pad_table_for_centering_keep_height(
            image_path,
            120.0,
            226.92,
            target_width_mm=165.0,
        )

        self.assertEqual(new_width_mm, 165.0)
        self.assertEqual(new_height_mm, 226.92)
        with Image.open(image_path) as img:
            self.assertEqual(img.size[1], 50)
            self.assertGreater(img.size[0], 100)

    def test_pad_table_for_centering_keep_height_is_noop_when_target_is_not_wider(self) -> None:
        processor = ImageProcessor(
            {
                'jpeg_quality': 95,
                'jpeg_subsampling': 0,
                'bg_color': '#FFFFFF',
            }
        )
        image_path = self._make_image('table_noop.jpg', (160, 40))

        new_width_mm, new_height_mm = processor.pad_table_for_centering_keep_height(
            image_path,
            165.0,
            88.0,
            target_width_mm=145.0,
        )

        self.assertEqual(new_width_mm, 165.0)
        self.assertEqual(new_height_mm, 88.0)
        with Image.open(image_path) as img:
            self.assertEqual(img.size, (160, 40))


if __name__ == '__main__':
    unittest.main()
