from __future__ import annotations

from typing import Any

from core.user_prefs import get_pref, set_pref

RULE_ENABLED_PREF_KEY = "formal_review.rule_enabled.v1"

RULE_REGISTRY: dict[str, dict[str, object]] = {
    "wordlist.claims.forbidden": {
        "label": "\u6743\u5229\u8981\u6c42\u4e66\u7981\u7528\u8bcd",
        "color_key": "wordlist.claims.forbidden",
        "default_enabled": True,
    },
    "wordlist.claims.sensitive": {
        "label": "\u6743\u5229\u8981\u6c42\u4e66\u654f\u611f\u8bcd",
        "color_key": "wordlist.claims.sensitive",
        "default_enabled": True,
    },
    "wordlist.description.forbidden": {
        "label": "\u8bf4\u660e\u4e66\u7981\u7528\u8bcd",
        "color_key": "wordlist.description.forbidden",
        "default_enabled": True,
    },
    "wordlist.description.sensitive": {
        "label": "\u8bf4\u660e\u4e66\u654f\u611f\u8bcd",
        "color_key": "wordlist.description.sensitive",
        "default_enabled": True,
    },
    "punctuation.repeated": {
        "label": "\u8fde\u7eed\u6807\u70b9",
        "color_key": "punctuation.repeated",
        "default_enabled": True,
    },
    "punctuation.invalid_combo": {
        "label": "\u6807\u70b9\u7ec4\u5408\u4e0d\u89c4\u8303",
        "color_key": "punctuation.invalid_combo",
        "default_enabled": True,
    },
    "text.repeated_word": {
        "label": "\u8fde\u7eed\u91cd\u590d\u8bcd\u8bed",
        "color_key": "text.repeated_word",
        "default_enabled": True,
    },
    "drawings.figure.ref.missing_in_impl": {
        "label": "\u9644\u56fe\u56fe\u53f7\u5728\u5b9e\u65bd\u65b9\u5f0f\u7f3a\u5931",
        "color_key": "drawings.figure.ref.missing_in_impl",
        "default_enabled": True,
    },
    "drawings.figure.ref.duplicate_in_drawings_section": {
        "label": "\u8bf4\u660e\u4e66\u9644\u56fe\u56fe\u53f7\u91cd\u590d",
        "color_key": "drawings.figure.ref.missing_in_impl",
        "default_enabled": True,
        "ui_domain": "drawings",
        "ui_level": "forbid",
    },
    "description.drawings.figure.ref.missing_in_drawings_section": {
        "label": "\u9644\u56fe\u8bf4\u660e\u56fe\u53f7\u672a\u5728\u8bf4\u660e\u4e66\u9644\u56fe\u51fa\u73b0",
        "color_key": "description.structure.error",
        "default_enabled": True,
        "ui_domain": "description",
        "ui_level": "forbid",
    },
    "drawings.figure.ref.missing_in_description_drawings": {
        "label": "\u8bf4\u660e\u4e66\u9644\u56fe\u56fe\u53f7\u672a\u5728\u9644\u56fe\u8bf4\u660e\u51fa\u73b0",
        "color_key": "drawings.figure.ref.missing_in_impl",
        "default_enabled": True,
        "ui_domain": "description",
        "ui_level": "forbid",
    },
    "description.impl_heading.missing_for_figure_check": {
        "label": "\u7f3a\u5c11\u5b9e\u65bd\u65b9\u5f0f\u6807\u9898",
        "color_key": "description.structure.error",
        "default_enabled": True,
    },
    "description.heading.missing.required": {
        "label": "\u8bf4\u660e\u4e66\u5fc5\u9700\u5c0f\u6807\u9898\u7f3a\u5931",
        "color_key": "description.structure.error",
        "default_enabled": True,
    },
    "description.title.missing": {
        "label": "\u8bf4\u660e\u4e66\u6807\u9898\u7f3a\u5931",
        "color_key": "description.structure.error",
        "default_enabled": True,
    },
    "description.title.length.exceeded": {
        "label": "\u8bf4\u660e\u4e66\u6807\u9898\u8d85\u957f",
        "color_key": "description.title.length.exceeded",
        "default_enabled": True,
    },
    "theme.claim1.multi_subject": {
        "label": "\u6743\u5229\u8981\u6c421\u4e3b\u9898\u591a\u5143",
        "color_key": "theme.consistency",
        "default_enabled": True,
    },
    "theme.title_claim1.mismatch": {
        "label": "\u6807\u9898\u4e0e\u6743\u5229\u8981\u6c421\u4e3b\u9898\u4e0d\u4e00\u81f4",
        "color_key": "theme.consistency",
        "default_enabled": True,
    },
    "theme.title_abstract.mismatch": {
        "label": "\u6807\u9898\u4e0e\u6458\u8981\u4e3b\u9898\u4e0d\u4e00\u81f4",
        "color_key": "theme.consistency",
        "default_enabled": True,
    },
    "theme.title.unrecognized": {
        "label": "\u6807\u9898\u4e3b\u9898\u672a\u8bc6\u522b",
        "color_key": "theme.consistency",
        "default_enabled": True,
    },
    "claim.ref.self": {"label": "\u6743\u5229\u8981\u6c42\u81ea\u5f15\u7528", "color_key": "claim.ref", "default_enabled": True},
    "claim.ref.future": {"label": "\u6743\u5229\u8981\u6c42\u5f15\u7528\u540e\u9879", "color_key": "claim.ref", "default_enabled": True},
    "claim.ref.missing_target": {
        "label": "\u6743\u5229\u8981\u6c42\u5f15\u7528\u7f3a\u5931",
        "color_key": "claim.ref",
        "default_enabled": True,
    },
    "claim.ref.choice_word_missing": {
        "label": "\u6743\u5229\u8981\u6c42\u7f3a\u5c11\u62e9\u4e00\u8bcd",
        "color_key": "claim.ref",
        "default_enabled": True,
    },
    "claim.ref.marker_basis.missing": {
        "label": "\u9644\u56fe\u6807\u8bb0\u5f15\u7528\u57fa\u7840\u7f3a\u5931",
        "color_key": "claim.ref",
        "default_enabled": False,
    },
    "claim.ref.term_basis.missing": {
        "label": "\u6240\u8ff0\u540e\u672f\u8bed\u672a\u5bf9\u5e94\u6807\u53f7\u8bf4\u660e",
        "color_key": "claim.ref",
        "default_enabled": False,
    },
    "claim.ref.multi_to_multi.recursive": {
        "label": "\u6743\u5229\u8981\u6c42\u591a\u5f15\u591a\u9012\u5f52",
        "color_key": "claim.ref",
        "default_enabled": True,
    },
    "claim1.word_count.exceeded": {
        "label": "\u6743\u5229\u8981\u6c421\u5b57\u6570\u8d85\u9650",
        "color_key": "claim.threshold",
        "default_enabled": False,
    },
    "claim1.marker_count.exceeded": {
        "label": "\u6743\u5229\u8981\u6c421\u9644\u56fe\u6807\u8bb0\u6570\u8d85\u9650",
        "color_key": "claim.threshold",
        "default_enabled": False,
    },
    "claim.punctuation.period.extra": {
        "label": "\u6743\u5229\u8981\u6c42\u53e5\u53f7\u91cd\u590d",
        "color_key": "claim.punctuation.structure",
        "default_enabled": True,
    },
    "claim.punctuation.period.tail_missing": {
        "label": "\u6743\u5229\u8981\u6c42\u672b\u5c3e\u7f3a\u53e5\u53f7",
        "color_key": "claim.punctuation.structure",
        "default_enabled": True,
    },
    "abstract.word_count.exceeded": {
        "label": "\u6458\u8981\u5b57\u6570\u8d85\u9650",
        "color_key": "abstract.word_count.exceeded",
        "default_enabled": True,
    },
}

RULE_REGISTRY.update(
    {
        "claim.number.start_at_one": {
            "label": "权利要求编号未从1开始",
            "description": "检查权利要求编号是否从1开始。",
            "suggestion": "将首项权利要求编号调整为1，并同步检查后续编号。",
            "color_key": "claim.ref",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "forbid",
        },
        "claim.number.duplicate": {
            "label": "权利要求编号重复",
            "description": "检查权利要求编号是否重复。",
            "suggestion": "删除重复编号或按顺序重新编号。",
            "color_key": "claim.ref",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "forbid",
        },
        "claim.number.gap": {
            "label": "权利要求编号不连续",
            "description": "检查权利要求编号序列是否存在缺号。",
            "suggestion": "补齐缺失编号或重新连续编号。",
            "color_key": "claim.ref",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "forbid",
        },
        "claim.marker.parentheses_missing": {
            "label": "权利要求附图标记缺少括号",
            "description": "检查已知部件后的附图标记是否使用括号。",
            "suggestion": "将附图标记统一写在全角或半角括号内。",
            "color_key": "claim.ref",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "warn",
        },
        "claim.reference.unclear_external": {
            "label": "权利要求不清楚外部引用",
            "description": "检查如图所示、如说明书所述等外部引用表达。",
            "suggestion": "在权利要求中直接写明必要技术特征。",
            "color_key": "claim.ref",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "warn",
        },
        "claim.language.weak_limitation": {
            "label": "权利要求弱限定提示",
            "description": "提示优选地、例如、可以等可能削弱限定清晰度的措辞。",
            "suggestion": "人工确认该措辞是否构成明确、必要的技术限定。",
            "color_key": "theme.consistency",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "remind",
        },
        "claim.content.non_claim_artifact": {
            "label": "权利要求图表内容提示",
            "description": "检查流程图、方框图、曲线图、相图等图表内容提示。",
            "suggestion": "确认该内容是否应改为文字技术特征并移至适当章节。",
            "color_key": "claim.ref",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "warn",
        },
        "claim.formula.parameter_explanation_missing": {
            "label": "公式参数说明复核",
            "description": "公式附近未检测到明显参数说明时提示人工复核。",
            "suggestion": "人工确认公式中的符号、参数及单位是否已清楚说明。",
            "color_key": "theme.consistency",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "remind",
        },
        "claim.marker.missing_in_description": {
            "label": "权利要求附图标记在说明书中缺失",
            "description": "检查权利要求附图标记能否在说明书中找到对应编号。",
            "suggestion": "在说明书中补充对应附图标记说明，或核对权利要求标记。",
            "color_key": "claim.ref",
            "default_enabled": True,
            "ui_domain": "claims",
            "ui_level": "warn",
        },
        "description.heading.duplicate": {
            "label": "说明书章节标题重复",
            "description": "检查常见说明书章节标题是否重复出现。",
            "suggestion": "合并重复章节或修正误用的章节标题。",
            "color_key": "description.structure.error",
            "default_enabled": True,
            "ui_domain": "description",
            "ui_level": "warn",
        },
        "description.figure.number.gap": {
            "label": "附图说明图号不连续",
            "description": "检查附图说明中的图号是否连续。",
            "suggestion": "补齐缺失图号或按顺序调整附图说明。",
            "color_key": "description.structure.error",
            "default_enabled": True,
            "ui_domain": "description",
            "ui_level": "forbid",
        },
        "description.placeholder.residue": {
            "label": "说明书占位符残留",
            "description": "检查XXX、TODO、待补充、未填写和空方括号等占位符。",
            "suggestion": "补充真实内容并删除占位符。",
            "color_key": "description.structure.error",
            "default_enabled": True,
            "ui_domain": "description",
            "ui_level": "forbid",
        },
        "description.template.residue": {
            "label": "说明书模板残留",
            "description": "检查此处省略、后续完善、根据客户补充、请在此处等模板文字。",
            "suggestion": "删除模板提示并补充最终申请文本。",
            "color_key": "description.structure.error",
            "default_enabled": True,
            "ui_domain": "description",
            "ui_level": "warn",
        },
        "description.impl.claim_reference_style": {
            "label": "实施方式权利要求引用式写法",
            "description": "检查具体实施方式中如权利要求X所述的引用式写法。",
            "suggestion": "将引用内容改写为完整、独立的技术描述。",
            "color_key": "description.structure.error",
            "default_enabled": True,
            "ui_domain": "description",
            "ui_level": "warn",
        },
        "abstract.missing": {
            "label": "摘要缺失",
            "description": "检查是否提供摘要内容。",
            "suggestion": "补充说明技术方案要点的摘要。",
            "color_key": "abstract.word_count.exceeded",
            "default_enabled": True,
            "ui_domain": "abstract",
            "ui_level": "forbid",
        },
        "abstract.promotional_language": {
            "label": "摘要宣传性词语",
            "description": "检查国际领先、性能卓越等明显宣传性或评价性词语。",
            "suggestion": "改为客观描述技术方案和技术效果。",
            "color_key": "abstract.word_count.exceeded",
            "default_enabled": True,
            "ui_domain": "abstract",
            "ui_level": "warn",
        },
        "abstract.placeholder.residue": {
            "label": "摘要占位符残留",
            "description": "检查摘要中的占位符和模板残留。",
            "suggestion": "补充真实摘要内容并删除占位文字。",
            "color_key": "abstract.word_count.exceeded",
            "default_enabled": True,
            "ui_domain": "abstract",
            "ui_level": "forbid",
        },
        "abstract.claim_numbering_style": {
            "label": "摘要权利要求式编号",
            "description": "检查摘要是否使用权利要求式编号组织正文。",
            "suggestion": "将摘要改写为连贯的说明性文本。",
            "color_key": "abstract.word_count.exceeded",
            "default_enabled": True,
            "ui_domain": "abstract",
            "ui_level": "warn",
        },
        "drawings.figure.number.gap": {
            "label": "附图编号不连续",
            "description": "检查说明书附图编号是否存在缺号。",
            "suggestion": "补齐缺失附图或重新连续编号。",
            "color_key": "drawings.figure.ref.missing_in_impl",
            "default_enabled": True,
            "ui_domain": "drawings",
            "ui_level": "forbid",
        },
        "drawings.figure.format.mixed": {
            "label": "附图图号格式混用",
            "description": "检查图1、图 1、图一等格式是否混用。",
            "suggestion": "统一附图图号的数字和空格格式。",
            "color_key": "drawings.figure.ref.missing_in_impl",
            "default_enabled": True,
            "ui_domain": "drawings",
            "ui_level": "warn",
        },
        "text.numbering.width.mixed": {
            "label": "全角半角数字混用",
            "description": "检查全文是否同时使用全角和半角数字。",
            "suggestion": "按申请文件格式要求统一数字宽度。",
            "color_key": "punctuation.invalid_combo",
            "default_enabled": True,
            "ui_domain": "general",
            "ui_level": "warn",
        },
        "text.symbol.width.mixed": {
            "label": "中英文符号混用",
            "description": "检查对应的中文和英文括号、逗号、冒号、分号是否混用。",
            "suggestion": "按上下文统一使用中文或英文符号。",
            "color_key": "punctuation.invalid_combo",
            "default_enabled": True,
            "ui_domain": "general",
            "ui_level": "warn",
        },
        "text.abnormal_whitespace": {
            "label": "异常连续空白",
            "description": "检查连续空格、Tab或全角空格。",
            "suggestion": "删除异常空白并保持段落格式一致。",
            "color_key": "punctuation.invalid_combo",
            "default_enabled": True,
            "ui_domain": "general",
            "ui_level": "warn",
        },
    }
)

_DETERMINISTIC_RULE_IDS = frozenset(
    {
        "claim.number.start_at_one",
        "claim.number.duplicate",
        "claim.number.gap",
        "claim.marker.parentheses_missing",
        "claim.reference.unclear_external",
        "claim.language.weak_limitation",
        "claim.content.non_claim_artifact",
        "claim.formula.parameter_explanation_missing",
        "claim.marker.missing_in_description",
        "description.heading.duplicate",
        "description.figure.number.gap",
        "description.placeholder.residue",
        "description.template.residue",
        "description.impl.claim_reference_style",
        "abstract.missing",
        "abstract.promotional_language",
        "abstract.placeholder.residue",
        "abstract.claim_numbering_style",
        "drawings.figure.number.gap",
        "drawings.figure.format.mixed",
        "text.numbering.width.mixed",
        "text.symbol.width.mixed",
        "text.abnormal_whitespace",
    }
)


def _infer_ui_domain(rule_id: str) -> str:
    rid = str(rule_id or "")
    if rid.startswith("wordlist.claims.") or rid.startswith("claim.") or rid.startswith("claim1."):
        return "claims"
    if rid.startswith("abstract."):
        return "abstract"
    if rid.startswith("wordlist.description.") or rid.startswith("description."):
        return "description"
    if rid.startswith("drawings."):
        return "drawings"
    if rid.startswith("punctuation.") or rid == "text.repeated_word" or rid.startswith("theme."):
        return "general"
    return "general"


def _infer_ui_level(rule_id: str) -> str:
    rid = str(rule_id or "")
    if rid.endswith(".forbidden"):
        return "forbid"
    if rid.endswith(".sensitive"):
        return "warn"
    if rid.startswith("description.") and ("missing" in rid or "exceeded" in rid):
        return "forbid"
    if rid in {"claim.ref.missing_target", "claim.ref.marker_basis.missing", "claim.ref.term_basis.missing"}:
        return "forbid"
    if rid.startswith("claim1.") and rid.endswith(".exceeded"):
        return "forbid"
    if rid == "abstract.word_count.exceeded":
        return "forbid"
    if rid.startswith("claim.ref."):
        return "warn"
    if rid.startswith("claim.punctuation.") or rid.startswith("punctuation.") or rid == "text.repeated_word" or rid.startswith("drawings."):
        return "warn"
    if rid.startswith("theme."):
        return "remind"
    return "warn"


for _rule_id in _DETERMINISTIC_RULE_IDS:
    _metadata = RULE_REGISTRY[_rule_id]
    _ui_domain = str(_metadata.get("ui_domain") or _infer_ui_domain(_rule_id))
    _ui_level = str(_metadata.get("ui_level") or _infer_ui_level(_rule_id))
    _metadata["category"] = _ui_domain
    _metadata["severity"] = {
        "forbid": "error",
        "warn": "warning",
        "remind": "info",
    }.get(_ui_level, "warning")


def default_rule_enabled_map() -> dict[str, bool]:
    defaults: dict[str, bool] = {}
    for rule_id, meta in RULE_REGISTRY.items():
        defaults[rule_id] = bool(meta.get("default_enabled", True))
    return defaults


def normalize_rule_enabled(payload: Any) -> dict[str, bool]:
    defaults = default_rule_enabled_map()
    if not isinstance(payload, dict):
        return defaults
    normalized: dict[str, bool] = {}
    for rule_id, default_value in defaults.items():
        normalized[rule_id] = bool(payload.get(rule_id, default_value))
    return normalized


def load_rule_enabled() -> dict[str, bool]:
    raw = get_pref(RULE_ENABLED_PREF_KEY, None)
    normalized = normalize_rule_enabled(raw)
    if raw != normalized:
        set_pref(RULE_ENABLED_PREF_KEY, normalized)
    return normalized


def save_rule_enabled(payload: dict[str, bool]) -> dict[str, bool]:
    normalized = normalize_rule_enabled(payload)
    set_pref(RULE_ENABLED_PREF_KEY, normalized)
    return normalized


def enabled_rule_id_set(payload: dict[str, bool] | None = None) -> set[str]:
    normalized = normalize_rule_enabled(payload if payload is not None else load_rule_enabled())
    return {rule_id for rule_id, enabled in normalized.items() if enabled}


def rule_items_for_ui() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rule_id, meta in RULE_REGISTRY.items():
        ui_domain = str(meta.get("ui_domain") or "").strip() or _infer_ui_domain(rule_id)
        ui_level = str(meta.get("ui_level") or "").strip() or _infer_ui_level(rule_id)
        rows.append(
            {
                "rule_id": rule_id,
                "label": str(meta.get("label") or rule_id),
                "color_key": str(meta.get("color_key") or "default"),
                "default_enabled": bool(meta.get("default_enabled", True)),
                "ui_domain": ui_domain,
                "ui_level": ui_level,
                "category": str(meta.get("category") or ui_domain),
                "severity": str(meta.get("severity") or ""),
                "description": str(meta.get("description") or ""),
                "suggestion": str(meta.get("suggestion") or ""),
            }
        )
    return rows


__all__ = [
    "RULE_ENABLED_PREF_KEY",
    "RULE_REGISTRY",
    "default_rule_enabled_map",
    "enabled_rule_id_set",
    "load_rule_enabled",
    "normalize_rule_enabled",
    "rule_items_for_ui",
    "save_rule_enabled",
]
