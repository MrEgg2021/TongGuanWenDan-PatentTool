from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from core.img_processor import ImageProcessor
from core.image_processing import equation_diag_ops


class EquationCropPreserveMarksTests(unittest.TestCase):
    @staticmethod
    def _make_equation_like_image() -> Image.Image:
        img = Image.new("RGB", (80, 40), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle((18, 16, 56, 30), fill="black")
        draw.rectangle((34, 7, 36, 9), fill="black")
        return img

    @staticmethod
    def _dark_pixels_in_top_rows(image: Image.Image, rows: int = 3) -> int:
        gray = np.array(image.convert("L"))
        return int((gray[:rows, :] < 230).sum())

    @staticmethod
    def _make_all_ink_equation_image() -> Image.Image:
        img = Image.new("RGB", (100, 70), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle((25, 20, 74, 45), fill="black")
        draw.point((48, 2), fill="black")
        draw.rectangle((48, 60, 49, 61), fill=(240, 240, 240))
        draw.point((5, 32), fill="black")
        draw.point((94, 32), fill="black")
        return img

    @staticmethod
    def _content_bbox(image: Image.Image, threshold: int = 245) -> tuple[int, int, int, int]:
        gray = np.array(image.convert("L"))
        ys, xs = np.where(gray <= threshold)
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

    def _make_processor(self) -> ImageProcessor:
        return ImageProcessor(
            {
                "bg_color": "#FFFFFF",
                "crop_edge_guard_px": 0,
                "crop_edge_guard_threshold": 245,
                "crop_output_min_margin_px": 0,
                "crop_padding_min": 0,
                "crop_padding_ratio": 0.0,
                "equation_crop_padding_min": 0,
                "min_short_edge": 0,
                "sharpen_enabled": False,
            }
        )

    def test_build_emf_crop_diagnostics_formula_mode_promotes_detached_dot(self) -> None:
        diag = equation_diag_ops.build_emf_crop_diagnostics(
            self._make_equation_like_image(),
            threshold=230,
            padding_ratio=0.0,
            padding_min=0,
            preserve_detached_equation_marks=True,
        )

        self.assertTrue(diag["promoted_micro_contours"])
        self.assertEqual([], diag["discarded_small_contours"])
        self.assertLessEqual(diag["final_bbox"]["top"], 7)

    def test_process_image_equation_crop_keeps_promoted_dot_on_second_crop(self) -> None:
        proc = self._make_processor()
        img = self._make_equation_like_image()

        emf_cropped = proc._crop_white_borders(
            img,
            padding_ratio=0.0,
            padding_min=0,
            preserve_detached_equation_marks=True,
        )
        default_cropped = proc._crop_white_borders(
            img,
            padding_ratio=0.0,
            padding_min=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "eq.png"
            processed_size = proc.process_image(
                emf_cropped,
                str(output_path),
                is_equation=True,
                crop=True,
                apply_enhancement=False,
            )

            self.assertIsNotNone(processed_size)
            self.assertGreater(emf_cropped.size[1], default_cropped.size[1])
            self.assertEqual(emf_cropped.size, processed_size)

            with Image.open(output_path) as final_img:
                self.assertGreater(self._dark_pixels_in_top_rows(final_img), 0)

    def test_formula_mode_promotes_all_ink_around_body(self) -> None:
        diag = equation_diag_ops.build_emf_crop_diagnostics(
            self._make_all_ink_equation_image(),
            threshold=245,
            padding_ratio=0.0,
            padding_min=0,
            preserve_detached_equation_marks=True,
        )

        self.assertEqual(
            {"above", "below", "left", "right"},
            {item["relative_position"] for item in diag["promoted_micro_contours"]},
        )
        self.assertEqual([], diag["discarded_small_contours"])
        self.assertEqual(
            {"left": 5, "top": 2, "right": 95, "bottom": 62, "width": 90, "height": 60},
            diag["final_bbox"],
        )

    def test_formula_mode_preserves_unanchored_single_pixel_components(self) -> None:
        img = Image.new("RGB", (20, 20), "white")
        draw = ImageDraw.Draw(img)
        draw.point((2, 3), fill="black")
        draw.point((17, 16), fill="black")

        diag = equation_diag_ops.analyze_crop_contours(
            img,
            threshold=245,
            preserve_detached_equation_marks=True,
        )

        self.assertIsNone(diag["raw_bbox"])
        self.assertEqual({"unanchored"}, {item["relative_position"] for item in diag["promoted_micro_contours"]})
        self.assertEqual({"left": 2, "top": 3, "right": 18, "bottom": 17, "width": 16, "height": 14}, diag["final_bbox"])

    def test_repeated_formula_crop_preserves_all_ink_but_ordinary_crop_filters_it(self) -> None:
        proc = self._make_processor()
        img = self._make_all_ink_equation_image()

        formula_cropped = proc._crop_white_borders(
            img,
            padding_ratio=0.0,
            padding_min=0,
            preserve_detached_equation_marks=True,
        )
        ordinary_cropped = proc._crop_white_borders(
            img,
            padding_ratio=0.0,
            padding_min=0,
        )

        self.assertEqual((90, 60), formula_cropped.size)
        self.assertEqual((50, 26), ordinary_cropped.size)
        self.assertEqual((0, 0, 89, 59), self._content_bbox(formula_cropped))

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "all_ink_eq.png"
            processed_size = proc.process_image(
                formula_cropped,
                str(output_path),
                is_equation=True,
                crop=True,
                apply_enhancement=False,
            )

            self.assertEqual(formula_cropped.size, processed_size)
            with Image.open(output_path) as final_img:
                self.assertEqual((0, 0, 89, 59), self._content_bbox(final_img))

    def test_equation_centering_preserves_side_marks_and_height(self) -> None:
        proc = self._make_processor()

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "center_eq.png"
            self._make_all_ink_equation_image().save(image_path)

            new_width_mm, new_height_mm = proc.pad_equation_for_centering(
                str(image_path),
                10.0,
                7.0,
                target_width_mm=20.0,
            )

            self.assertEqual((20.0, 7.0), (new_width_mm, new_height_mm))
            with Image.open(image_path) as centered:
                self.assertEqual(70, centered.size[1])
                left, _top, right, _bottom = self._content_bbox(centered)
                self.assertEqual(89, right - left)

    def test_process_image_creates_missing_parent_dir_before_save(self) -> None:
        proc = self._make_processor()
        img = self._make_equation_like_image()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "deeper" / "eq.png"
            processed_size = proc.process_image(
                img,
                str(output_path),
                is_equation=True,
                crop=False,
                apply_enhancement=False,
            )

            self.assertEqual(img.size, processed_size)
            self.assertTrue(output_path.is_file())


if __name__ == "__main__":
    unittest.main()
