import unittest

from core.formal_review.deterministic_rules import (
    check_abstract_deterministic_issues,
    check_claim_numbering_issues,
    check_claim_text_issues,
    check_description_deterministic_issues,
    check_drawings_deterministic_issues,
    check_text_consistency_issues,
)
from core.formal_review.models import ClaimItem, FormalReviewDocument


def _rule_ids(issues) -> set[str]:
    return {str(issue.rule_id) for issue in issues}


class FormalReviewDeterministicRulesTests(unittest.TestCase):
    def test_valid_document_has_no_new_deterministic_issues(self) -> None:
        document = FormalReviewDocument(
            claims=[
                ClaimItem(num=1, text="一种装置，包括壳体（1）。", markers=["1"]),
                ClaimItem(num=2, text="根据权利要求1所述的装置，其特征在于还包括支架（2）。", markers=["2"]),
            ],
            description=(
                "一种装置\n"
                "技术领域\n本发明涉及装置领域。\n"
                "背景技术\n现有装置存在结构复杂的问题。\n"
                "发明内容\n本发明提供一种装置。\n"
                "附图说明\n图1为装置结构示意图。\n"
                "具体实施方式\n如图1所示，壳体（1）与支架（2）连接。"
            ),
            abstract="本发明公开了一种装置，该装置包括壳体和支架。",
            drawings="图1\n装置结构示意图",
        )

        issues = []
        issues.extend(check_claim_numbering_issues(document.claims))
        issues.extend(check_claim_text_issues(document.claims, marker_note_map={"1": "壳体", "2": "支架"}))
        issues.extend(check_description_deterministic_issues(document))
        issues.extend(check_abstract_deterministic_issues(document))
        issues.extend(check_drawings_deterministic_issues(document))
        issues.extend(check_text_consistency_issues(document))

        self.assertEqual([], issues)

    def test_empty_and_incomplete_inputs_do_not_raise(self) -> None:
        empty = FormalReviewDocument()
        incomplete = FormalReviewDocument(claims=[ClaimItem(num=1, text="一种装置。")])

        self.assertEqual([], check_claim_numbering_issues(empty.claims))
        self.assertIn("abstract.missing", _rule_ids(check_abstract_deterministic_issues(empty)))
        self.assertIn("abstract.missing", _rule_ids(check_abstract_deterministic_issues(incomplete)))
        self.assertEqual([], check_drawings_deterministic_issues(incomplete))

    def test_claim_numbering_start_duplicate_and_gap_are_reported(self) -> None:
        claims = [
            ClaimItem(num=2, text="第二项。"),
            ClaimItem(num=2, text="重复第二项。"),
            ClaimItem(num=4, text="第四项。"),
        ]

        issues = check_claim_numbering_issues(claims)

        self.assertEqual(
            {"claim.number.start_at_one", "claim.number.duplicate", "claim.number.gap"},
            _rule_ids(issues),
        )
        self.assertEqual({"claims"}, {issue.category for issue in issues})

    def test_claim_text_prompts_are_bounded_and_classified(self) -> None:
        claims = [
            ClaimItem(
                num=1,
                text=(
                    "一种装置，包括壳体1；优选地，可以如图所示设置流程图；"
                    "计算结果满足Y=aX+b。"
                ),
                markers=["1"],
            )
        ]

        issues = check_claim_text_issues(claims, marker_note_map={"1": "壳体"})
        by_rule = {issue.rule_id: issue for issue in issues}

        self.assertIn("claim.marker.parentheses_missing", by_rule)
        self.assertIn("claim.reference.unclear_external", by_rule)
        self.assertIn("claim.language.weak_limitation", by_rule)
        self.assertIn("claim.content.non_claim_artifact", by_rule)
        self.assertIn("claim.formula.parameter_explanation_missing", by_rule)
        self.assertEqual("info", by_rule["claim.formula.parameter_explanation_missing"].severity)

    def test_explained_formula_and_parenthesized_marker_do_not_warn(self) -> None:
        claims = [
            ClaimItem(
                num=1,
                text="一种装置，包括壳体（1），且Y=aX+b，其中a为系数，b为常数。",
                markers=["1"],
            )
        ]

        issues = check_claim_text_issues(claims, marker_note_map={"1": "壳体"})

        self.assertNotIn("claim.marker.parentheses_missing", _rule_ids(issues))
        self.assertNotIn("claim.formula.parameter_explanation_missing", _rule_ids(issues))

    def test_claim_marker_missing_in_description_is_reported(self) -> None:
        claims = [ClaimItem(num=1, text="一种装置，包括壳体（1）。", markers=["1"])]
        document = FormalReviewDocument(
            claims=claims,
            description="一种装置\n技术领域\n背景技术\n发明内容\n具体实施方式\n该装置包括壳体。",
            abstract="一种装置。",
        )

        issues = check_claim_text_issues(
            document.claims,
            description_text=document.description,
        )

        self.assertIn("claim.marker.missing_in_description", _rule_ids(issues))

    def test_claim_marker_missing_is_reported_when_description_is_empty(self) -> None:
        claims = [ClaimItem(num=1, text="一种装置，包括壳体（1）。", markers=["1"])]

        issues = check_claim_text_issues(claims, description_text="")

        self.assertIn("claim.marker.missing_in_description", _rule_ids(issues))

    def test_valid_marker_note_mapping_satisfies_description_basis(self) -> None:
        claims = [ClaimItem(num=1, text="一种装置，包括壳体（1）。", markers=["1"])]

        issues = check_claim_text_issues(
            claims,
            marker_note_map={"1": "壳体"},
            description_text="",
        )

        self.assertNotIn("claim.marker.missing_in_description", _rule_ids(issues))

    def test_claim_rule_hits_are_bounded_per_rule(self) -> None:
        claims = [
            ClaimItem(num=index, text="一种可以调整的装置。")
            for index in range(1, 122)
        ]

        issues = check_claim_text_issues(claims)
        weak_issues = [
            issue
            for issue in issues
            if issue.rule_id == "claim.language.weak_limitation"
        ]

        self.assertEqual(100, len(weak_issues))

    def test_description_duplicate_heading_figure_gap_and_residue_are_reported(self) -> None:
        document = FormalReviewDocument(
            description=(
                "一种装置\n"
                "技术领域\n内容一。\n"
                "技术领域\n内容二。\n"
                "背景技术\n内容。\n"
                "发明内容\nTODO【】根据客户补充。\n"
                "附图说明\n图1为结构图。\n图3为流程图。\n"
                "具体实施方式\n如权利要求1所述的壳体安装于支架。"
            )
        )

        issues = check_description_deterministic_issues(document)

        self.assertTrue(
            {
                "description.heading.duplicate",
                "description.figure.number.gap",
                "description.placeholder.residue",
                "description.template.residue",
                "description.impl.claim_reference_style",
            }.issubset(_rule_ids(issues))
        )

    def test_abstract_missing_promotion_placeholder_and_numbering_are_reported(self) -> None:
        missing = check_abstract_deterministic_issues(FormalReviewDocument())
        populated = check_abstract_deterministic_issues(
            FormalReviewDocument(abstract="1. 本产品性能卓越，达到国际领先水平，TODO待补充。")
        )

        self.assertIn("abstract.missing", _rule_ids(missing))
        self.assertTrue(
            {
                "abstract.promotional_language",
                "abstract.placeholder.residue",
                "abstract.claim_numbering_style",
            }.issubset(_rule_ids(populated))
        )

    def test_drawings_gap_and_figure_format_mixing_are_reported(self) -> None:
        document = FormalReviewDocument(drawings="图1\n结构图\n图 3\n流程图\n图四\n曲线图")

        issues = check_drawings_deterministic_issues(document)

        self.assertIn("drawings.figure.number.gap", _rule_ids(issues))
        self.assertIn("drawings.figure.format.mixed", _rule_ids(issues))

    def test_text_width_symbol_and_whitespace_mixing_are_reported(self) -> None:
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="部件1与部件２连接（稳定），并使用(test)接口。")],
            description="一种  装置。",
        )

        issues = check_text_consistency_issues(document)

        self.assertTrue(
            {
                "text.numbering.width.mixed",
                "text.symbol.width.mixed",
                "text.abnormal_whitespace",
            }.issubset(_rule_ids(issues))
        )


if __name__ == "__main__":
    unittest.main()
