from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication


def install_qt_zh_translator(
    app: QApplication,
    *,
    logger: logging.Logger | None = None,
) -> bool:
    """Install Qt zh_CN translator for standard widget strings (context menus, etc.)."""

    if app is None:
        return False

    log = logger or logging.getLogger(__name__)
    try:
        translations_root = Path(
            QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        )
    except Exception as exc:
        log.warning("[qt_i18n] resolve translations path failed: %s", str(exc))
        return False

    candidates = ("qtbase_zh_CN.qm", "qt_zh_CN.qm")
    for filename in candidates:
        qm_path = translations_root / filename
        if not qm_path.exists():
            continue
        translator = QTranslator(app)
        try:
            if not translator.load(str(qm_path)):
                continue
            if not app.installTranslator(translator):
                continue
        except Exception:
            continue

        # Keep a strong reference to avoid GC.
        try:
            translators = getattr(app, "_qt_runtime_translators", None)
            if translators is None:
                translators = []
                setattr(app, "_qt_runtime_translators", translators)
            translators.append(translator)
        except Exception:
            pass
        log.info("[qt_i18n] installed translator: %s", str(qm_path))
        return True

    log.warning(
        "[qt_i18n] zh_CN Qt translator not found under: %s (candidates=%s)",
        str(translations_root),
        ",".join(candidates),
    )
    return False


__all__ = ["install_qt_zh_translator"]
