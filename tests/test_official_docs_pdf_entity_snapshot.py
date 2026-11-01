from __future__ import annotations

import unittest
from unittest.mock import patch

from core.official_docs.pdf_entity_extract_v3 import (
    extract_pdf_entity_fields,
    resolve_pdf_applicable_fields,
)


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = str(text or "")

    def get_text(self, mode: str) -> str:
        _ = mode
        return self._text


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self.page_count = 1
        self._page = _FakePage(text)

    def __getitem__(self, index: int) -> _FakePage:
        _ = index
        return self._page

    def close(self) -> None:
        return None


class OfficialDocsPdfEntitySnapshotTests(unittest.TestCase):
    def test_applicable_fields_snapshot_for_review_notice(self) -> None:
        fields = resolve_pdf_applicable_fields(notice_key="210401|第一次审查意见通知书")
        self.assertEqual(
            fields,
            (
                "department",
                "center",
                "applicant",
                "inventor",
                "agency_raw",
                "examiner",
                "examiner_phone",
                "reject_reason",
                "prior_art",
                "dossier_no",
                "agent",
            ),
        )

    def test_extract_snapshot_for_review_notice(self) -> None:
        sample_text = "\n".join(
            [
                "审查部门：协作中心X",
                "申请人：Alpha公司",
                "发明人：Bob",
                "专利代理机构：Test Agency",
                "审查员：Zhang",
                "审查员电话：010-12345678",
                "☑权利要求1不符合专利法第26条第4款的规定。",
                "对比文件：CN1234567A；CN7654321B。",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )

        snapshot = {
            "status": str(result.status or ""),
            "applicable_fields": tuple(result.applicable_fields or ()),
            "department": str(result.department or ""),
            "center": str(result.center or ""),
            "applicant": str(result.applicant or ""),
            "inventor": str(result.inventor or ""),
            "agency_raw": str(result.agency_raw or ""),
            "agent": str(result.agent or ""),
            "examiner": str(result.examiner or ""),
            "examiner_phone": str(result.examiner_phone or ""),
            "prior_art": str(result.prior_art or ""),
            "reject_reason_non_empty": bool(str(result.reject_reason or "").strip()),
            "evidence_keys": tuple(
                sorted([key for key, value in dict(result.evidence or {}).items() if str(value or "").strip()])
            ),
        }
        expected = {
            "status": "成功",
            "applicable_fields": (
                "department",
                "center",
                "applicant",
                "inventor",
                "agency_raw",
                "examiner",
                "examiner_phone",
                "reject_reason",
                "prior_art",
                "dossier_no",
                "agent",
            ),
            "department": "协作中心X",
            "center": "",
            "applicant": "Alpha公司",
            "inventor": "Bob",
            "agency_raw": "Test Agency",
            "agent": "",
            "examiner": "Zhang",
            "examiner_phone": "010-12345678",
            "prior_art": "CN1234567A;CN7654321B",
            "reject_reason_non_empty": False,
            "evidence_keys": (
                "evidence_agency_raw",
                "evidence_applicant",
                "evidence_department",
                "evidence_examiner",
                "evidence_examiner_phone",
                "evidence_inventor",
                "evidence_prior_art",
            ),
        }
        self.assertEqual(snapshot, expected)


if __name__ == "__main__":
    unittest.main()
