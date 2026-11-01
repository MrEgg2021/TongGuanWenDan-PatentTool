from __future__ import annotations

import unittest

from core.official_docs.field_registry import (
    PATENT_GROUP_DESIGN,
    PATENT_GROUP_INVENTION,
    PATENT_GROUP_UTILITY,
    get_supported_type_catalog,
    get_supported_type_keys,
    get_type_disabled_reason,
    get_type_display_name,
    infer_patent_group_from_type_key,
    is_notice_key_processable,
    is_type_processable,
    normalize_notice_type,
)


class OfficialDocsFieldRegistryTests(unittest.TestCase):
    def test_normalize_preserves_notice_key(self) -> None:
        key = "200601|办理登记手续通知书"
        self.assertEqual(normalize_notice_type(key), key)

    def test_display_name_for_notice_key(self) -> None:
        text = get_type_display_name("200601|办理登记手续通知书")
        self.assertEqual(text, "办理登记手续通知书（200601）")

    def test_display_name_for_builtin_kind(self) -> None:
        self.assertEqual(get_type_display_name("exam_opinion"), "审查意见通知书")
        self.assertEqual(get_type_display_name("rectification"), "补正通知书")

    def test_supported_catalog_contains_items(self) -> None:
        catalog = get_supported_type_catalog()
        self.assertGreater(len(catalog), 0)
        self.assertTrue(any(str(item.get("key", "")).strip() == "exam_opinion" for item in catalog))

    def test_processable_lookup_for_receipt_types(self) -> None:
        self.assertFalse(is_type_processable("200105|电子申请回执"))
        self.assertIn("回执", get_type_disabled_reason("200105|电子申请回执"))
        self.assertTrue(is_type_processable("10071|电子提交收据"))
        self.assertEqual(get_type_disabled_reason("10071|电子提交收据"), "")

    def test_get_supported_type_keys_can_filter_unprocessable(self) -> None:
        all_keys = get_supported_type_keys(include_unprocessable=True)
        processable = get_supported_type_keys(include_unprocessable=False)
        self.assertIn("200105|电子申请回执", all_keys)
        self.assertIn("10071|电子提交收据", all_keys)
        self.assertNotIn("200105|电子申请回执", processable)
        self.assertIn("10071|电子提交收据", processable)
        self.assertIn("PCT/ISA/210C|国际检索报告", processable)
        self.assertIn("PCT/RO/102C|关于缴纳规定费用的通知书", processable)

    def test_notice_key_processability_applies_pct_whitelist(self) -> None:
        ok, reason = is_notice_key_processable("PCT/ISA/210C|国际检索报告")
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        ok_unknown_pct, reason_unknown_pct = is_notice_key_processable("PCT/NEW/999|未知PCT通知书")
        self.assertFalse(ok_unknown_pct)
        self.assertIn("白名单", reason_unknown_pct)

        ok_receipt, reason_receipt = is_notice_key_processable("200105|电子申请回执")
        self.assertFalse(ok_receipt)
        self.assertIn("回执", reason_receipt)

    def test_patent_group_inference(self) -> None:
        self.assertEqual(infer_patent_group_from_type_key("210403|第N次审查意见通知书"), PATENT_GROUP_INVENTION)
        self.assertEqual(infer_patent_group_from_type_key("220301|第一次审查意见通知书"), PATENT_GROUP_UTILITY)
        self.assertEqual(infer_patent_group_from_type_key("230302|第N次审查意见通知书"), PATENT_GROUP_DESIGN)


if __name__ == "__main__":
    unittest.main()
