import unittest
from unittest.mock import patch

from core import conversion
from core.config import load_config


class StopBeforeOffice(Exception):
    pass


class ConversionImageOverridesTests(unittest.TestCase):
    def test_display_scale_is_applied_without_changing_image_resolution(self):
        for ratio, expected in ((0.6, 0.6), (0.2, 0.4), (2.0, 1.0)):
            with self.subTest(ratio=ratio):
                config = load_config()
                pixels = config["image_processing"].copy()
                with (
                    patch.object(conversion, "load_config", return_value=config),
                    patch.object(conversion, "WordEngine", side_effect=StopBeforeOffice),
                    self.assertRaises(StopBeforeOffice),
                ):
                    conversion.run_conversion("input.docx", image_processing_overrides={
                        "equation_display_scale_ratio": ratio,
                    })
                self.assertEqual(expected, config["equation_display_scale_ratio"])
                self.assertEqual(pixels, config["image_processing"])

    def test_invalid_scale_fails_before_office_is_created(self):
        for ratio in (0, -1, "invalid"):
            with self.subTest(ratio=ratio), patch.object(conversion, "WordEngine") as word:
                with self.assertRaises(ValueError):
                    conversion.run_conversion("input.docx", image_processing_overrides={
                        "equation_display_scale_ratio": ratio,
                    })
                word.assert_not_called()


if __name__ == "__main__":
    unittest.main()
