from __future__ import annotations

import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from core.document_parser.image_equation_mixin import ImageEquationMixin
from core.document_parser.image_shape_mixin import ImageShapeMixin
from core.img_processor import ImageProcessor
from core.xml_generator import XMLBuilder


def _png_bytes(size: tuple[int, int] = (48, 24), color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _inline_paragraph(rid: str, *, crop_attrs: str = "") -> str:
    src_rect = f"<a:srcRect {crop_attrs}/>" if crop_attrs else ""
    return f"""
<w:p>
  <w:r>
    <w:drawing>
      <wp:inline>
        <a:graphic>
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic>
              <pic:blipFill>
                <a:blip r:embed="{rid}"/>
                {src_rect}
              </pic:blipFill>
            </pic:pic>
          </a:graphicData>
        </a:graphic>
      </wp:inline>
    </w:drawing>
  </w:r>
</w:p>
""".strip()


def _vml_paragraph(rid: str, *, floating: bool = False) -> str:
    position = "position:absolute;" if floating else ""
    return f"""
<w:p>
  <w:r>
    <w:pict>
      <v:shape style="{position}width:120pt;height:40pt">
        <v:imagedata r:id="{rid}"/>
      </v:shape>
    </w:pict>
  </w:r>
</w:p>
""".strip()


def _ole_preview_paragraph(rid: str) -> str:
    return f"""
<w:p>
  <w:r>
    <w:object>
      <v:shape style="width:200pt;height:80pt">
        <v:imagedata r:id="{rid}"/>
      </v:shape>
    </w:object>
  </w:r>
</w:p>
""".strip()


def _text_paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _table_with_inline(rid: str) -> str:
    return f"""
<w:tbl>
  <w:tr>
    <w:tc>
      <w:p>
        <w:r>
          <w:drawing>
            <wp:inline>
              <a:graphic>
                <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                  <pic:pic>
                    <pic:blipFill>
                      <a:blip r:embed="{rid}"/>
                    </pic:blipFill>
                  </pic:pic>
                </a:graphicData>
              </a:graphic>
            </wp:inline>
          </w:drawing>
        </w:r>
      </w:p>
    </w:tc>
  </w:tr>
</w:tbl>
""".strip()


def _write_test_docx(path: Path, paragraphs: list[str], rel_targets: dict[str, str], media: dict[str, bytes]) -> None:
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
  xmlns:v="urn:schemas-microsoft-com:vml">
  <w:body>
    {''.join(paragraphs)}
    <w:sectPr/>
  </w:body>
</w:document>
"""
    rels_rows = []
    for rid, target in rel_targets.items():
        rels_rows.append(
            f'<Relationship Id="{rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="{target}"/>'
        )
    rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {''.join(rels_rows)}
</Relationships>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", rels_xml)
        for zip_path, payload in media.items():
            zf.writestr(zip_path, payload)


def _write_sectioned_test_docx(
    path: Path,
    sections: list[tuple[str, list[str]]],
    rel_targets: dict[str, str],
    media: dict[str, bytes],
) -> None:
    header_text = {
        "claims": "权 利 要 求 书",
        "description": "说 明 书",
        "drawings": "说 明 书 附 图",
        "abstract": "说 明 书 摘 要",
    }
    body_parts: list[str] = []
    rels_rows = [
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/>'
        for rid, target in rel_targets.items()
    ]
    for index, (section_key, paragraphs) in enumerate(sections, start=1):
        body_parts.extend(paragraphs)
        header_rid = f"rHdr{index}"
        rels_rows.append(
            f'<Relationship Id="{header_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header{index}.xml"/>'
        )
        sect_pr = f'<w:sectPr><w:headerReference w:type="default" r:id="{header_rid}"/></w:sectPr>'
        if index == len(sections):
            body_parts.append(sect_pr)
        else:
            body_parts.append(f"<w:p><w:pPr>{sect_pr}</w:pPr></w:p>")

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
  xmlns:v="urn:schemas-microsoft-com:vml"><w:body>{''.join(body_parts)}</w:body></w:document>"""
    rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(rels_rows)}</Relationships>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", rels_xml)
        for index, (section_key, _) in enumerate(sections, start=1):
            zf.writestr(
                f"word/header{index}.xml",
                f"<w:hdr xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:p><w:r><w:t>{header_text[section_key]}</w:t></w:r></w:p></w:hdr>",
            )
        for zip_path, payload in media.items():
            zf.writestr(zip_path, payload)


class _DummyDrawingsHost(ImageShapeMixin):
    def __init__(self) -> None:
        self.config = {
            "jpeg_quality": 100,
            "jpeg_subsampling": 0,
        }


class _StubWord:
    def __init__(self, clean_docx: str) -> None:
        self.doc = SimpleNamespace(FullName=clean_docx)
        self.app = None

    def export_inline_shape_as_picture(self, shape_obj, output_path: str) -> bool:
        return False

    def copy_shape_to_clipboard(self, shape_obj) -> bool:
        return False


class _ExportImageWord(_StubWord):
    def export_inline_shape_as_picture(self, shape_obj, output_path: str) -> bool:
        img = Image.new("RGB", (1200, 800), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle((500, 120, 720, 260), outline="black", width=4)
        img.save(output_path, format="JPEG", quality=100, subsampling=0)
        return True


class _StubImageProcessor:
    def __init__(self) -> None:
        self._last_drawings_opt_meta = {}
        self.allow_edge_crop_calls = []

    def optimize_drawings_image_file(
        self,
        output_path: str,
        *,
        ratio_num: float,
        ratio_den: float,
        allow_edge_crop: bool = True,
    ):
        self.allow_edge_crop_calls.append(bool(allow_edge_crop))
        with Image.open(output_path) as img:
            return img.size

    def calculate_drawings_dimensions(self, original_width_point, original_height_point, processed_img_size):
        return (70.56, 28.22)


class _DrawingsHandleHost(ImageShapeMixin):
    def __init__(self, *, clean_docx: str, temp_dir: str) -> None:
        self.word = _StubWord(clean_docx)
        self.img_proc = _StubImageProcessor()
        self.input_file_path = clean_docx
        self.config = {
            "jpeg_quality": 100,
            "jpeg_subsampling": 0,
            "paths": {"temp_dir": temp_dir},
        }

    def _is_equation_shape(self, shape_obj) -> bool:
        return False


class _PipelineHost(ImageEquationMixin):
    pass


class _FakeRange:
    def __init__(self, word_open_xml: str) -> None:
        self.WordOpenXML = word_open_xml


class _FakeShape:
    def __init__(self, *, xml: str, width: float = 200.0, height: float = 80.0, pictureformat=None) -> None:
        self.Range = _FakeRange(xml)
        self.Type = 3
        self.Width = width
        self.Height = height
        self.PictureFormat = pictureformat


class DrawingsFidelityPolicyTests(unittest.TestCase):
    def test_emf_package_media_renders_to_jpg_at_target_width(self) -> None:
        target_width_px = 1800

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "emf.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[_text_paragraph("说明书附图"), _inline_paragraph("rIdDraw1")],
                rel_targets={"rIdDraw1": "media/draw1.emf"},
                media={"word/media/draw1.emf": b"fake-emf-bytes"},
            )
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            host.config["drawings_fidelity"] = {
                "mode": "smart",
                "target_dpi": 300,
                "output_format": "jpg",
                "low_dpi_policy": "warn",
            }

            def fake_render(
                emf_bytes,
                output_path,
                *,
                scale=1.0,
                min_width=1000,
                trim_render_margin=False,
            ):
                self.assertEqual(b"fake-emf-bytes", emf_bytes)
                self.assertEqual(target_width_px, min_width)
                self.assertTrue(trim_render_margin)
                Image.new("RGB", (int(min_width), 900), "white").save(output_path, format="PNG")
                return True

            host._render_emf_bytes_to_png = fake_render

            extracted = host._extract_drawings_media_zip_path_to_temp(
                zip_path="word/media/draw1.emf",
                filename_prefix="img_",
                force_jpg_for_non_tiff=True,
                target_width_px=target_width_px,
            )

            self.assertIsNotNone(extracted)
            filename, output_path = extracted
            self.assertTrue(filename.endswith(".jpg"))
            with Image.open(output_path) as img:
                self.assertEqual("JPEG", img.format)
                self.assertEqual(target_width_px, img.size[0])

            meta = getattr(host, "_drawings_media_quality_meta_by_file", {}).get(filename)
            self.assertIsInstance(meta, dict)
            self.assertEqual("emf_high_fidelity_rendered", meta.get("kind"))
            self.assertEqual(target_width_px, meta.get("target_width_px"))

    def test_low_pixel_png_keeps_source_size_but_records_effective_dpi_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "low-png.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[_inline_paragraph("rIdDraw1")],
                rel_targets={"rIdDraw1": "media/draw1.png"},
                media={
                    "word/media/draw1.png": _png_bytes(size=(120, 40), color=(0, 255, 0)),
                },
            )
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            host.forced_section_key = "drawings"
            host.config["drawings_fidelity"] = {
                "mode": "smart",
                "target_dpi": 300,
                "output_format": "jpg",
                "low_dpi_policy": "warn",
            }
            parent = SimpleNamespace(tag="cn-drawings")
            shape = _FakeShape(xml="<w:p xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")

            filename, width_mm, height_mm, _ = host.handle_shape(shape, parent_node=parent)

            output_path = Path(tmpdir) / str(filename)
            with Image.open(output_path) as img:
                self.assertEqual((120, 40), img.size)
            self.assertEqual((70.56, 28.22), (width_mm, height_mm))

            warnings = getattr(host, "_drawings_quality_warnings", [])
            low_dpi = [item for item in warnings if item.get("kind") == "low_effective_dpi"]
            self.assertEqual(1, len(low_dpi))
            self.assertEqual(filename, low_dpi[0].get("temp_file"))
            self.assertEqual(".png", low_dpi[0].get("source_ext"))
            self.assertLess(float(low_dpi[0].get("effective_dpi")), 300.0)

    def test_drawings_jpg_xml_keeps_jpg_format_and_ft_filename(self) -> None:
        xml = XMLBuilder({"drawings_img_max_wi_mm": 164.0, "drawings_img_max_he_mm": 230.0})
        parent = xml.init_xml("cn-drawings")

        img = xml.create_image_node(parent, "ft_1.jpg", 100.0, 50.0, img_type="draw", inline=False)

        self.assertEqual("ft_1.jpg", img.get("file"))
        self.assertEqual("jpg", img.get("img-format"))

    def test_media_extract_allowed_without_crop(self) -> None:
        host = _DummyDrawingsHost()
        self.assertTrue(host._should_extract_drawings_from_media(crop_info=None, explicit_pf_crop=None))

    def test_media_extract_allowed_with_exact_openxml_crop(self) -> None:
        host = _DummyDrawingsHost()
        self.assertTrue(
            host._should_extract_drawings_from_media(
                crop_info={"l": 0.1, "t": 0.0, "r": 0.0, "b": 0.0},
                package_crop_info=None,
                explicit_pf_crop=None,
            )
        )

    def test_media_extract_blocked_with_pictureformat_only_crop(self) -> None:
        host = _DummyDrawingsHost()
        self.assertFalse(
            host._should_extract_drawings_from_media(
                crop_info=None,
                package_crop_info=None,
                explicit_pf_crop={"_source": "PictureFormat", "_raw": {"CropLeft": 12.0}},
            )
        )

    def test_media_extract_allowed_with_package_exact_crop_even_when_runtime_only_has_pictureformat_crop(self) -> None:
        host = _DummyDrawingsHost()
        self.assertTrue(
            host._should_extract_drawings_from_media(
                crop_info=None,
                package_crop_info={"l": 0.1, "t": 0.0, "r": 0.0, "b": 0.0},
                explicit_pf_crop={"_source": "PictureFormat", "_raw": {"CropLeft": 12.0}},
            )
        )
        self.assertEqual(
            "package_exact",
            host._get_drawings_media_gate_reason(
                crop_info=None,
                package_crop_info={"l": 0.1, "t": 0.0, "r": 0.0, "b": 0.0},
                explicit_pf_crop={"_source": "PictureFormat", "_raw": {"CropLeft": 12.0}},
            ),
        )

    def test_drawings_dimensions_follow_word_display_frame_ratio(self) -> None:
        proc = ImageProcessor({"width_factor": 0.3528, "max_width_mm": 165.0})
        width_mm, height_mm = proc.calculate_drawings_dimensions(
            original_width_point=200.0,
            original_height_point=80.0,
            processed_img_size=(1200, 600),
        )

        self.assertEqual((70.56, 28.22), (width_mm, height_mm))

    def test_drawings_dimensions_fallback_to_processed_ratio_when_height_invalid(self) -> None:
        proc = ImageProcessor({"width_factor": 0.3528, "max_width_mm": 165.0})
        width_mm, height_mm = proc.calculate_drawings_dimensions(
            original_width_point=200.0,
            original_height_point=0.0,
            processed_img_size=(1200, 600),
        )

        self.assertEqual((70.56, 35.28), (width_mm, height_mm))

    def test_package_queue_requires_resolved_scope_unless_forced_drawings(self) -> None:
        host = _DummyDrawingsHost()
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "queue.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[
                    _text_paragraph("说明书"),
                    _inline_paragraph("rIdDesc"),
                    _table_with_inline("rIdTable"),
                    _text_paragraph("说明书附图"),
                    _inline_paragraph("rIdDraw1", crop_attrs='l="10000"'),
                    _inline_paragraph("rIdDraw2"),
                    _text_paragraph("说明书摘要"),
                    _inline_paragraph("rIdAbstract"),
                ],
                rel_targets={
                    "rIdDesc": "media/desc.png",
                    "rIdTable": "media/table.png",
                    "rIdDraw1": "media/draw1.png",
                    "rIdDraw2": "media/draw2.png",
                    "rIdAbstract": "media/abstract.png",
                },
                media={},
            )

            items = host._build_drawings_inline_package_queue(str(docx_path))
            self.assertEqual([], items)

            host.forced_section_key = "drawings"
            items = host._build_drawings_inline_package_queue(str(docx_path))

        self.assertEqual(["rIdDesc", "rIdDraw1", "rIdDraw2", "rIdAbstract"], [item["rid"] for item in items])
        self.assertTrue(all(item["section"] == "drawings" for item in items))
        self.assertEqual("word/media/draw1.png", items[1]["zip_path"])
        self.assertEqual({"l": 0.1, "t": 0.0, "r": 0.0, "b": 0.0}, items[1]["crop_info"])

    def test_package_queue_includes_vml_inline_in_document_order_and_excludes_vml_floating(self) -> None:
        host = _DummyDrawingsHost()
        host.forced_section_key = "drawings"
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "vml-queue.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[
                    _inline_paragraph("rIdDrawingML"),
                    _vml_paragraph("rIdVmlInline"),
                    _vml_paragraph("rIdVmlFloating", floating=True),
                ],
                rel_targets={
                    "rIdDrawingML": "media/drawingml.png",
                    "rIdVmlInline": "media/vml-inline.png",
                    "rIdVmlFloating": "media/vml-floating.png",
                },
                media={},
            )

            items = host._build_drawings_inline_package_queue(str(docx_path))

        self.assertEqual(["rIdDrawingML", "rIdVmlInline"], [item["rid"] for item in items])
        self.assertEqual(["drawingml_inline", "vml_inline"], [item["object_kind"] for item in items])

    def test_package_queue_includes_ole_preview_in_document_order(self) -> None:
        host = _DummyDrawingsHost()
        host.forced_section_key = "drawings"
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "ole-preview-queue.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[
                    _ole_preview_paragraph("rIdOlePreview"),
                    _inline_paragraph("rIdDrawingML"),
                ],
                rel_targets={
                    "rIdOlePreview": "media/ole-preview.png",
                    "rIdDrawingML": "media/drawingml.png",
                },
                media={},
            )

            items = host._build_drawings_inline_package_queue(str(docx_path))

        self.assertEqual(["rIdOlePreview", "rIdDrawingML"], [item["rid"] for item in items])
        self.assertEqual(["vml_ole_preview", "drawingml_inline"], [item["object_kind"] for item in items])

    def test_visio_preview_uses_package_queue_when_runtime_relationship_id_is_remapped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "visio-preview.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[_ole_preview_paragraph("rIdPackagePreview")],
                rel_targets={"rIdPackagePreview": "media/preview.png"},
                media={"word/media/preview.png": _png_bytes(size=(300, 120), color=(0, 0, 0))},
            )
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            host.forced_section_key = "drawings"
            shape = SimpleNamespace(
                Type=1,
                Width=200.0,
                Height=80.0,
                PictureFormat=None,
                OLEFormat=SimpleNamespace(ClassType="Visio.Drawing.15"),
                Range=_FakeRange(_ole_preview_paragraph("rIdRuntimePreview")),
            )
            parent = SimpleNamespace(tag="cn-drawings")

            filename, width_mm, height_mm, _ = host.handle_shape(shape, parent_node=parent)

            self.assertTrue(str(filename).endswith(".jpg"))
            self.assertTrue((Path(tmpdir) / str(filename)).is_file())
            self.assertEqual((70.56, 28.22), (width_mm, height_mm))
            state = host._get_drawings_inline_package_queue_state()
            self.assertEqual(1, state["index"])
            self.assertFalse(bool(state["disabled"]))

    def test_package_queue_rebuild_rebinds_state_to_reopened_docx(self) -> None:
        host = _DummyDrawingsHost()
        host.forced_section_key = "drawings"
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.docx"
            reopened_path = Path(tmpdir) / "temp_clean.docx"
            _write_test_docx(
                source_path,
                paragraphs=[_inline_paragraph("rIdSource")],
                rel_targets={"rIdSource": "media/source.png"},
                media={},
            )
            _write_test_docx(
                reopened_path,
                paragraphs=[_vml_paragraph("rIdReopened")],
                rel_targets={"rIdReopened": "media/reopened.png"},
                media={},
            )
            host.word = SimpleNamespace(doc=SimpleNamespace(FullName=str(source_path)))
            old_state = host._get_drawings_inline_package_queue_state()
            host.word.doc.FullName = str(reopened_path)

            new_state = host._rebuild_drawings_inline_package_queue_state()

        self.assertEqual("rIdSource", old_state["items"][0]["rid"])
        self.assertEqual(str(reopened_path.resolve()), new_state["docx_path"])
        self.assertEqual(["rIdReopened"], [item["rid"] for item in new_state["items"]])
        self.assertEqual(0, new_state["index"])

    def test_non_drawings_handle_paths_do_not_advance_drawings_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "four-sections.docx"
            _write_sectioned_test_docx(
                docx_path,
                sections=[
                    ("claims", [_inline_paragraph("rIdClaims")]),
                    ("description", [_inline_paragraph("rIdDescription")]),
                    ("drawings", [_inline_paragraph("rIdDraw1", crop_attrs='l="10000"'), _inline_paragraph("rIdDraw2")]),
                    ("abstract", [_inline_paragraph("rIdAbstract")]),
                ],
                rel_targets={
                    "rIdClaims": "media/claims.png",
                    "rIdDescription": "media/description.png",
                    "rIdDraw1": "media/draw1.png",
                    "rIdDraw2": "media/draw2.png",
                    "rIdAbstract": "media/abstract.png",
                },
                media={"word/media/draw1.png": _png_bytes(size=(120, 40), color=(0, 255, 0))},
            )
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            state = host._get_drawings_inline_package_queue_state()
            self.assertEqual(["rIdDraw1", "rIdDraw2"], [item["rid"] for item in state["items"]])
            self.assertEqual({"l": 0.1, "t": 0.0, "r": 0.0, "b": 0.0}, state["items"][0]["crop_info"])
            self.assertIsNone(host._consume_drawings_inline_package_item(runtime_rid="rIdDescription", section_key="description"))

            for section_key, rid, parent_tag in (
                ("claims", "rIdClaims", "cn-claims"),
                ("description", "rIdDescription", "cn-description"),
                ("abstract", "rIdAbstract", "cn-abstract"),
            ):
                result = host.handle_shape(
                    _FakeShape(xml=_inline_paragraph(rid)),
                    parent_node=SimpleNamespace(tag=parent_tag),
                    section_key=section_key,
                )
                self.assertEqual((None, 0, 0, None), result)
                self.assertEqual(0, state["index"])
                self.assertFalse(bool(state["disabled"]))

            filename, width_mm, height_mm, _ = host.handle_shape(
                _FakeShape(xml="<w:p xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>"),
                parent_node=SimpleNamespace(tag="cn-drawings"),
            )

            with Image.open(Path(tmpdir) / str(filename)) as img:
                self.assertEqual((108, 40), img.size)
            self.assertEqual((70.56, 28.22), (width_mm, height_mm))
            self.assertEqual(1, state["index"])
            self.assertFalse(bool(state["disabled"]))
            self.assertEqual([False], host.img_proc.allow_edge_crop_calls)

    def test_package_queue_filters_to_drawings_section_when_docx_sections_are_resolvable(self) -> None:
        host = _DummyDrawingsHost()
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "queue.docx"
            document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    {_inline_paragraph("rIdAbstract")}
    <w:p>
      <w:pPr>
        <w:sectPr>
          <w:headerReference w:type="default" r:id="rHdrAbstract"/>
        </w:sectPr>
      </w:pPr>
    </w:p>
    {_inline_paragraph("rIdDraw1", crop_attrs='l="10000"')}
    {_inline_paragraph("rIdDraw2")}
    <w:sectPr>
      <w:headerReference w:type="default" r:id="rHdrDraw"/>
    </w:sectPr>
  </w:body>
</w:document>
"""
            rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdAbstract" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/abstract.png"/>
  <Relationship Id="rIdDraw1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/draw1.png"/>
  <Relationship Id="rIdDraw2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/draw2.png"/>
  <Relationship Id="rHdrAbstract" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rHdrDraw" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header2.xml"/>
</Relationships>
"""
            content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
            header_abstract = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:t>\u6458 \u8981 \u9644 \u56fe</w:t></w:r></w:p>
</w:hdr>
"""
            header_drawings = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:t>\u8bf4 \u660e \u4e66 \u9644 \u56fe</w:t></w:r></w:p>
</w:hdr>
"""
            with zipfile.ZipFile(docx_path, "w") as zf:
                zf.writestr("[Content_Types].xml", content_types)
                zf.writestr("word/document.xml", document_xml)
                zf.writestr("word/_rels/document.xml.rels", rels_xml)
                zf.writestr("word/header1.xml", header_abstract)
                zf.writestr("word/header2.xml", header_drawings)

            items = host._build_drawings_inline_package_queue(str(docx_path))

        self.assertEqual(["rIdDraw1", "rIdDraw2"], [item["rid"] for item in items])
        self.assertEqual("drawings", items[0]["section"])
        self.assertEqual({"l": 0.1, "t": 0.0, "r": 0.0, "b": 0.0}, items[0]["crop_info"])

    def test_runtime_missing_rid_can_fall_back_to_package_queue_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "queue.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[_inline_paragraph("rIdDraw1")],
                rel_targets={"rIdDraw1": "media/draw1.png"},
                media={
                    "word/media/draw1.png": _png_bytes(size=(120, 40), color=(0, 255, 0)),
                },
            )
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            host.forced_section_key = "drawings"
            parent = SimpleNamespace(tag="cn-drawings")
            shape = _FakeShape(xml="<w:p xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")

            filename, width_mm, height_mm, _ = host.handle_shape(shape, parent_node=parent)

            self.assertTrue(str(filename).endswith(".jpg"))
            self.assertTrue(os.path.exists(Path(tmpdir) / str(filename)))
            self.assertEqual((70.56, 28.22), (width_mm, height_mm))
            state = host._get_drawings_inline_package_queue_state()
            self.assertEqual(1, state["index"])
            self.assertFalse(bool(state["disabled"]))
            self.assertEqual([False], host.img_proc.allow_edge_crop_calls)

    def test_package_exact_crop_can_unlock_media_when_runtime_only_reports_pictureformat_crop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "queue.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[_inline_paragraph("rIdDraw1", crop_attrs='l="10000"')],
                rel_targets={"rIdDraw1": "media/draw1.png"},
                media={
                    "word/media/draw1.png": _png_bytes(size=(120, 40), color=(0, 255, 0)),
                },
            )
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            host.forced_section_key = "drawings"
            parent = SimpleNamespace(tag="cn-drawings")
            shape = _FakeShape(
                xml="<w:p xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>",
                pictureformat=SimpleNamespace(CropLeft=12.0, CropRight=0.0, CropTop=0.0, CropBottom=0.0),
            )

            filename, width_mm, height_mm, _ = host.handle_shape(shape, parent_node=parent)

            output_path = Path(tmpdir) / str(filename)
            self.assertTrue(str(filename).endswith(".jpg"))
            self.assertTrue(output_path.exists())
            with Image.open(output_path) as img:
                self.assertEqual((108, 40), img.size)
            self.assertEqual((70.56, 28.22), (width_mm, height_mm))
            state = host._get_drawings_inline_package_queue_state()
            self.assertEqual(1, state["index"])
            self.assertFalse(bool(state["disabled"]))
            self.assertEqual([False], host.img_proc.allow_edge_crop_calls)

    def test_corrupt_package_raster_aborts_before_word_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "corrupt-media.docx"
            valid_png = _png_bytes(size=(120, 40), color=(0, 255, 0))
            _write_test_docx(
                docx_path,
                paragraphs=[_inline_paragraph("rIdDraw1")],
                rel_targets={"rIdDraw1": "media/draw1.png"},
                media={"word/media/draw1.png": valid_png[: len(valid_png) // 2]},
            )
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            host.forced_section_key = "drawings"
            parent = SimpleNamespace(tag="cn-drawings")
            shape = _FakeShape(xml=_inline_paragraph("rIdDraw1"))

            with self.assertRaisesRegex(RuntimeError, "内嵌图片数据已损坏"):
                host.handle_shape(shape, parent_node=parent)

            warnings = getattr(host, "_drawings_quality_warnings", [])
            self.assertEqual(1, len(warnings))
            self.assertEqual("source_media_corrupt", warnings[0]["kind"])
            self.assertEqual("word/media/draw1.png", warnings[0]["zip_path"])
            self.assertEqual([], host.img_proc.allow_edge_crop_calls)

    def test_queue_ignores_runtime_fragment_rid_mismatch(self) -> None:
        host = _DummyDrawingsHost()
        host.forced_section_key = "drawings"
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "queue.docx"
            _write_test_docx(
                docx_path,
                paragraphs=[
                    _text_paragraph("说明书附图"),
                    _inline_paragraph("rIdDraw1"),
                ],
                rel_targets={"rIdDraw1": "media/draw1.png"},
                media={"word/media/draw1.png": _png_bytes()},
            )
            host.word = SimpleNamespace(doc=SimpleNamespace(FullName=str(docx_path)))

            item = host._consume_drawings_inline_package_item(runtime_rid="rIdMismatch", section_key="drawings")

            self.assertEqual("rIdDraw1", item["rid"])
            state = host._get_drawings_inline_package_queue_state()
            self.assertFalse(bool(state["disabled"]))
            self.assertEqual(1, state["index"])

    def test_drawings_package_queue_order_wins_over_reused_runtime_rid(self) -> None:
        sizes = [(40 + idx, 20 + idx) for idx in range(1, 8)]
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "queue.docx"
            rel_targets = {
                f"rIdDraw{idx}": f"media/draw{idx}.png"
                for idx in range(1, 8)
            }
            media = {
                f"word/media/draw{idx}.png": _png_bytes(size=sizes[idx - 1], color=(idx * 20, 0, 255 - idx * 20))
                for idx in range(1, 8)
            }
            _write_test_docx(
                docx_path,
                paragraphs=[_inline_paragraph(f"rIdDraw{idx}") for idx in range(1, 8)],
                rel_targets=rel_targets,
                media=media,
            )
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            host.forced_section_key = "drawings"
            parent = SimpleNamespace(tag="cn-drawings")
            actual_sizes = []

            for _ in range(7):
                shape = _FakeShape(xml=_inline_paragraph("rIdDraw1"))
                filename, _, _, _ = host.handle_shape(shape, parent_node=parent)
                with Image.open(Path(tmpdir) / str(filename)) as img:
                    actual_sizes.append(img.size)

            self.assertEqual(sizes, actual_sizes)
            state = host._get_drawings_inline_package_queue_state()
            self.assertEqual(7, state["index"])
            self.assertFalse(bool(state["disabled"]))
            self.assertEqual([False] * 7, host.img_proc.allow_edge_crop_calls)

    def test_drawings_fallback_render_allows_edge_crop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "empty.docx"
            _write_test_docx(docx_path, paragraphs=[], rel_targets={}, media={})
            host = _DrawingsHandleHost(clean_docx=str(docx_path), temp_dir=tmpdir)
            host.word = _ExportImageWord(str(docx_path))
            parent = SimpleNamespace(tag="cn-drawings")
            shape = _FakeShape(xml="<w:p xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")

            filename, _, _, _ = host.handle_shape(shape, parent_node=parent)

            self.assertTrue(str(filename).endswith(".jpg"))
            self.assertEqual([True], host.img_proc.allow_edge_crop_calls)

    def test_image_pipeline_stats_accept_drawings_media_and_saveas(self) -> None:
        host = _PipelineHost()
        host._img_pipeline_stats = {"EMF": 0, "PDF": 0, "BITMAP": 0, "MEDIA": 0, "SAVEAS": 0}

        host._record_image_pipeline("MEDIA")
        host._record_image_pipeline("SAVEAS")

        self.assertEqual(1, host._img_pipeline_stats["MEDIA"])
        self.assertEqual(1, host._img_pipeline_stats["SAVEAS"])

    def test_optimize_drawings_skips_edge_crop_when_explicit_crop_already_applied(self) -> None:
        proc = ImageProcessor({"jpeg_quality": 100, "jpeg_subsampling": 0})
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "explicit-crop.jpg"
            img = Image.new("RGB", (200, 120), "white")
            draw = ImageDraw.Draw(img)
            draw.rectangle((20, 20, 140, 100), outline="black", width=2)
            draw.text((182, 42), "3", fill="black")
            img.save(image_path, format="JPEG", quality=100, subsampling=0)

            out_size = proc.optimize_drawings_image_file(
                str(image_path),
                ratio_num=5,
                ratio_den=3,
                allow_edge_crop=False,
            )

            self.assertEqual((200, 120), out_size)
            self.assertFalse(bool(proc._last_drawings_opt_meta.get("edge_cropped")))
            self.assertTrue(bool(proc._last_drawings_opt_meta.get("edge_crop_skipped")))

    def test_optimize_drawings_can_skip_edge_crop_and_still_pad_to_ratio(self) -> None:
        proc = ImageProcessor({"jpeg_quality": 100, "jpeg_subsampling": 0})
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "ratio-pad.jpg"
            img = Image.new("RGB", (100, 100), "white")
            draw = ImageDraw.Draw(img)
            draw.line((0, 50, 99, 50), fill="black", width=1)
            img.save(image_path, format="JPEG", quality=100, subsampling=0)

            out_size = proc.optimize_drawings_image_file(
                str(image_path),
                ratio_num=2,
                ratio_den=1,
                allow_edge_crop=False,
            )

            self.assertEqual((200, 100), out_size)
            with Image.open(image_path) as out_img:
                self.assertEqual((200, 100), out_img.size)
            self.assertFalse(bool(proc._last_drawings_opt_meta.get("edge_cropped")))
            self.assertTrue(bool(proc._last_drawings_opt_meta.get("edge_crop_skipped")))

    def test_optimize_drawings_crops_page_level_white_margin_when_allowed(self) -> None:
        proc = ImageProcessor({"jpeg_quality": 100, "jpeg_subsampling": 0})
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "pdf-page-margin.jpg"
            img = Image.new("RGB", (1200, 800), "white")
            draw = ImageDraw.Draw(img)
            draw.rectangle((500, 120, 720, 260), outline="black", width=4)
            draw.line((520, 240, 700, 140), fill="black", width=3)
            img.save(image_path, format="JPEG", quality=100, subsampling=0)

            out_size = proc.optimize_drawings_image_file(
                str(image_path),
                ratio_num=2,
                ratio_den=1,
                allow_edge_crop=True,
            )

            self.assertIsNotNone(out_size)
            self.assertLess(out_size[0], 500)
            self.assertLess(out_size[1], 260)
            self.assertTrue(bool(proc._last_drawings_opt_meta.get("edge_cropped")))
            self.assertFalse(bool(proc._last_drawings_opt_meta.get("edge_crop_skipped")))


if __name__ == "__main__":
    unittest.main()
