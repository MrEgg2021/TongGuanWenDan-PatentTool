from __future__ import annotations

from pathlib import Path
import unittest

from gui.main_window.mixins.official_docs_ops import shared


class OfficialDocsConfirmDefaultV260Tests(unittest.TestCase):
    @staticmethod
    def _read(path: str) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / path).read_text(encoding="utf-8")

    def test_ui_default_unchecks_confirm_each(self) -> None:
        text = self._read("gui/ui_layout_impl/official_docs_page_parts/settings_panel.py")
        self.assertIn("chk_confirm.setChecked(False)", text)

    def test_shared_default_settings_disable_confirm_each(self) -> None:
        defaults = shared._default_settings()
        self.assertIs(defaults["confirm_each"], False)


if __name__ == "__main__":
    unittest.main()
