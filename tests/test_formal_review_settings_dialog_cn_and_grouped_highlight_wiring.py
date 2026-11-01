import unittest

from tests.formal_review_settings_dialog_source_loader import load_formal_review_settings_dialog_source


class FormalReviewSettingsDialogCnAndGroupedHighlightWiringTests(unittest.TestCase):
    def test_bottom_buttons_are_cn(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn('save_button.setText("保存")', source)
        self.assertIn('cancel_button.setText("取消")', source)
        self.assertIn('reset_button = QPushButton("恢复默认颜色")', source)

    def test_highlight_tab_has_three_levels_domain_fold_and_advanced_mode(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn('"forbid": "禁止级别"', source)
        self.assertIn('"warn": "警告级别"', source)
        self.assertIn('"remind": "提醒级别"', source)
        self.assertIn('"claims": "与权利要求书相关的"', source)
        self.assertIn('"abstract": "与说明书摘要相关的"', source)
        self.assertIn('"description": "与说明书相关的"', source)
        self.assertIn('"drawings": "与说明书附图相关的"', source)
        self.assertIn('"general": "通用"', source)
        self.assertIn('self._advanced_color_mode_check = QCheckBox("显示高级逐规则配色")', source)
        self.assertIn("toggle_button.toggled.connect(lambda checked, _domain=domain: self._toggle_domain_section(_domain, checked))", source)
        self.assertIn("def _on_toggle_advanced_color_mode(self, checked: bool) -> None:", source)


if __name__ == "__main__":
    unittest.main()

