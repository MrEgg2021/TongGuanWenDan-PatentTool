import unittest

from core.formal_review.models import ClaimItem, FormalReviewDocument
from core.formal_review.rule_registry import default_rule_enabled_map
from core.formal_review.service import run_formal_review


class FormalReviewServiceRuleFilterTests(unittest.TestCase):
    def test_disabled_rule_is_filtered_out(self) -> None:
        doc = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="一种装置，，其特征在于，包含壳体（1）。", anchor_start=10)],
            description="说明书中绝对可靠。",
            abstract="字" * 20,
            drawings="图1为结构示意图。",
        )
        wordlists = {"forbidden": ["绝对"], "sensitive": []}
        defaults = default_rule_enabled_map()
        enabled_ids = {rule_id for rule_id, enabled in defaults.items() if enabled}
        enabled_ids.discard("wordlist.description.forbidden")
        result = run_formal_review(doc, wordlists=wordlists, enabled_rule_ids=enabled_ids, ignored_issue_ids=set(), abstract_threshold=300)
        issues = list(result.get("issues", []) or [])
        self.assertFalse(any(issue.rule_id == "wordlist.description.forbidden" for issue in issues))
        self.assertTrue(any(issue.rule_id == "punctuation.repeated" for issue in issues))

    def test_new_optional_rule_respects_enabled_rule_filter(self) -> None:
        doc = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="一种设备，其特征在于，包括模块A、模块B、模块C。", anchor_start=0)],
            description="",
            abstract="",
            drawings="",
        )
        enabled_ids = {"claim1.word_count.exceeded"}
        result = run_formal_review(
            doc,
            wordlists={},
            enabled_rule_ids=enabled_ids,
            ignored_issue_ids=set(),
            abstract_threshold=300,
            rule_params={"claim1_word_limit": 5},
        )
        issues = list(result.get("issues", []) or [])
        self.assertTrue(any(issue.rule_id == "claim1.word_count.exceeded" for issue in issues))

        result_filtered = run_formal_review(
            doc,
            wordlists={},
            enabled_rule_ids=set(),
            ignored_issue_ids=set(),
            abstract_threshold=300,
            rule_params={"claim1_word_limit": 5},
        )
        filtered_issues = list(result_filtered.get("issues", []) or [])
        self.assertFalse(any(issue.rule_id == "claim1.word_count.exceeded" for issue in filtered_issues))

    def test_marker_basis_rule_respects_enabled_rule_filter(self) -> None:
        doc = FormalReviewDocument(
            claims=[
                ClaimItem(num=1, text="一种装置，其特征在于，所述喷嘴（1）设置于壳体内。", anchor_start=0),
                ClaimItem(num=2, text="根据权利要求1所述的装置，所述导流喷嘴（2）连接。", anchor_start=100),
            ],
            description="",
            abstract="",
            drawings="",
        )
        enabled_ids = {"claim.ref.marker_basis.missing"}
        result = run_formal_review(
            doc,
            wordlists={},
            enabled_rule_ids=enabled_ids,
            ignored_issue_ids=set(),
            abstract_threshold=300,
            marker_note_map={"1": "喷嘴", "2": "导流喷嘴"},
        )
        issues = list(result.get("issues", []) or [])
        self.assertTrue(any(issue.rule_id == "claim.ref.marker_basis.missing" for issue in issues))

        result_filtered = run_formal_review(
            doc,
            wordlists={},
            enabled_rule_ids=set(),
            ignored_issue_ids=set(),
            abstract_threshold=300,
            marker_note_map={"1": "喷嘴", "2": "导流喷嘴"},
        )
        filtered_issues = list(result_filtered.get("issues", []) or [])
        self.assertFalse(any(issue.rule_id == "claim.ref.marker_basis.missing" for issue in filtered_issues))

    def test_drawings_cross_section_rules_respect_enabled_rule_filter(self) -> None:
        doc = FormalReviewDocument(
            claims=[],
            description=(
                "一种设备\n"
                "技术领域\n本申请涉及设备结构。\n"
                "背景技术\n现有方案存在不足。\n"
                "发明内容\n提出改进方案。\n"
                "附图说明\n"
                "图1为结构示意图。\n"
                "图2为分解示意图。\n"
                "图3为另一视角图。\n"
                "图4为导流单元示意图。\n"
                "图5为风道示意图。\n"
                "具体实施方式\n"
                "如图1所示，主体包括壳体。\n"
                "如图2所示，壳体连接支架。\n"
                "如图3所示，壳体设置导流结构。"
            ),
            abstract="",
            drawings="图1\n图2\n图3",
        )
        defaults = default_rule_enabled_map()
        enabled_ids = {rule_id for rule_id, enabled in defaults.items() if enabled}
        enabled_ids.discard("description.drawings.figure.ref.missing_in_drawings_section")
        enabled_ids.discard("drawings.figure.ref.missing_in_description_drawings")
        result = run_formal_review(
            doc,
            wordlists={},
            enabled_rule_ids=enabled_ids,
            ignored_issue_ids=set(),
            abstract_threshold=300,
        )
        issues = list(result.get("issues", []) or [])
        self.assertFalse(
            any(issue.rule_id == "description.drawings.figure.ref.missing_in_drawings_section" for issue in issues)
        )
        self.assertFalse(
            any(issue.rule_id == "drawings.figure.ref.missing_in_description_drawings" for issue in issues)
        )

    def test_drawings_duplicate_rule_respects_enabled_rule_filter(self) -> None:
        duplicate_rule_id = "drawings.figure.ref.duplicate_in_drawings_section"
        doc = FormalReviewDocument(
            claims=[],
            description="",
            abstract="",
            drawings="\u56fe1\n\u56fe2\n\u56fe1\n",
        )
        defaults = default_rule_enabled_map()
        enabled_ids = {rule_id for rule_id, enabled in defaults.items() if enabled}
        enabled_ids.discard(duplicate_rule_id)
        result = run_formal_review(
            doc,
            wordlists={},
            enabled_rule_ids=enabled_ids,
            ignored_issue_ids=set(),
            abstract_threshold=300,
        )
        issues = list(result.get("issues", []) or [])
        self.assertFalse(any(issue.rule_id == duplicate_rule_id for issue in issues))

    def test_drawings_duplicate_rule_emits_when_enabled(self) -> None:
        duplicate_rule_id = "drawings.figure.ref.duplicate_in_drawings_section"
        doc = FormalReviewDocument(
            claims=[],
            description="",
            abstract="",
            drawings="\u56fe1\n\u56fe2\n\u56fe1\n",
        )
        result = run_formal_review(
            doc,
            wordlists={},
            enabled_rule_ids={duplicate_rule_id},
            ignored_issue_ids=set(),
            abstract_threshold=300,
        )
        issues = list(result.get("issues", []) or [])
        self.assertTrue(any(issue.rule_id == duplicate_rule_id for issue in issues))


if __name__ == "__main__":
    unittest.main()
