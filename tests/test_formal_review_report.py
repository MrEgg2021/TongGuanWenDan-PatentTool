import unittest

from core.formal_review.models import ClaimItem, FormalReviewDocument, Issue
from core.formal_review.report import build_report_payload, build_report_markdown


class FormalReviewReportTests(unittest.TestCase):
    def test_report_payload_contains_ignored(self) -> None:
        doc = FormalReviewDocument(claims=[ClaimItem(num=1, text="一种装置。")], description="", abstract="", drawings="")
        issues = [
            Issue(
                rule_id="x",
                severity="warning",
                category="rule",
                section="claims",
                claim_num=1,
                message="m",
                ignored=True,
            )
        ]
        payload = build_report_payload(source_file="a.docx", document=doc, issues=issues)
        self.assertEqual(payload["summary"]["issues_ignored"], 1)
        md = build_report_markdown(payload)
        self.assertIn("[已忽略]", md)


if __name__ == "__main__":
    unittest.main()
