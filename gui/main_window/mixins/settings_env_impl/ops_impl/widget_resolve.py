from PySide6.QtCore import QObject


def _resolve_env_status_widgets(window):
    word_status = getattr(window, "settings_env_word_status", None)
    wps_status = getattr(window, "settings_env_wps_status", None)
    preview_status = getattr(window, "settings_env_preview_status", None)
    windows_status = getattr(window, "settings_env_windows_status", None)
    runtime_status = getattr(window, "settings_env_runtime_status", None)
    pdf_export_status = getattr(window, "settings_env_pdf_export_status", None)

    if (
        word_status is not None
        and wps_status is not None
        and preview_status is not None
        and windows_status is not None
        and runtime_status is not None
        and pdf_export_status is not None
    ):
        return word_status, wps_status, preview_status, windows_status, runtime_status, pdf_export_status

    page = getattr(window, "settings_page", None)
    if page is None:
        page = getattr(window, "_settings_page", None)

    if page is not None:
        try:
            if word_status is None:
                word_status = page.findChild(QObject, "settingsEnvWordStatus")
            if wps_status is None:
                wps_status = page.findChild(QObject, "settingsEnvWpsStatus")
            if preview_status is None:
                preview_status = page.findChild(QObject, "settingsEnvPreviewStatus")
            if windows_status is None:
                windows_status = page.findChild(QObject, "settingsEnvWindowsStatus")
            if runtime_status is None:
                runtime_status = page.findChild(QObject, "settingsEnvRuntimeStatus")
            if pdf_export_status is None:
                pdf_export_status = page.findChild(QObject, "settingsEnvPdfExportStatus")
        except Exception:
            pass

    try:
        if word_status is not None:
            window.settings_env_word_status = word_status
    except Exception:
        pass
    try:
        if wps_status is not None:
            window.settings_env_wps_status = wps_status
    except Exception:
        pass
    try:
        if preview_status is not None:
            window.settings_env_preview_status = preview_status
    except Exception:
        pass
    try:
        if windows_status is not None:
            window.settings_env_windows_status = windows_status
    except Exception:
        pass
    try:
        if runtime_status is not None:
            window.settings_env_runtime_status = runtime_status
    except Exception:
        pass

    try:
        if pdf_export_status is not None:
            window.settings_env_pdf_export_status = pdf_export_status
    except Exception:
        pass

    return word_status, wps_status, preview_status, windows_status, runtime_status, pdf_export_status
