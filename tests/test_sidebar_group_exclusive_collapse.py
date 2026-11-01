import unittest
from pathlib import Path
from gui_source_loader import read_modern_shell_source


class SidebarGroupExclusiveCollapseTests(unittest.TestCase):
    def test_only_domestic_group_defaults_to_collapsed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_modern_shell_source(repo_root)
        self.assertIn("sidebar._domestic_conversion_expanded = False", text)
        self.assertNotIn("sidebar._subscription_expanded = False", text)

    def test_domestic_group_no_longer_tracks_subscription_exclusivity(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_modern_shell_source(repo_root)
        self.assertNotIn('exclusive_other_attr="_subscription_expanded"', text)
        self.assertNotIn('exclusive_other_attr="_domestic_conversion_expanded"', text)
        self.assertNotIn('expanded_attr="_subscription_expanded"', text)

    def test_sidebar_is_compact_without_middle_stretch(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_modern_shell_source(repo_root)
        start = text.find("def _build_sidebar() -> QFrame:")
        end = text.find("def _build_header(", start)
        section = text[start:end] if start >= 0 and end > start else text
        self.assertNotIn("layout.addStretch(1)", section)


if __name__ == "__main__":
    unittest.main()
