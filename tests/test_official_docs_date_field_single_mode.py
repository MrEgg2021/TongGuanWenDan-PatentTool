from __future__ import annotations

import unittest

from core.official_docs.field_registry import get_type_tokens
from core.official_docs.naming_rules import normalize_type_naming_config


class OfficialDocsDateFieldSingleModeTests(unittest.TestCase):
    def test_type_tokens_only_keep_issue_date(self) -> None:
        tokens = get_type_tokens("exam_opinion")
        self.assertIn("发文日", tokens)
        self.assertNotIn("发文日8", tokens)

    def test_legacy_issue_date8_is_migrated_to_issue_date(self) -> None:
        cfg = normalize_type_naming_config(
            {"naming_mode": "custom", "filename_fields": ["申请号", "发文日8", "通知书名称"]},
            "exam_opinion",
        )
        self.assertEqual(cfg.filename_fields, ["申请号", "发文日", "通知书名称"])

    def test_migration_deduplicates_issue_date_tokens(self) -> None:
        cfg = normalize_type_naming_config(
            {"naming_mode": "custom", "filename_fields": ["申请号", "发文日", "发文日8", "通知书名称"]},
            "exam_opinion",
        )
        self.assertEqual(cfg.filename_fields, ["申请号", "发文日", "通知书名称"])


if __name__ == "__main__":
    unittest.main()
