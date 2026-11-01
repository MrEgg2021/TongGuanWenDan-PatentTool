from __future__ import annotations

from pathlib import Path
import unittest


class QtContextMenuCnTranslatorWiringV251Tests(unittest.TestCase):
    @staticmethod
    def _read(rel_path: str) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / rel_path).read_text(encoding="utf-8")

    def test_main_app_startup_installs_translator(self) -> None:
        text = self._read("gui_app.py")
        self.assertIn("from core.qt_i18n import install_qt_zh_translator", text)
        self.assertIn("install_qt_zh_translator(app, logger=logger)", text)



if __name__ == "__main__":
    unittest.main()
