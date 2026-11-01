from __future__ import annotations

import os
import re

try:
    import winreg
except Exception:
    winreg = None


def is_wps_path_text(text: str) -> bool:
    probe = str(text or "").lower()
    return ("kingsoft" in probe) or ("wps" in probe)


def reg_read_default(root, subkey: str) -> str:
    if winreg is None:
        return ""
    wow64_flags = [0]
    try:
        f64 = getattr(winreg, "KEY_WOW64_64KEY", None)
        if isinstance(f64, int):
            wow64_flags.append(f64)
    except Exception:
        pass
    try:
        f32 = getattr(winreg, "KEY_WOW64_32KEY", None)
        if isinstance(f32, int):
            wow64_flags.append(f32)
    except Exception:
        pass
    seen = set()
    for extra in wow64_flags:
        if extra in seen:
            continue
        seen.add(extra)
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | int(extra)) as k:
                v, _t = winreg.QueryValueEx(k, "")
                s = str(v or "")
                if s.strip():
                    return s
        except Exception:
            continue
    return ""


def progid_localserver32(progid: str) -> str:
    if winreg is None:
        return ""

    def _read_any(path_in_classes: str) -> str:
        v = ""
        try:
            v = reg_read_default(winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + path_in_classes)
        except Exception:
            v = ""
        if str(v).strip():
            return str(v).strip()
        try:
            v = reg_read_default(winreg.HKEY_LOCAL_MACHINE, "Software\\Classes\\" + path_in_classes)
        except Exception:
            v = ""
        if str(v).strip():
            return str(v).strip()
        try:
            v = reg_read_default(winreg.HKEY_CLASSES_ROOT, path_in_classes)
        except Exception:
            v = ""
        return str(v).strip()

    clsid = _read_any(progid + "\\CLSID")
    if not clsid:
        return ""
    return _read_any(f"CLSID\\{clsid}\\LocalServer32")


def parse_localserver_exe_path(localserver32: str) -> str:
    s = str(localserver32 or "").strip()
    if not s:
        return ""
    if s.startswith('"'):
        end = s.find('"', 1)
        if end > 1:
            return s[1:end]
    try:
        low = s.lower()
        exe_idx = low.find(".exe")
        if exe_idx > 0:
            return s[: exe_idx + 4]
    except Exception:
        pass
    parts = s.split()
    if parts:
        return parts[0]
    return s


def _version_from_path(exe_path: str) -> float | None:
    try:
        m = re.search(r"office(\d{1,2})", str(exe_path or ""), flags=re.IGNORECASE)
        if m:
            return float(int(m.group(1)))
    except Exception:
        return None
    return None


def discover_ms_word_versions_from_registry() -> list[int]:
    if winreg is None:
        return []
    found: list[int] = []
    for v in range(8, 41):
        progid = f"Word.Application.{v}"
        server = progid_localserver32(progid)
        if not server:
            continue
        exe_path = parse_localserver_exe_path(server)
        probe = str(exe_path or "").lower()
        if "winword.exe" not in probe:
            continue
        if is_wps_path_text(probe):
            continue
        try:
            if not os.path.exists(exe_path):
                continue
        except Exception:
            continue
        found.append(v)
    found.sort()
    return found


def find_winword_exe_candidates() -> list[str]:
    candidates: list[str] = []
    try:
        if winreg is not None:
            app_paths = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WINWORD.EXE",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\WINWORD.EXE",
            ]
            for subkey in app_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey) as k:
                        val, _ = winreg.QueryValueEx(k, "")
                    if val:
                        candidates.append(str(val))
                except Exception:
                    continue
    except Exception:
        pass

    for version in discover_ms_word_versions_from_registry():
        server = progid_localserver32(f"Word.Application.{version}")
        exe_path = parse_localserver_exe_path(server)
        if exe_path:
            candidates.append(exe_path)

    unique: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        norm = str(path or "").strip()
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            if not os.path.exists(norm):
                continue
        except Exception:
            continue
        if not norm.lower().endswith("winword.exe"):
            continue
        unique.append(norm)
    return unique


def find_first_winword_exe() -> str | None:
    candidates = find_winword_exe_candidates()
    if candidates:
        return candidates[0]
    return None


def _build_word_candidates(versions: list[int]) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    for version in sorted(set(int(v) for v in versions), reverse=True):
        progid = f"Word.Application.{version}"
        server = progid_localserver32(progid)
        exe_path = parse_localserver_exe_path(server)
        if not exe_path:
            continue
        low = exe_path.lower()
        if "winword.exe" not in low or is_wps_path_text(low):
            continue
        try:
            if not os.path.exists(exe_path):
                continue
        except Exception:
            continue
        if low in seen:
            continue
        seen.add(low)
        candidates.append(
            {
                "progid": progid,
                "version": float(version),
                "localserver32": str(server or ""),
                "exe_path": exe_path,
            }
        )

    for exe_path in find_winword_exe_candidates():
        low = str(exe_path or "").lower()
        if low in seen:
            continue
        seen.add(low)
        candidates.append(
            {
                "progid": "",
                "version": _version_from_path(exe_path),
                "localserver32": "",
                "exe_path": exe_path,
            }
        )
    return candidates


def probe_word_com_registration() -> dict:
    server = progid_localserver32("Word.Application")
    exe_path = parse_localserver_exe_path(server)
    default_exists = False
    try:
        default_exists = bool(exe_path and os.path.exists(exe_path))
    except Exception:
        default_exists = False
    default_is_wps = is_wps_path_text(exe_path)
    default_is_word = ("winword.exe" in str(exe_path or "").lower()) and (not default_is_wps)

    versions = discover_ms_word_versions_from_registry()
    word_candidates = _build_word_candidates(versions)
    fallback_possible = bool(word_candidates)

    word_ok = bool(default_is_word or fallback_possible)
    hijacked = bool(default_is_wps)

    word_version = None
    if versions:
        try:
            word_version = float(max(versions))
        except Exception:
            word_version = None
    if word_version is None and default_is_word:
        word_version = _version_from_path(exe_path)
    if word_version is None:
        for candidate in word_candidates:
            try:
                if candidate.get("version") is not None:
                    word_version = float(candidate["version"])
                    break
            except Exception:
                continue

    if hijacked and not fallback_possible:
        block_reason = "no_word_candidates"
    elif not word_ok:
        block_reason = "no_word_registration"
    else:
        block_reason = ""

    return {
        "default_com_target": str(server or ""),
        "default_com_exe_path": str(exe_path or ""),
        "default_com_path_exists": bool(default_exists),
        "default_com_is_wps": bool(default_is_wps),
        "default_com_is_word": bool(default_is_word),
        "word_candidates": list(word_candidates),
        "fallback_possible": bool(fallback_possible),
        "word_ok": bool(word_ok),
        "hijacked": bool(hijacked),
        "word_version": word_version,
        "block_reason": str(block_reason or ""),
        "localserver32": str(server or ""),
    }
