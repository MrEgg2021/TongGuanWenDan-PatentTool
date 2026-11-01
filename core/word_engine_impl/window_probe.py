def _visible_window_pids() -> set[int] | None:
    try:
        import win32gui
        import win32process
        import win32con
    except Exception:
        return None

    pids: set[int] = set()

    def _cb(hwnd, _param):
        try:
            iconic = False
            try:
                iconic = bool(win32gui.IsIconic(hwnd))
            except Exception:
                iconic = False

            try:
                if not win32gui.IsWindowVisible(hwnd) and not iconic:
                    return True
            except Exception:
                if not iconic:
                    return True

            try:
                style = int(win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE))
                if style & int(win32con.WS_CHILD):
                    return True
            except Exception:
                pass
            try:
                if not iconic:
                    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                    if (right - left) < 50 or (bottom - top) < 50:
                        return True
            except Exception:
                pass
            _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                pids.add(int(pid))
        except Exception:
            return True
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        return None
    return pids
