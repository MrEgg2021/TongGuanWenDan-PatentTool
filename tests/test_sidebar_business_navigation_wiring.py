import unittest
from pathlib import Path

from gui_source_loader import read_modern_shell_source


class SidebarBusinessNavigationWiringTests(unittest.TestCase):
    def test_sidebar_width_contract_matches_spec(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_modern_shell_source(repo_root)
        self.assertIn("SIDEBAR_WIDTH_EXPANDED = 200", text)
        self.assertIn("SIDEBAR_WIDTH_COLLAPSED = 64", text)

    def test_business_entries_are_direct_sidebar_items_in_stable_order(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_modern_shell_source(repo_root)
        i_preview = text.find("layout.addWidget(nav_preview)")
        i_data = text.find("layout.addWidget(nav_data_management)")
        i_official = text.find("layout.addWidget(nav_official_docs)")
        i_formal = text.find("layout.addWidget(nav_formal_review)")
        i_settings = text.find("layout.addWidget(nav_settings)")
        self.assertGreaterEqual(i_preview, 0)
        self.assertGreaterEqual(i_data, 0)
        self.assertGreaterEqual(i_official, 0)
        self.assertGreaterEqual(i_formal, 0)
        self.assertGreaterEqual(i_settings, 0)
        self.assertLess(i_preview, i_data)
        self.assertLess(i_data, i_official)
        self.assertLess(i_official, i_formal)
        self.assertLess(i_formal, i_settings)

    def test_retired_access_group_wiring_is_removed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_modern_shell_source(repo_root)
        self.assertNotIn('subscription_header = QPushButton("订阅功能', text)
        self.assertNotIn("subscription_container = QFrame()", text)
        self.assertNotIn("subscription_layout.addWidget(", text)
        self.assertNotIn('nav_data_management.setProperty("subItem", True)', text)
        self.assertNotIn('nav_official_docs.setProperty("subItem", True)', text)
        self.assertNotIn('nav_formal_review.setProperty("subItem", True)', text)


if __name__ == "__main__":
    unittest.main()
