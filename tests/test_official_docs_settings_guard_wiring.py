import unittest
from pathlib import Path
from gui_source_loader import read_navigation_mixin_source


class OfficialDocsSettingsGuardWiringTests(unittest.TestCase):
    def test_navigation_checks_official_docs_unsaved_guard(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_navigation_mixin_source(repo_root)
        self.assertIn("_confirm_leave_official_docs_if_dirty", text)

    def test_tray_checks_official_docs_unsaved_guard(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/main_window/mixins/tray_mixin.py").read_text(encoding="utf-8")
        self.assertIn("_confirm_leave_official_docs_if_dirty", text)


if __name__ == "__main__":
    unittest.main()
