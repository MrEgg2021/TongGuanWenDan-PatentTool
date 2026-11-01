import ctypes
import os
import sys

from gui.dialog_utils import show_blocking_alert_modal


def _probe_windows_runtime_env() -> dict:
    runtime_ok = True
    missing: list[str] = []
    build = None
    major = None
    minor = None
    ver_text = ""

    if os.name != "nt":
        return {
            "runtime_ok": True,
            "missing_dlls": [],
            "windows_build": None,
            "windows_major": None,
            "windows_minor": None,
            "windows_text": "",
            "hint": "",
        }

    try:
        wv = sys.getwindowsversion()
        major = int(getattr(wv, "major", 0) or 0)
        minor = int(getattr(wv, "minor", 0) or 0)
        build = int(getattr(wv, "build", 0) or 0)
        sp = str(getattr(wv, "service_pack", "") or "").strip()
        ver_text = f"Windows {major}.{minor} (Build {build})".strip()
        if sp:
            ver_text = ver_text + f" {sp}"
    except Exception:
        major = None
        minor = None
        build = None
        ver_text = ""

    if major is not None and major < 10:
        runtime_ok = False

    dlls = [
        "api-ms-win-core-path-l1-1-0.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
        "ucrtbase.dll",
    ]
    for name in dlls:
        try:
            ctypes.WinDLL(name)
        except Exception:
            missing.append(name)

    if missing:
        runtime_ok = False

    hint_lines: list[str] = []
    if ver_text:
        hint_lines.append(f"当前系统版本：{ver_text}")
    if major is not None and major < 10:
        hint_lines.append("当前系统版本可能过低，建议升级到 Windows 10/11 的较新版本后再运行。")
    if missing:
        hint_lines.append("检测到以下系统运行库可能缺失或无法加载：")
        hint_lines.extend([f"- {x}" for x in missing])
        hint_lines.append("")
        hint_lines.append("建议处理：")
        hint_lines.append("1) 安装 Microsoft Visual C++ 2015-2022 Redistributable（x64）")
        hint_lines.append("2) 通过 Windows Update 更新系统补丁（部分精简版系统可能缺少必要组件）")

    hint = "\n".join([x for x in hint_lines if x is not None])
    return {
        "runtime_ok": bool(runtime_ok),
        "missing_dlls": missing,
        "windows_build": build,
        "windows_major": major,
        "windows_minor": minor,
        "windows_text": ver_text,
        "hint": hint,
    }


def maybe_alert_runtime_issues(window, *, runtime_ok: bool, hint: str = "") -> None:
    if runtime_ok:
        return
    msg = "检测到当前系统运行环境可能不满足本工具运行需求。\n\n"
    if str(hint or "").strip():
        msg += str(hint)
    else:
        msg += "建议升级系统并安装 Microsoft Visual C++ 2015-2022 Redistributable（x64）。"
    try:
        show_blocking_alert_modal(window, "系统运行环境异常", msg, primary_text="关闭", secondary_text="关闭")
    except Exception:
        pass
