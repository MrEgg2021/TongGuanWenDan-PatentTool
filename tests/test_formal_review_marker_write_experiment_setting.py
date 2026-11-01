import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewSettingsDualModeTests(unittest.TestCase):
    def test_settings_dialog_no_longer_exposes_experiment_toggle(self) -> None:
        text = Path("gui/widgets_impl/formal_review/settings_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn("marker_write_experiment_enabled", text)
        self.assertIn("结果可能部分完成", text)
        self.assertNotIn("原子提交", text)

    def test_mixin_no_longer_persists_experiment_pref(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn("_MARKER_WRITE_EXPERIMENT_PREF_KEY", text)
        self.assertNotIn("_formal_review_marker_write_experiment", text)


if __name__ == "__main__":
    unittest.main()
