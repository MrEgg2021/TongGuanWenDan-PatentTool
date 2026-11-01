from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from core.document_parser.image_shape_mixin import ImageShapeMixin
from core.document_parser.paragraph_inline_impl.segment_builder import build_segments


class _Range:
    def __init__(self, *, start: int = 0, end: int = 1, text: str = "", xml: str = "") -> None:
        self.Start = start
        self.End = end
        self.Text = text
        self.WordOpenXML = xml
        self.OMaths = SimpleNamespace(Count=0)


class _InlineShapes:
    Count = 1

    def __init__(self, shape) -> None:
        self._shape = shape

    def __call__(self, index: int):
        if index != 1:
            raise IndexError(index)
        return self._shape


class _ParagraphRange(_Range):
    def __init__(self, shape) -> None:
        super().__init__(start=0, end=1, text="\x01\r")
        self.InlineShapes = _InlineShapes(shape)


class _Shape:
    def __init__(self, *, type_code: int = 3, width: float = 200.0, height: float = 100.0) -> None:
        self.Type = type_code
        self.Width = width
        self.Height = height
        self.Range = _Range(
            start=0,
            end=1,
            xml="<w:p xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>",
        )
        self.PictureFormat = None


class _SegmentHost:
    def __init__(self) -> None:
        self.config = {"defensive": {"large_img_height_mm": 40.0}}
        self.captured_section_key = None
        self.word = SimpleNamespace(doc=SimpleNamespace(Range=lambda _start, _end: _Range(text="")))

    def _sanitize_text(self, text: str) -> str:
        return str(text or "")

    def _extract_text_with_formatting(self, _rng) -> str:
        return ""

    def handle_shape(self, obj, *, parent_node=None, section_key=None):
        self.captured_section_key = section_key
        return "sms_test.jpg", 10.0, 10.0, None

    def handle_omath(self, _obj):
        return None, 0.0, 0.0

    def _is_equation_shape(self, _obj) -> bool:
        return False


class _Word:
    def __init__(
        self,
        *,
        export_size: tuple[int, int] | None = None,
        copy_succeeds: bool = True,
    ) -> None:
        self.doc = SimpleNamespace(FullName="")
        self.app = None
        self.export_size = export_size
        self.copy_succeeds = copy_succeeds
        self.export_calls = 0
        self.copy_calls = 0
        self.scaled_copy_calls = 0
        self.last_scale_factor = 1.0

    def export_inline_shape_as_picture(self, _shape, output_path: str) -> bool:
        self.export_calls += 1
        if not self.export_size:
            return False
        Image.new("RGB", self.export_size, "white").save(output_path, format="JPEG", quality=100, subsampling=0)
        return True

    def copy_shape_to_clipboard(self, _shape, use_copy_as_picture: bool = False) -> bool:
        self.copy_calls += 1
        return self.copy_succeeds

    def copy_shape_to_clipboard_scaled(
        self,
        _shape,
        scale_factor: float = 1.0,
        use_copy_as_picture: bool = True,
    ) -> bool:
        self.scaled_copy_calls += 1
        self.last_scale_factor = float(scale_factor)
        return self.copy_succeeds

    def copy_range_as_picture(self, *_args, **_kwargs) -> bool:
        return False


class _ImageProcessor:
    def __init__(
        self,
        *,
        fallback_size: tuple[int, int] = (300, 180),
        clipboard_sizes: list[tuple[int, int]] | None = None,
    ) -> None:
        self.fallback_size = fallback_size
        self.clipboard_sizes = list(clipboard_sizes or [])
        self.process_calls = 0

    def get_image_from_clipboard(self):
        size = self.clipboard_sizes.pop(0) if self.clipboard_sizes else self.fallback_size
        return Image.new("RGB", size, "white")

    def process_image(self, image, output_path, **_kwargs):
        self.process_calls += 1
        image.save(output_path, format="JPEG", quality=100, subsampling=0)
        return image.size

    def calculate_xml_dimensions(self, original_width_point, processed_img_size):
        width_mm = round(float(original_width_point or 0.0) * 0.3528, 2)
        height_mm = round(width_mm * float(processed_img_size[1]) / float(processed_img_size[0]), 2)
        return width_mm, height_mm

    def calculate_equation_dimensions(self, processed_img_size):
        return self.calculate_xml_dimensions(100.0, processed_img_size)


class _HandleHost(ImageShapeMixin):
    def __init__(
        self,
        temp_dir: str,
        *,
        export_size: tuple[int, int] | None,
        min_dpi: float = 100.0,
        copy_succeeds: bool = True,
        fallback_size: tuple[int, int] = (300, 180),
        clipboard_sizes: list[tuple[int, int]] | None = None,
    ) -> None:
        self.word = _Word(export_size=export_size, copy_succeeds=copy_succeeds)
        self.img_proc = _ImageProcessor(fallback_size=fallback_size, clipboard_sizes=clipboard_sizes)
        self.config = {
            "paths": {"temp_dir": temp_dir},
            "image_processing": {
                "jpeg_quality": 100,
                "jpeg_subsampling": 0,
                "description_visible_export_min_dpi": min_dpi,
            },
            "jpeg_quality": 100,
            "jpeg_subsampling": 0,
        }
        self.pipeline = []

    def _is_equation_shape(self, _shape) -> bool:
        return False

    def _record_image_pipeline(self, source: str) -> None:
        self.pipeline.append(source)


class DescriptionImageFidelityTests(unittest.TestCase):
    def test_build_segments_passes_effective_section_key_to_handle_shape(self) -> None:
        host = _SegmentHost()
        shape = _Shape()
        para = SimpleNamespace(Range=_ParagraphRange(shape))

        segments = build_segments(
            host,
            para,
            parent_node=SimpleNamespace(tag="cn-application-body"),
            section_key="description",
            is_claim=False,
            has_inline=True,
            inline_shapes=para.Range.InlineShapes,
            inline_count=1,
            enable_wordopenxml_supsub=False,
        )

        self.assertEqual("description", host.captured_section_key)
        self.assertEqual("sms_test.jpg", segments[0]["filename"])

    def test_description_inline_picture_uses_visible_export_before_bitmap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _HandleHost(td, export_size=(900, 500), min_dpi=80.0)
            filename, width_mm, height_mm, _ = host.handle_shape(
                _Shape(width=200.0),
                parent_node=SimpleNamespace(tag="cn-application-body"),
                section_key="description",
            )

            self.assertTrue(filename)
            self.assertTrue((Path(td) / str(filename)).is_file())
            self.assertEqual(1, host.word.export_calls)
            self.assertEqual(0, host.word.copy_calls)
            self.assertEqual(0, host.img_proc.process_calls)
            self.assertEqual(["SAVEAS"], host.pipeline)
            self.assertGreater(width_mm, 0)
            self.assertGreater(height_mm, 0)

    def test_low_quality_visible_export_falls_back_to_bitmap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _HandleHost(td, export_size=(20, 10), min_dpi=300.0)
            filename, _, _, _ = host.handle_shape(
                _Shape(width=200.0),
                parent_node=SimpleNamespace(tag="cn-application-body"),
                section_key="description",
            )

            self.assertTrue(filename)
            self.assertEqual(1, host.word.export_calls)
            self.assertEqual(2, host.word.copy_calls)
            self.assertEqual(1, host.word.scaled_copy_calls)
            self.assertEqual(3, host.img_proc.process_calls)
            self.assertEqual(["BITMAP"], host.pipeline)
            with Image.open(Path(td) / str(filename)) as img:
                self.assertEqual((300, 180), img.size)

    def test_copy_as_picture_visible_export_is_used_when_saveas_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _HandleHost(td, export_size=None, min_dpi=80.0, fallback_size=(900, 420))
            filename, _, _, _ = host.handle_shape(
                _Shape(width=200.0),
                parent_node=SimpleNamespace(tag="cn-application-body"),
                section_key="description",
            )

            self.assertTrue(filename)
            self.assertEqual(1, host.word.export_calls)
            self.assertEqual(1, host.word.copy_calls)
            self.assertEqual(0, host.word.scaled_copy_calls)
            self.assertEqual(1, host.img_proc.process_calls)
            self.assertEqual(["SAVEAS"], host.pipeline)
            with Image.open(Path(td) / str(filename)) as img:
                self.assertEqual((900, 420), img.size)

    def test_low_quality_copy_as_picture_can_use_scaled_visible_copy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _HandleHost(
                td,
                export_size=None,
                min_dpi=180.0,
                clipboard_sizes=[(300, 180), (900, 420)],
            )
            filename, _, _, _ = host.handle_shape(
                _Shape(width=200.0),
                parent_node=SimpleNamespace(tag="cn-application-body"),
                section_key="description",
            )

            self.assertTrue(filename)
            self.assertEqual(1, host.word.export_calls)
            self.assertEqual(1, host.word.copy_calls)
            self.assertEqual(1, host.word.scaled_copy_calls)
            self.assertGreater(host.word.last_scale_factor, 1.0)
            self.assertEqual(2, host.img_proc.process_calls)
            self.assertEqual(["SAVEAS"], host.pipeline)
            with Image.open(Path(td) / str(filename)) as img:
                self.assertEqual((900, 420), img.size)

    def test_non_description_picture_does_not_use_visible_export_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _HandleHost(td, export_size=(900, 500), min_dpi=80.0)
            filename, _, _, _ = host.handle_shape(
                _Shape(width=200.0),
                parent_node=SimpleNamespace(tag="cn-abstract"),
                section_key="abstract",
            )

            self.assertTrue(filename)
            self.assertEqual(0, host.word.export_calls)
            self.assertEqual(1, host.word.copy_calls)
            self.assertEqual(1, host.img_proc.process_calls)
            self.assertEqual(["BITMAP"], host.pipeline)


if __name__ == "__main__":
    unittest.main()
