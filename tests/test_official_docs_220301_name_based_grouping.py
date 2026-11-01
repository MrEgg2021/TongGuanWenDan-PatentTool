from __future__ import annotations

import unittest
from pathlib import Path


class OfficialDocs220301NameBasedGroupingTests(unittest.TestCase):
    def test_220301_not_force_corrected_by_code(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "core/official_docs/notice_name_rules.py").read_text(encoding="utf-8")
        self.assertIn('"230301": "第N次补正通知书"', text)
        self.assertIn('"230302": "第N次审查意见通知书"', text)
        self.assertNotIn('"220301":', text)

    def test_supported_types_keep_220301_raw_name_variants(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "resources/official_doc_supported_types.json").read_text(encoding="utf-8")
        self.assertIn('"key": "220301|第一次审查意见通知书"', text)
        self.assertIn('"key": "220301|第二次审查意见通知书"', text)
        self.assertNotIn('"key": "220301|第一次补正通知书"', text)


if __name__ == "__main__":
    unittest.main()
