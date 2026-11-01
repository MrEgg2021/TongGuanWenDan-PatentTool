import unittest
from unittest.mock import patch

from core.formal_review.models import FormalReviewDocument
from core.formal_review import semantic_rules
from core.formal_review.semantic_rules import (
    _DescriptionDrawingsSection,
    check_drawings_cross_section_consistency_issues,
)


class FormalReviewDrawingsSectionConsistencyTests(unittest.TestCase):
    def test_reports_missing_in_drawings_section_when_description_drawings_has_extra_refs(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种设备\n"
                "技术领域\n"
                "背景技术\n"
                "发明内容\n"
                "附图说明\n"
                "图1为结构示意图。\n"
                "图2为分解示意图。\n"
                "图3为另一视角图。\n"
                "图4为导流单元示意图。\n"
                "图5为风道示意图。\n"
                "具体实施方式\n"
                "如图1所示，主体包括壳体。"
            ),
            drawings="图1\n图2\n图3",
        )
        issues = check_drawings_cross_section_consistency_issues(doc)
        self.assertEqual(1, len(issues))
        issue = issues[0]
        self.assertEqual("description.drawings.figure.ref.missing_in_drawings_section", issue.rule_id)
        self.assertEqual("error", issue.severity)
        self.assertIn("图4", str(issue.message))
        self.assertIn("图5", str(issue.message))
        self.assertEqual("description", str(issue.section))
        span_text = str(doc.description[int(issue.span_start) : int(issue.span_end)] or "")
        self.assertEqual(str(issue.snippet or ""), span_text)
        self.assertIn("附图说明", span_text)
        anchor = dict(getattr(issue, "anchor", {}) or {})
        self.assertEqual("drawings_heading_line", str(anchor.get("intent", "") or ""))

    def test_reports_missing_in_description_drawings_when_drawings_section_has_extra_refs(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种设备\n"
                "附图说明\n"
                "图1为结构示意图。\n"
                "图2为分解示意图。\n"
                "具体实施方式\n"
                "如图1所示，主体包括壳体。"
            ),
            drawings="说明书附图\n图1\n图2\n图3",
        )
        issues = check_drawings_cross_section_consistency_issues(doc)
        self.assertEqual(1, len(issues))
        issue = issues[0]
        self.assertEqual("drawings.figure.ref.missing_in_description_drawings", issue.rule_id)
        self.assertEqual("error", issue.severity)
        self.assertEqual("description", str(issue.section))
        self.assertIn("图3", str(issue.message))
        span_text = str(doc.description[int(issue.span_start) : int(issue.span_end)] or "")
        self.assertIn("附图说明", span_text)
        self.assertEqual("附图说明", str(issue.snippet or ""))
        anchor = dict(getattr(issue, "anchor", {}) or {})
        self.assertEqual("drawings_heading_line", str(anchor.get("intent", "") or ""))
        self.assertEqual("附图说明", str(anchor.get("expected_hit", "") or ""))
        candidates = list(anchor.get("expected_hit_candidates", []) or [])
        self.assertTrue(candidates)
        self.assertEqual("附图说明", str(candidates[0]))
        self.assertFalse(bool(anchor.get("fallback_used")))

    def test_drawings_side_rule_fallbacks_to_first_description_line_when_heading_unrecognized(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种设备\n"
                "图1为结构示意图。\n"
                "图2为分解示意图。\n"
                "具体实施方式\n"
                "如图1所示。"
            ),
            drawings="图1\n图2\n图3",
        )
        fake_desc_section = _DescriptionDrawingsSection(
            text="图1为结构示意图。\n图2为分解示意图。",
            start=0,
            end=20,
            heading_text="",
            heading_start=0,
            heading_end=0,
        )
        with patch.object(semantic_rules, "_extract_description_drawings_section", return_value=fake_desc_section):
            issues = check_drawings_cross_section_consistency_issues(doc)
        self.assertEqual(1, len(issues))
        issue = issues[0]
        self.assertEqual("drawings.figure.ref.missing_in_description_drawings", issue.rule_id)
        self.assertEqual("description", str(issue.section))
        self.assertIn("未识别附图说明标题，已回退定位", str(issue.message))
        anchor = dict(getattr(issue, "anchor", {}) or {})
        self.assertTrue(bool(anchor.get("fallback_used")))
        self.assertEqual("一种设备", str(issue.snippet or ""))
        self.assertEqual("一种设备", str(anchor.get("expected_hit", "") or ""))

    def test_passes_when_refs_are_consistent_with_ranges(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种设备\n"
                "附图说明\n"
                "图3到图1为结构示意图。\n"
                "具体实施方式\n"
                "图1示出基座。\n"
                "图2示出连接件。\n"
                "图3示出端盖。"
            ),
            drawings="图1-图3为结构示意图。",
        )
        issues = check_drawings_cross_section_consistency_issues(doc)
        self.assertEqual([], issues)

    def test_ignores_impl_refs_outside_description_drawings_subsection(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种设备\n"
                "附图说明\n"
                "图1为结构示意图。\n"
                "图2为分解示意图。\n"
                "图3为另一视角图。\n"
                "具体实施方式\n"
                "如图4所示，导流单元设置在壳体内。\n"
                "如图5所示，风道设置在壳体侧壁。"
            ),
            drawings="图1\n图2\n图3",
        )
        issues = check_drawings_cross_section_consistency_issues(doc)
        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
