from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from core.document_parser.table_ops import render_pdf_ops as render_pdf_module
from core.document_parser.table_ops.process_steps.types import TablePdfFragment


class _FakeImageProcessor:
    def __init__(self, *, forced_height_mm: float | None = None) -> None:
        self.forced_height_mm = forced_height_mm

    def process_image(self, image, output_path, **_kwargs):
        image.save(output_path, format="JPEG", quality=95, subsampling=0)
        return image.size

    def calculate_xml_dimensions(self, width_point, size):
        width_px, height_px = int(size[0]), int(size[1])
        width_mm = float(width_point)
        if self.forced_height_mm is not None:
            return width_mm, float(self.forced_height_mm)
        return width_mm, round(width_mm * float(height_px) / float(width_px), 2)


class _FakeOwner:
    def __init__(self, temp_dir: Path, *, preview_fit: dict | None = None, forced_height_mm: float | None = None) -> None:
        self.config = {
            "paths": {"temp_dir": str(temp_dir)},
            "table_capture": {
                "preview_fit": preview_fit or {"enabled": False},
            },
        }
        self.img_proc = _FakeImageProcessor(forced_height_mm=forced_height_mm)
        self.removed: list[str] = []

    def _remove_temp_image_if_exists(self, filename: str | None) -> None:
        if not filename:
            return
        self.removed.append(str(filename))
        path = Path(self.config["paths"]["temp_dir"]) / str(filename)
        if path.is_file():
            path.unlink()


def _write_sample_table_fragment(path: Path, *, size: tuple[int, int]) -> None:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    width, height = size
    for y in range(20, height - 20, 220):
        draw.rectangle((20, y, width - 20, min(y + 80, height - 20)), outline="black", width=4)
    draw.line((0, int(height / 2), width, int(height / 2)), fill="white", width=10)
    img.save(path, format="JPEG", quality=95, subsampling=0)


def _write_group_slice_fixture(path: Path, *, size: tuple[int, int], rule_y: int | None = None) -> None:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    width, height = size
    draw.rectangle((20, 20, width - 20, height - 20), outline="black", width=4)
    if rule_y is not None:
        draw.line((20, int(rule_y), width - 20, int(rule_y)), fill="black", width=5)
    img.save(path, format="JPEG", quality=95, subsampling=0)


def _horizontal_dark_ratio(path: Path, y: int) -> float:
    with Image.open(path) as opened:
        img = opened.convert("RGB")
    width, height = img.size
    y = max(0, min(int(y), int(height) - 1))
    px = img.load()
    dark = 0
    for x in range(width):
        r, g, b = px[x, y]
        if r < 120 and g < 120 and b < 120:
            dark += 1
    return float(dark) / float(width)


class TablePdfVisualSliceTests(unittest.TestCase):
    def test_overlimit_pdf_fragment_is_split_into_balanced_legal_slices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            original_path = temp_dir / "tbl_page.jpg"
            _write_sample_table_fragment(original_path, size=(1000, 2500))
            owner = _FakeOwner(temp_dir)
            fragment = TablePdfFragment("tbl_page.jpg", 1, 1000, 2500, 100.0, 250.0, "selection")

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                [fragment],
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertIsNotNone(result)
            self.assertEqual(len(result or []), 2)
            self.assertFalse(original_path.exists())
            for sliced in result or []:
                self.assertTrue((temp_dir / sliced.file).is_file())
                self.assertLessEqual(sliced.height_mm, 240.0)
                self.assertGreater(sliced.height_mm, 100.0)
                self.assertTrue(sliced.file.startswith("tbl_page_s"))

    def test_visual_slice_does_not_chase_blank_row_into_overlimit_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            original_path = temp_dir / "tail_guard.jpg"
            img = Image.new("RGB", (1000, 4800), "white")
            draw = ImageDraw.Draw(img)
            draw.rectangle((20, 10, 980, 4780), outline="black", width=4)
            draw.rectangle((40, 400, 960, 1800), outline="black", width=8)
            draw.line((0, 2200, 1000, 2200), fill="white", width=18)
            draw.line((20, 2400, 980, 2400), fill="black", width=5)
            img.save(original_path, format="JPEG", quality=95, subsampling=0)
            owner = _FakeOwner(temp_dir)
            fragment = TablePdfFragment("tail_guard.jpg", 1, 1000, 4800, 100.0, 480.0, "selection")

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                [fragment],
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertIsNotNone(result)
            self.assertEqual(len(result or []), 2)
            self.assertTrue(all(sliced.height_mm <= 240.0 for sliced in result or []))

    def test_preview_fit_bypass_keeps_original_fragment_without_slicing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            original_path = temp_dir / "slight.jpg"
            _write_sample_table_fragment(original_path, size=(1000, 2420))
            owner = _FakeOwner(
                temp_dir,
                preview_fit={"enabled": True, "safe_max_he_mm": 240.0, "max_excess_mm": 3.0},
            )
            fragment = TablePdfFragment("slight.jpg", 1, 1000, 2420, 100.0, 242.0, "selection")

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                [fragment],
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertEqual(result, [fragment])
            self.assertTrue(original_path.is_file())
            self.assertEqual(sorted(p.name for p in temp_dir.glob("slight_s*.jpg")), [])

    def test_visual_slice_failure_returns_none_and_removes_generated_slices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            original_path = temp_dir / "bad.jpg"
            _write_sample_table_fragment(original_path, size=(1000, 2500))
            owner = _FakeOwner(temp_dir, forced_height_mm=300.0)
            fragment = TablePdfFragment("bad.jpg", 1, 1000, 2500, 100.0, 250.0, "selection")

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                [fragment],
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertIsNone(result)
            self.assertTrue(original_path.is_file())
            self.assertEqual(sorted(p.name for p in temp_dir.glob("bad_s*.jpg")), [])

    def test_multi_page_table_is_packed_as_group_near_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            first_path = temp_dir / "group_p1.jpg"
            second_path = temp_dir / "group_p2.jpg"
            _write_group_slice_fixture(first_path, size=(1000, 2500), rule_y=2400)
            _write_group_slice_fixture(second_path, size=(1000, 2300), rule_y=None)
            owner = _FakeOwner(temp_dir)
            fragments = [
                TablePdfFragment("group_p1.jpg", 1, 1000, 2500, 100.0, 250.0, "selection"),
                TablePdfFragment("group_p2.jpg", 2, 1000, 2300, 100.0, 230.0, "selection"),
            ]

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                fragments,
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertIsNotNone(result)
            self.assertEqual(len(result or []), 2)
            self.assertTrue(all(220.0 <= item.height_mm <= 240.0 for item in result or []))
            self.assertFalse(first_path.exists())
            self.assertFalse(second_path.exists())

    def test_single_low_density_row_is_not_a_safe_visual_cut(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            original_path = temp_dir / "unsafe.jpg"
            img = Image.new("RGB", (1000, 2500), "white")
            draw = ImageDraw.Draw(img)
            draw.line((20, 20, 20, 2480), fill="black", width=4)
            draw.line((980, 20, 980, 2480), fill="black", width=4)
            draw.line((500, 20, 500, 2480), fill="black", width=4)
            for y in range(930, 1575, 6):
                draw.line((620, y, 760, y), fill="black", width=3)
            img.save(original_path, format="JPEG", quality=95, subsampling=0)
            owner = _FakeOwner(temp_dir)
            fragment = TablePdfFragment("unsafe.jpg", 1, 1000, 2500, 100.0, 250.0, "selection")

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                [fragment],
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertIsNone(result)
            self.assertTrue(original_path.is_file())
            self.assertEqual(sorted(p.name for p in temp_dir.glob("unsafe_s*.jpg")), [])

    def test_clear_band_with_vertical_borders_can_be_used_as_safe_cut(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            original_path = temp_dir / "clear_band.jpg"
            img = Image.new("RGB", (1000, 2500), "white")
            draw = ImageDraw.Draw(img)
            draw.line((20, 20, 20, 2480), fill="black", width=4)
            draw.line((980, 20, 980, 2480), fill="black", width=4)
            draw.line((500, 20, 500, 2480), fill="black", width=4)
            draw.text((620, 1100), "merged content above", fill="black")
            draw.text((620, 1400), "merged content below", fill="black")
            img.save(original_path, format="JPEG", quality=95, subsampling=0)
            owner = _FakeOwner(temp_dir)
            fragment = TablePdfFragment("clear_band.jpg", 1, 1000, 2500, 100.0, 250.0, "selection")

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                [fragment],
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertIsNotNone(result)
            self.assertEqual(len(result or []), 2)
            self.assertFalse(original_path.exists())
            self.assertTrue(all(item.height_mm <= 240.0 for item in result or []))

    def test_partial_horizontal_rule_in_merged_region_is_not_a_safe_cut(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            original_path = temp_dir / "partial_rule.jpg"
            img = Image.new("RGB", (1000, 2500), "white")
            draw = ImageDraw.Draw(img)
            draw.rectangle((20, 20, 980, 2480), outline="black", width=4)
            draw.line((500, 20, 500, 2480), fill="black", width=4)
            draw.line((20, 1250, 500, 1250), fill="black", width=4)
            for y in range(930, 1575, 6):
                draw.line((620, y, 760, y), fill="black", width=3)
            img.save(original_path, format="JPEG", quality=95, subsampling=0)
            owner = _FakeOwner(temp_dir)
            fragment = TablePdfFragment("partial_rule.jpg", 1, 1000, 2500, 100.0, 250.0, "selection")

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                [fragment],
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertIsNone(result)
            self.assertTrue(original_path.is_file())
            self.assertEqual(sorted(p.name for p in temp_dir.glob("partial_rule_s*.jpg")), [])

    def test_visual_slice_boundaries_are_closed_without_dropping_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            first_path = temp_dir / "closed_p1.jpg"
            second_path = temp_dir / "closed_p2.jpg"
            _write_group_slice_fixture(first_path, size=(1000, 2500), rule_y=2400)
            _write_group_slice_fixture(second_path, size=(1000, 2300), rule_y=None)
            owner = _FakeOwner(temp_dir)
            fragments = [
                TablePdfFragment("closed_p1.jpg", 1, 1000, 2500, 100.0, 250.0, "selection"),
                TablePdfFragment("closed_p2.jpg", 2, 1000, 2300, 100.0, 230.0, "selection"),
            ]

            result = render_pdf_module._expand_overlimit_pdf_fragments(
                owner,
                fragments,
                width_point=100.0,
                max_height_mm=240.0,
            )

            self.assertIsNotNone(result)
            first_slice, second_slice = result or []
            first_slice_path = temp_dir / first_slice.file
            second_slice_path = temp_dir / second_slice.file
            self.assertGreater(_horizontal_dark_ratio(first_slice_path, int(first_slice.height_px) - 2), 0.85)
            self.assertGreater(_horizontal_dark_ratio(second_slice_path, 1), 0.85)
            self.assertEqual(
                sum(item.height_px for item in result or []),
                4800,
            )


if __name__ == "__main__":
    unittest.main()
