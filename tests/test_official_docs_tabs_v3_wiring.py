from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_page_source


class OfficialDocsTabsV3WiringTests(unittest.TestCase):
    def test_tabs_include_task_naming_archive_and_pdf_parse(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('tabs.addTab(task_tab, "处理任务")', text)
        self.assertIn('tabs.addTab(settings_tab, "命名归档")', text)
        self.assertIn('tabs.addTab(pdf_parse_tab, "PDF解析")', text)


if __name__ == "__main__":
    unittest.main()
