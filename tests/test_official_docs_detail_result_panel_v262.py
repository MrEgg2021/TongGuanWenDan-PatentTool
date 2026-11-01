from __future__ import annotations

import unittest
from pathlib import Path

from official_docs_source_loader import read_official_docs_mixin_source


class OfficialDocsDetailResultPanelV262Tests(unittest.TestCase):
    def test_detail_panel_uses_expected_and_actual_sections(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('"预计信息"', text)
        self.assertIn('"实际结果"', text)
        self.assertIn('f"预计输出 PDF 名称: {preview_name or \'-\'}"', text)
        self.assertIn('f"处理状态: {actual_status or \'-\'}"', text)
        self.assertIn('f"实际输出 PDF 名称: {actual_output_name or \'-\'}"', text)

    def test_process_results_are_cached_back_to_leaf_state(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("def _cache_official_docs_process_results(self, summary: ProcessSummary) -> None:", text)
        self.assertIn('leaf["last_result"] = {', text)
        self.assertIn('"status": str(result.status or "")', text)
        self.assertIn('"reason": str(result.reason or "")', text)
        self.assertIn('self._cache_official_docs_process_results(summary)', text)


if __name__ == "__main__":
    unittest.main()
