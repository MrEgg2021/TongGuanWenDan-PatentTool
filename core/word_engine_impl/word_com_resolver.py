from __future__ import annotations

import psutil
import win32com.client

from .registry_probe import discover_ms_word_versions_from_registry, is_wps_path_text


def collect_word_app_diag(app_obj) -> dict:
    def _safe_getattr(obj, attr):
        try:
            return getattr(obj, attr, None)
        except Exception:
            return None

    app_name = _safe_getattr(app_obj, "Name")
    app_path = _safe_getattr(app_obj, "Path")
    app_hwnd = _safe_getattr(app_obj, "Hwnd")
    pid = None
    proc_name = None
    proc_exe = None

    if app_hwnd:
        try:
            import win32process

            _tid, pid = win32process.GetWindowThreadProcessId(int(app_hwnd))
        except Exception:
            pid = None

    if pid:
        try:
            process = psutil.Process(int(pid))
            proc_name = process.name()
            proc_exe = process.exe()
        except Exception:
            proc_name = None
            proc_exe = None

    return {
        "Name": app_name,
        "Path": app_path,
        "Hwnd": app_hwnd,
        "PID": pid,
        "ProcName": proc_name,
        "ProcExe": proc_exe,
    }


def is_wps_runtime_diag(diag: dict | None) -> bool:
    if not isinstance(diag, dict):
        return False
    probe = " ".join(
        [
            str(diag.get("Name") or ""),
            str(diag.get("Path") or ""),
            str(diag.get("ProcName") or ""),
            str(diag.get("ProcExe") or ""),
        ]
    )
    return is_wps_path_text(probe)


def _close_quietly(app_obj) -> None:
    if app_obj is None:
        return
    try:
        app_obj.Quit(SaveChanges=0)
    except Exception:
        pass


def dispatch_word_via_com(*, client=None) -> tuple[object | None, dict]:
    target_client = client or win32com.client
    attempted_progids: list[str] = []
    last_diag = None
    last_error = None

    try:
        attempted_progids.append("Word.Application")
        app_obj = target_client.DispatchEx("Word.Application")
        diag = collect_word_app_diag(app_obj)
        if not is_wps_runtime_diag(diag):
            return app_obj, {
                "binding_source": "default_progid",
                "binding_progid": "Word.Application",
                "attempted_progids": list(attempted_progids),
                "last_diag": diag,
                "last_error": None,
            }
        last_diag = diag
        _close_quietly(app_obj)
    except Exception as exc:
        last_error = exc

    for version in sorted(set(discover_ms_word_versions_from_registry()), reverse=True):
        progid = f"Word.Application.{int(version)}"
        attempted_progids.append(progid)
        try:
            app_obj = target_client.DispatchEx(progid)
            diag = collect_word_app_diag(app_obj)
            if is_wps_runtime_diag(diag):
                last_diag = diag
                _close_quietly(app_obj)
                continue
            return app_obj, {
                "binding_source": "versioned_progid",
                "binding_progid": progid,
                "attempted_progids": list(attempted_progids),
                "last_diag": diag,
                "last_error": last_error,
            }
        except Exception as exc:
            last_error = exc
            continue

    return None, {
        "binding_source": "",
        "binding_progid": "",
        "attempted_progids": list(attempted_progids),
        "last_diag": last_diag,
        "last_error": last_error,
    }


def get_active_word_via_com(*, client=None) -> tuple[object, dict]:
    target_client = client or win32com.client
    attempted_progids: list[str] = []
    last_diag = None
    last_error = None

    for progid in ["Word.Application"] + [f"Word.Application.{int(v)}" for v in sorted(set(discover_ms_word_versions_from_registry()), reverse=True)]:
        attempted_progids.append(progid)
        try:
            app_obj = target_client.GetActiveObject(progid)
            diag = collect_word_app_diag(app_obj)
            if is_wps_runtime_diag(diag):
                last_diag = diag
                continue
            source = "active_default_progid" if progid == "Word.Application" else "active_versioned_progid"
            return app_obj, {
                "binding_source": source,
                "binding_progid": progid,
                "attempted_progids": list(attempted_progids),
                "last_diag": diag,
                "last_error": last_error,
            }
        except Exception as exc:
            last_error = exc
            continue

    detail = ""
    if last_diag:
        detail = f" last_diag={last_diag!r}"
    elif last_error is not None:
        detail = f" last_error={last_error!r}"
    raise RuntimeError("未能绑定到活动 Microsoft Word 实例。" + detail)


def get_active_or_dispatch_word_via_com(*, client=None) -> tuple[object, bool, dict]:
    try:
        app_obj, info = get_active_word_via_com(client=client)
        return app_obj, False, info
    except Exception:
        app_obj, info = dispatch_word_via_com(client=client)
        if app_obj is not None:
            return app_obj, True, info

    detail = ""
    if info.get("last_diag") is not None:
        detail = f" last_diag={info['last_diag']!r}"
    elif info.get("last_error") is not None:
        detail = f" last_error={info['last_error']!r}"
    raise RuntimeError("未能绑定到可用的 Microsoft Word COM 实例。" + detail)
