from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EquationCropPaddingWiringTests(unittest.TestCase):
    def test_config_declares_explicit_equation_crop_padding_default(self) -> None:
        text = (ROOT / "resources" / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("equation_crop_padding_min: 8", text)

    def test_equation_emf_paths_no_longer_hardcode_zero_padding(self) -> None:
        handle_text = (ROOT / "core" / "document_parser" / "image_shape_ops" / "handle_shape_ops.py").read_text(encoding="utf-8")
        equation_text = (ROOT / "core" / "document_parser" / "equation_mixin.py").read_text(encoding="utf-8")

        self.assertIn("equation_crop_padding_min", handle_text)
        self.assertIn("equation_crop_padding_min", equation_text)
        self.assertNotIn("padding_min=0", handle_text)
        self.assertNotIn("padding_min=0", equation_text)


if __name__ == "__main__":
    unittest.main()
