from __future__ import annotations

import unittest

from core.official_docs.field_policy import (
    get_business_field_order,
    get_naming_whitelist_from_levels,
    get_patent_type_mapping,
    get_uncertain_field_order,
    load_field_policy,
)


class OfficialDocsFieldPolicyTests(unittest.TestCase):
    def test_policy_structure_is_available(self) -> None:
        policy = load_field_policy()
        self.assertIsInstance(policy, dict)
        self.assertIn("levels", policy)
        self.assertIn("field_levels", policy)
        self.assertIn("naming", policy)

    def test_zone_orders_are_non_empty(self) -> None:
        self.assertIn("申请号", get_business_field_order())
        self.assertIn("发明名称", get_business_field_order())
        self.assertIn("DMHFLAG_raw", get_uncertain_field_order())

    def test_naming_whitelist_is_level_driven(self) -> None:
        whitelist = get_naming_whitelist_from_levels(
            candidate_fields=["申请号", "通知书类型", "DMHFLAG_raw"]
        )
        self.assertIn("申请号", whitelist)
        self.assertNotIn("通知书类型", whitelist)
        self.assertNotIn("DMHFLAG_raw", whitelist)

    def test_patent_type_mapping_includes_app_no_codes(self) -> None:
        mapping = get_patent_type_mapping()
        self.assertEqual(mapping.get("1"), "发明专利")
        self.assertEqual(mapping.get("2"), "实用新型专利")
        self.assertEqual(mapping.get("3"), "外观专利")
        self.assertEqual(mapping.get("6"), "海牙外观")
        self.assertEqual(mapping.get("8"), "PCT发明")
        self.assertEqual(mapping.get("9"), "PCT实用新型")


if __name__ == "__main__":
    unittest.main()
