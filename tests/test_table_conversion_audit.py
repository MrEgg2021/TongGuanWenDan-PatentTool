from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.quality.table_conversion_audit import build_audit_report, main


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _touch_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-image")


def _write_complementary_fragment(path: Path, *, dark_side: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (600, 900), "white")
    draw = ImageDraw.Draw(img)
    if dark_side == "right":
        draw.rectangle((340, 40, 560, 280), fill="black")
    elif dark_side == "left":
        draw.rectangle((40, 40, 260, 280), fill="black")
    else:
        raise ValueError(f"unsupported side: {dark_side}")
    draw.rectangle((80, 420, 520, 820), outline="black", width=8)
    img.save(path, format="JPEG")


class TableConversionAuditTests(unittest.TestCase):
    def test_audit_reports_pass_with_warnings_for_split_fallback_and_sequential_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "output" / "10000390" / "100002" / "100002.xml"
            log_path = root / "conversion.log"

            for name in ("sms_11.jpg", "sms_12.jpg", "sms_13.jpg", "sms_14.jpg", "sms_16.jpg", "sms_17.jpg", "sms_18.jpg"):
                _touch_image(xml_path.parent / name)

            _write_text(
                xml_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN"><description>
<p id="p0001" num="XXXX" Italic="0"><img id="idf_0001" file="sms_11.jpg" img-format="jpg" wi="165.00" he="234.19" inline="no"/></p>
<p id="p0002" num="XXXX" Italic="0"><img id="idf_0002" file="sms_12.jpg" img-format="jpg" wi="165.00" he="234.61" inline="no"/></p>
<p id="p0003" num="XXXX" Italic="0"><img id="idf_0003" file="sms_13.jpg" img-format="jpg" wi="165.00" he="228.88" inline="no"/></p>
<p id="p0004" num="XXXX" Italic="0"><img id="idf_0004" file="sms_14.jpg" img-format="jpg" wi="165.00" he="13.27" inline="no"/></p>
<p id="p0005" num="XXXX" Italic="0"><img id="idf_0005" file="sms_16.jpg" img-format="jpg" wi="165.00" he="226.92" inline="no"/></p>
<p id="p0006" num="XXXX" Italic="0"><img id="idf_0006" file="sms_17.jpg" img-format="jpg" wi="165.00" he="226.59" inline="no"/></p>
<p id="p0007" num="XXXX" Italic="0"><img id="idf_0007" file="sms_18.jpg" img-format="jpg" wi="165.00" he="168.12" inline="no"/></p>
</description></cn-application-body>
""",
            )
            _write_text(
                log_path,
                """
2026-03-21 21:15:08,267 - main - INFO - [TABLE_CAPTURE_TRY] idx=184 section=description range=(10377,12212) rows=89 cols=2
2026-03-21 21:15:08,268 - main - INFO - [TABLE_CAPTURE_PATH] method=pdf_first section=description range_start=10377 range_end=12212 rows=89 cols=2
2026-03-21 21:15:08,269 - main - INFO - [TABLE_SPLIT] section=description rows=89
2026-03-21 21:15:52,011 - main - INFO - [TABLE_SPLIT_ACCEPT] section=description loop=1 requested_row=30 safe_row=30 applied_safe_row=30 height_mm=234.19
2026-03-21 21:16:06,389 - main - INFO - [TABLE_SPLIT_ACCEPT] section=description loop=2 requested_row=30 safe_row=30 applied_safe_row=30 height_mm=234.61
2026-03-21 21:16:16,161 - main - INFO - [TABLE_SPLIT_ACCEPT] section=description loop=3 requested_row=30 safe_row=30 applied_safe_row=30 height_mm=228.88
2026-03-21 21:16:17,827 - main - DEBUG - [TABLE_CENTER] file=tbl_a.jpg section=description target_width_mm=165.00 before_w_mm=104.73 before_h_mm=234.19 after_w_mm=165.00 after_h_mm=234.19
2026-03-21 21:16:17,985 - main - DEBUG - [TABLE_CENTER] file=tbl_b.jpg section=description target_width_mm=165.00 before_w_mm=104.73 before_h_mm=234.61 after_w_mm=165.00 after_h_mm=234.61
2026-03-21 21:16:18,132 - main - DEBUG - [TABLE_CENTER] file=tbl_c.jpg section=description target_width_mm=165.00 before_w_mm=104.73 before_h_mm=228.88 after_w_mm=165.00 after_h_mm=228.88
2026-03-21 21:16:18,143 - main - DEBUG - [TABLE_CENTER] file=tbl_d.jpg section=description target_width_mm=165.00 before_w_mm=104.73 before_h_mm=13.27 after_w_mm=165.00 after_h_mm=13.27
2026-03-21 21:16:18,199 - main - INFO - [TABLE_CAPTURE_RESULT] idx=184 section=description range=(10377,12212) success=True
2026-03-21 21:16:49,028 - main - INFO - [TABLE_CAPTURE_TRY] idx=504 section=description range=(15897,19725) rows=60 cols=6
2026-03-21 21:17:19,888 - main - INFO - [TABLE_PDF_FRAGMENT_EMIT] pages=3 source_method=selection hard_table=True
2026-03-21 21:17:20,239 - main - DEBUG - [TABLE_CENTER] file=tbl_e_p1.jpg section=description target_width_mm=165.00 before_w_mm=141.12 before_h_mm=226.92 after_w_mm=165.00 after_h_mm=226.92
2026-03-21 21:17:20,552 - main - DEBUG - [TABLE_CENTER] file=tbl_e_p2.jpg section=description target_width_mm=165.00 before_w_mm=141.12 before_h_mm=226.59 after_w_mm=165.00 after_h_mm=226.59
2026-03-21 21:17:20,738 - main - DEBUG - [TABLE_CENTER] file=tbl_e_p3.jpg section=description target_width_mm=165.00 before_w_mm=141.12 before_h_mm=168.12 after_w_mm=165.00 after_h_mm=168.12
2026-03-21 21:17:20,739 - main - INFO - [TABLE_CAPTURE_RESULT] idx=504 section=description range=(15897,19725) success=True
""".strip(),
            )

            report = build_audit_report(log_path=log_path, xml_path=xml_path)

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["failures"], [])
        self.assertEqual(len(report["tables"]), 2)
        self.assertEqual(report["tables"][0]["fragment_count_log"], 4)
        self.assertEqual(report["tables"][0]["fragment_count_xml"], 4)
        self.assertTrue(report["tables"][0]["used_split_fallback"])
        self.assertIn("used split fallback", report["tables"][0]["warnings"])
        self.assertEqual(report["tables"][1]["fragment_count_log"], 3)
        self.assertEqual(report["tables"][1]["fragment_count_xml"], 3)
        self.assertEqual(len(report["replay_manifest"]["entries"]), 7)

    def test_audit_fails_on_placeholder_count_mismatch_missing_image_and_center_height_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "output" / "10000390" / "100002" / "100002.xml"
            log_path = root / "conversion.log"

            _write_text(
                xml_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN"><description>
<p id="p0001" num="XXXX" Italic="0">表格截图失败，未写入 XML，请人工核对原文。</p>
<p id="p0002" num="XXXX" Italic="0"><img id="idf_0001" file="sms_9.jpg" img-format="jpg" wi="165.00" he="210.00" inline="no"/></p>
</description></cn-application-body>
""",
            )
            _write_text(
                log_path,
                """
2026-03-22 10:00:00,000 - main - INFO - [TABLE_CAPTURE_TRY] idx=9 section=description range=(100,200) rows=10 cols=2
2026-03-22 10:00:01,000 - main - DEBUG - [TABLE_CENTER] file=tbl_bad_1.jpg section=description target_width_mm=165.00 before_w_mm=100.00 before_h_mm=200.00 after_w_mm=165.00 after_h_mm=210.00
2026-03-22 10:00:01,100 - main - INFO - [TABLE_EMIT_SUMMARY] idx=9 section=description range_start=100 range_end=200 fragments=2 files=tbl_bad_1.jpg|tbl_bad_2.jpg widths_mm=165.00|165.00 heights_mm=210.00|50.00
2026-03-22 10:00:01,200 - main - INFO - [TABLE_CAPTURE_RESULT] idx=9 section=description range=(100,200) success=True
2026-03-22 10:00:02,000 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_bad_1.jpg final=sms_9.jpg
2026-03-22 10:00:02,010 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_bad_2.jpg final=sms_10.jpg
""".strip(),
            )

            report = build_audit_report(log_path=log_path, xml_path=xml_path)

        self.assertEqual(report["status"], "FAIL")
        joined_failures = "\n".join(report["failures"])
        self.assertIn("placeholder", joined_failures)
        self.assertIn("fragment count mismatch", joined_failures)
        self.assertIn("missing image file", joined_failures)
        self.assertIn("centering changed height", joined_failures)

    def test_main_writes_reports_and_replay_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "output" / "10000390" / "100002" / "100002.xml"
            log_path = root / "conversion.log"
            artifact_dir = root / "artifacts"

            _touch_image(xml_path.parent / "sms_11.jpg")
            _write_text(
                xml_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN"><description>
<p id="p0001" num="XXXX" Italic="0"><img id="idf_0001" file="sms_11.jpg" img-format="jpg" wi="165.00" he="234.19" inline="no"/></p>
</description></cn-application-body>
""",
            )
            _write_text(
                log_path,
                """
2026-03-22 10:00:00,000 - main - INFO - [TABLE_CAPTURE_TRY] idx=11 section=description range=(100,200) rows=10 cols=2
2026-03-22 10:00:01,000 - main - INFO - [TABLE_EMIT_SUMMARY] idx=11 section=description range_start=100 range_end=200 fragments=1 files=tbl_a.jpg widths_mm=165.00 heights_mm=234.19
2026-03-22 10:00:01,100 - main - INFO - [TABLE_CAPTURE_RESULT] idx=11 section=description range=(100,200) success=True
""".strip(),
            )

            code = main(
                [
                    "--log",
                    str(log_path),
                    "--output-root",
                    str(root / "output"),
                    "--case-id",
                    "10000390",
                    "--doc-code",
                    "100002",
                    "--artifact-dir",
                    str(artifact_dir),
                ]
            )

            report_path = artifact_dir / "table_conversion_audit_report.json"
            manifest_path = artifact_dir / "replay_manifest.json"
            self.assertEqual(code, 0)
            self.assertTrue(report_path.is_file())
            self.assertTrue(manifest_path.is_file())

    def test_audit_fails_on_complementary_blank_half_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "output" / "10000390" / "100002" / "100002.xml"
            log_path = root / "conversion.log"

            _write_complementary_fragment(xml_path.parent / "sms_11.jpg", dark_side="right")
            _write_complementary_fragment(xml_path.parent / "sms_12.jpg", dark_side="left")
            _write_text(
                xml_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN"><description>
<p id="p0001" num="XXXX" Italic="0"><img id="idf_0001" file="sms_11.jpg" img-format="jpg" wi="165.00" he="210.00" inline="no"/></p>
<p id="p0002" num="XXXX" Italic="0"><img id="idf_0002" file="sms_12.jpg" img-format="jpg" wi="165.00" he="205.00" inline="no"/></p>
</description></cn-application-body>
""",
            )
            _write_text(
                log_path,
                """
2026-04-01 10:07:29,701 - main - INFO - [TABLE_CAPTURE_TRY] idx=1883 section=description range=(46709,48599) rows=89 cols=2
2026-04-01 10:08:09,050 - main - INFO - [TABLE_EMIT_SUMMARY] idx=1883 section=description range_start=46709 range_end=48599 fragments=2 files=tbl_p1.jpg|tbl_p2.jpg widths_mm=165.00|165.00 heights_mm=210.00|205.00
2026-04-01 10:09:02,351 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_p1.jpg final=sms_11.jpg
2026-04-01 10:09:02,359 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_p2.jpg final=sms_12.jpg
2026-04-01 10:09:02,500 - main - INFO - [TABLE_CAPTURE_RESULT] idx=1883 section=description range=(46709,48599) success=True
""".strip(),
            )

            report = build_audit_report(log_path=log_path, xml_path=xml_path)

        self.assertEqual(report["status"], "FAIL")
        joined_failures = "\n".join(report["failures"])
        self.assertIn("complementary blank-half", joined_failures)

    def test_audit_records_valid_visual_slice_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "output" / "10000390" / "100002" / "100002.xml"
            log_path = root / "conversion.log"

            _touch_image(xml_path.parent / "sms_21.jpg")
            _touch_image(xml_path.parent / "sms_22.jpg")
            _write_text(
                xml_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN"><description>
<p id="p0001" num="XXXX" Italic="0"><img id="idf_0001" file="sms_21.jpg" img-format="jpg" wi="100.00" he="125.00" inline="no"/></p>
<p id="p0002" num="XXXX" Italic="0"><img id="idf_0002" file="sms_22.jpg" img-format="jpg" wi="100.00" he="125.00" inline="no"/></p>
</description></cn-application-body>
""",
            )
            _write_text(
                log_path,
                """
2026-04-08 10:00:00,000 - main - INFO - [TABLE_CAPTURE_TRY] idx=24 section=description range=(1000,2000) rows=89 cols=2
2026-04-08 10:00:01,000 - main - INFO - [TABLE_PDF_FRAGMENT_VISUAL_SLICE] page=1 file=tbl_long.jpg original_height_mm=250.00 max_height_mm=240.00 slices=2 slice_heights_mm=125.00|125.00 cut_modes=horizontal_rule mode=group total_height_mm=250.00 cuts_px=1250 cut_scores=1.000 boundary_closed=True
2026-04-08 10:00:01,100 - main - INFO - [TABLE_PDF_FRAGMENT_EMIT] pages=2 source_method=selection hard_table=True
2026-04-08 10:00:01,200 - main - INFO - [TABLE_EMIT_SUMMARY] idx=24 section=description range_start=1000 range_end=2000 fragments=2 files=tbl_long_s1.jpg|tbl_long_s2.jpg widths_mm=100.00|100.00 heights_mm=125.00|125.00
2026-04-08 10:00:01,300 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_long_s1.jpg final=sms_21.jpg
2026-04-08 10:00:01,310 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_long_s2.jpg final=sms_22.jpg
2026-04-08 10:00:01,400 - main - INFO - [TABLE_CAPTURE_RESULT] idx=24 section=description range=(1000,2000) success=True
""".strip(),
            )

            report = build_audit_report(log_path=log_path, xml_path=xml_path)

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["tables"][0]["visual_slice_event_count"], 1)
        self.assertIn("used visual slice fallback", report["tables"][0]["warnings"])
        event = report["tables"][0]["visual_slice_events"][0]
        self.assertEqual(event["mode"], "group")
        self.assertEqual(event["cuts_px"], [1250])
        self.assertTrue(event["boundary_closed"])

    def test_audit_fails_when_visual_slice_event_reports_overlimit_slice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "output" / "10000390" / "100002" / "100002.xml"
            log_path = root / "conversion.log"

            _touch_image(xml_path.parent / "sms_31.jpg")
            _touch_image(xml_path.parent / "sms_32.jpg")
            _write_text(
                xml_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN"><description>
<p id="p0001" num="XXXX" Italic="0"><img id="idf_0001" file="sms_31.jpg" img-format="jpg" wi="100.00" he="120.00" inline="no"/></p>
<p id="p0002" num="XXXX" Italic="0"><img id="idf_0002" file="sms_32.jpg" img-format="jpg" wi="100.00" he="120.00" inline="no"/></p>
</description></cn-application-body>
""",
            )
            _write_text(
                log_path,
                """
2026-04-08 10:00:00,000 - main - INFO - [TABLE_CAPTURE_TRY] idx=25 section=description range=(3000,4000) rows=89 cols=2
2026-04-08 10:00:01,000 - main - INFO - [TABLE_PDF_FRAGMENT_VISUAL_SLICE] page=1 file=tbl_bad.jpg original_height_mm=481.00 max_height_mm=240.00 slices=2 slice_heights_mm=240.00|241.00 cut_modes=horizontal_rule mode=group total_height_mm=481.00 cuts_px=2400 cut_scores=1.000 boundary_closed=True
2026-04-08 10:00:01,100 - main - INFO - [TABLE_EMIT_SUMMARY] idx=25 section=description range_start=3000 range_end=4000 fragments=2 files=tbl_bad_s1.jpg|tbl_bad_s2.jpg widths_mm=100.00|100.00 heights_mm=120.00|120.00
2026-04-08 10:00:01,200 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_bad_s1.jpg final=sms_31.jpg
2026-04-08 10:00:01,210 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_bad_s2.jpg final=sms_32.jpg
2026-04-08 10:00:01,300 - main - INFO - [TABLE_CAPTURE_RESULT] idx=25 section=description range=(3000,4000) success=True
""".strip(),
            )

            report = build_audit_report(log_path=log_path, xml_path=xml_path)

        self.assertEqual(report["status"], "FAIL")
        self.assertIn("visual slice height exceeds max_height_mm", "\n".join(report["failures"]))

    def test_audit_fails_when_visual_slice_event_reports_unsafe_cut_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "output" / "10000390" / "100002" / "100002.xml"
            log_path = root / "conversion.log"

            _touch_image(xml_path.parent / "sms_33.jpg")
            _touch_image(xml_path.parent / "sms_34.jpg")
            _write_text(
                xml_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN"><description>
<p id="p0001" num="XXXX" Italic="0"><img id="idf_0001" file="sms_33.jpg" img-format="jpg" wi="100.00" he="120.00" inline="no"/></p>
<p id="p0002" num="XXXX" Italic="0"><img id="idf_0002" file="sms_34.jpg" img-format="jpg" wi="100.00" he="120.00" inline="no"/></p>
</description></cn-application-body>
""",
            )
            _write_text(
                log_path,
                """
2026-04-08 10:00:00,000 - main - INFO - [TABLE_CAPTURE_TRY] idx=26 section=description range=(5000,6000) rows=89 cols=2
2026-04-08 10:00:01,000 - main - INFO - [TABLE_PDF_FRAGMENT_VISUAL_SLICE] page=1 file=tbl_unsafe.jpg original_height_mm=250.00 max_height_mm=240.00 slices=2 slice_heights_mm=125.00|125.00 cut_modes=low_density mode=group total_height_mm=250.00 cuts_px=1250 cut_scores=0.010 boundary_closed=True
2026-04-08 10:00:01,100 - main - INFO - [TABLE_EMIT_SUMMARY] idx=26 section=description range_start=5000 range_end=6000 fragments=2 files=tbl_unsafe_s1.jpg|tbl_unsafe_s2.jpg widths_mm=100.00|100.00 heights_mm=120.00|120.00
2026-04-08 10:00:01,200 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_unsafe_s1.jpg final=sms_33.jpg
2026-04-08 10:00:01,210 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_unsafe_s2.jpg final=sms_34.jpg
2026-04-08 10:00:01,300 - main - INFO - [TABLE_CAPTURE_RESULT] idx=26 section=description range=(5000,6000) success=True
""".strip(),
            )

            report = build_audit_report(log_path=log_path, xml_path=xml_path)

        self.assertEqual(report["status"], "FAIL")
        self.assertIn("unsafe cut mode", "\n".join(report["failures"]))

    def test_audit_filters_log_blocks_to_target_xml_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "output" / "10000390" / "100002" / "100002.xml"
            log_path = root / "conversion.log"

            _touch_image(xml_path.parent / "sms_41.jpg")
            _write_text(
                xml_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<cn-application-body lang="zh" country="CN"><description>
<p id="p0001" num="XXXX" Italic="0"><img id="idf_0001" file="sms_41.jpg" img-format="jpg" wi="100.00" he="120.00" inline="no"/></p>
</description></cn-application-body>
""",
            )
            _write_text(
                log_path,
                """
2026-04-08 10:00:00,000 - main - INFO - [TABLE_CAPTURE_TRY] idx=1 section=claims range=(10,20) rows=1 cols=2
2026-04-08 10:00:00,100 - main - INFO - [TABLE_EMIT_SUMMARY] idx=1 section=claims range_start=10 range_end=20 fragments=2 files=tbl_claim_a.jpg|tbl_claim_b.jpg widths_mm=100.00|100.00 heights_mm=20.00|20.00
2026-04-08 10:00:00,200 - main - INFO - [TABLE_CAPTURE_RESULT] idx=1 section=claims range=(10,20) success=True
2026-04-08 10:00:01,000 - main - INFO - [TABLE_CAPTURE_TRY] idx=2 section=description range=(30,40) rows=1 cols=2
2026-04-08 10:00:01,100 - main - INFO - [TABLE_EMIT_SUMMARY] idx=2 section=description range_start=30 range_end=40 fragments=1 files=tbl_desc.jpg widths_mm=100.00 heights_mm=120.00
2026-04-08 10:00:01,200 - main - INFO - [TABLE_OUTPUT_MAP] section=description temp=tbl_desc.jpg final=sms_41.jpg
2026-04-08 10:00:01,300 - main - INFO - [TABLE_CAPTURE_RESULT] idx=2 section=description range=(30,40) success=True
""".strip(),
            )

            report = build_audit_report(log_path=log_path, xml_path=xml_path)

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["tables"]), 1)
        self.assertEqual(report["tables"][0]["section"], "description")
        self.assertEqual(report["tables"][0]["fragment_count_xml"], 1)


if __name__ == "__main__":
    unittest.main()
