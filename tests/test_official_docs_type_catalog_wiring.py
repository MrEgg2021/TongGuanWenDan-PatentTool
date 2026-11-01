from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source

from core.official_docs.field_registry import (
    get_supported_type_catalog,
    get_supported_type_keys,
    get_type_disabled_reason,
    is_type_processable,
)


class OfficialDocsTypeCatalogWiringTests(unittest.TestCase):
    def test_catalog_contains_unprocessable_types(self) -> None:
        catalog = get_supported_type_catalog()
        self.assertGreater(len(catalog), 0)
        unprocessable = [item for item in catalog if not bool(item.get("processable", True))]
        self.assertTrue(unprocessable)

    def test_receipt_processability_follows_current_scope(self) -> None:
        self.assertFalse(is_type_processable("200105|电子申请回执"))
        self.assertIn("回执", get_type_disabled_reason("200105|电子申请回执"))
        self.assertTrue(is_type_processable("10071|电子提交收据"))
        self.assertEqual(get_type_disabled_reason("10071|电子提交收据"), "")

    def test_processable_key_filtering(self) -> None:
        all_keys = get_supported_type_keys(include_unprocessable=True)
        processable_keys = get_supported_type_keys(include_unprocessable=False)
        self.assertGreater(len(all_keys), len(processable_keys))
        self.assertNotIn("200105|电子申请回执", processable_keys)
        self.assertIn("10071|电子提交收据", processable_keys)
        self.assertIn("PCT/ISA/210C|国际检索报告", processable_keys)
        self.assertIn("PCT/ISA/237C|国际检索单位书面意见", processable_keys)
        self.assertIn("PCT/RO/102C|关于缴纳规定费用的通知书", processable_keys)

    def test_new_notice_types_are_catalogued_and_in_default_group(self) -> None:
        from gui.main_window.mixins.official_docs_ops.shared import (
            OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS,
            _default_naming_groups_payload,
        )

        expected = {
            "200029|办理手续补正通知书",
            "210326|向外国申请专利保密审查意见通知书",
        }
        self.assertEqual(set(OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS), expected)
        catalog = {
            str(item.get("key", "")): item for item in get_supported_type_catalog()
        }
        for key in expected:
            self.assertIn(key, catalog)
            self.assertTrue(catalog[key].get("processable"))

        groups, _membership = _default_naming_groups_payload()
        review_group = next(group for group in groups if group["id"] == "review_rectification")
        members = review_group["member_type_keys"]
        self.assertIn("210326|向外国申请专利保密审查意见通知书", members)
        self.assertIn("200029|办理手续补正通知书", members)

    def test_mixin_contains_unprocessable_item_disable_wiring(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('labels.append("不可处理")', text)
        self.assertIn("TYPE_PROCESSABLE_ROLE", text)
        self.assertIn("~Qt.ItemIsSelectable", text)
        self.assertIn("~Qt.ItemIsEnabled", text)
        self.assertIn("def _match_type_search(entry: dict[str, Any], query: str)", text)


if __name__ == "__main__":
    unittest.main()
