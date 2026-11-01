from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source

from core.tgd_data_management_impl.pinyin_utils import get_pinyin_full, get_pinyin_initials


class OfficialDocsTypeSearchMatchTests(unittest.TestCase):
    def test_pinyin_utils_support_full_and_initials(self) -> None:
        text = "审查意见通知书"
        self.assertIn("shencha", get_pinyin_full(text))
        self.assertIn("scyj", get_pinyin_initials(text))

    def test_mixin_matcher_uses_all_search_dimensions(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        content = read_official_docs_mixin_source(repo_root)
        self.assertIn('str(terms.get("display_name", "") or "").lower()', content)
        self.assertIn('str(terms.get("code", "") or "").lower()', content)
        self.assertIn('str(terms.get("pinyin_full", "") or "").lower()', content)
        self.assertIn('str(terms.get("pinyin_initials", "") or "").lower()', content)
        self.assertIn("member_keys = entry.get(\"member_keys\")", content)
        self.assertIn("member_code = _extract_notice_code(member_text)", content)
        self.assertIn("return any(key in target for target in targets if target)", content)

    def test_new_notice_types_match_code_name_keyword_and_pinyin(self) -> None:
        from gui.main_window.mixins.official_docs_ops.shared import _match_type_search

        entries = [
            {
                "key": "200029|办理手续补正通知书",
                "display_name": "办理手续补正通知书",
            },
            {
                "key": "210326|向外国申请专利保密审查意见通知书",
                "display_name": "向外国申请专利保密审查意见通知书",
            },
        ]
        self.assertTrue(_match_type_search(entries[0], "200029"))
        self.assertTrue(_match_type_search(entries[0], "办理手续补正通知书"))
        self.assertTrue(_match_type_search(entries[0], "补正"))
        self.assertTrue(_match_type_search(entries[0], "blsx"))
        self.assertTrue(_match_type_search(entries[1], "210326"))
        self.assertTrue(_match_type_search(entries[1], "外国申请专利保密审查"))
        self.assertTrue(_match_type_search(entries[1], "wg"))


if __name__ == "__main__":
    unittest.main()
