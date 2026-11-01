import unittest
from pathlib import Path

from tests.official_docs_source_loader import read_official_docs_page_source


class OfficialDocsSettingsSplitterWiringTests(unittest.TestCase):
    def test_settings_uses_horizontal_splitter(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("settings_splitter = QSplitter(Qt.Horizontal)", text)
        self.assertIn('settings_splitter.setObjectName("OfficialDocsSettingsSplitter")', text)
        self.assertIn("settings_splitter.setChildrenCollapsible(False)", text)
        self.assertIn("settings_splitter.addWidget(type_card)", text)
        self.assertIn("settings_splitter.addWidget(config_container)", text)
        self.assertIn("settings_splitter.setStretchFactor(0, 1)", text)
        self.assertIn("settings_splitter.setStretchFactor(1, 3)", text)
        self.assertIn("type_card.setMinimumWidth(340)", text)
        self.assertIn("settings_splitter.setSizes([430, 930])", text)
        self.assertIn("settings_root.addWidget(settings_splitter, 1)", text)
        self.assertIn("window.official_docs_settings_splitter = settings_splitter", text)


if __name__ == "__main__":
    unittest.main()
