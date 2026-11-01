import unittest
from pathlib import Path


class FormalReviewOverlayWarningCopyWiringTests(unittest.TestCase):
    def test_formal_review_overlay_warning_helper_exists(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _resolve_formal_review_warning_text(status_text: str) -> str:", source)
        self.assertIn("def _apply_formal_review_overlay_warning(self, status_text: str) -> None:", source)
        self.assertIn("⚠ 形式审查准备中：请勿关闭 Word 或切换到其他文档。", source)
        self.assertIn("⚠ 形式审查进行中：请勿手动编辑 Word 正文或切换窗口，避免定位偏差。", source)
        self.assertIn("⚠ 正在写入修订：请勿操作键鼠、切换窗口或关闭 Word，避免写入中断。", source)
        self.assertIn("⚠ 形式审查处理中，请稍候。", source)
        self.assertNotIn("转换期间请不要操作鼠标或键盘", source)

    def test_show_and_update_overlay_apply_formal_review_warning(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(encoding="utf-8")
        self.assertIn("self._apply_formal_review_overlay_warning(str(status_text or \"\"))", source)
        show_pos = source.find("def _show_formal_review_overlay")
        update_pos = source.find("def _update_formal_review_overlay")
        apply_pos = source.find("self._apply_formal_review_overlay_warning(str(status_text or \"\"))")
        self.assertGreaterEqual(show_pos, 0)
        self.assertGreaterEqual(update_pos, 0)
        self.assertGreaterEqual(apply_pos, 0)


if __name__ == "__main__":
    unittest.main()
