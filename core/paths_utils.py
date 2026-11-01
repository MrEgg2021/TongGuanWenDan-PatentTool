from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path


def _get_project_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def get_app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return _get_project_root()


def get_resource_dir() -> str:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = os.path.join(str(meipass), "resources")
            if os.path.exists(base):
                return base
            return str(meipass)

        base = os.path.join(get_app_dir(), "resources")
        return base

    base = os.path.join(get_app_dir(), "resources")
    if os.path.exists(base):
        return base
    return get_app_dir()


def get_resource_path(relative_path: str) -> str:
    return os.path.join(get_resource_dir(), relative_path)


def _get_windows_roaming_appdata() -> str:
    """使用 WinAPI 获取 Roaming AppData 路径，失败时返回空字符串。"""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        csidl_appdata = 26
        shgfp_type_current = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        res = ctypes.windll.shell32.SHGetFolderPathW(None, csidl_appdata, None, shgfp_type_current, buf)
        if int(res) == 0:
            value = str(buf.value or "").strip()
            if value:
                return value
    except Exception:
        return ""
    return ""


def _get_windows_common_appdata() -> str:
    """Windows ProgramData (Common AppData) path. Returns empty string on failure."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        csidl_common_appdata = 35
        shgfp_type_current = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        res = ctypes.windll.shell32.SHGetFolderPathW(None, csidl_common_appdata, None, shgfp_type_current, buf)
        if int(res) == 0:
            value = str(buf.value or "").strip()
            if value:
                return value
    except Exception:
        return ""
    return ""


def _get_windows_common_documents() -> str:
    """Windows Public Documents path. Returns empty string on failure."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        csidl_common_documents = 46
        shgfp_type_current = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        res = ctypes.windll.shell32.SHGetFolderPathW(None, csidl_common_documents, None, shgfp_type_current, buf)
        if int(res) == 0:
            value = str(buf.value or "").strip()
            if value:
                return value
    except Exception:
        return ""
    return ""


def get_user_data_dir() -> str:
    """返回用户数据目录（优先 WinAPI，失败时回退）。"""
    base = ""
    try:
        base = _get_windows_roaming_appdata()
    except Exception:
        base = ""
    if not base:
        try:
            base = os.environ.get("APPDATA")
        except RecursionError:
            base = ""
        except Exception:
            base = ""
    if base:
        return os.path.join(base, "CPC-XML-Converter")
    return os.path.join(get_app_dir(), "user_data")


def _ensure_writable_dir(path: str) -> bool:
    if not path:
        return False
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return False
    probe_name = os.path.join(path, f".write_probe_{uuid.uuid4().hex}.tmp")
    try:
        with open(probe_name, "x", encoding="utf-8") as probe:
            probe.write("ok")
        return True
    except Exception:
        return False
    finally:
        try:
            os.remove(probe_name)
        except FileNotFoundError:
            pass
        except Exception:
            pass


def get_machine_data_dir() -> str:
    """Return per-machine data directory shared across Windows accounts.

    Preference order:
    1) ProgramData\\CPC-XML-Converter
    2) Public Documents\\CPC-XML-Converter
    3) User data dir (fallback; not shared across accounts)
    """

    candidates: list[str] = []
    if os.name == "nt":
        base = ""
        try:
            base = _get_windows_common_appdata()
        except Exception:
            base = ""
        if not base:
            try:
                base = os.environ.get("ProgramData") or ""
            except Exception:
                base = ""
        if base:
            candidates.append(os.path.join(base, "CPC-XML-Converter"))

        docs = ""
        try:
            docs = _get_windows_common_documents()
        except Exception:
            docs = ""
        if docs:
            candidates.append(os.path.join(docs, "CPC-XML-Converter"))

        # Fallback for some locked-down environments
        try:
            public = os.environ.get("PUBLIC") or ""
        except Exception:
            public = ""
        if public:
            candidates.append(os.path.join(public, "Documents", "CPC-XML-Converter"))

    # Last resort
    candidates.append(get_user_data_dir())

    for cand in candidates:
        if _ensure_writable_dir(cand):
            return cand

    # Should not happen; return user dir anyway
    return get_user_data_dir()
