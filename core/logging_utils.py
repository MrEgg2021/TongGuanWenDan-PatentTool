from __future__ import annotations

import logging
import os
import sys
import threading
from typing import TextIO

from core.paths_utils import get_app_dir, get_user_data_dir

# Keep behavior aligned with legacy main.py
IS_FROZEN = getattr(sys, "frozen", False)
_STDIO_CAPTURE_INSTALLED = False
_CURRENT_LOG_PATH = ""


class _MirrorStream:
    """Mirror writes to original stream and conversion.log.

    This captures non-logging output (Qt/PySide stderr, print, raw trace text)
    into conversion.log so users can still inspect failures after console closes.
    """

    def __init__(self, original: TextIO, mirror_file: TextIO):
        self._original = original
        self._mirror_file = mirror_file
        self._lock = threading.Lock()
        self.encoding = getattr(original, "encoding", "utf-8")

    def write(self, data):
        text = str(data or "")
        if not text:
            return 0
        with self._lock:
            try:
                self._original.write(text)
            except Exception:
                pass
            try:
                self._mirror_file.write(text)
                self._mirror_file.flush()
            except Exception:
                pass
        return len(text)

    def flush(self):
        with self._lock:
            try:
                self._original.flush()
            except Exception:
                pass
            try:
                self._mirror_file.flush()
            except Exception:
                pass

    def isatty(self):
        try:
            return bool(self._original.isatty())
        except Exception:
            return False

    def fileno(self):
        return self._original.fileno()

    def __getattr__(self, item):
        return getattr(self._original, item)


def _resolve_log_path() -> str:
    candidates: list[str] = []
    try:
        candidates.append(os.path.join(get_app_dir(), "conversion.log"))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(get_user_data_dir(), "conversion.log"))
    except Exception:
        pass

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parent = os.path.dirname(candidate)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(candidate, mode="a", encoding="utf-8"):
                pass
            return candidate
        except Exception:
            continue

    try:
        return os.path.join(get_app_dir(), "conversion.log")
    except Exception:
        return "conversion.log"


def _install_stdio_capture(log_path: str) -> None:
    """Capture raw stderr/stdout text into conversion.log."""

    global _STDIO_CAPTURE_INSTALLED
    if _STDIO_CAPTURE_INSTALLED:
        return
    try:
        mirror_file = open(log_path, mode="a", encoding="utf-8")
    except Exception:
        return

    try:
        sys.stdout = _MirrorStream(sys.stdout, mirror_file)
    except Exception:
        pass
    try:
        sys.stderr = _MirrorStream(sys.stderr, mirror_file)
    except Exception:
        pass

    _STDIO_CAPTURE_INSTALLED = True


def _install_global_exception_hooks(logger_obj: logging.Logger) -> None:
    """Ensure uncaught Python exceptions are logged into conversion.log."""

    prev_excepthook = sys.excepthook

    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            logger_obj.error(
                "[UNCAUGHT] Unhandled exception",
                exc_info=(exc_type, exc_value, exc_tb),
            )
        except Exception:
            pass
        try:
            prev_excepthook(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _excepthook

    if hasattr(threading, "excepthook"):
        prev_thread_hook = threading.excepthook

        def _thread_excepthook(args):
            try:
                logger_obj.error(
                    "[UNCAUGHT] Unhandled thread exception",
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                )
            except Exception:
                pass
            try:
                prev_thread_hook(args)
            except Exception:
                pass

        threading.excepthook = _thread_excepthook


def _init_logger() -> logging.Logger:
    """Initialize global logger."""
    global _CURRENT_LOG_PATH

    # 源码与 EXE 都写本地日志，供用户自行排查；不上传任何日志。
    handlers: list[logging.Handler] = []
    if not IS_FROZEN:
        handlers.append(logging.StreamHandler())

    log_path = _resolve_log_path()

    if log_path:
        try:
            handlers.append(logging.FileHandler(log_path, mode="w", encoding="utf-8"))
            _CURRENT_LOG_PATH = log_path
        except Exception:
            log_path = ""
            _CURRENT_LOG_PATH = ""
    else:
        _CURRENT_LOG_PATH = ""

    level = logging.DEBUG

    if not handlers:
        handlers = [logging.NullHandler()]

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )
    logger_obj = logging.getLogger("main")
    logger_obj.setLevel(level)

    if log_path:
        try:
            _install_stdio_capture(log_path)
        except Exception:
            pass
    try:
        _install_global_exception_hooks(logger_obj)
    except Exception:
        pass
    try:
        logger_obj.info(
            "[DIAGNOSTIC_SESSION_START] frozen=%s file_log=%s log_level=%s",
            bool(IS_FROZEN),
            bool(log_path),
            logging.getLevelName(level),
        )
    except Exception:
        pass

    return logger_obj


# Shared global logger
logger: logging.Logger = _init_logger()


def get_conversion_log_path() -> str:
    if _CURRENT_LOG_PATH:
        return _CURRENT_LOG_PATH
    return ""


def swallow_exception(context: str = "", exc: BaseException | None = None) -> None:
    """Log intentionally swallowed exceptions for troubleshooting."""
    if exc is None:
        import sys as _sys

        exc = _sys.exc_info()[1]

    if exc is None:
        return

    msg = (
        f"[SWALLOWED] {context}: {type(exc).__name__}: {exc}"
        if context
        else f"[SWALLOWED] {type(exc).__name__}: {exc}"
    )
    logger.debug(msg)
