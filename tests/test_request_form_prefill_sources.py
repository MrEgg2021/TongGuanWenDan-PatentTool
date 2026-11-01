from __future__ import annotations

import types
import unittest

from gui.request_form_ui_parts.builder import build_request_form_payload
from gui.widgets_impl.request_form.data_io_impl.merge_ops import _merge_data_mgmt_draft_if_any


class RequestFormPrefillSourcesTests(unittest.TestCase):
    def test_build_payload_keeps_missing_fields_blank_without_global_profile(self) -> None:
        result = build_request_form_payload({}, "invention")

        self.assertEqual(result["applicants"][0]["name"], "")
        self.assertEqual(result["applicants"][0]["id_no"], "")
        self.assertEqual(result["agency_enabled"], False)
        self.assertNotIn("agency_info", result)
        self.assertNotIn("_applicant_profile_enabled", result)
        self.assertNotIn("_agency_profile_overridden", result)

    def test_build_payload_preserves_explicit_agency_and_poa_from_input(self) -> None:
        parsed_info = {
            "agency_enabled": True,
            "power_of_attorney_no": "POA-001",
            "agency_info": {
                "name": "杭州某代理机构",
                "code": "33000",
                "agent1": {"name": "张三", "cert_no": "A001", "phone": "13800000000"},
            },
        }

        result = build_request_form_payload(parsed_info, "invention")

        self.assertTrue(result["agency_enabled"])
        self.assertEqual(result["power_of_attorney_no"], "POA-001")
        self.assertEqual(result["agency_info"]["name"], "杭州某代理机构")
        self.assertEqual(result["agency_info"]["agent1"]["name"], "张三")

    def test_merge_data_mgmt_draft_still_overlays_same_run_saved_fields(self) -> None:
        dialog = types.SimpleNamespace(
            _request_form_cache={
                "bundle.zip": {
                    "data_mgmt_draft": {
                        "group_name": "草稿组",
                        "applicants": [{"name": "申请人A"}],
                        "inventors": [{"name": "发明人A"}],
                        "contact": {"name": "联系人A"},
                    }
                }
            },
            _request_form_cache_key="bundle.zip",
        )
        info = {
            "group_name": "原始组",
            "applicants": [{"name": "原始申请人"}],
            "inventors": [{"name": "原始发明人"}],
            "contact": {"name": "原始联系人"},
            "agency_info": {"name": "原始代理机构"},
        }

        merged = _merge_data_mgmt_draft_if_any(dialog, info)

        self.assertEqual(merged["group_name"], "草稿组")
        self.assertEqual(merged["applicants"][0]["name"], "申请人A")
        self.assertEqual(merged["inventors"][0]["name"], "发明人A")
        self.assertEqual(merged["contact"]["name"], "联系人A")
        self.assertEqual(merged["agency_info"]["name"], "原始代理机构")


if __name__ == "__main__":
    unittest.main()
