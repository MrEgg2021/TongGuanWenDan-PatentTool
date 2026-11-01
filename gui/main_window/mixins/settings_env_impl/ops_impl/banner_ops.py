from gui.main_window.mixins.settings_env_impl.ops_impl.word_env_ops import format_word_version_for_user, is_env_abnormal


def set_env_banner(window, *, icon_text: str, text: str, show_help: bool) -> None:
    frame = getattr(window, "env_warning_frame", None)
    icon = getattr(window, "env_warning_icon", None)
    label = getattr(window, "env_warning_text", None)
    btn_help = getattr(window, "env_warning_help_button", None)
    btn_retry = getattr(window, "env_warning_retry_button", None)
    sidebar_btn = None
    try:
        shell = getattr(window, "_modern_shell", None)
        if shell is not None:
            sidebar_btn = getattr(shell, "env_status", None)
    except Exception:
        sidebar_btn = None

    sidebar_tooltip = str(text or "")
    sidebar_label = "环境未检测"
    try:
        t = str(text or "")
        if "环境正常" in t:
            sidebar_label = "环境正常"
        elif "异常" in t:
            sidebar_label = "环境异常"
        elif "检测中" in t:
            sidebar_label = "环境检测中"
    except Exception:
        sidebar_label = "环境未检测"

    sidebar_text = sidebar_label
    if str(icon_text or "").strip():
        sidebar_text = f"{icon_text} {sidebar_text}".strip()

    try:
        window._env_last_show_help = bool(show_help)
    except Exception:
        pass
    try:
        if sidebar_btn is not None:
            try:
                sidebar_btn._full_text = sidebar_text
            except Exception:
                pass
            try:
                sidebar_btn.setToolTip(sidebar_tooltip)
            except Exception:
                pass
            collapsed = False
            try:
                collapsed = bool(sidebar_btn.property("collapsed"))
            except Exception:
                collapsed = False
            try:
                sidebar_btn.setText("" if collapsed else sidebar_text)
            except Exception:
                pass
    except Exception:
        pass

    if frame is None or label is None:
        return

    try:
        if icon is not None:
            icon.setText(str(icon_text or ""))
    except Exception:
        pass
    try:
        label.setText(str(text or ""))
    except Exception:
        pass
    try:
        if btn_help is not None:
            btn_help.setVisible(bool(show_help))
    except Exception:
        pass
    try:
        if btn_retry is not None:
            btn_retry.setVisible(True)
    except Exception:
        pass
    try:
        frame.setVisible(True)
    except Exception:
        pass


def update_env_banner_checking(window) -> None:
    set_env_banner(window, icon_text="…", text="环境检测：检测中...", show_help=False)


def update_env_banner_from_result(
    window,
    *,
    word_ok: bool,
    hijacked: bool,
    word_too_low: bool,
    ver,
    runtime_ok: bool | None = None,
    pdf_export_ok: bool | None = None,
) -> None:
    if is_env_abnormal(word_ok, hijacked, word_too_low):
        if hijacked:
            set_env_banner(window, icon_text="⚠", text="环境检测：异常（后台端口被挟持）", show_help=True)
        elif word_too_low:
            set_env_banner(window, icon_text="⚠", text="环境检测：异常（Word 版本过低）", show_help=bool(runtime_ok is False))
        else:
            set_env_banner(
                window,
                icon_text="⚠",
                text="环境检测：异常（未检测到 Microsoft Word）",
                show_help=bool(runtime_ok is False),
            )
        return

    if runtime_ok is False:
        set_env_banner(window, icon_text="⚠", text="环境检测：异常（系统运行环境不满足）", show_help=True)
        return

    if pdf_export_ok is False:
        set_env_banner(window, icon_text="⚠", text="环境检测：异常（Word PDF 导出不可用）", show_help=True)
        return

    vtxt = ""
    try:
        if ver is not None:
            vtxt = format_word_version_for_user(ver)
    except Exception:
        vtxt = ""
    if pdf_export_ok is None:
        set_env_banner(window, icon_text="…", text="环境基本正常，Word PDF 导出未检测", show_help=False)
    elif vtxt:
        set_env_banner(window, icon_text="√", text=f"环境检测：环境正常（{vtxt}）", show_help=False)
    else:
        set_env_banner(window, icon_text="√", text="环境检测：环境正常", show_help=False)
