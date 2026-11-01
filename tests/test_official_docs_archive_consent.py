import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source
from gui_source_loader import read_official_docs_dialogs_source


class OfficialDocsArchiveConsentWiringTests(unittest.TestCase):
    def test_mixin_wires_archive_consent_flow(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        mixin_text = read_official_docs_mixin_source(repo_root)
        self.assertIn("show_official_docs_archive_consent_dialog", mixin_text)
        self.assertIn("def _ensure_archive_consent", mixin_text)
        self.assertIn("def on_official_docs_archive_checkbox_toggled", mixin_text)
        self.assertIn("setChecked(False)", mixin_text)

    def test_dialog_requires_scroll_and_explicit_agreement(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        dialog_text = read_official_docs_dialogs_source(repo_root)
        self.assertIn("show_official_docs_archive_consent_dialog", dialog_text)
        self.assertIn("请先滚动到文末后再勾选同意", dialog_text)
        self.assertIn("我已完整阅读并同意启用“长期归档”", dialog_text)


if __name__ == "__main__":
    unittest.main()
