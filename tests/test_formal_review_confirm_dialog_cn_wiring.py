import unittest
from pathlib import Path


class FormalReviewConfirmDialogCnWiringTests(unittest.TestCase):
    def test_shared_has_continue_cancel_helper(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/shared.py").read_text(encoding="utf-8")
        self.assertIn("def _ask_continue_cancel_cn(", source)
        self.assertIn("continue_text=\"继续\"", source)
        self.assertIn("cancel_text=\"取消\"", source)
        self.assertIn("yes_btn.setText(\"继续\")", source)
        self.assertIn("no_btn.setText(\"取消\")", source)

    def test_formal_review_ops_no_direct_qmessagebox_question(self) -> None:
        ops_dir = Path("gui/main_window/mixins/formal_review_ops")
        for fp in ops_dir.glob("*.py"):
            source = fp.read_text(encoding="utf-8")
            self.assertNotIn("QMessageBox.question(", source, msg=f"{fp} still uses QMessageBox.question")


if __name__ == "__main__":
    unittest.main()
