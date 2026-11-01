from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from core.document_parser.equation_mixin import EquationRenderingMixin
from core.document_parser.image_shape_mixin import ImageShapeMixin
from core.document_parser.paragraph_inline_impl.segment_builder import build_segments


class _Range:
    def __init__(self, *, start: int = 0, end: int = 1, text: str = "") -> None:
        self.Start = start
        self.End = end
        self.Text = text
        self.copy_calls = 0

    def Copy(self) -> None:
        self.copy_calls += 1


class _OMath:
    def __init__(self, start: int = 0, end: int = 1) -> None:
        self.Range = _Range(start=start, end=end)


class _ImageProcessor:
    def __init__(self, *, emf_size: tuple[int, int] | None = (120, 40)) -> None:
        self.emf_size = emf_size
        self.save_emf_calls = 0
        self.clipboard_image_calls = 0
        self.process_calls = 0

    def save_emf_from_clipboard(self, *_args, **_kwargs):
        self.save_emf_calls += 1
        return self.emf_size

    def get_image_from_clipboard(self):
        self.clipboard_image_calls += 1
        return Image.new("RGB", (80, 30), "white")

    def process_image(self, image, *_args, **_kwargs):
        self.process_calls += 1
        return image.size

    def calculate_equation_dimensions(self, processed_img_size):
        width_px, height_px = processed_img_size
        return float(width_px), float(height_px)


class _Word:
    def __init__(self) -> None:
        self.app = None
        self.copy_range_calls = 0

    def copy_range_as_picture(self, _range) -> bool:
        self.copy_range_calls += 1
        return True


class _EquationHost(EquationRenderingMixin):
    def __init__(self, temp_dir: str, *, mode: str = "pdf", emf_size: tuple[int, int] | None = (120, 40)) -> None:
        self.config = {"paths": {"temp_dir": temp_dir}, "equation_rendering": {"mode": mode}, "image_processing": {}}
        self.img_proc = _ImageProcessor(emf_size=emf_size)
        self.word = _Word()
        self.pdf_calls = 0

    def _render_equation_via_pdf(self, _shape_obj, _output_path):
        self.pdf_calls += 1
        return (640, 240)


class _ShapeEquationHost(EquationRenderingMixin, ImageShapeMixin):
    def __init__(self, temp_dir: str) -> None:
        self.config = {
            "paths": {"temp_dir": temp_dir},
            "equation_rendering": {"mode": "pdf"},
            "image_processing": {},
            "ole_compatibility": {"broken_ole_classtype_blacklist": []},
        }
        self.img_proc = _ImageProcessor(emf_size=(120, 40))
        self.word = _Word()
        self.pdf_calls = 0
        self._drawings_inline_package_queue_state = {"docx_path": "", "items": [], "index": 0, "disabled": False}

    def _is_equation_shape(self, _shape_obj) -> bool:
        return True

    def _render_equation_via_pdf(self, _shape_obj, _output_path):
        self.pdf_calls += 1
        return (640, 240)

    def _extract_drawings_media_to_temp(self, *_args, **_kwargs):
        return None

    def _extract_drawings_media_zip_path_to_temp(self, *_args, **_kwargs):
        return None


class _FormulaShape:
    def __init__(self) -> None:
        self.Type = 1
        self.Range = _Range(start=0, end=1)
        self.Range.WordOpenXML = ""
        self.Width = 100.0
        self.Height = 30.0
        self.PictureFormat = None
        self.OLEFormat = SimpleNamespace(ClassType="Equation.3")


class _Collection:
    def __init__(self, items) -> None:
        self._items = list(items)
        self.Count = len(self._items)

    def __call__(self, index: int):
        return self._items[index - 1]


class _SegmentHost:
    def __init__(self) -> None:
        self.config = {"defensive": {"large_img_height_mm": 40.0}}
        self.word = SimpleNamespace(doc=SimpleNamespace(Range=lambda _start, _end: _Range(text="")))
        self.shape_calls = 0
        self.omath_calls = 0

    def _sanitize_text(self, text: str) -> str:
        return str(text or "")

    def _extract_text_with_formatting(self, _rng) -> str:
        return ""

    def _is_equation_shape(self, _shape) -> bool:
        return True

    def handle_shape(self, *_args, **_kwargs):
        self.shape_calls += 1
        return "shape.jpg", 10.0, 5.0, None

    def handle_omath(self, *_args, **_kwargs):
        self.omath_calls += 1
        return "omath.jpg", 10.0, 5.0


class FormulaClipboardTransactionTests(unittest.TestCase):
    def test_visio_embedded_ole_is_not_treated_as_equation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _EquationHost(td)
            visio = SimpleNamespace(Type=1, OLEFormat=SimpleNamespace(ClassType="Visio.Drawing.15"))
            equation = SimpleNamespace(Type=1, OLEFormat=SimpleNamespace(ClassType="Equation.3"))
            legacy_unknown = SimpleNamespace(Type=1, OLEFormat=None)

            self.assertFalse(host._is_equation_shape(visio))
            self.assertTrue(host._is_equation_shape(equation))
            self.assertTrue(host._is_equation_shape(legacy_unknown))

    def test_omath_emf_does_not_read_stale_clipboard_when_not_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _EquationHost(td, mode="pdf", emf_size=(120, 40))
            omath = _OMath()

            with mock.patch("core.clipboard_utils.get_clipboard_sequence_number", create=True, return_value=10), mock.patch(
                "core.clipboard_utils.wait_for_clipboard_fresh_content",
                create=True,
                return_value=False,
            ):
                filename, width, height = host.handle_omath(omath)

            self.assertTrue(filename)
            self.assertEqual((640.0, 240.0), (width, height))
            self.assertEqual(2, omath.Range.copy_calls)
            self.assertEqual(0, host.img_proc.save_emf_calls)
            self.assertEqual(1, host.pdf_calls)

    def test_equation_shape_emf_does_not_read_stale_clipboard_when_not_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _ShapeEquationHost(td)
            shape = _FormulaShape()

            with mock.patch("core.clipboard_utils.get_clipboard_sequence_number", create=True, return_value=10), mock.patch(
                "core.clipboard_utils.wait_for_clipboard_fresh_content",
                create=True,
                return_value=False,
            ):
                filename, width, height, _px_per_mm = host.handle_shape(shape, parent_node=SimpleNamespace(tag="cn-description"))

            self.assertTrue(filename)
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
            self.assertEqual(2, shape.Range.copy_calls)
            self.assertEqual(0, host.img_proc.save_emf_calls)
            self.assertEqual(1, host.pdf_calls)

    def test_omath_bitmap_fallback_does_not_read_stale_clipboard_when_not_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _EquationHost(td, mode="screenshot", emf_size=None)
            omath = _OMath()

            with mock.patch("core.clipboard_utils.get_clipboard_sequence_number", create=True, return_value=10), mock.patch(
                "core.clipboard_utils.wait_for_clipboard_fresh_content",
                create=True,
                return_value=False,
            ):
                filename, width, height = host.handle_omath(omath)

            self.assertIsNone(filename)
            self.assertEqual((0, 0), (width, height))
            self.assertEqual(2, host.word.copy_range_calls)
            self.assertEqual(0, host.img_proc.clipboard_image_calls)

    def test_overlapping_equation_shape_and_omath_emit_one_segment(self) -> None:
        host = _SegmentHost()
        shape = SimpleNamespace(Range=_Range(start=0, end=1))
        omath = _OMath(start=0, end=1)
        para_range = _Range(start=0, end=1, text="\x01\r")
        para_range.InlineShapes = _Collection([shape])
        para_range.OMaths = _Collection([omath])
        para = SimpleNamespace(Range=para_range)

        segments = build_segments(
            host,
            para,
            is_claim=False,
            has_inline=True,
            inline_shapes=para_range.InlineShapes,
            inline_count=1,
            enable_wordopenxml_supsub=False,
        )

        image_segments = [segment for segment in segments if segment.get("kind") == "img"]
        self.assertEqual(1, len(image_segments))
        self.assertEqual("omath.jpg", image_segments[0]["filename"])
        self.assertEqual(0, host.shape_calls)
        self.assertEqual(1, host.omath_calls)


if __name__ == "__main__":
    unittest.main()
