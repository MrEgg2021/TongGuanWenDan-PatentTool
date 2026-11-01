from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton, QTabWidget, QTextBrowser, QWidget

from core import app_preferences, config, paths_utils, user_prefs
from gui.about_ui import build_about_page
from gui_app import MainWindow
from gui.ui_layout_impl.header import build_header_area


class FreeCommunityEditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_preferences_keep_existing_values_without_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            prefs = Path(directory) / "user_prefs.json"
            original = {
                "pdf_preview_mode": "full", "main_window_geometry_v1": "existing",
                "activated": False, "expires_at": 0, "custom_preference": "keep",
            }
            prefs.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(user_prefs, "get_user_data_dir", return_value=directory):
                self.assertEqual("full", app_preferences.get_pdf_preview_mode())
                self.assertEqual("existing", app_preferences.get_main_window_geometry_v1())
                app_preferences.set_auto_open_pdf_preview_single(True)
                saved = json.loads(prefs.read_text(encoding="utf-8"))
                for key, value in original.items():
                    self.assertEqual(value, saved[key])
                self.assertTrue(saved["auto_open_pdf_preview_single"])

    def test_retired_license_is_not_read_or_migrated_to_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = Path(directory) / "license.json"
            legacy_path.write_text(json.dumps({"machine_id": "old", "pdf_preview_mode": "full"}), encoding="utf-8")
            original = legacy_path.read_bytes()
            with (
                patch.object(user_prefs, "get_user_data_dir", return_value=directory),
                patch.object(user_prefs, "_load_json", wraps=user_prefs._load_json) as load_json,
            ):
                self.assertEqual({}, user_prefs.load_prefs())
                self.assertEqual("legacy", app_preferences.get_pdf_preview_mode())
                app_preferences.set_pdf_preview_mode("full")
                self.assertEqual({"pdf_preview_mode": "full"}, user_prefs.load_prefs())
                self.assertTrue(all(call.args[0] == str(Path(directory) / "user_prefs.json") for call in load_json.call_args_list))
            self.assertEqual(original, legacy_path.read_bytes())

    def test_real_window_navigation_and_editing_need_no_license(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            configured = config.load_config()
            configured["version"] = "9.8.7"
            stack.enter_context(patch.object(config, "load_config", return_value=configured))
            stack.enter_context(patch.object(paths_utils, "_get_windows_roaming_appdata", return_value=directory))
            for target in (
                "core.cnipa_preview.runtime.get_machine_data_dir",
                "core.official_docs.resource_mirror.get_machine_data_dir",
            ):
                stack.enter_context(patch(target, return_value=directory))
            stack.enter_context(patch.object(MainWindow, "_init_tray"))
            stack.enter_context(patch.object(MainWindow, "_auto_env_check_and_alert_if_needed"))
            stack.enter_context(patch("gui.tools_ui_impl.preview_impl.service_status.start_preview_services"))
            window = MainWindow()
            try:
                self.app.processEvents()
                expected_title = "通官文旦-专利工具 V9.8.7"
                self.assertEqual(expected_title, window.windowTitle())
                self.assertIn(expected_title, [label.text() for label in window.about_page.findChildren(QLabel)])
                header = build_header_area(window)
                self.assertIn(expected_title, [label.text() for label in header.findChildren(QLabel)])
                header.deleteLater()
                self.assertFalse(hasattr(window, "_license_status"))
                self.assertFalse(hasattr(window, "_entitlements_refresh_timer"))
                for route, target in (
                    ("_nav_to_home", "home"), ("_nav_to_batch", "batch"),
                    ("_nav_to_official_docs", "official_docs"),
                    ("_nav_to_formal_review", "formal_review"),
                    ("_nav_to_response", "response"), ("_nav_to_correction", "correction"),
                    ("_nav_to_active_response", "active_response"),
                    ("_nav_to_active_correction", "active_correction"),
                    ("_nav_to_preview", "preview"), ("_nav_to_settings", "settings"),
                ):
                    with self.subTest(route=route):
                        getattr(window, route)()
                        self.assertEqual(target, window._current_nav_target)
                self.assertTrue(window.settings_save_button.isEnabled())
                self.assertTrue(window.settings_scale_ratio.isEnabled())
                window._nav_to_data_management()
                manager = window.tgd_fact_record_manager_dialog
                for button in (manager.btn_add, manager.btn_delete, manager.btn_save):
                    self.assertTrue(button.isEnabled())
                window._nav_to_about()
                text = "\n".join(label.text() for label in window.about_page.findChildren(QLabel))
                self.assertIn("AGPL-3.0-only", text)
                self.assertFalse(window.about_page.findChildren(QTextBrowser))
                self.assertFalse(window.about_page.findChildren(QLineEdit))
                self.assertFalse((Path(__file__).resolve().parents[1] / "core/licensing").exists())
            finally:
                window._allow_close = True
                window.close()
                window.deleteLater()
                self.app.processEvents()

    def test_about_license_button_opens_complete_notices(self):
        window = QWidget()
        page = build_about_page(window)
        try:
            contact = next(label for label in page.findChildren(QLabel) if "1649251313@qq.com" in label.text())
            self.assertIn("微信：MrEgg208", contact.text())
            self.assertTrue(contact.textInteractionFlags() & Qt.TextSelectableByMouse)
            self.assertTrue(contact.textInteractionFlags() & Qt.TextSelectableByKeyboard)
            self.assertFalse(page.findChildren(QTextBrowser))
            button = next(button for button in page.findChildren(QPushButton) if button.text() == "开源许可与第三方声明")

            with patch.object(QDialog, "exec", return_value=QDialog.Rejected) as execute:
                button.click()
                execute.assert_called_once()
            dialog = window.findChild(QDialog)
            self.assertEqual("开源许可与第三方声明", dialog.windowTitle())
            tabs = dialog.findChild(QTabWidget)
            self.assertEqual(
                ["开源许可（中文说明）", "第三方声明", "AGPL 英文原文"],
                [tabs.tabText(index) for index in range(tabs.count())],
            )
            self.assertEqual(0, tabs.currentIndex())
            browsers = [tabs.widget(index) for index in range(tabs.count())]
            self.assertTrue(all(browser.isReadOnly() for browser in browsers))
            self.assertIn("非官方中文阅读说明", browsers[0].toPlainText())
            self.assertIn("第三方声明", browsers[1].toPlainText())
            self.assertIn("PyMuPDF", browsers[1].toPlainText())
            self.assertEqual(Path("resources/LICENSE").read_text(encoding="utf-8"), browsers[2].toPlainText())
            self.assertEqual(Path("LICENSE").read_bytes(), Path("resources/LICENSE").read_bytes())
            self.assertEqual(Path("THIRD_PARTY_NOTICES.md").read_bytes(), Path("resources/THIRD_PARTY_NOTICES.md").read_bytes())
            self.assertIn("关闭", [button.text() for button in dialog.findChildren(QPushButton)])
        finally:
            page.deleteLater()
            window.deleteLater()
            self.app.processEvents()
