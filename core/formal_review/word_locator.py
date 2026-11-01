from __future__ import annotations

from dataclasses import dataclass

from .range_resolver import ResolverPolicy, resolve_issue_range
from .text_projection import ProjectionBundle


@dataclass(slots=True)
class LocateResult:
    ok: bool
    level: str
    message: str


def _select_range(rng) -> None:
    try:
        rng.Select()
    except Exception:
        app = getattr(rng, "Application", None)
        if app is None:
            raise
        selection = getattr(app, "Selection", None)
        if selection is None:
            raise
        selection.SetRange(int(rng.Start), int(rng.End))
    try:
        app = getattr(rng, "Application", None)
        selection = getattr(app, "Selection", None) if app is not None else None
        if selection is not None:
            selection.Range.ScrollIntoView()
            return
    except Exception:
        pass
    try:
        rng.ScrollIntoView()
    except Exception:
        pass


def _activate_word_window(session) -> None:
    hwnd = None
    try:
        hwnd = int(getattr(session, "word_hwnd", 0) or 0)
    except Exception:
        hwnd = 0
    if not hwnd:
        try:
            hwnd = int(session.doc.Windows(1).Hwnd)
            session.word_hwnd = hwnd
        except Exception:
            hwnd = 0
    if not hwnd:
        return
    try:
        import win32con
        import win32gui

        try:
            win32gui.ShowWindow(int(hwnd), int(win32con.SW_RESTORE))
        except Exception:
            pass
        win32gui.SetForegroundWindow(int(hwnd))
    except Exception:
        try:
            app = getattr(session, "app", None)
            if app is not None:
                app.Activate()
        except Exception:
            pass


def locate_issue_in_word(
    session,
    issue,
    *,
    projections: ProjectionBundle | None = None,
    activate_window: bool = False,
    strict: bool = True,
    require_com_ready: bool = False,
) -> LocateResult:
    doc = getattr(session, "doc", None)
    if doc is None:
        return LocateResult(False, "fail", "Word 会话不可用。")

    resolved = resolve_issue_range(
        doc,
        issue,
        projections,
        strict=bool(strict),
        allow_legacy_fallback=False,
        policy=ResolverPolicy(
            strict=bool(strict),
            allow_legacy_fallback=False,
            require_com_ready=bool(require_com_ready),
        ),
    )
    if not bool(getattr(resolved, "ok", False)):
        reason = str(getattr(resolved, "reason", "") or "未能在当前 Word 文档中定位该问题。")
        reason_code = str(getattr(resolved, "reason_code", "") or "resolve_failed")
        detail = str(getattr(resolved, "detail", "") or "")
        if detail:
            reason = f"{reason}（{reason_code}: {detail}）"
        else:
            reason = f"{reason}（{reason_code}）"
        return LocateResult(False, "fail", reason)
    try:
        rng = doc.Range(int(getattr(resolved, "start")), int(getattr(resolved, "end")))
        _select_range(rng)
    except Exception as exc:
        return LocateResult(False, "fail", f"选中定位范围失败：{exc}")
    if activate_window:
        _activate_word_window(session)
    level = str(getattr(resolved, "level", "") or "projection")
    rule_id = str(getattr(issue, "rule_id", "") or "")
    start = int(getattr(resolved, "start"))
    end = int(getattr(resolved, "end"))
    return LocateResult(True, level, f"已定位({rule_id})：{start}-{end} [{level}]")
