import unittest
from unittest.mock import patch

from core.formal_review.models import FormalReviewDocument, Issue
from core.formal_review.service import run_formal_review


class FormalReviewRuleIsolationAndMetadataTests(unittest.TestCase):
    def test_issue_serialization_keeps_existing_fields_and_adds_structured_aliases(self) -> None:
        issue = Issue(
            rule_id="abstract.missing",
            rule_name="摘要缺失",
            severity="error",
            category="abstract",
            section="abstract",
            message="缺少摘要。",
            suggestion="补充摘要。",
            location={"section": "abstract"},
            evidence={"snippet": ""},
        )

        payload = issue.to_dict()

        self.assertEqual("abstract.missing", payload["rule_id"])
        self.assertEqual("abstract.missing", payload["ruleId"])
        self.assertEqual("摘要缺失", payload["rule_name"])
        self.assertEqual("摘要缺失", payload["ruleName"])
        self.assertEqual("补充摘要。", payload["suggestion"])
        self.assertEqual({"section": "abstract"}, payload["location"])
        self.assertEqual({"snippet": ""}, payload["evidence"])

    def test_rule_failure_is_reported_and_later_rules_continue(self) -> None:
        document = FormalReviewDocument()

        with patch(
            "core.formal_review.service.check_claim_numbering_issues",
            side_effect=RuntimeError("numbering failed"),
        ):
            result = run_formal_review(document, wordlists={})

        self.assertIn("abstract.missing", {issue.rule_id for issue in result["issues"]})
        self.assertEqual(1, len(result["rule_errors"]))
        self.assertEqual("claim.numbering", result["rule_errors"][0]["checker_id"])
        self.assertEqual("RuntimeError", result["rule_errors"][0]["error_type"])
        self.assertIn("numbering failed", result["rule_errors"][0]["message"])

    def test_successful_review_has_structured_metadata_and_no_rule_errors(self) -> None:
        result = run_formal_review(FormalReviewDocument(), wordlists={})

        self.assertEqual([], result["rule_errors"])
        abstract_issue = next(issue for issue in result["issues"] if issue.rule_id == "abstract.missing")
        self.assertEqual("摘要缺失", abstract_issue.rule_name)
        self.assertEqual("abstract", abstract_issue.category)
        self.assertTrue(abstract_issue.suggestion)
        self.assertEqual("abstract", abstract_issue.location["section"])
        self.assertIn("snippet", abstract_issue.evidence)


if __name__ == "__main__":
    unittest.main()
