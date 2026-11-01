import unittest
from pathlib import Path


class UiComboStyleWiringTests(unittest.TestCase):
    @staticmethod
    def _read(path: str) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / path).read_text(encoding="utf-8")

    def test_theme_has_global_combobox_popup_container_style(self) -> None:
        qss = self._read("gui/ui_layout_impl/theme.qss")
        self.assertIn("QComboBox QComboBoxPrivateContainer", qss)
        self.assertIn("QComboBox QAbstractItemView", qss)
        self.assertIn("QComboBox::drop-down", qss)




if __name__ == "__main__":
    unittest.main()
