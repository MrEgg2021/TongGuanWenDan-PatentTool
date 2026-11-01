from PySide6.QtWidgets import QApplication

from core.app_preferences import get_env_check_cache, set_env_check_cache
from core.cnipa_preview.runtime import PreviewRuntimeError, get_default_runtime_manager
from gui.main_window.mixins.settings_env_registry import probe_word_env_from_registry
from gui.tools_ui_impl.preview_impl.legacy import (
    build_legacy_preview_base_url,
    ping_legacy_preview_service,
    read_legacy_preview_port,
)
from gui.tools_ui_impl.preview_impl.service_status import full_preview_status

from gui.main_window.mixins.settings_env_impl.ops_impl.banner_ops import update_env_banner_checking, update_env_banner_from_result
from gui.main_window.mixins.settings_env_impl.ops_impl.runtime_probe import _probe_windows_runtime_env
from gui.main_window.mixins.settings_env_impl.ops_impl.widget_resolve import _resolve_env_status_widgets
from gui.main_window.mixins.settings_env_impl.ops_impl.word_env_ops import build_hijack_help_text, format_word_version_for_user


def init_settings_env_section(window) -> None:
    cache = {}
    try:
        cache = get_env_check_cache() or {}
    except Exception:
        cache = {}

    try:
        preview_status = getattr(window, "settings_env_preview_status", None)
        if preview_status:
            cached_text = None
            try:
                cached_text = cache.get("preview_status")
            except Exception:
                cached_text = None
            if isinstance(cached_text, str) and cached_text.strip():
                txt = cached_text.strip()
                if txt.startswith("未检测（") or txt.startswith("未检测("):
                    txt = "未检测"
                preview_status.setText(txt)
                try:
                    preview_status.setToolTip(txt)
                except Exception:
                    pass
            else:
                preview_status.setText("未检测")
                try:
                    preview_status.setToolTip("未检测")
                except Exception:
                    pass
    except Exception:
        pass

    try:
        windows_status = getattr(window, "settings_env_windows_status", None)
        if windows_status:
            cached_text = None
            try:
                cached_text = cache.get("windows_status")
            except Exception:
                cached_text = None
            if isinstance(cached_text, str) and cached_text.strip():
                windows_status.setText(cached_text.strip())
            else:
                win_text = str(cache.get("windows_text") or "").strip() if isinstance(cache, dict) else ""
                if win_text:
                    windows_status.setText(win_text)
                else:
                    windows_status.setText("未检测")
    except Exception:
        pass

    try:
        runtime_status = getattr(window, "settings_env_runtime_status", None)
        if runtime_status:
            cached_text = None
            try:
                cached_text = cache.get("runtime_status")
            except Exception:
                cached_text = None
            if isinstance(cached_text, str) and cached_text.strip():
                runtime_status.setText(cached_text.strip())
            else:
                rhint = str(cache.get("runtime_hint") or "") if isinstance(cache, dict) else ""
                rok = True
                try:
                    if "runtime_ok" in cache:
                        rok = bool(cache.get("runtime_ok"))
                except Exception:
                    rok = True
                missing = []
                try:
                    missing = cache.get("runtime_missing_dlls") or []
                except Exception:
                    missing = []
                if not rok:
                    if missing:
                        runtime_status.setText("缺失：" + "，".join(missing))
                    elif rhint.strip():
                        runtime_status.setText(rhint.strip())
                    else:
                        runtime_status.setText("异常")
                else:
                    runtime_status.setText("正常")
    except Exception:
        pass

    try:
        word_status = getattr(window, "settings_env_word_status", None)
        if word_status:
            cached_text = None
            try:
                cached_text = cache.get("word_status")
            except Exception:
                cached_text = None
            if isinstance(cached_text, str) and cached_text.strip():
                txt = cached_text.strip()
                word_status.setText(format_word_version_for_user(txt))
            else:
                word_status.setText("未检测")
    except Exception:
        pass

    try:
        wps_status = getattr(window, "settings_env_wps_status", None)
        if wps_status:
            cached_text = None
            try:
                cached_text = cache.get("wps_status")
            except Exception:
                cached_text = None
            if isinstance(cached_text, str) and cached_text.strip():
                txt = cached_text.strip()
                if txt == "疑似被劫持":
                    txt = "被挟持"
                wps_status.setText(txt)
            else:
                wps_status.setText("未检测")
    except Exception:
        pass

    try:
        pdf_status = getattr(window, "settings_env_pdf_export_status", None)
        cached_pdf_status = str(cache.get("pdf_export_status") or "").strip()
        if pdf_status:
            pdf_status.setText(cached_pdf_status or "未检测")
            pdf_status.setToolTip(str(cache.get("pdf_export_error") or cached_pdf_status or "未检测"))
        cached_pdf_ok = cache.get("pdf_export_ok")
        window._env_pdf_export_ok = cached_pdf_ok if isinstance(cached_pdf_ok, bool) else None
        window._env_pdf_export_error = str(cache.get("pdf_export_error") or "")
    except Exception:
        pass

    try:
        wps_help = getattr(window, "settings_env_wps_help_button", None)
        if wps_help:
            wps_help.setEnabled(True)
            try:
                wps_status = getattr(window, "settings_env_wps_status", None)
                hijacked = bool(wps_status and str(wps_status.text()).strip() == "被挟持")
            except Exception:
                hijacked = False
            try:
                wps_help.setVisible(bool(hijacked))
            except Exception:
                pass
    except Exception:
        pass

    try:
        hint = ""
        try:
            hint = str(cache.get("wps_hint") or "")
        except Exception:
            hint = ""
        window._env_wps_hint_text = hint
    except Exception:
        pass

    try:
        rhint = ""
        try:
            rhint = str(cache.get("runtime_hint") or "")
        except Exception:
            rhint = ""
        window._env_runtime_hint_text = rhint
    except Exception:
        pass

    try:
        rok = True
        try:
            if "runtime_ok" in cache:
                rok = bool(cache.get("runtime_ok"))
        except Exception:
            rok = True
        window._env_runtime_ok = bool(rok)
    except Exception:
        pass

    try:
        if not str(getattr(window, "_env_wps_hint_text", "") or "").strip():
            window._env_wps_hint_text = build_hijack_help_text(hijacked=False, detail="")
    except Exception:
        pass
    try:
        window._env_wps_fallback_possible = False
    except Exception:
        pass


def run_env_check(window, *, update_ui: bool = True) -> dict:
    word_ok = False
    hijacked = False
    word_too_low = False
    word_error = ""

    try:
        runtime = _probe_windows_runtime_env() or {}
    except Exception:
        runtime = {}
    runtime_ok = bool(runtime.get("runtime_ok", True))
    runtime_hint = str(runtime.get("hint", "") or "")
    runtime_missing = runtime.get("missing_dlls") or []
    windows_text = str(runtime.get("windows_text", "") or "").strip()
    try:
        window._env_runtime_ok = bool(runtime_ok)
    except Exception:
        pass
    try:
        window._env_runtime_hint_text = runtime_hint
    except Exception:
        pass

    word_status, wps_status, preview_status, windows_status, runtime_status, pdf_export_status = _resolve_env_status_widgets(window)

    if update_ui:
        try:
            update_env_banner_checking(window)
            if word_status:
                word_status.setText("检测中...")
            if wps_status:
                wps_status.setText("检测中...")
            if windows_status:
                windows_status.setText("检测中...")
            if runtime_status:
                runtime_status.setText("检测中...")
            QApplication.processEvents()
        except Exception:
            pass

    ver = None
    try:
        probed = None
        try:
            if hasattr(window, "_probe_word_env_from_registry"):
                probed = window._probe_word_env_from_registry()
        except Exception:
            probed = None
        if not isinstance(probed, dict):
            probed = probe_word_env_from_registry()

        word_ok = bool(probed.get("word_ok", False))
        hijacked = bool(probed.get("hijacked", False))
        fallback_possible = bool(probed.get("fallback_possible", False))
        ver = probed.get("word_version")
        word_error = str(probed.get("word_error", "") or "")
        try:
            window._env_wps_fallback_possible = bool(fallback_possible)
        except Exception:
            pass

        hint = ""
        try:
            hint = str(probed.get("wps_hint", "") or "")
        except Exception:
            hint = ""
        if not hint.strip():
            try:
                server = str(probed.get("localserver32", "") or "")
                if hijacked:
                    base = build_hijack_help_text(hijacked=True, detail="")
                    if server.strip():
                        hint = f"当前 Word.Application 指向：\n{server}\n\n" + base
                    else:
                        hint = base
                else:
                    hint = build_hijack_help_text(hijacked=False, detail="")
            except Exception:
                hint = ""
        try:
            window._env_wps_hint_text = str(hint or "")
        except Exception:
            pass
    except Exception as e:
        word_ok = False
        hijacked = False
        fallback_possible = False
        ver = None
        word_error = str(e)
        try:
            window._env_wps_hint_text = build_hijack_help_text(hijacked=False, detail="")
        except Exception:
            pass
        try:
            window._env_wps_fallback_possible = False
        except Exception:
            pass

    try:
        if ver is not None and float(ver) < 12.0:
            word_too_low = True
    except Exception:
        word_too_low = False

    if update_ui:
        try:
            if word_status:
                if hijacked and fallback_possible:
                    if ver is not None:
                        word_status.setText(format_word_version_for_user(ver))
                    elif word_ok:
                        word_status.setText("未知")
                    else:
                        word_status.setText("未检测")
                elif hijacked:
                    word_status.setText("无法检测")
                elif ver is not None:
                    word_status.setText(format_word_version_for_user(ver))
                elif word_ok:
                    word_status.setText("未知")
                else:
                    word_status.setText("未检测")
            if wps_status:
                if hijacked and fallback_possible:
                    wps_status.setText("WPS兼容：可自动绕过")
                elif hijacked:
                    wps_status.setText("被挟持")
                elif word_ok:
                    wps_status.setText("正常")
                else:
                    wps_status.setText("未检测")
            if windows_status:
                if windows_text:
                    windows_status.setText(windows_text)
                else:
                    windows_status.setText("未知")
            if runtime_status:
                if runtime_ok:
                    runtime_status.setText("正常")
                else:
                    if runtime_missing:
                        runtime_status.setText("缺失：" + "，".join(runtime_missing))
                    elif runtime_hint.strip():
                        runtime_status.setText(runtime_hint.strip())
                    else:
                        runtime_status.setText("异常")
        except Exception:
            pass

    if update_ui:
        try:
            wps_help = getattr(window, "settings_env_wps_help_button", None)
            if wps_help:
                # 若被挟持或运行库异常，则可点击查看建议
                wps_help.setVisible(bool(hijacked or (not runtime_ok)))
        except Exception:
            pass
    legacy_port = read_legacy_preview_port()
    legacy_base_url = build_legacy_preview_base_url(legacy_port)
    legacy_text = f"正常（127.0.0.1:{legacy_port}）" if ping_legacy_preview_service(legacy_base_url) else f"未检测到服务（端口 {legacy_port}）"
    try:
        manager = get_default_runtime_manager()
        _, preview_text = full_preview_status(
            manager, warming=getattr(window, "_preview_warmup_thread", None) is not None,
        )
    except PreviewRuntimeError as exc:
        preview_text = f"预览组件不可用：{exc}"
    except OSError as exc:
        preview_text = f"无法读取预览组件：{exc}"
    try:
        if update_ui and preview_status:
            preview_status.setText(preview_text)
            try:
                preview_status.setToolTip(preview_text)
            except Exception:
                pass
    except Exception:
        pass
    try:
        legacy_status = getattr(window, "settings_env_legacy_preview_status", None)
        if update_ui and legacy_status:
            legacy_status.setText(legacy_text)
            legacy_status.setToolTip(legacy_text)
    except Exception:
        pass

    try:
        cache = {
            "word_status": str(word_status.text()) if word_status else "",
            "wps_status": str(wps_status.text()) if wps_status else "",
            "preview_status": str(preview_status.text()) if preview_status else "",
            "windows_status": str(windows_status.text()) if windows_status else "",
            "runtime_status": str(runtime_status.text()) if runtime_status else "",
            "pdf_export_status": str(pdf_export_status.text()) if pdf_export_status else "未检测",
            "pdf_export_ok": getattr(window, "_env_pdf_export_ok", None),
            "pdf_export_error": str(getattr(window, "_env_pdf_export_error", "") or ""),
            "wps_hint": str(getattr(window, "_env_wps_hint_text", "") or ""),
            "runtime_ok": bool(runtime_ok),
            "runtime_hint": str(runtime_hint or ""),
            "runtime_missing_dlls": list(runtime_missing) if isinstance(runtime_missing, list) else [],
            "windows_build": runtime.get("windows_build"),
            "windows_text": windows_text,
        }
        set_env_check_cache(cache)
    except Exception:
        pass

    try:
        update_env_banner_from_result(
            window,
            word_ok=word_ok,
            hijacked=bool(hijacked and not fallback_possible),
            word_too_low=word_too_low,
            ver=ver,
            runtime_ok=bool(runtime_ok),
            pdf_export_ok=getattr(window, "_env_pdf_export_ok", None),
        )
    except Exception:
        pass

    return {
        "word_ok": bool(word_ok),
        "hijacked": bool(hijacked),
        "word_too_low": bool(word_too_low),
        "word_error": str(word_error or ""),
        "word_version": ver,
        "runtime_ok": bool(runtime_ok),
        "runtime_hint": str(runtime_hint or ""),
        "pdf_export_ok": getattr(window, "_env_pdf_export_ok", None),
    }


def update_pdf_export_check_result(
    window,
    *,
    pdf_export_ok: bool | None,
    pdf_export_error: str = "",
    status_text: str,
    base_result: dict,
) -> None:
    status = getattr(window, "settings_env_pdf_export_status", None)
    if status is not None:
        status.setText(str(status_text))
        try:
            status.setToolTip(str(pdf_export_error or status_text))
        except Exception:
            pass

    window._env_pdf_export_ok = pdf_export_ok if isinstance(pdf_export_ok, bool) else None
    window._env_pdf_export_error = str(pdf_export_error or "")

    try:
        cache = get_env_check_cache() or {}
        cache.update(
            {
                "pdf_export_status": str(status_text),
                "pdf_export_ok": window._env_pdf_export_ok,
                "pdf_export_error": window._env_pdf_export_error,
            }
        )
        set_env_check_cache(cache)
    except Exception:
        pass

    update_env_banner_from_result(
        window,
        word_ok=bool(base_result.get("word_ok", False)),
        hijacked=bool(base_result.get("hijacked", False)),
        word_too_low=bool(base_result.get("word_too_low", False)),
        ver=base_result.get("word_version"),
        runtime_ok=bool(base_result.get("runtime_ok", True)),
        pdf_export_ok=window._env_pdf_export_ok,
    )
