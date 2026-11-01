from __future__ import annotations

import unittest
from pathlib import Path


class OfficialDocsTypeTreeVisualWiringTests(unittest.TestCase):
    def test_theme_defines_explicit_open_closed_branch_icons(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn('QTreeWidget#OfficialDocsTypeTree::branch:closed:has-children', text)
        self.assertIn('QTreeWidget#OfficialDocsTypeTree::branch:open:has-children', text)
        self.assertIn('image: url("__THEME_DIR__/assets/chevron_right.svg");', text)
        self.assertIn('image: url("__THEME_DIR__/assets/chevron_down.svg");', text)

    def test_stylesheet_warns_when_chevron_right_asset_is_missing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/ui_layout_impl/stylesheet.py").read_text(encoding="utf-8")
        self.assertIn('theme_path.parent / "assets" / "chevron_right.svg"', text)

    def test_chevron_right_asset_exists(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        asset = repo_root / "gui/ui_layout_impl/assets/chevron_right.svg"
        self.assertTrue(asset.exists(), f"missing asset: {asset}")


if __name__ == "__main__":
    unittest.main()
