from pathlib import Path
import unittest
from unittest.mock import patch

from gui_app import MainWindow


class FirstRunDefaultsWiringV250Tests(unittest.TestCase):
    @staticmethod
    def _read(path: str) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / path).read_text(encoding="utf-8")

    def test_settings_page_defaults(self) -> None:
        text = self._read("gui/ui_layout_impl/settings_page.py")
        self.assertIn('desc_combo.findData("word_period_end")', text)
        self.assertIn("spin_ratio.setValue(0.8)", text)

    def test_config_default_equation_ratio(self) -> None:
        text = self._read("resources/config.yaml")
        self.assertIn("equation_display_scale_ratio: 0.8", text)

    def test_data_management_import_defaults(self) -> None:
        text = self._read("gui/ui_layout_impl/data_management_page.py")
        self.assertIn("chk_confirm_each.setChecked(False)", text)
        self.assertIn("chk_parse_poa.setChecked(True)", text)

    def test_single_batch_defaults(self) -> None:
        text = self._read("gui/ui_layout_impl/single_panel.py")
        self.assertIn("window.chk_request_form.setChecked(False)", text)
        self.assertIn("window.batch_chk_confirm_req.setChecked(False)", text)
        self.assertIn("window.chk_auto_open_preview.setChecked(False)", text)

    def test_desc_mode_fallback_and_application_display_name(self) -> None:
        text = self._read("gui_app.py")
        with patch("gui_app.get_desc_para_split_mode", return_value=None):
            self.assertEqual("word_period_end", MainWindow.get_description_paragraph_split_mode(None))
        self.assertIn('app.setApplicationName("通官文旦-专利工具")', text)
        self.assertIn('app.setApplicationDisplayName(get_app_display_title())', text)


if __name__ == "__main__":
    unittest.main()

