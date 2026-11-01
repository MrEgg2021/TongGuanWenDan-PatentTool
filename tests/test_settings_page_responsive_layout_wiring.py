import unittest
from pathlib import Path


class SettingsPageResponsiveLayoutWiringTests(unittest.TestCase):
    def test_root_content_is_expandable_in_page_row(self) -> None:
        source = Path("gui/ui_layout_impl/settings_page.py").read_text(encoding="utf-8")
        self.assertIn("content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)", source)
        self.assertIn("page_row.addWidget(content, 1)", source)
        self.assertNotIn("page_row.addWidget(content, 0)", source)
        self.assertNotIn("page_row.addStretch(1)", source)


if __name__ == "__main__":
    unittest.main()
