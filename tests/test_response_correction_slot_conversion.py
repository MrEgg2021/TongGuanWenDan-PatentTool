from __future__ import annotations

import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from core.archive_safety import ArchiveBudget, ArchiveSafetyError
from core.response_correction.slot_conversion import convert_document_slot, extract_preconverted_slot_package


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _zip_bytes(entries: dict[str, str | bytes]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, value in entries.items():
            payload = value.encode("utf-8") if isinstance(value, str) else value
            zf.writestr(name, payload)
    return buf.getvalue()


class ResponseCorrectionSlotConversionTests(unittest.TestCase):
    def test_preconverted_zip_rejects_unsafe_members_before_overwriting_targets(self) -> None:
        xml = '<cn-application-body><description /></cn-application-body>'
        for unsafe in (
            "case/100002/../escaped.txt",
            "case\\100002\\..\\escaped.txt",
            "/case/100002/escaped.txt",
            "C:/case/100002/escaped.txt",
            "//server/share/escaped.txt",
            "case/100002/.. /escaped.txt",
            "case/100002/CON.txt",
        ):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / "source.zip"
                source.write_bytes(_zip_bytes({"case/100002/100002.xml": xml, unsafe: b"overwritten"}))
                out = root / "out"
                _write(out / "100002.xml", "original")
                _write(root / "escaped.txt", "sentinel")
                with self.assertRaisesRegex(ArchiveSafetyError, "路径不安全"):
                    extract_preconverted_slot_package(str(source), "100002", str(out))
                self.assertEqual((out / "100002.xml").read_text(encoding="utf-8"), "original")
                self.assertEqual((root / "escaped.txt").read_text(encoding="utf-8"), "sentinel")

    def test_preconverted_zip_rejects_nested_over_budget_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner = _zip_bytes({"case/100002/100002.xml": '<cn-application-body><description /></cn-application-body>'})
            source = root / "source.zip"
            source.write_bytes(_zip_bytes({"inner.zip": inner}))
            out = root / "out"
            _write(out / "100002.xml", "original")
            with patch("core.response_correction.slot_conversion.ArchiveBudget", return_value=ArchiveBudget(max_total_bytes=len(inner) + 10)):
                with self.assertRaisesRegex(ArchiveSafetyError, "总解压大小"):
                    extract_preconverted_slot_package(str(source), "100002", str(out))
            self.assertEqual((out / "100002.xml").read_text(encoding="utf-8"), "original")

    def test_preconverted_zip_corrupt_media_keeps_existing_slot_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.zip"
            with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("case/100002/100002.xml", '<cn-application-body><description /></cn-application-body>')
                archive.writestr("case/100002/media.jpg", b"BROKEN_A")
            source.write_bytes(source.read_bytes().replace(b"BROKEN_A", b"BROKEN_B", 1))
            out = root / "out"
            _write(out / "100002.xml", "original")
            _write(out / "media.jpg", "sentinel")
            with self.assertRaises(zipfile.BadZipFile):
                extract_preconverted_slot_package(str(source), "100002", str(out))
            self.assertEqual((out / "100002.xml").read_text(encoding="utf-8"), "original")
            self.assertEqual((out / "media.jpg").read_text(encoding="utf-8"), "sentinel")
            self.assertEqual(list(out.glob(".slot_extract_*")), [])

    def test_extract_preconverted_slot_package_accepts_direct_inner_zip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_zip = root / "100001.zip"
            source_zip.write_bytes(
                _zip_bytes(
                    {
                        "10000009/100001/100001.xml": '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>权 利 要 求 书</claim-text></claim><claim id="c1_cl002" num="2"><claim-text>一种装置。</claim-text></claim></cn-claims></cn-application-body>',
                        "10000009/100001/img_01.jpg": b"image",
                    }
                )
            )
            out = root / "out"

            result = extract_preconverted_slot_package(str(source_zip), "100001", str(out))

            self.assertEqual(Path(result.xml_path), out / "100001.xml")
            self.assertTrue((out / "100001.xml").is_file())
            self.assertTrue((out / "img_01.jpg").is_file())
            claims = ET.parse(result.xml_path).findall(".//claim")
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0].attrib["num"], "1")

    def test_extract_preconverted_slot_package_accepts_outer_zip_with_single_inner_zip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner_bytes = _zip_bytes(
                {
                    "10000009/100002/100002.xml": '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><description /></cn-application-body>',
                    "10000009/100002/desc_01.jpg": b"image",
                }
            )
            source_zip = root / "outer.zip"
            source_zip.write_bytes(_zip_bytes({"wrapper.zip": inner_bytes}))
            out = root / "out"

            result = extract_preconverted_slot_package(str(source_zip), "100002", str(out))

            self.assertEqual(Path(result.xml_path), out / "100002.xml")
            self.assertTrue((out / "desc_01.jpg").is_file())

    def test_extract_preconverted_slot_package_rejects_slot_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_zip = root / "mismatch.zip"
            source_zip.write_bytes(
                _zip_bytes(
                    {
                        "10000009/100002/100002.xml": '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><description /></cn-application-body>',
                    }
                )
            )

            with self.assertRaisesRegex(ValueError, "所选文件类型与案卷包内容不一致"):
                extract_preconverted_slot_package(str(source_zip), "100001", str(root / "out"))

    def test_extract_preconverted_slot_package_rejects_ambiguous_structure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_zip = root / "ambiguous.zip"
            source_zip.write_bytes(
                _zip_bytes(
                    {
                        "10000009/100001/100001.xml": '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims /></cn-application-body>',
                        "10000009/100002/100002.xml": '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><description /></cn-application-body>',
                    }
                )
            )

            with self.assertRaisesRegex(ValueError, "案卷包结构不明确"):
                extract_preconverted_slot_package(str(source_zip), "100001", str(root / "out"))

    def test_forced_claims_slot_uses_existing_conversion_without_request_form(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write(root / "claims.docx", "placeholder")
            out = root / "out"

            def fake_run_conversion(*_args, **kwargs):
                output_root = Path(kwargs["output_dir_override"])
                folder = output_root / "10000009" / "100001"
                _write(
                    folder / "100001.xml",
                    '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>权 利 要 求 书</claim-text></claim><claim id="c1_cl002" num="2"><claim-text>一种装置。</claim-text></claim></cn-claims></cn-application-body>',
                )
                return {"case_id": "10000009"}

            with patch("core.response_correction.slot_conversion.run_conversion", side_effect=fake_run_conversion) as mock_run:
                result = convert_document_slot(str(source), "100001", str(out), patent_type="invention", case_id="10000009")

            self.assertEqual(Path(result.xml_path), out / "100001.xml")
            self.assertTrue((out / "100001.xml").is_file())
            claims = ET.parse(result.xml_path).findall(".//claim")
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0].attrib["num"], "1")
            self.assertEqual(claims[0].attrib["id"], "c1_cl001")
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(kwargs["forced_section_key"], "claims")
            self.assertEqual(kwargs["enabled_sections"], {"claims": True, "description": False, "drawings": False, "abstract": False, "request_form": False})
            self.assertEqual(kwargs["case_id"], "10000009")

    def test_convert_document_slot_creates_absolute_temp_dirs_before_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write(root / "claims.docx", "placeholder")
            out = root / "out"

            def fake_run_conversion(*_args, **kwargs):
                temp_output = Path(kwargs["output_dir_override"])
                temp_processing = Path(kwargs["temp_dir_override"])
                self.assertTrue(temp_output.is_absolute())
                self.assertTrue(temp_processing.is_absolute())
                self.assertTrue(temp_output.is_dir())
                self.assertTrue(temp_processing.is_dir())
                folder = temp_output / "10000009" / "100001"
                _write(
                    folder / "100001.xml",
                    '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>测试权利要求</claim-text></claim></cn-claims></cn-application-body>',
                )
                return {"case_id": "10000009"}

            with patch("core.response_correction.slot_conversion.run_conversion", side_effect=fake_run_conversion):
                result = convert_document_slot(str(source), "100001", str(out), patent_type="invention", case_id="10000009")

            self.assertEqual(Path(result.xml_path), out / "100001.xml")
            self.assertTrue((out / "100001.xml").is_file())

    def test_convert_document_slot_reads_case_root_returned_by_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write(root / "description.docx", "placeholder")
            out = root / "out"

            def fake_run_conversion(*_args, **kwargs):
                case_root = Path(kwargs["output_dir_override"]) / ".conversion-task" / "case"
                _write(case_root / "100002" / "100002.xml", '<cn-application-body><description /></cn-application-body>')
                return {"case_root": str(case_root)}

            with patch("core.response_correction.slot_conversion.run_conversion", side_effect=fake_run_conversion):
                result = convert_document_slot(str(source), "100002", str(out), patent_type="invention")
            self.assertEqual(Path(result.xml_path), out / "100002.xml")
            self.assertTrue((out / "100002.xml").is_file())

    def test_convert_document_slot_routes_drawings_and_abstract_slots_to_canonical_sections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write(root / "slot.docx", "placeholder")

            def fake_run_conversion(*_args, **kwargs):
                output_root = Path(kwargs["output_dir_override"])
                case_id = str(kwargs["case_id"])
                section = str(kwargs["forced_section_key"])
                slot_code = "100003" if section == "drawings" else "100004"
                folder = output_root / case_id / slot_code
                tag = "cn-drawings" if section == "drawings" else "cn-abstract"
                _write(
                    folder / f"{slot_code}.xml",
                    f'<?xml version="1.0" encoding="UTF-8"?><cn-application-body><{tag} /></cn-application-body>',
                )
                return {"case_id": case_id}

            with patch("core.response_correction.slot_conversion.run_conversion", side_effect=fake_run_conversion) as mock_run:
                drawings_result = convert_document_slot(
                    str(source),
                    "100003",
                    str(root / "drawings_out"),
                    patent_type="invention",
                    case_id="10000009",
                )
                abstract_result = convert_document_slot(
                    str(source),
                    "100004",
                    str(root / "abstract_out"),
                    patent_type="invention",
                    case_id="10000009",
                )

            self.assertEqual(Path(drawings_result.xml_path), root / "drawings_out" / "100003.xml")
            self.assertEqual(Path(abstract_result.xml_path), root / "abstract_out" / "100004.xml")
            self.assertEqual(mock_run.call_args_list[0].kwargs["forced_section_key"], "drawings")
            self.assertEqual(mock_run.call_args_list[1].kwargs["forced_section_key"], "abstract")

    def test_opinion_body_conversion_disables_centering_and_writes_cn_other_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write(root / "opinion.docx", "placeholder")
            out = root / "out"

            def fake_run_conversion(*_args, **kwargs):
                output_root = Path(kwargs["output_dir_override"])
                folder = output_root / "10000009" / "100004"
                _write(
                    folder / "100004.xml",
                    '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-other-file lang="zh" country="CN"><p id="p0001" num="0001" Italic="0"><img file="zjwj_1.jpg" /></p></cn-other-file></cn-application-body>',
                )
                _write(folder / "zjwj_1.jpg", "image")
                return {"case_id": "10000009"}

            with patch("core.response_correction.slot_conversion.run_conversion", side_effect=fake_run_conversion) as mock_run:
                result = convert_document_slot(
                    str(source),
                    "100012_body",
                    str(out),
                    patent_type="utility_model",
                    disable_centering=True,
                    case_id="10000009",
                )

            self.assertEqual(Path(result.xml_path), out / "section_1.xml")
            self.assertTrue((out / "zjwj_1.jpg").is_file())
            raw = Path(result.xml_path).read_text(encoding="utf-8")
            self.assertIn('<!DOCTYPE cn-other-file SYSTEM "/dtdandxsl/cn-other-file-20080416.dtd">', raw)
            root_node = ET.parse(result.xml_path).getroot()
            self.assertEqual(root_node.tag, "cn-other-file")
            self.assertEqual(root_node.find(".//p").attrib["num"], "1")
            self.assertEqual(root_node.find(".//img").attrib["file"], "zjwj_1.jpg")
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(kwargs["forced_section_key"], "abstract")
            self.assertFalse(kwargs["optimize_equation_centering"])
            self.assertFalse(kwargs["optimize_table_image_centering"])
            self.assertEqual(kwargs["output_body_root_tags"], {"abstract": "cn-other-file"})
            self.assertEqual(kwargs["image_prefix_overrides"], {"abstract": "zjwj"})

    def test_opinion_body_requires_centering_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = _write(Path(td) / "opinion.docx", "placeholder")
            with self.assertRaisesRegex(ValueError, "必须禁用居中处理"):
                convert_document_slot(str(source), "100012_body", str(Path(td) / "out"), patent_type="invention")

    def test_opinion_body_does_not_accept_zip_package(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "opinion.zip"
            source.write_bytes(_zip_bytes({"10000009/100012/section_1.xml": "<cn-other-file />"}))
            with self.assertRaisesRegex(ValueError, "仅支持 Word"):
                convert_document_slot(str(source), "100012_body", str(Path(td) / "out"), patent_type="invention", disable_centering=True)


if __name__ == "__main__":
    unittest.main()
