from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace

from PIL import Image

from core.document_parser.image_shape_mixin import ImageShapeMixin
from core.xml_generator import XMLBuilder
from gui.batch_run_impl.finalize_flow import _build_batch_fallback_notice
from gui.single_run_impl.postprocess_flow import _build_single_fallback_notice


def _drawing_xml(*, embed_rid: str | None = None, link_rid: str | None = None, prog_id: str | None = None) -> str:
    embed_attr = f' r:embed="{embed_rid}"' if embed_rid else ""
    link_attr = f' r:link="{link_rid}"' if link_rid else ""
    prog = f' ProgID="{prog_id}"' if prog_id else ""
    return f"""
<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
     xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
     xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
     xmlns:v="urn:schemas-microsoft-com:vml"
     xmlns:o="urn:schemas-microsoft-com:office:office">
  <w:drawing>
    <a:graphic>
      <a:graphicData>
        <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <pic:blipFill>
            <a:blip{embed_attr}{link_attr}/>
          </pic:blipFill>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </w:drawing>
  <w:pict>
    <v:shape>
      <v:imagedata r:id="{embed_rid or ''}"/>
      <o:OLEObject{prog}/>
    </v:shape>
  </w:pict>
</w:r>
""".strip()


class _Range:
    def __init__(self, xml: str) -> None:
        self.WordOpenXML = xml


class _SafeWord:
    def __init__(self) -> None:
        self.inline_export_calls = 0
        self.shape_export_calls = 0
        self.copy_calls = 0
        self.app = None
        self.doc = SimpleNamespace(FullName="")

    def export_inline_shape_as_picture(self, shape_obj, output_path: str) -> bool:
        self.inline_export_calls += 1
        raise AssertionError("dangerous inline export path should not be called")

    def export_shape_as_picture(self, shape_obj, output_path: str) -> bool:
        self.shape_export_calls += 1
        raise AssertionError("dangerous shape export path should not be called")

    def copy_shape_to_clipboard(self, shape_obj, use_copy_as_picture: bool = True) -> bool:
        self.copy_calls += 1
        raise AssertionError("clipboard path should not be called")


class _SafeImageProcessor:
    def __init__(self) -> None:
        self._last_drawings_opt_meta = {}

    def optimize_drawings_image_file(
        self,
        output_path: str,
        *,
        ratio_num: float,
        ratio_den: float,
        allow_edge_crop: bool = True,
    ):
        return (600, 300)

    def calculate_drawings_dimensions(self, original_width_point, original_height_point, processed_img_size):
        width_mm = round(float(original_width_point or 100.0) * 0.3528, 2)
        height_mm = round(float(original_height_point or 50.0) * 0.3528, 2)
        return width_mm, height_mm

    def process_image(self, *args, **kwargs):
        raise AssertionError("generic bitmap processing should not be called for activation_risky placeholder path")

    def get_image_from_clipboard(self):
        raise AssertionError("clipboard should not be read for activation_risky placeholder path")


class _Host(ImageShapeMixin):
    def __init__(self, temp_dir: str) -> None:
        self.word = _SafeWord()
        self.img_proc = _SafeImageProcessor()
        self.config = {
            "paths": {"temp_dir": temp_dir},
            "jpeg_quality": 90,
            "jpeg_subsampling": 0,
            "ole_compatibility": {"broken_ole_classtype_blacklist": ["chemdraw", "kingdraw"]},
        }
        self._drawings_inline_package_queue_state = {"docx_path": "", "items": [], "index": 0, "disabled": False}
        self.object_fallback_failures = []

    def _is_equation_shape(self, shape_obj) -> bool:
        return False

    def _extract_drawings_media_to_temp(
        self,
        rid: str,
        filename_prefix: str = "img_",
        force_jpg_for_non_tiff: bool = True,
        target_width_px: int | None = None,
    ):
        _ = (rid, filename_prefix, force_jpg_for_non_tiff, target_width_px)
        return None

    def _extract_drawings_media_zip_path_to_temp(
        self,
        zip_path: str,
        filename_prefix: str = "img_",
        force_jpg_for_non_tiff: bool = True,
        target_width_px: int | None = None,
    ):
        _ = (zip_path, filename_prefix, force_jpg_for_non_tiff, target_width_px)
        return None


class _PreviewHost(_Host):
    def __init__(self, temp_dir: str) -> None:
        super().__init__(temp_dir)
        self.preview_target_width_px = None

    def _extract_drawings_media_to_temp(
        self,
        rid: str,
        filename_prefix: str = "img_",
        force_jpg_for_non_tiff: bool = True,
        target_width_px: int | None = None,
    ):
        _ = (rid, force_jpg_for_non_tiff)
        self.preview_target_width_px = target_width_px
        filename = f"{filename_prefix}preview.jpg"
        output_path = os.path.join(self.config["paths"]["temp_dir"], filename)
        Image.new("RGB", (300, 300), "white").save(output_path, format="JPEG")
        return filename, output_path


class _ShapeRange:
    Count = 1

    def __init__(self, shape) -> None:
        self.shape = shape

    def __call__(self, index: int):
        if index != 1:
            raise IndexError(index)
        return self.shape


class _FloatingPreviewHost(_PreviewHost):
    def __init__(self, temp_dir: str) -> None:
        super().__init__(temp_dir)
        self.xml = XMLBuilder({})
        self.pipeline = []

    def process_paragraph_content(self, *_args, **_kwargs) -> None:
        return None

    def _record_image_pipeline(self, source: str) -> None:
        self.pipeline.append(source)


class _InvalidatingFloatingShape:
    Type = 13
    PictureFormat = None

    def __init__(self, *, width: float, height: float) -> None:
        self._width = float(width)
        self._height = float(height)
        self._valid = True
        self.Range = _Range(_drawing_xml())

    @property
    def Width(self):
        if not self._valid:
            raise RuntimeError("floating shape is no longer valid")
        return self._width

    @property
    def Height(self):
        if not self._valid:
            raise RuntimeError("floating shape is no longer valid")
        return self._height

    def invalidate(self) -> None:
        self._valid = False


class _InvalidatingExportWord(_SafeWord):
    def export_shape_as_picture(self, shape_obj, output_path: str) -> bool:
        Image.new("RGB", (300, 300), "white").save(output_path, format="JPEG")
        shape_obj.invalidate()
        return True


class _FloatingSaveAsHost(_FloatingPreviewHost):
    def __init__(self, temp_dir: str) -> None:
        super().__init__(temp_dir)
        self.word = _InvalidatingExportWord()


class _InlineShape:
    def __init__(
        self,
        *,
        type_code: int,
        xml: str,
        width: float = 200.0,
        height: float = 80.0,
        class_type: str = "",
    ) -> None:
        self.Type = type_code
        self.Range = _Range(xml)
        self.Width = width
        self.Height = height
        self.PictureFormat = None
        self.OLEFormat = SimpleNamespace(ClassType=class_type) if class_type else None


class ExternalObjectClassifierTests(unittest.TestCase):
    def test_plain_drawings_inline_picture_is_package_direct(self) -> None:
        host = _Host(tempfile.mkdtemp())
        shape = _InlineShape(type_code=3, xml=_drawing_xml(embed_rid="rId5"))

        info = host._classify_external_object(shape, section_key="drawings")

        self.assertEqual("package_direct", info["classifier"])
        self.assertEqual("inline_picture", info["object_kind"])

    def test_linked_picture_without_preview_is_activation_risky(self) -> None:
        host = _Host(tempfile.mkdtemp())
        shape = _InlineShape(type_code=4, xml=_drawing_xml(link_rid="rIdLink"))

        info = host._classify_external_object(shape, section_key="drawings")

        self.assertEqual("activation_risky", info["classifier"])
        self.assertEqual("linked_picture", info["object_kind"])

    def test_linked_ole_with_embedded_preview_prefers_preview_embedded(self) -> None:
        host = _Host(tempfile.mkdtemp())
        shape = _InlineShape(
            type_code=2,
            xml=_drawing_xml(embed_rid="rIdPreview", link_rid="rIdSource", prog_id="Visio.Drawing.15"),
            class_type="Visio.Drawing.15",
        )

        info = host._classify_external_object(shape, section_key="drawings")

        self.assertEqual("preview_embedded", info["classifier"])
        self.assertEqual("linked_ole", info["object_kind"])


class ExternalObjectPlaceholderRouteTests(unittest.TestCase):
    def test_floating_shape_keeps_frame_when_export_invalidates_original_com_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            host = _FloatingSaveAsHost(tmpdir)
            shape = _InvalidatingFloatingShape(width=200.0, height=80.0)
            para = SimpleNamespace(
                Range=SimpleNamespace(
                    Start=10,
                    ShapeRange=_ShapeRange(shape),
                )
            )
            parent = host.xml.init_xml("cn-drawings")

            handled = host._process_floating_shapes(para, parent, "drawings")

            self.assertTrue(handled)
            img = next(parent.iter("img"))
            self.assertEqual("70.56", img.get("wi"))
            self.assertEqual("28.22", img.get("he"))
            self.assertEqual(["SAVEAS"], host.pipeline)

    def test_floating_vml_preview_uses_target_width_and_emits_frame_sized_xml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            host = _FloatingPreviewHost(tmpdir)
            shape = _InlineShape(
                type_code=13,
                xml=_drawing_xml(embed_rid="rIdPreview", prog_id="Visio.Drawing.15"),
                width=200.0,
                height=80.0,
                class_type="Visio.Drawing.15",
            )
            para = SimpleNamespace(
                Range=SimpleNamespace(
                    Start=10,
                    ShapeRange=_ShapeRange(shape),
                )
            )
            parent = host.xml.init_xml("cn-drawings")

            handled = host._process_floating_shapes(para, parent, "drawings")

            self.assertTrue(handled)
            self.assertEqual(834, host.preview_target_width_px)
            img = next(parent.iter("img"))
            self.assertEqual("70.56", img.get("wi"))
            self.assertEqual("28.22", img.get("he"))
            self.assertEqual(["PREVIEW"], host.pipeline)

    def test_visio_preview_uses_word_frame_target_width_and_frame_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            host = _PreviewHost(tmpdir)
            parent = SimpleNamespace(tag="cn-drawings")
            shape = _InlineShape(
                type_code=1,
                xml=_drawing_xml(embed_rid="rIdPreview", prog_id="Visio.Drawing.15"),
                width=200.0,
                height=80.0,
                class_type="Visio.Drawing.15",
            )

            filename, width_mm, height_mm, _ = host.handle_shape(shape, parent_node=parent)

            self.assertTrue(filename.startswith("obj_"), filename)
            self.assertEqual(834, host.preview_target_width_px)
            self.assertEqual((70.56, 28.22), (width_mm, height_mm))
            self.assertEqual(0, host.word.inline_export_calls)
            self.assertEqual(0, host.word.copy_calls)

    def test_activation_risky_inline_object_uses_placeholder_without_word_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            host = _Host(tmpdir)
            parent = SimpleNamespace(tag="cn-drawings")
            shape = _InlineShape(
                type_code=2,
                xml=_drawing_xml(link_rid="rIdSource", prog_id="Visio.Drawing.15"),
                class_type="Visio.Drawing.15",
            )

            filename, width_mm, height_mm, _ = host.handle_shape(shape, parent_node=parent)

            self.assertTrue(filename.startswith("obj_"), filename)
            self.assertTrue(os.path.exists(os.path.join(tmpdir, filename)))
            self.assertGreater(width_mm, 0.0)
            self.assertGreater(height_mm, 0.0)
            self.assertEqual(0, host.word.inline_export_calls)
            self.assertEqual(0, host.word.copy_calls)
            self.assertEqual(1, len(host.object_fallback_failures))
            failure = host.object_fallback_failures[0]
            self.assertEqual("activation_risky", failure["classifier"])
            self.assertEqual("placeholder_inserted", failure["resolution_code"])
            self.assertEqual("linked_ole", failure["object_kind"])


class ExternalObjectNoticeTests(unittest.TestCase):
    def test_single_notice_summarizes_object_fallback_failures(self) -> None:
        window = SimpleNamespace()
        result = {
            "object_fallback_failures": [
                {"section": "drawings", "object_kind": "linked_ole", "classifier": "activation_risky"},
                {"section": "description", "object_kind": "linked_picture", "classifier": "preview_embedded"},
            ]
        }

        notice = _build_single_fallback_notice(window, result)

        self.assertIsInstance(notice, str)
        self.assertIn("部分外部对象未能完整转换", notice)
        self.assertIn("说明书附图", notice)
        self.assertIn("说明书", notice)

    def test_batch_notice_summarizes_hit_files(self) -> None:
        window = SimpleNamespace(
            _batch_object_fallback_warn_files=[
                ("a.docx", 1, "linked_ole"),
                ("b.docx", 2, "linked_picture"),
            ]
        )

        notice = _build_batch_fallback_notice(window, enabled_sections={})

        self.assertIsInstance(notice, str)
        self.assertIn("部分外部对象未能完整转换", notice)
        self.assertIn("a.docx", notice)
        self.assertIn("b.docx", notice)


if __name__ == "__main__":
    unittest.main()
