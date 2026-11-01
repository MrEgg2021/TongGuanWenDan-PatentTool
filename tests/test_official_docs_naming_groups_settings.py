from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from gui.main_window.mixins.official_docs_mixin import OfficialDocsMixin
from gui.main_window.mixins.official_docs_ops import shared


class OfficialDocsNamingGroupsSettingsTests(unittest.TestCase):
    def test_default_settings_include_group_fields(self) -> None:
        defaults = shared._default_settings()

        self.assertIn("naming_groups", defaults)
        self.assertIn("type_group_membership", defaults)
        group_names = {str(group.get("name", "")) for group in defaults["naming_groups"]}
        self.assertIn("证书", group_names)
        self.assertIn("收据", group_names)
        self.assertIn("费用通知", group_names)
        self.assertEqual(defaults["type_group_membership"]["10071|电子提交收据"], "receipt")
        self.assertNotIn("200105|电子申请回执", defaults["type_group_membership"])

    def test_normalize_empty_group_settings_injects_default_groups(self) -> None:
        dummy = OfficialDocsMixin()
        raw = {
            "version": shared.OFFICIAL_DOC_SETTINGS_VERSION,
            "write_summary": True,
            "write_archive": False,
            "confirm_each": False,
            "enable_exam_pdf_parse": False,
            "summary_root_dir": "D:/summary",
            "archive_root_dir": "D:/archive",
            "type_configs": {},
            "naming_groups": [],
            "type_group_membership": {},
        }

        with patch("gui.main_window.mixins.official_docs_ops.state_ops.set_official_doc_settings"):
            normalized = dummy._normalize_official_doc_settings(raw)

        self.assertEqual(normalized["type_group_membership"]["10071|电子提交收据"], "receipt")
        self.assertNotIn("200105|电子申请回执", normalized["type_group_membership"])

    def test_normalize_untouched_legacy_defaults_adds_new_review_rectification_types(self) -> None:
        dummy = OfficialDocsMixin()
        raw = copy.deepcopy(shared._default_settings())
        added_keys = set(shared.OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS)
        for group in raw["naming_groups"]:
            if group["id"] == "review_rectification":
                group["member_type_keys"] = [
                    key for key in group["member_type_keys"] if key not in added_keys
                ]
        for key in added_keys:
            raw["type_group_membership"].pop(key, None)

        with patch("gui.main_window.mixins.official_docs_ops.state_ops.set_official_doc_settings"):
            normalized = dummy._normalize_official_doc_settings(raw)

        review_group = next(group for group in normalized["naming_groups"] if group["id"] == "review_rectification")
        for key in added_keys:
            self.assertEqual(normalized["type_group_membership"][key], "review_rectification")
            self.assertEqual(review_group["member_type_keys"].count(key), 1)

    def test_normalize_customized_legacy_defaults_does_not_move_new_types(self) -> None:
        dummy = OfficialDocsMixin()
        raw = copy.deepcopy(shared._default_settings())
        added_keys = set(shared.OFFICIAL_DOC_REVIEW_RECTIFICATION_NEW_TYPE_KEYS)
        for group in raw["naming_groups"]:
            if group["id"] == "review_rectification":
                group["name"] = "我的审查分组"
                group["member_type_keys"] = [
                    key for key in group["member_type_keys"] if key not in added_keys
                ]
        for key in added_keys:
            raw["type_group_membership"].pop(key, None)

        with patch("gui.main_window.mixins.official_docs_ops.state_ops.set_official_doc_settings"):
            normalized = dummy._normalize_official_doc_settings(raw)

        self.assertEqual(normalized["naming_groups"][0]["name"], "我的审查分组")
        for key in added_keys:
            self.assertNotIn(key, normalized["type_group_membership"])

    def test_normalize_settings_preserves_groups_and_membership(self) -> None:
        dummy = OfficialDocsMixin()
        type_key = "210401|第一次审查意见通知书"
        raw = {
            "version": shared.OFFICIAL_DOC_SETTINGS_VERSION,
            "write_summary": True,
            "write_archive": False,
            "confirm_each": False,
            "enable_exam_pdf_parse": False,
            "summary_root_dir": "D:/summary",
            "archive_root_dir": "D:/archive",
            "type_configs": {},
            "naming_groups": [
                {
                    "id": "notice-group",
                    "name": "通知书",
                    "member_type_keys": [type_key],
                    "group_config": {
                        "naming_mode": "custom",
                        "filename_fields": ["通知书名称"],
                        "alias_rules": [],
                    },
                }
            ],
            "type_group_membership": {
                type_key: "notice-group",
            },
        }

        with patch("gui.main_window.mixins.official_docs_ops.state_ops.set_official_doc_settings"):
            normalized = dummy._normalize_official_doc_settings(raw)

        self.assertEqual(normalized["naming_groups"][0]["id"], "notice-group")
        self.assertEqual(normalized["naming_groups"][0]["member_type_keys"], [type_key])
        self.assertEqual(normalized["type_group_membership"][type_key], "notice-group")

    def test_normalize_settings_migrates_matching_group_alias_rules_to_type_configs(self) -> None:
        dummy = OfficialDocsMixin()
        exam_key = "210401|第一次审查意见通知书"
        rect_key = "210302|第一次补正通知书"
        raw = {
            "version": shared.OFFICIAL_DOC_SETTINGS_VERSION,
            "write_summary": True,
            "write_archive": False,
            "confirm_each": False,
            "enable_exam_pdf_parse": False,
            "summary_root_dir": "D:/summary",
            "archive_root_dir": "D:/archive",
            "type_configs": {},
            "naming_groups": [
                {
                    "id": "notice-group",
                    "name": "通知书",
                    "member_type_keys": [exam_key, rect_key],
                    "group_config": {
                        "naming_mode": "custom",
                        "filename_fields": ["通知书名称"],
                        "alias_rules": [
                            {
                                "notice_name": "第一次审查意见通知书",
                                "short_name": "一审",
                                "enabled": True,
                            },
                            {
                                "notice_name": "不存在的通知书",
                                "short_name": "废弃",
                                "enabled": True,
                            },
                        ],
                    },
                }
            ],
            "type_group_membership": {
                exam_key: "notice-group",
                rect_key: "notice-group",
            },
        }

        with patch("gui.main_window.mixins.official_docs_ops.state_ops.set_official_doc_settings"):
            normalized = dummy._normalize_official_doc_settings(raw)

        self.assertEqual(
            normalized["type_configs"][exam_key]["alias_rules"],
            [
                {
                    "notice_name": "第一次审查意见通知书",
                    "short_name": "一审",
                    "enabled": True,
                }
            ],
        )
        self.assertEqual(normalized["type_configs"][rect_key]["alias_rules"], [])
        self.assertEqual(normalized["naming_groups"][0]["group_config"]["alias_rules"], [])

    def test_normalize_settings_drops_membership_to_missing_group(self) -> None:
        dummy = OfficialDocsMixin()
        type_key = "210401|第一次审查意见通知书"
        raw = {
            "version": shared.OFFICIAL_DOC_SETTINGS_VERSION,
            "write_summary": True,
            "write_archive": False,
            "confirm_each": False,
            "enable_exam_pdf_parse": False,
            "summary_root_dir": "D:/summary",
            "archive_root_dir": "D:/archive",
            "type_configs": {},
            "naming_groups": [],
            "type_group_membership": {
                type_key: "missing-group",
            },
        }

        with patch("gui.main_window.mixins.official_docs_ops.state_ops.set_official_doc_settings"):
            normalized = dummy._normalize_official_doc_settings(raw)

        self.assertEqual(normalized["type_group_membership"], {})


if __name__ == "__main__":
    unittest.main()
