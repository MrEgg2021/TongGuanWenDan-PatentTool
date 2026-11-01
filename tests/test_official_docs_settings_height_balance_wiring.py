import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_page_source


class OfficialDocsSettingsHeightBalanceWiringTests(unittest.TestCase):
    def test_filename_and_alias_use_vertical_splitter(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("naming_splitter = QSplitter(Qt.Vertical)", text)
        self.assertIn('naming_splitter.setObjectName("OfficialDocsNamingConfigSplitter")', text)
        self.assertIn("naming_splitter.setChildrenCollapsible(False)", text)
        self.assertIn("naming_splitter.addWidget(filename_card)", text)
        self.assertIn("naming_splitter.addWidget(alias_card)", text)
        self.assertIn("naming_splitter.setStretchFactor(0, 3)", text)
        self.assertIn("naming_splitter.setStretchFactor(1, 2)", text)
        self.assertIn("naming_splitter.setSizes([3, 2])", text)

    def test_alias_table_keeps_min_height_without_hard_max_lock(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("table.setMinimumHeight(120)", text)
        self.assertNotIn("table.setMaximumHeight(76)", text)


if __name__ == "__main__":
    unittest.main()
