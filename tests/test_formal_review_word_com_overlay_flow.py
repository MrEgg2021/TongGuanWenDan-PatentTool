import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewWordComOverlayFlowTests(unittest.TestCase):
    def test_choose_file_requires_clean_gate_before_start(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def on_formal_review_choose_file(self):", text)
        self.assertIn('if not self._ensure_companion_doc_clean_or_prompt(trigger="choose_file", allow_retry=False):', text)
        self.assertIn("self._set_status_text(\"形式审查：工作副本已就绪，请点击“开始审查”。\")", text)

    def test_word_start_check_shows_and_hides_overlay(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def on_formal_review_start_check(self):", text)
        self.assertIn("self._show_formal_review_overlay(overlay_title, overlay_file)", text)
        self.assertIn("正在执行形式审查并同步批注，请不要编辑 Word 文档，请稍等。", text)
        self.assertNotIn("正在审核稿件并生成标记，请不要进行其他操作，请稍等。", text)
        self.assertIn("self._formal_review_overlay_progress_callback = (", text)
        self.assertIn("self._run_companion_review_cycle(trigger=\"start_check\", auto_sync_comments=True, redock=False)", text)
        self.assertIn("self._hide_formal_review_overlay(overlay_visible)", text)

    def test_choose_file_shows_open_word_overlay(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def on_formal_review_choose_file(self):", text)
        self.assertIn("正在打开形式审查工作副本，请不要编辑 Word 文档，请稍等。", text)
        self.assertIn("正在连接工作副本文档，请稍等。", text)
        self.assertIn("正在检查旧批注、修订和保存状态，请稍等。", text)
        self.assertNotIn("正在打开 Word 窗口，请不要进行其他操作，请稍等。", text)
        self.assertIn("self._show_formal_review_overlay(overlay_title, overlay_file)", text)
        self.assertIn("self._hide_formal_review_overlay(overlay_visible)", text)

    def test_overlay_show_and_update_force_first_frame_render(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _show_formal_review_overlay(self, status_text: str, file_text: str = \"\") -> bool:", text)
        self.assertIn("def _update_formal_review_overlay(self, percent: int, status_text: str = \"\", detail_text: str = \"\") -> None:", text)
        self.assertIn("ui_pump_api.pump(allow_user_input=False)", text)

    def test_word_mode_parse_delegates_to_connect_path(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def on_formal_review_parse(self):", text)
        self.assertIn('if mode == "word":', text)
        self.assertIn("self.on_formal_review_connect_word()", text)

    def test_export_annotated_word_flow_is_removed(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn("def on_formal_review_export_annotated_word", text)
        self.assertNotIn("导出批注Word", text)
        self.assertNotIn("导出批注 Word", text)


if __name__ == "__main__":
    unittest.main()
