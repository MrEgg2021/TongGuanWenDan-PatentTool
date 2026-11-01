from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lxml import etree
from PIL import Image, ImageDraw

from core.document_parser.paragraph_mixin_impl import ParagraphTraversalMixin
from core.document_parser.structure_mixin_impl import StructureNormalizationMixin


class _Host(ParagraphTraversalMixin):
    def __init__(self, temp_dir: str) -> None:
        self.config = {"paths": {"temp_dir": temp_dir}, "temp_dir": temp_dir}
        self.sections = {"drawings": etree.Element("cn-drawings")}


class _StructureHost(ParagraphTraversalMixin, StructureNormalizationMixin):
    def __init__(self, temp_dir: str) -> None:
        self.config = {"paths": {"temp_dir": temp_dir}, "temp_dir": temp_dir}
        self.sections = {"drawings": etree.Element("cn-drawings")}


def _write_image(path: Path, *, blank: bool) -> None:
    img = Image.new("RGB", (500, 500), "white")
    if not blank:
        draw = ImageDraw.Draw(img)
        draw.rectangle((100, 100, 400, 260), outline="black", width=8)
        draw.line((120, 240, 380, 120), fill="black", width=6)
    img.save(path, format="JPEG", quality=100, subsampling=0)


class DrawingsBlankPlaceholderFilterTests(unittest.TestCase):
    def test_drawings_label_registration_ignores_slash_and_non_label_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _Host(td)
            host._init_drawings_label_state()

            for text in ("/", "普通说明文字", "", " 图1 ", "图2"):
                host._register_drawings_label_text(text)

        self.assertEqual(["图1", "图2"], host._drawings_label_lines)

    def test_blank_placeholders_are_removed_before_figure_labels_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _Host(td)
            host._init_drawings_label_state()
            for idx in range(1, 7):
                filename = f"ft_{idx}.jpg"
                _write_image(Path(td) / filename, blank=idx in {1, 3, 5})
                p = etree.SubElement(host.sections["drawings"], "p")
                etree.SubElement(p, "img", file=filename)
            for label in ("图1", "图2", "图3"):
                host._register_drawings_label_text(label)

            host._finalize_drawings_labels()

            remaining = [img for img in host.sections["drawings"].iter("img") if img.get("file")]
            labels = [host._drawings_img_label_by_file.get(str(img.get("file"))) for img in remaining]

        self.assertEqual(["ft_2.jpg", "ft_4.jpg", "ft_6.jpg"], [img.get("file") for img in remaining])
        self.assertEqual(["图1", "图2", "图3"], labels)
        self.assertEqual(3, host._drawings_label_report["img_count"])
        self.assertEqual(0, host._drawings_label_report["missing_count"])

    def test_normalize_drawings_structure_uses_file_label_map_after_reiterating_lxml_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _StructureHost(td)
            host._init_drawings_label_state()
            for idx in range(1, 4):
                filename = f"ft_{idx}.jpg"
                _write_image(Path(td) / filename, blank=False)
                p = etree.SubElement(host.sections["drawings"], "p")
                etree.SubElement(p, "img", file=filename)
                host._register_drawings_label_text(f"图{idx}")

            host._finalize_drawings_labels()
            host._normalize_drawings_structure()

            labels = [fig.get("figure-labels") for fig in host.sections["drawings"].iter("figure")]

        self.assertEqual(["图1", "图2", "图3"], labels)

    def test_subfigure_suffixes_are_preserved_in_figure_labels(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _StructureHost(td)
            host._init_drawings_label_state()
            source_labels = ("图 10 （ A ）", "图10（B）", "图14(A)", "图14(B)")
            for idx, label in enumerate(source_labels, 1):
                filename = f"ft_{idx}.jpg"
                _write_image(Path(td) / filename, blank=False)
                p = etree.SubElement(host.sections["drawings"], "p")
                etree.SubElement(p, "img", file=filename)
                host._register_drawings_label_text(label)

            host._finalize_drawings_labels()
            host._normalize_drawings_structure()

            labels = [fig.get("figure-labels") for fig in host.sections["drawings"].iter("figure")]

        self.assertEqual(["图10（A）", "图10（B）", "图14(A)", "图14(B)"], labels)
        self.assertEqual([], host._drawings_label_report["duplicate_labels"])

    def test_duplicate_detection_uses_full_subfigure_label(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _Host(td)
            host._init_drawings_label_state()
            for idx in range(1, 3):
                filename = f"ft_{idx}.jpg"
                _write_image(Path(td) / filename, blank=False)
                p = etree.SubElement(host.sections["drawings"], "p")
                etree.SubElement(p, "img", file=filename)
                host._register_drawings_label_text("图10（A）")

            host._finalize_drawings_labels()

        self.assertEqual(["图10（A）"], host._drawings_label_report["duplicate_labels"])

    def test_slash_separators_do_not_shift_valid_drawings_labels(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            host = _StructureHost(td)
            host._init_drawings_label_state()
            for idx in range(1, 4):
                filename = f"ft_{idx}.jpg"
                _write_image(Path(td) / filename, blank=False)
                p = etree.SubElement(host.sections["drawings"], "p")
                etree.SubElement(p, "img", file=filename)
                host._register_drawings_label_text("/")
                host._register_drawings_label_text(f"图{idx}")

            host._finalize_drawings_labels()
            host._normalize_drawings_structure()

            labels = [fig.get("figure-labels") for fig in host.sections["drawings"].iter("figure")]

        self.assertEqual(["图1", "图2", "图3"], labels)


if __name__ == "__main__":
    unittest.main()
