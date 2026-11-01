from __future__ import annotations

import unittest
from pathlib import Path


class ThemeQssTextQualityTests(unittest.TestCase):
    def test_theme_qss_comments_do_not_contain_common_mojibake_markers(self) -> None:
        text = Path("gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")

        markers = ("閫", "鏂", "鑳", "榛", "鈥", "锛", "€")
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
