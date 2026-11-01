from __future__ import annotations

import unittest
from unittest.mock import patch

from core import app_preferences


class CnipaPreviewPreferenceTests(unittest.TestCase):
    def test_preview_mode_defaults_to_legacy_and_accepts_only_known_values(self) -> None:
        with patch.object(app_preferences, "get_pref", return_value=None):
            self.assertEqual("legacy", app_preferences.get_pdf_preview_mode())
        with patch.object(app_preferences, "set_pref") as set_pref:
            app_preferences.set_pdf_preview_mode("full")
            set_pref.assert_called_once_with(app_preferences.PDF_PREVIEW_MODE_KEY, "full")
        with self.assertRaises(ValueError):
            app_preferences.set_pdf_preview_mode("automatic")

    def test_runtime_source_preference_is_strict(self) -> None:
        with patch.object(
            app_preferences,
            "get_pref",
            return_value={"source_kind": "installed_client", "source_path": r"D:\CNIPAClient"},
        ):
            self.assertEqual(
                {"source_kind": "installed_client", "source_path": r"D:\CNIPAClient"},
                app_preferences.get_cnipa_runtime_source_v1(),
            )
        with patch.object(app_preferences, "get_pref", return_value={"source_kind": "download", "source_path": "x"}):
            self.assertIsNone(app_preferences.get_cnipa_runtime_source_v1())
        with patch.object(app_preferences, "set_pref") as set_pref:
            app_preferences.set_cnipa_runtime_source_v1("archive", r"D:\runtime.zip")
            set_pref.assert_called_once_with(
                app_preferences.CNIPA_RUNTIME_SOURCE_V1_KEY,
                {"source_kind": "archive", "source_path": r"D:\runtime.zip"},
            )


if __name__ == "__main__":
    unittest.main()
