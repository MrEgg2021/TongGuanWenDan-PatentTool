from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QWidget

from core import app_preferences, user_prefs
from gui.app_impl.image_overrides import init_advanced_image_overrides, get_effective_image_overrides
from gui.main_window.mixins.navigation_mixin_impl import NavigationMixin
from gui.main_window.mixins.settings_preferences_impl import apply_ops, save_ops, snapshot_ops


class SettingsPreferencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.prefs = Path(directory.name) / "user_prefs.json"
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(user_prefs, "get_user_data_dir", return_value=directory.name))
        stack.enter_context(patch.object(apply_ops, "init_settings_env_section"))
        self.alert = stack.enter_context(patch.object(save_ops, "show_blocking_alert_modal"))
        self.window = QWidget()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)
        for name in (
            "settings_opt_center", "settings_table_img_center", "settings_req_form_skip_tip",
            "settings_id_validation_cn", "settings_id_validation_uscc", "chk_auto_open_preview",
        ):
            setattr(self.window, name, QCheckBox(self.window))
        self.window.settings_desc_split_mode = QComboBox(self.window)
        for mode in ("word", "period", "word_period_end"):
            self.window.settings_desc_split_mode.addItem(mode, mode)
        self.window.settings_scale_ratio = QDoubleSpinBox(self.window)
        self.window.settings_scale_ratio.setRange(0.4, 1.0)
        self.window._settings_page = self.window
        self.window._on_auto_preview_toggled = Mock()
        self.window.get_description_paragraph_split_mode = (
            lambda: app_preferences.get_desc_para_split_mode() or "word_period_end"
        )
        self.window.show()

    def initialize(self):
        init_advanced_image_overrides(self.window)
        apply_ops.apply_persisted_preferences(self.window)

    def test_first_run_defaults(self):
        self.initialize()
        self.assertEqual({
            "optimize_equation_centering": False,
            "optimize_table_image_centering": False,
            "request_form_skip_tip_enabled": True,
            "id_validation_cn_enabled": False,
            "id_validation_uscc_enabled": False,
            "desc_para_split_mode": "word_period_end",
            "equation_display_scale_ratio": 0.8,
        }, snapshot_ops.settings_collect_snapshot_from_ui(self.window))
        self.assertFalse(snapshot_ops.settings_has_unsaved_changes(self.window))

    def test_saved_values_restore_without_emitting_control_signals(self):
        user_prefs.save_prefs({
            "optimize_equation_centering": True, "optimize_table_image_centering": True,
            "request_form_skip_tip_enabled": False, "id_validation_cn_enabled": True,
            "id_validation_uscc_enabled": True, "desc_para_split_mode": "period",
            "equation_display_scale_ratio": 0.65, "auto_open_pdf_preview_single": True,
        })
        changed = Mock()
        self.window.settings_opt_center.toggled.connect(changed)
        self.initialize()
        changed.assert_not_called()
        self.window._on_auto_preview_toggled.assert_not_called()
        self.assertTrue(self.window.chk_auto_open_preview.isChecked())
        self.assertTrue(self.window.settings_table_img_center.isChecked())
        self.assertEqual("period", self.window.settings_desc_split_mode.currentData())
        self.assertEqual({"equation_display_scale_ratio": 0.65}, get_effective_image_overrides(self.window))

    def test_save_commits_all_values_in_one_write_and_preserves_other_preferences(self):
        user_prefs.save_prefs({"unrelated": {"keep": True}})
        self.initialize()
        self.window.settings_opt_center.setChecked(True)
        self.window.settings_desc_split_mode.setCurrentIndex(1)
        self.window.settings_scale_ratio.setValue(0.6)
        expected = snapshot_ops.settings_collect_snapshot_from_ui(self.window)
        with patch.object(user_prefs, "_save_json_atomic", wraps=user_prefs._save_json_atomic) as write:
            self.assertTrue(save_ops.on_other_settings_save(self.window))
        write.assert_called_once()
        self.assertEqual({"unrelated": {"keep": True}, **expected}, user_prefs.load_prefs())
        self.assertTrue(self.window._opt_center_enabled)
        self.assertEqual(0.6, self.window._img_scale_ratio_override)
        self.assertFalse(snapshot_ops.settings_has_unsaved_changes(self.window))

    def test_failed_replace_keeps_file_runtime_and_unsaved_state(self):
        user_prefs.save_prefs({"unrelated": "keep"})
        self.initialize()
        original = self.prefs.read_bytes()
        saved = self.window._settings_saved_snapshot.copy()
        self.window.settings_opt_center.setChecked(True)
        self.window.settings_scale_ratio.setValue(0.55)
        with patch.object(user_prefs.os, "replace", side_effect=PermissionError("denied")):
            self.assertFalse(save_ops.on_other_settings_save(self.window))
        self.assertEqual(original, self.prefs.read_bytes())
        self.assertFalse(self.window._opt_center_enabled)
        self.assertEqual(0.8, self.window._img_scale_ratio_override)
        self.assertEqual(saved, self.window._settings_saved_snapshot)
        self.assertTrue(snapshot_ops.settings_has_unsaved_changes(self.window))
        self.assertEqual("保存失败", self.alert.call_args.args[1])

    def test_navigation_stays_on_settings_when_requested_save_fails(self):
        self.initialize()
        self.window.settings_opt_center.setChecked(True)
        self.window._confirm_leave_official_docs_if_dirty = lambda: True
        self.window._confirm_leave_settings_if_dirty = lambda: snapshot_ops.confirm_leave_settings_if_dirty(self.window)
        self.window._set_nav_checked = Mock()
        with (
            patch.object(snapshot_ops, "show_blocking_alert_modal", return_value="primary"),
            patch.object(save_ops, "save_prefs", side_effect=OSError("full")),
        ):
            self.assertFalse(NavigationMixin._confirm_leave_settings_before_navigation(self.window))
        self.window._set_nav_checked.assert_called_once_with("settings")

    def test_discard_restores_committed_controls(self):
        self.initialize()
        saved = self.window._settings_saved_snapshot.copy()
        self.window.settings_opt_center.setChecked(True)
        self.window.settings_desc_split_mode.setCurrentIndex(1)
        self.window.settings_scale_ratio.setValue(0.4)
        with patch.object(snapshot_ops, "show_blocking_alert_modal", return_value="secondary"):
            self.assertTrue(snapshot_ops.confirm_leave_settings_if_dirty(self.window))
        self.assertEqual(saved, snapshot_ops.settings_collect_snapshot_from_ui(self.window))
        self.assertFalse(snapshot_ops.settings_has_unsaved_changes(self.window))
        self.assertFalse(self.prefs.exists())

    def test_cancel_keeps_unsaved_edits(self):
        self.initialize()
        self.window.settings_opt_center.setChecked(True)
        with patch.object(snapshot_ops, "show_blocking_alert_modal", return_value="cancel"):
            self.assertFalse(snapshot_ops.confirm_leave_settings_if_dirty(self.window))
        self.assertTrue(snapshot_ops.settings_has_unsaved_changes(self.window))

    def test_retired_pixel_override_does_not_change_equation_scale(self):
        self.prefs.write_text(json.dumps({
            "image_processing_overrides": {"scale_factor": 2.0, "min_short_edge": 500},
        }), encoding="utf-8")
        self.initialize()
        self.assertEqual({"equation_display_scale_ratio": 0.8}, get_effective_image_overrides(self.window))


if __name__ == "__main__":
    unittest.main()
