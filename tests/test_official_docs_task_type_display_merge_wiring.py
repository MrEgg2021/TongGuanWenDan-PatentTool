from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source


class OfficialDocsTaskTypeDisplayMergeWiringTests(unittest.TestCase):
    def test_task_page_uses_canonical_notice_name_for_display(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)

        self.assertIn("def _canonical_notice_name_for_display(notice_name: str) -> str:", text)
        self.assertIn(
            "canonical_notice_name = _canonical_notice_name_for_display(",
            text,
        )
        self.assertIn(
            "notice_name = _canonical_notice_name_for_display(",
            text,
        )
        self.assertIn(
            '_canonical_notice_name_for_display(normalize_notice_name_for_meta(parsed.meta) or parsed.meta.notice_name) or \'-\'',
            text,
        )

    def test_task_page_leaf_row_orders_notice_appno_package(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)

        self.assertIn("summary_parts = [notice_name]", text)
        self.assertIn("summary_parts.append(app_no)", text)
        self.assertIn("summary_parts.append(name)", text)


if __name__ == "__main__":
    unittest.main()

