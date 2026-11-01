import unittest
from dataclasses import dataclass, field

from core.formal_review.models import ClaimItem, FormalReviewDocument
from core.formal_review.rule_registry import RULE_REGISTRY
from core.formal_review.service import run_formal_review


WORDLISTS = {
    "claims": {"forbidden": ["禁用词"], "sensitive": ["敏感词"]},
    "description": {"forbidden": ["绝对"], "sensitive": ["保证"]},
}


@dataclass(frozen=True)
class _RuleCase:
    document: FormalReviewDocument
    marker_note_map: dict[str, str] = field(default_factory=dict)
    rule_params: dict[str, object] = field(default_factory=dict)
    abstract_threshold: int = 300


def _base_description(title: str = "一种装置") -> str:
    return "\n".join(
        [
            title,
            "技术领域",
            "本申请涉及装置领域。",
            "背景技术",
            "现有装置存在结构复杂的问题。",
            "发明内容",
            "本申请提供一种装置。",
            "附图说明",
            "图1为装置结构示意图。",
            "具体实施方式",
            "如图1所示，壳体（1）与支架（2）连接。",
        ]
    )


def _doc(
    claim_text: str = "一种装置。",
    *,
    claims: list[ClaimItem] | None = None,
    description: str | None = None,
    abstract: str = "一种装置。",
    drawings: str = "",
    markers: list[str] | None = None,
) -> FormalReviewDocument:
    return FormalReviewDocument(
        claims=claims if claims is not None else [ClaimItem(num=1, text=claim_text, markers=list(markers or []))],
        description=_base_description() if description is None else description,
        abstract=abstract,
        drawings=drawings,
    )


def _cases() -> dict[str, _RuleCase]:
    return {
        "wordlist.claims.forbidden": _RuleCase(_doc("一种禁用词装置。")),
        "wordlist.claims.sensitive": _RuleCase(_doc("一种敏感词装置。")),
        "wordlist.description.forbidden": _RuleCase(_doc(description=_base_description() + "\n绝对可靠。")),
        "wordlist.description.sensitive": _RuleCase(_doc(description=_base_description() + "\n保证稳定。")),
        "punctuation.repeated": _RuleCase(_doc("一种装置，，包括模块。")),
        "punctuation.invalid_combo": _RuleCase(_doc("一种装置，；包括模块。")),
        "text.repeated_word": _RuleCase(_doc("一种装置，包括模块模块。")),
        "claim.number.start_at_one": _RuleCase(
            _doc(claims=[ClaimItem(num=2, text="第二项。")])
        ),
        "claim.number.duplicate": _RuleCase(
            _doc(claims=[ClaimItem(num=1, text="第一项。"), ClaimItem(num=1, text="重复第一项。")])
        ),
        "claim.number.gap": _RuleCase(
            _doc(claims=[ClaimItem(num=1, text="第一项。"), ClaimItem(num=3, text="第三项。")])
        ),
        "claim.marker.parentheses_missing": _RuleCase(
            _doc("一种装置，包括壳体1。", markers=["1"]),
            marker_note_map={"1": "壳体"},
        ),
        "claim.reference.unclear_external": _RuleCase(_doc("一种如图所示的装置。")),
        "claim.language.weak_limitation": _RuleCase(_doc("一种可以调节的装置。")),
        "claim.content.non_claim_artifact": _RuleCase(_doc("一种装置，包括流程图。")),
        "claim.formula.parameter_explanation_missing": _RuleCase(_doc("一种计算装置，满足Y=aX+b。")),
        "claim.marker.missing_in_description": _RuleCase(
            _doc("一种装置，包括壳体（9）。", markers=["9"]),
        ),
        "claim.ref.self": _RuleCase(
            _doc(claims=[ClaimItem(num=1, text="根据权利要求1所述的装置。")])
        ),
        "claim.ref.future": _RuleCase(
            _doc(claims=[ClaimItem(num=1, text="根据权利要求2所述的装置。"), ClaimItem(num=2, text="一种装置。")])
        ),
        "claim.ref.missing_target": _RuleCase(
            _doc(claims=[ClaimItem(num=1, text="根据权利要求5所述的装置。")])
        ),
        "claim.ref.choice_word_missing": _RuleCase(
            _doc(
                claims=[
                    ClaimItem(num=1, text="一种装置。"),
                    ClaimItem(num=2, text="一种系统。"),
                    ClaimItem(num=3, text="根据权利要求1和2所述的设备。"),
                ]
            )
        ),
        "claim.ref.marker_basis.missing": _RuleCase(
            _doc(
                claims=[
                    ClaimItem(num=1, text="一种装置，其特征在于，所述喷嘴设置于壳体。"),
                    ClaimItem(num=2, text="根据权利要求1所述的装置，所述导流喷嘴（2）连接于管路。"),
                ]
            ),
            marker_note_map={"1": "喷嘴", "2": "导流喷嘴"},
        ),
        "claim.ref.term_basis.missing": _RuleCase(
            _doc(
                claims=[
                    ClaimItem(num=1, text="一种装置，其特征在于，所述喷嘴设置于壳体。"),
                    ClaimItem(num=2, text="根据权利要求1所述的装置，所述导流孔与壳体连通。"),
                ]
            ),
            marker_note_map={"1": "喷嘴"},
        ),
        "claim.ref.multi_to_multi.recursive": _RuleCase(
            _doc(
                claims=[
                    ClaimItem(num=1, text="一种装置。"),
                    ClaimItem(num=2, text="一种系统。"),
                    ClaimItem(num=3, text="根据权利要求1和2任一项所述的设备。"),
                    ClaimItem(num=4, text="根据权利要求2和3任一项所述的设备。"),
                ]
            )
        ),
        "claim1.word_count.exceeded": _RuleCase(
            _doc("字" * 20 + "。"),
            rule_params={"claim1_word_limit": 5},
        ),
        "claim1.marker_count.exceeded": _RuleCase(
            _doc("一种装置，包括（1）（2）（3）。"),
            rule_params={"claim1_marker_limit": 1},
        ),
        "claim.punctuation.period.extra": _RuleCase(_doc("一种装置。包括模块。")),
        "claim.punctuation.period.tail_missing": _RuleCase(_doc("一种装置，包括模块")),
        "abstract.word_count.exceeded": _RuleCase(_doc(abstract="字" * 20), abstract_threshold=5),
        "abstract.missing": _RuleCase(_doc(abstract="")),
        "abstract.promotional_language": _RuleCase(_doc(abstract="本产品性能卓越。")),
        "abstract.placeholder.residue": _RuleCase(_doc(abstract="TODO待补充。")),
        "abstract.claim_numbering_style": _RuleCase(_doc(abstract="1. 一种装置。")),
        "description.heading.missing.required": _RuleCase(_doc(description="一种装置\n只有正文。")),
        "description.title.missing": _RuleCase(_doc(description="技术领域\n本申请涉及装置。")),
        "description.title.length.exceeded": _RuleCase(_doc(description=("超" * 26) + "\n技术领域\n正文。")),
        "description.heading.duplicate": _RuleCase(
            _doc(description="一种装置\n技术领域\n内容一。\n技术领域\n内容二。\n背景技术\n内容。\n发明内容\n内容。\n具体实施方式\n内容。")
        ),
        "description.figure.number.gap": _RuleCase(
            _doc(description="一种装置\n附图说明\n图1为结构图。\n图3为流程图。\n具体实施方式\n正文。")
        ),
        "description.placeholder.residue": _RuleCase(_doc(description=_base_description() + "\nTODO")),
        "description.template.residue": _RuleCase(_doc(description=_base_description() + "\n根据客户补充")),
        "description.impl.claim_reference_style": _RuleCase(
            _doc(description=_base_description() + "\n如权利要求1所述的壳体安装于支架。")
        ),
        "description.impl_heading.missing_for_figure_check": _RuleCase(
            _doc(description="一种装置\n技术领域\n正文。", drawings="图1为结构图。")
        ),
        "drawings.figure.ref.missing_in_impl": _RuleCase(
            _doc(description="一种装置\n具体实施方式\n如图1所示。\n如图3所示。", drawings="图1-图3为结构图。")
        ),
        "drawings.figure.ref.duplicate_in_drawings_section": _RuleCase(
            _doc(drawings="图1\n结构图\n图1\n另一结构图")
        ),
        "description.drawings.figure.ref.missing_in_drawings_section": _RuleCase(
            _doc(description="一种装置\n附图说明\n图1为结构图。\n图2为流程图。\n具体实施方式\n如图1所示。", drawings="图1")
        ),
        "drawings.figure.ref.missing_in_description_drawings": _RuleCase(
            _doc(description="一种装置\n附图说明\n图1为结构图。\n具体实施方式\n如图1所示。", drawings="说明书附图\n图1\n图2")
        ),
        "drawings.figure.number.gap": _RuleCase(_doc(drawings="图1\n图3")),
        "drawings.figure.format.mixed": _RuleCase(_doc(drawings="图1\n图二")),
        "theme.claim1.multi_subject": _RuleCase(
            _doc("一种数据处理方法系统。", description="一种数据处理装置\n技术领域\n正文。")
        ),
        "theme.title_claim1.mismatch": _RuleCase(
            _doc("一种数据处理系统。", description="一种数据处理装置\n技术领域\n正文。")
        ),
        "theme.title_abstract.mismatch": _RuleCase(
            _doc("一种数据处理装置。", description="一种数据处理装置\n技术领域\n正文。", abstract="一种计算机程序产品。")
        ),
        "theme.title.unrecognized": _RuleCase(
            _doc("一种设备。", description="一种改进方案\n技术领域\n正文。", abstract="一种方案。")
        ),
        "text.numbering.width.mixed": _RuleCase(_doc("部件1与部件２连接。")),
        "text.symbol.width.mixed": _RuleCase(_doc("部件（1）与部件(2)连接。")),
        "text.abnormal_whitespace": _RuleCase(_doc("一种  装置。")),
    }


class FormalReviewRuleRegistryCapabilityTests(unittest.TestCase):
    def test_every_registered_rule_has_service_level_trigger_fixture(self) -> None:
        cases = _cases()
        self.assertEqual(set(RULE_REGISTRY), set(cases))

        missed: dict[str, set[str]] = {}
        rule_errors: dict[str, list[dict[str, str]]] = {}
        for rule_id, case in sorted(cases.items()):
            result = run_formal_review(
                case.document,
                wordlists=WORDLISTS,
                ignored_issue_ids=set(),
                abstract_threshold=case.abstract_threshold,
                enabled_rule_ids={rule_id},
                rule_params=dict(case.rule_params),
                marker_note_map=dict(case.marker_note_map),
            )
            emitted = {str(getattr(issue, "rule_id", "") or "") for issue in list(result.get("issues", []) or [])}
            if rule_id not in emitted:
                missed[rule_id] = emitted
            errors = list(result.get("rule_errors", []) or [])
            if errors:
                rule_errors[rule_id] = errors

        self.assertEqual({}, rule_errors)
        self.assertEqual({}, missed)


if __name__ == "__main__":
    unittest.main()
