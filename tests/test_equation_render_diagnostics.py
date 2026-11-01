from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


class EquationRenderDiagnosticsTests(unittest.TestCase):
    @staticmethod
    def _read(path: str) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / path).read_text(encoding="utf-8")

    def _import_ops(self):
        try:
            from core.image_processing import equation_diag_ops
        except ImportError as exc:  # pragma: no cover - red phase should fail here first
            self.fail(f"equation_diag_ops module missing: {exc}")
        return equation_diag_ops

    def test_config_default_equation_diag_settings(self) -> None:
        text = self._read("resources/config.yaml")
        self.assertIn("equation_diag_enabled: false", text)
        self.assertIn('equation_diag_dir: "temp_processing/eq_diag"', text)

    def test_save_equation_diag_stage_disabled_does_not_write(self) -> None:
        ops = self._import_ops()
        with tempfile.TemporaryDirectory() as tmpdir:
            diag_root = Path(tmpdir) / "eq_diag"
            config = {
                "equation_diag_enabled": False,
                "equation_diag_dir": str(diag_root),
            }
            img = Image.new("RGB", (12, 12), "white")

            result = ops.save_equation_diag_stage(
                config,
                "temp_processing/img_demo.jpg",
                "01_render_raw.png",
                img,
            )

            self.assertIsNone(result)
            self.assertFalse(diag_root.exists())

    def test_save_equation_diag_stage_enabled_writes_expected_path(self) -> None:
        ops = self._import_ops()
        with tempfile.TemporaryDirectory() as tmpdir:
            diag_root = Path(tmpdir) / "eq_diag"
            config = {
                "equation_diag_enabled": True,
                "equation_diag_dir": str(diag_root),
            }
            img = Image.new("RGB", (12, 12), "white")

            result = ops.save_equation_diag_stage(
                config,
                "temp_processing/img_demo.jpg",
                "01_render_raw.png",
                img,
            )

            expected = diag_root / "img_demo" / "01_render_raw.png"
            self.assertEqual(Path(result), expected)
            self.assertTrue(expected.is_file())

    def test_write_equation_output_mapping_reuses_existing_diag_dir(self) -> None:
        ops = self._import_ops()
        with tempfile.TemporaryDirectory() as tmpdir:
            diag_root = Path(tmpdir) / "eq_diag"
            config = {
                "equation_diag_enabled": True,
                "equation_diag_dir": str(diag_root),
            }
            img = Image.new("RGB", (12, 12), "white")
            ops.save_equation_diag_stage(
                config,
                "temp_processing/img_demo.jpg",
                "01_render_raw.png",
                img,
            )

            result = ops.write_equation_output_mapping(
                config,
                "img_demo.jpg",
                temp_source="temp_processing/img_demo.jpg",
                final_output="output/10000390/100001/qlyqs_6.jpg",
                section_key="claims",
            )

            expected = diag_root / "img_demo" / "output_mapping.json"
            self.assertEqual(Path(result), expected)
            payload = json.loads(expected.read_text(encoding="utf-8"))
            self.assertEqual(payload["temp_source"], "temp_processing/img_demo.jpg")
            self.assertEqual(payload["final_output"], "output/10000390/100001/qlyqs_6.jpg")
            self.assertEqual(payload["section_key"], "claims")

    def test_build_emf_crop_diagnostics_reports_small_dot_above_final_bbox(self) -> None:
        ops = self._import_ops()
        img = Image.new("RGB", (80, 40), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle((18, 16, 56, 30), fill="black")
        draw.rectangle((34, 7, 36, 9), fill="black")

        diag = ops.build_emf_crop_diagnostics(
            img,
            threshold=230,
            padding_ratio=0.0,
            padding_min=0,
        )

        self.assertEqual(diag["threshold"], 230)
        self.assertEqual(diag["render_size"], [80, 40])
        self.assertEqual(diag["retained_min_area"], 20)
        self.assertTrue(diag["retained_contour_areas"])
        self.assertIsNotNone(diag["final_bbox"])
        self.assertGreater(diag["final_bbox"]["top"], 9)
        self.assertEqual([], diag["promoted_micro_contours"])
        self.assertTrue(
            any(item["is_above_final_bbox"] for item in diag["discarded_small_contours"]),
            "expected at least one discarded contour above final bbox",
        )


if __name__ == "__main__":
    unittest.main()
