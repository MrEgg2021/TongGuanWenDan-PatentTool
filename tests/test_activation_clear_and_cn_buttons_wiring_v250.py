from pathlib import Path
import unittest


class ActivationClearAndCnButtonsWiringV250Tests(unittest.TestCase):
    @staticmethod
    def _read(path: str) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / path).read_text(encoding="utf-8")



    def test_official_docs_unsaved_confirm_uses_cn_buttons(self) -> None:
        text = self._read("gui/main_window/mixins/official_docs_ops/settings_ops.py")
        self.assertIn('btn_save = box.addButton("保存", QMessageBox.AcceptRole)', text)
        self.assertIn('btn_discard = box.addButton("不保存", QMessageBox.DestructiveRole)', text)
        self.assertIn('box.addButton("取消", QMessageBox.RejectRole)', text)
        self.assertNotIn(
            "QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel",
            text,
        )


if __name__ == "__main__":
    unittest.main()

