import unittest
from pathlib import Path


class FormalReviewOverlayVisibilityWiringTests(unittest.TestCase):
    def test_companion_overlay_helpers_force_event_refresh(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _show_formal_review_overlay(self, status_text: str, file_text: str = \"\") -> bool:", source)
        self.assertIn("def _update_formal_review_overlay(self, percent: int, status_text: str = \"\", detail_text: str = \"\") -> None:", source)
        self.assertIn("ui_pump_api.pump(allow_user_input=False)", source)

    def test_choose_and_start_review_use_overlay_show_update_hide(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(encoding="utf-8")
        self.assertIn("overlay_title = \"正在打开形式审查工作副本，请不要编辑 Word 文档，请稍等。\"", source)
        self.assertIn("overlay_title = \"正在执行形式审查并同步批注，请不要编辑 Word 文档，请稍等。\"", source)
        self.assertIn("overlay_visible = self._show_formal_review_overlay(overlay_title, overlay_file)", source)
        self.assertIn("self._update_formal_review_overlay(8, overlay_title, overlay_file)", source)
        self.assertIn("self._formal_review_overlay_progress_callback = (", source)
        self.assertIn("self._hide_formal_review_overlay(overlay_visible)", source)

    def test_marker_revision_use_overlay_show_update_hide(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/marker_ops.py").read_text(encoding="utf-8")
        self.assertIn("overlay_title = \"正在以修订模式生成附图标记，请不要进行其他操作，请稍等。\"", source)
        self.assertIn("overlay_visible = self._show_formal_review_overlay(overlay_title, overlay_file)", source)
        self.assertIn("self._update_formal_review_overlay(40, \"正在执行修订预检，请稍等。\", overlay_file)", source)
        self.assertIn("self._update_formal_review_overlay(76, \"正在应用修订，请稍等。\", overlay_file)", source)
        self.assertIn("self._hide_formal_review_overlay(overlay_visible)", source)

    def test_marker_revision_analysis_stage_overlay_progress(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/marker_ops.py").read_text(encoding="utf-8")
        self.assertIn("analysis_overlay_visible = self._show_formal_review_overlay(overlay_title, overlay_file)", source)
        self.assertIn("self._update_formal_review_overlay(10, \"正在准备分析环境，请稍等。\", overlay_file)", source)
        self.assertIn("self._update_formal_review_overlay(35, \"正在解析标号说明并生成修订计划，请稍等。\", overlay_file)", source)
        self.assertIn("self._update_formal_review_overlay(70, \"正在校验应用范围，请稍等。\", overlay_file)", source)
        self.assertIn("self._update_formal_review_overlay(100, \"分析完成，等待确认。\", overlay_file)", source)
        self.assertIn("self._hide_formal_review_overlay(analysis_overlay_visible)", source)
        self.assertLess(
            source.find("analysis_overlay_visible = self._show_formal_review_overlay(overlay_title, overlay_file)"),
            source.find("plan, scope_missing = self._build_combined_write_plan()"),
        )


if __name__ == "__main__":
    unittest.main()
