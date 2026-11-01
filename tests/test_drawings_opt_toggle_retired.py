from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DrawingsOptimizeToggleRetiredTests(unittest.TestCase):
    def test_settings_page_no_longer_exposes_drawings_opt_checkbox(self) -> None:
        text = (ROOT / "gui" / "ui_layout_impl" / "settings_page.py").read_text(encoding="utf-8")
        self.assertNotIn("settingsDrawingsImageOptimize", text)
        self.assertNotIn("说明书附图图片优化", text)

    def test_runtime_snapshot_and_overrides_ignore_legacy_drawings_toggle(self) -> None:
        snapshot_text = (ROOT / "gui" / "main_window" / "mixins" / "settings_preferences_impl" / "snapshot_ops.py").read_text(encoding="utf-8")
        menu_text = (ROOT / "gui" / "app_impl" / "image_overrides.py").read_text(encoding="utf-8")
        conversion_text = (ROOT / "core" / "conversion.py").read_text(encoding="utf-8")
        config_text = (ROOT / "resources" / "config.yaml").read_text(encoding="utf-8")
        preferences_text = (ROOT / "core" / "app_preferences.py").read_text(encoding="utf-8")

        self.assertNotIn("drawings_image_optimize", snapshot_text)
        self.assertNotIn("drawings_image_optimize_enabled", menu_text)
        self.assertNotIn("drawings_image_optimize_enabled", conversion_text)
        self.assertNotIn("drawings_image_optimize_enabled", config_text)
        self.assertNotIn("DRAWINGS_IMAGE_OPTIMIZE_DEFAULT_KEY", preferences_text)


if __name__ == "__main__":
    unittest.main()
