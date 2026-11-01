import unittest
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewRevisionApplyWiringTests(unittest.TestCase):
    def test_page_uses_marker_direct_button_and_hides_top_revision_buttons(self) -> None:
        text = read_formal_review_page_source()
        self.assertIn('marker_apply_btn = QPushButton("生成附图标记修订")', text)
        self.assertIn("marker_apply_btn.clicked.connect(window.on_formal_review_apply_marker_revision_direct)", text)
        self.assertIn("window.formal_review_build_revision_plan_button = None", text)
        self.assertIn("window.formal_review_apply_revision_plan_button = None", text)
        self.assertIn("window.formal_review_apply_marker_button = marker_apply_btn", text)
        self.assertNotIn("btn_build_plan = QPushButton(", text)
        self.assertNotIn("btn_apply_plan = QPushButton(", text)
        self.assertNotIn("connect_word_btn = QPushButton(", text)

    def test_mixin_has_marker_direct_apply_handler(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def on_formal_review_apply_marker_revision_direct(self):", text)
        self.assertIn("正在以修订模式生成附图标记，请不要进行其他操作，请稍等。", text)
        self.assertIn("self._hide_processing_overlay_cancel_button()", text)
        self.assertIn("run_write_preflight(", text)
        self.assertIn("apply_write_commands(", text)
        self.assertIn("atomic_commit=False", text)
        self.assertIn("是否继续修改", text)


if __name__ == "__main__":
    unittest.main()
