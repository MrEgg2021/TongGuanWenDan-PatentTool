from gui.dialog_utils import show_blocking_alert_modal


def format_word_version_for_user(ver) -> str:
    if ver is None:
        return "未知"

    if isinstance(ver, str):
        s = ver.strip()
        if not s:
            return "未知"
        if s.startswith("Word"):
            return s

    try:
        v = float(ver)
    except Exception:
        try:
            s = str(ver).strip()
            return s if s else "未知"
        except Exception:
            return "未知"
    if v >= 16.0:
        return "Word 16+"
    if 15.0 <= v < 16.0:
        return "Word 2013"
    if 14.0 <= v < 15.0:
        return "Word 2010"
    if 12.0 <= v < 13.0:
        return "Word 2007"
    if 11.0 <= v < 12.0:
        return "Word 2003"
    if 10.0 <= v < 11.0:
        return "Word 2002（XP）"
    if 9.0 <= v < 10.0:
        return "Word 2000"
    if 8.0 <= v < 9.0:
        return "Word 97"
    try:
        return f"Word {v:g}"
    except Exception:
        return "未知"


def build_hijack_help_text(*, hijacked: bool, detail: str = "") -> str:
    base = (
        "【常见原因】\n"
        "- 安装了 WPS，并开启了 WPS 对第三方系统/软件的兼容选项，可能导致 Word 后台端口被接管。\n\n"
        "【建议处理方式】\n"
        "1) 打开电脑开始菜单，找到“WPS Office文件夹”→“WPS Office工具”→“配置工具”，右键以管理员运行\n"
        "2) 点击“高级”→“兼容设置”→“WPS Office 兼容第三方系统和软件”→取消勾选→“确定”\n"
        "3) 关闭所有 WPS/Word 进程后重试\n"
    )
    if hijacked:
        if detail.strip():
            return str(detail).strip()
        return "检测到后台端口疑似被其他软件劫持。\n\n" + base
    return "当前检测结果：正常。\n\n" + base


def is_env_abnormal(word_ok: bool, hijacked: bool, word_too_low: bool) -> bool:
    try:
        return bool(hijacked or word_too_low or (not word_ok))
    except Exception:
        return True


def maybe_alert_env_issues(window, *, word_ok: bool, hijacked: bool, word_too_low: bool, word_error: str = "") -> None:
    if not is_env_abnormal(word_ok, hijacked, word_too_low):
        return

    title = "环境检测异常"
    msg = ""
    if hijacked:
        fallback_possible = False
        try:
            fallback_possible = bool(getattr(window, "_env_wps_fallback_possible", False))
        except Exception:
            fallback_possible = False
        if fallback_possible:
            return
        else:
            title = "检测到 Word 后台端口被挟持"
            msg = "检测到 Word 后台端口可能被其他软件挟持，这会导致转换不稳定或异常。\n\n" + build_hijack_help_text(
                hijacked=True, detail=str(getattr(window, "_env_wps_hint_text", "") or "")
            )
    elif word_too_low:
        title = "Word 版本过低"
        msg = "检测到当前 Word 版本低于 Word 2007，本工具仅支持 Word 2007 及以上版本。"
    else:
        title = "无法启动 Word"
        msg = "未能启动 Word 或读取版本信息，请确认已正确安装 Microsoft Word，并关闭所有 WPS/Word 进程后重试。"
        if str(word_error).strip():
            msg += f"\n\n错误信息：\n{word_error}"

    try:
        show_blocking_alert_modal(window, title, msg, primary_text="关闭", secondary_text="关闭")
    except Exception:
        pass
