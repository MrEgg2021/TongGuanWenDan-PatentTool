from __future__ import annotations

from dataclasses import dataclass

from .annotator import TOOL_COMMENT_PREFIX, is_tool_comment
from .range_resolver import ResolverPolicy, resolve_issue_range
from .rule_registry import RULE_REGISTRY
from .text_projection import ProjectionBundle


@dataclass(slots=True)
class HighlightSyncResult:
    highlighted: int
    skipped: int
    cleared: int
    warnings: list[str]


def _hex_to_bgr_int(value: str) -> int:
    text = str(value or "").strip()
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) != 7:
        raise ValueError(f"invalid hex color: {value!r}")
    red = int(text[1:3], 16)
    green = int(text[3:5], 16)
    blue = int(text[5:7], 16)
    return int((blue << 16) | (green << 8) | red)


def _issue_color_key(issue) -> str:
    rule_id = str(getattr(issue, "rule_id", "") or "")
    row = RULE_REGISTRY.get(rule_id) if isinstance(RULE_REGISTRY, dict) else None
    return str((row or {}).get("color_key") or "default")


def _issue_color(issue, color_map: dict[str, str]) -> str:
    cmap = dict(color_map or {})
    rule_id = str(getattr(issue, "rule_id", "") or "")
    key = _issue_color_key(issue)
    return str(cmap.get(rule_id) or cmap.get(key) or cmap.get("default") or "#E0E0E0")


def _clear_range_highlight(rng) -> None:
    # Prefer clearing both classic highlight and shading background.
    try:
        rng.HighlightColorIndex = 0
    except Exception:
        pass
    try:
        rng.Shading.BackgroundPatternColor = -16777216  # wdColorAutomatic
    except Exception:
        pass
    try:
        rng.Shading.Texture = 0
    except Exception:
        pass


def _scope_tuple(scope) -> tuple[int, int] | None:
    if scope is None:
        return None
    try:
        start = int(getattr(scope, "Start", 0) or 0)
        end = int(getattr(scope, "End", 0) or 0)
    except Exception:
        return None
    if int(end) <= int(start):
        return None
    return int(start), int(end)


def clear_tool_highlights_via_comments(
    doc,
    tool_prefix: str = TOOL_COMMENT_PREFIX,
    target_ranges: set[tuple[int, int]] | None = None,
) -> int:
    if doc is None:
        return 0
    comments = getattr(doc, "Comments", None)
    if comments is None:
        return 0
    targets = set(target_ranges or set())
    use_targets = bool(targets)
    try:
        total = int(getattr(comments, "Count", 0) or 0)
    except Exception:
        total = 0
    cleared = 0
    for idx in range(total, 0, -1):
        try:
            row = comments(idx)
            text = str(getattr(getattr(row, "Range", None), "Text", "") or "")
            if not is_tool_comment(text, prefix=tool_prefix):
                continue
            scope = getattr(row, "Scope", None) or getattr(row, "Reference", None) or getattr(row, "Range", None)
            if scope is None:
                continue
            if use_targets:
                scope_row = _scope_tuple(scope)
                if scope_row is None or scope_row not in targets:
                    continue
            _clear_range_highlight(scope)
            cleared += 1
        except Exception:
            continue
    return cleared


def apply_issue_highlights(
    doc,
    issues: list,
    color_map: dict[str, str],
    tool_prefix: str = TOOL_COMMENT_PREFIX,
    projections: ProjectionBundle | None = None,
    require_com_ready: bool = True,
) -> HighlightSyncResult:
    warnings: list[str] = []
    highlighted = 0
    skipped = 0
    cleared = clear_tool_highlights_via_comments(doc, tool_prefix=tool_prefix)

    for issue in list(issues or []):
        if bool(getattr(issue, "ignored", False)):
            skipped += 1
            continue
        resolved = resolve_issue_range(
            doc,
            issue,
            projections,
            strict=True,
            allow_legacy_fallback=False,
            policy=ResolverPolicy(
                strict=True,
                allow_legacy_fallback=False,
                require_com_ready=bool(require_com_ready),
            ),
        )
        if not bool(getattr(resolved, "ok", False)):
            skipped += 1
            continue
        start = int(getattr(resolved, "start"))
        end = int(getattr(resolved, "end"))
        try:
            rng = doc.Range(start, end)
        except Exception:
            skipped += 1
            continue
        color = _issue_color(issue, color_map)
        try:
            bgr = _hex_to_bgr_int(color)
        except Exception as exc:
            skipped += 1
            warnings.append(f"无效颜色 {color!r}：{exc}")
            continue
        applied = False
        try:
            rng.Shading.BackgroundPatternColor = int(bgr)
            applied = True
        except Exception:
            pass
        if not applied:
            try:
                rng.HighlightColorIndex = 7  # wdYellow
                applied = True
            except Exception:
                pass
        if applied:
            highlighted += 1
        else:
            skipped += 1

    return HighlightSyncResult(
        highlighted=int(highlighted),
        skipped=int(skipped),
        cleared=int(cleared),
        warnings=warnings,
    )


__all__ = ["HighlightSyncResult", "apply_issue_highlights", "clear_tool_highlights_via_comments"]
