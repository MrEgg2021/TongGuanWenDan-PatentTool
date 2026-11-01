from __future__ import annotations

import unittest
from unittest.mock import patch

from core.official_docs.pdf_entity_extract import (
    extract_pdf_entity_fields,
    resolve_pdf_applicable_fields,
)


class OfficialDocsPdfEntityMatrixTests(unittest.TestCase):
    def test_resolve_applicable_fields_for_known_notice(self) -> None:
        fields = resolve_pdf_applicable_fields(notice_key="210401|第一次审查意见通知书")
        self.assertIn("department", fields)
        self.assertIn("applicant", fields)
        self.assertIn("reject_reason", fields)
        self.assertIn("prior_art", fields)
        self.assertIn("dossier_no", fields)

    def test_review_notice_includes_applicant_for_reexamination_requester(self) -> None:
        fields = resolve_pdf_applicable_fields(notice_key="200912|复审决定书")
        self.assertIn("applicant", fields)
        self.assertIn("panel_head", fields)
        self.assertIn("panel_main", fields)
        self.assertIn("panel_member", fields)

    def test_new_notice_codes_explicitly_support_applicant_only(self) -> None:
        self.assertEqual(
            resolve_pdf_applicable_fields(notice_key="200029|办理手续补正通知书"),
            ("applicant",),
        )
        self.assertEqual(
            resolve_pdf_applicable_fields(notice_key="210326|向外国申请专利保密审查意见通知书"),
            ("applicant",),
        )

    def test_unapplicable_notice_returns_not_applicable_without_opening_pdf(self) -> None:
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open") as mocked_open:
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="10071|电子提交收据",
            )
        self.assertEqual(result.status, "未适用")
        self.assertEqual(result.applicable_fields, ())
        mocked_open.assert_not_called()

    def test_unknown_notice_code_defaults_to_not_applicable(self) -> None:
        result = extract_pdf_entity_fields(
            pdf_bytes=b"pdf",
            notice_key="999999|未知通知书",
        )
        self.assertEqual(result.status, "未适用")
        self.assertEqual(result.applicable_fields, ())


if __name__ == "__main__":
    unittest.main()
