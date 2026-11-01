import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewUiSignalRegressionTests(unittest.TestCase):
    def test_wordlist_dialog_accept_code_uses_qdialog_enum(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("QDialog.DialogCode.Accepted", text)

    def test_checkstate_comparison_uses_qt_checkstate_enum(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("Qt.CheckState.Checked", text)
        self.assertIn("Qt.CheckState(state)", text)


if __name__ == "__main__":
    unittest.main()
