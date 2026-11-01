import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_page_source


class OfficialDocsNamingAliasSplitterWiringTests(unittest.TestCase):
    def test_naming_splitter_is_exposed_and_wired(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('naming_splitter.setObjectName("OfficialDocsNamingConfigSplitter")', text)
        self.assertIn('naming_splitter = settings_ctx["naming_splitter"]', text)
        self.assertIn(
            "naming_splitter.splitterMoved.connect(window.on_official_docs_naming_splitter_moved)",
            text,
        )
        self.assertIn("window.official_docs_naming_splitter = naming_splitter", text)


if __name__ == "__main__":
    unittest.main()
