from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class DockLayout:
    left_ratio: float = 0.30
    primary_monitor_only: bool = True


@dataclass(slots=True, frozen=True)
class DockResult:
    ok: bool
    message: str
    app_rect: tuple[int, int, int, int] | None = None
    word_rect: tuple[int, int, int, int] | None = None


def _primary_monitor_rect() -> tuple[int, int, int, int] | None:
    try:
        import win32api
        import win32con

        monitor = win32api.MonitorFromPoint((0, 0), int(win32con.MONITOR_DEFAULTTOPRIMARY))
        info = win32api.GetMonitorInfo(monitor)
        left, top, right, bottom = info.get("Work")
        return int(left), int(top), int(right), int(bottom)
    except Exception:
        return None


def _window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    try:
        import win32gui

        left, top, right, bottom = win32gui.GetWindowRect(int(hwnd))
        return int(left), int(top), int(right), int(bottom)
    except Exception:
        return None


def _canonical_top_level_hwnd(hwnd: int) -> int:
    try:
        import win32con
        import win32gui

        candidate = int(hwnd)
        if candidate <= 0:
            return 0
        try:
            root = int(win32gui.GetAncestor(candidate, int(win32con.GA_ROOT)))
            if root > 0:
                candidate = root
        except Exception:
            pass
        return candidate
    except Exception:
        try:
            return int(hwnd)
        except Exception:
            return 0


def dock_app_and_word(app_hwnd: int, word_hwnd: int, layout: DockLayout | None = None) -> DockResult:
    if not app_hwnd or not word_hwnd:
        return DockResult(False, "窗口句柄无效，无法自动分屏。")

    app_target = _canonical_top_level_hwnd(int(app_hwnd))
    word_target = _canonical_top_level_hwnd(int(word_hwnd))
    if not app_target or not word_target:
        return DockResult(False, "窗口句柄归一化失败，无法自动分屏。")

    ratio = float((layout or DockLayout()).left_ratio)
    ratio = max(0.15, min(0.60, ratio))
    work_rect = _primary_monitor_rect()
    if work_rect is None:
        return DockResult(False, "无法读取主显示器工作区。")

    left, top, right, bottom = work_rect
    width = max(1, right - left)
    height = max(1, bottom - top)
    app_width = max(280, int(width * ratio))
    word_width = max(420, width - app_width)

    app_rect = (left, top, left + app_width, top + height)
    word_rect = (left + app_width, top, left + app_width + word_width, top + height)

    try:
        import win32con
        import win32gui

        flags = int(win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
        win32gui.ShowWindow(int(app_target), int(win32con.SW_RESTORE))
        win32gui.ShowWindow(int(word_target), int(win32con.SW_RESTORE))
        win32gui.SetWindowPos(
            int(app_target),
            0,
            int(app_rect[0]),
            int(app_rect[1]),
            int(app_rect[2] - app_rect[0]),
            int(app_rect[3] - app_rect[1]),
            flags,
        )
        win32gui.SetWindowPos(
            int(word_target),
            0,
            int(word_rect[0]),
            int(word_rect[1]),
            int(word_rect[2] - word_rect[0]),
            int(word_rect[3] - word_rect[1]),
            flags,
        )
    except Exception as exc:
        app_now = _window_rect(int(app_target)) or _window_rect(int(app_hwnd))
        word_now = _window_rect(int(word_target)) or _window_rect(int(word_hwnd))
        return DockResult(False, f"自动分屏失败（SetWindowPos）：{exc}", app_now, word_now)

    return DockResult(True, "已自动完成窗口分屏。", app_rect=app_rect, word_rect=word_rect)


__all__ = ["DockLayout", "DockResult", "dock_app_and_word"]
