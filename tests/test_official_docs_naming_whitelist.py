from __future__ import annotations

import unittest

from core.official_docs.field_registry import FORBIDDEN_NAMING_FIELDS, get_type_tokens


class OfficialDocsNamingWhitelistTests(unittest.TestCase):
    def test_forbidden_fields_not_in_naming_tokens(self) -> None:
        forbidden = {str(token or "").strip() for token in FORBIDDEN_NAMING_FIELDS if str(token or "").strip()}
        for notice_type in ("exam_opinion", "rectification"):
            tokens = set(get_type_tokens(notice_type))
            self.assertTrue(forbidden.isdisjoint(tokens))

    def test_apply_date_field_visible_for_naming(self) -> None:
        tokens = get_type_tokens("exam_opinion")
        self.assertIn("申请日", tokens)
        self.assertIn("发明名称", tokens)
        self.assertIn("申请人信息", tokens)
        self.assertNotIn("通知书类型", tokens)
        self.assertNotIn("次数", tokens)


if __name__ == "__main__":
    unittest.main()
