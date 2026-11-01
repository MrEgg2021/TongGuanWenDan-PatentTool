from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QSplitter

from core.user_prefs import get_pref, set_pref

SPLITTER_DEBOUNCE_MS = 300
SPLITTER_MIN_SIZE = 48

SINGLE_MAIN_SPLITTER_KEY = "layout.single.main_splitter_sizes.v1"
BATCH_MAIN_SPLITTER_KEY = "layout.batch.main_splitter_sizes.v1"
OFFICIAL_DOCS_TASK_VERTICAL_SPLITTER_KEY = "layout.official_docs.task_vertical_splitter_sizes.v1"
PREVIEW_TOP_BOTTOM_SPLITTER_KEY = "layout.preview.top_bottom_splitter_sizes.v1"
PREVIEW_LEFT_RIGHT_SPLITTER_KEY = "layout.preview.left_right_splitter_sizes.v1"
WORKFLOW_HOME_SPLITTER_SINGLE_KEY = "layout.workflow.home_splitter_single_sizes.v1"
WORKFLOW_HOME_SPLITTER_BATCH_KEY = "layout.workflow.home_splitter_batch_sizes.v1"
WORKFLOW_FOOTER_SPLITTER_SINGLE_KEY = "layout.workflow.footer_splitter_single_sizes.v1"
WORKFLOW_FOOTER_SPLITTER_BATCH_KEY = "layout.workflow.footer_splitter_batch_sizes.v1"
RESPONSE_PROCESSING_SPLITTER_KEY = "layout.response.processing_splitter_sizes.v1"
CORRECTION_PROCESSING_SPLITTER_KEY = "layout.correction.processing_splitter_sizes.v1"
ACTIVE_RESPONSE_PROCESSING_SPLITTER_KEY = "layout.active_response.processing_splitter_sizes.v1"
ACTIVE_CORRECTION_PROCESSING_SPLITTER_KEY = "layout.active_correction.processing_splitter_sizes.v1"
RESPONSE_PROCESSING_UPPER_HEIGHT_KEY = "layout.response.processing_upper_height.v1"
CORRECTION_PROCESSING_UPPER_HEIGHT_KEY = "layout.correction.processing_upper_height.v1"
ACTIVE_RESPONSE_PROCESSING_UPPER_HEIGHT_KEY = "layout.active_response.processing_upper_height.v1"
ACTIVE_CORRECTION_PROCESSING_UPPER_HEIGHT_KEY = "layout.active_correction.processing_upper_height.v1"


def _normalize_sizes(raw: Any, expected_count: int) -> list[int] | None:
    if not isinstance(raw, (list, tuple)):
        return None
    values: list[int] = []
    for item in list(raw):
        try:
            value = int(item)
        except Exception:
            return None
        values.append(max(SPLITTER_MIN_SIZE, value))
    if len(values) != int(expected_count):
        return None
    return values


def _normalize_height(raw: Any, minimum: int = SPLITTER_MIN_SIZE) -> int | None:
    try:
        value = int(raw)
    except Exception:
        return None
    return max(int(minimum), value)


def _restore_splitter_sizes(splitter: QSplitter, key: str, default_sizes: list[int]) -> None:
    expected_count = len(default_sizes)
    raw = get_pref(key, None)
    target = _normalize_sizes(raw, expected_count)
    if target is None:
        target = list(default_sizes)
    try:
        splitter.setSizes(target)
    except Exception:
        pass


def _persist_splitter_sizes(splitter: QSplitter, key: str, default_sizes: list[int]) -> None:
    expected_count = len(default_sizes)
    try:
        current_sizes = list(splitter.sizes() or [])
    except Exception:
        current_sizes = []
    normalized = _normalize_sizes(current_sizes, expected_count)
    if normalized is None:
        return
    try:
        set_pref(key, list(normalized))
    except Exception:
        pass


def _bind_splitter(window, attr_name: str, key: str, default_sizes: list[int]) -> None:
    splitter = getattr(window, attr_name, None)
    if splitter is None or (not isinstance(splitter, QSplitter)):
        return

    _restore_splitter_sizes(splitter, key, default_sizes)

    timer = QTimer(window)
    timer.setSingleShot(True)
    timer.setInterval(SPLITTER_DEBOUNCE_MS)
    timer.timeout.connect(lambda: _persist_splitter_sizes(splitter, key, default_sizes))

    def _on_moved(_pos: int, _index: int) -> None:
        try:
            timer.start()
        except Exception:
            pass

    try:
        splitter.splitterMoved.connect(_on_moved)
    except Exception:
        pass

    timers = getattr(window, "_layout_splitter_pref_timers", None)
    if not isinstance(timers, dict):
        timers = {}
        window._layout_splitter_pref_timers = timers
    timers[attr_name] = timer


def _restore_response_correction_height(pane, key: str, default_height: int, legacy_splitter_key: str) -> None:
    target_height = _normalize_height(get_pref(key, None))
    if target_height is None:
        legacy_sizes = _normalize_sizes(get_pref(legacy_splitter_key, None), 2)
        if legacy_sizes is not None:
            target_height = int(legacy_sizes[0])
    if target_height is None:
        target_height = int(default_height)
    try:
        pane.set_upper_content_height(int(target_height))
    except Exception:
        pass


def _persist_response_correction_height(pane, key: str, default_height: int) -> None:
    try:
        raw_height = pane.upper_content_height()
    except Exception:
        raw_height = default_height
    target_height = _normalize_height(raw_height)
    if target_height is None:
        return
    try:
        set_pref(key, int(target_height))
    except Exception:
        pass


def _bind_response_correction_height(window, attr_name: str, key: str, default_height: int, legacy_splitter_key: str) -> None:
    pane = getattr(window, attr_name, None)
    if pane is None or (not hasattr(pane, "set_upper_content_height")) or (not hasattr(pane, "upper_content_height")):
        return

    _restore_response_correction_height(pane, key, default_height, legacy_splitter_key)

    timer = QTimer(window)
    timer.setSingleShot(True)
    timer.setInterval(SPLITTER_DEBOUNCE_MS)
    timer.timeout.connect(lambda: _persist_response_correction_height(pane, key, default_height))

    def _on_height_changed(_height: int) -> None:
        try:
            timer.start()
        except Exception:
            pass

    try:
        pane.upperHeightChanged.connect(_on_height_changed)
    except Exception:
        pass

    timers = getattr(window, "_layout_splitter_pref_timers", None)
    if not isinstance(timers, dict):
        timers = {}
        window._layout_splitter_pref_timers = timers
    timers[attr_name] = timer


def bind_layout_splitter_prefs(window) -> None:
    _bind_splitter(window, "single_main_splitter", SINGLE_MAIN_SPLITTER_KEY, [7, 3])
    _bind_splitter(window, "batch_main_splitter", BATCH_MAIN_SPLITTER_KEY, [3, 7])
    _bind_splitter(
        window,
        "official_docs_task_vertical_splitter",
        OFFICIAL_DOCS_TASK_VERTICAL_SPLITTER_KEY,
        [2, 8],
    )
    _bind_splitter(window, "preview_main_vertical_splitter", PREVIEW_TOP_BOTTOM_SPLITTER_KEY, [3, 7])
    _bind_splitter(window, "preview_main_horizontal_splitter", PREVIEW_LEFT_RIGHT_SPLITTER_KEY, [2, 1])
    _bind_response_correction_height(window, "response_processing_pane", RESPONSE_PROCESSING_UPPER_HEIGHT_KEY, 520, RESPONSE_PROCESSING_SPLITTER_KEY)
    _bind_response_correction_height(window, "correction_processing_pane", CORRECTION_PROCESSING_UPPER_HEIGHT_KEY, 560, CORRECTION_PROCESSING_SPLITTER_KEY)
    _bind_response_correction_height(window, "active_response_processing_pane", ACTIVE_RESPONSE_PROCESSING_UPPER_HEIGHT_KEY, 520, ACTIVE_RESPONSE_PROCESSING_SPLITTER_KEY)
    _bind_response_correction_height(window, "active_correction_processing_pane", ACTIVE_CORRECTION_PROCESSING_UPPER_HEIGHT_KEY, 560, ACTIVE_CORRECTION_PROCESSING_SPLITTER_KEY)


def _workflow_home_mode(window) -> str:
    try:
        mode = str(getattr(window, "_processing_mode", "single") or "single")
    except Exception:
        mode = "single"
    return "batch" if mode == "batch" else "single"


def _workflow_home_key_and_default(window) -> tuple[str, list[int]]:
    if _workflow_home_mode(window) == "batch":
        return WORKFLOW_HOME_SPLITTER_BATCH_KEY, [8, 2]
    return WORKFLOW_HOME_SPLITTER_SINGLE_KEY, [7, 3]


def _workflow_footer_key_and_default(window) -> tuple[str, list[int]]:
    if _workflow_home_mode(window) == "batch":
        return WORKFLOW_FOOTER_SPLITTER_BATCH_KEY, [9, 1]
    return WORKFLOW_FOOTER_SPLITTER_SINGLE_KEY, [8, 2]


def restore_workflow_home_splitter_for_mode(window) -> None:
    splitter = getattr(window, "workflow_home_splitter", None)
    if splitter is None or (not isinstance(splitter, QSplitter)):
        return
    key, default_sizes = _workflow_home_key_and_default(window)
    _restore_splitter_sizes(splitter, key, default_sizes)


def _persist_workflow_home_splitter_for_mode(window) -> None:
    splitter = getattr(window, "workflow_home_splitter", None)
    if splitter is None or (not isinstance(splitter, QSplitter)):
        return
    key, default_sizes = _workflow_home_key_and_default(window)
    _persist_splitter_sizes(splitter, key, default_sizes)


def restore_workflow_footer_splitter_for_mode(window) -> None:
    splitter = getattr(window, "workflow_footer_splitter", None)
    if splitter is None or (not isinstance(splitter, QSplitter)):
        return
    key, default_sizes = _workflow_footer_key_and_default(window)
    _restore_splitter_sizes(splitter, key, default_sizes)


def _persist_workflow_footer_splitter_for_mode(window) -> None:
    splitter = getattr(window, "workflow_footer_splitter", None)
    if splitter is None or (not isinstance(splitter, QSplitter)):
        return
    key, default_sizes = _workflow_footer_key_and_default(window)
    _persist_splitter_sizes(splitter, key, default_sizes)


def bind_workflow_home_splitter_prefs(window) -> None:
    splitter = getattr(window, "workflow_home_splitter", None)
    if splitter is None or (not isinstance(splitter, QSplitter)):
        return

    restore_workflow_home_splitter_for_mode(window)

    timer = QTimer(window)
    timer.setSingleShot(True)
    timer.setInterval(SPLITTER_DEBOUNCE_MS)
    timer.timeout.connect(lambda: _persist_workflow_home_splitter_for_mode(window))

    def _on_moved(_pos: int, _index: int) -> None:
        try:
            timer.start()
        except Exception:
            pass

    try:
        splitter.splitterMoved.connect(_on_moved)
    except Exception:
        pass

    timers = getattr(window, "_layout_splitter_pref_timers", None)
    if not isinstance(timers, dict):
        timers = {}
        window._layout_splitter_pref_timers = timers
    timers["workflow_home_splitter"] = timer


def bind_workflow_footer_splitter_prefs(window) -> None:
    splitter = getattr(window, "workflow_footer_splitter", None)
    if splitter is None or (not isinstance(splitter, QSplitter)):
        return

    restore_workflow_footer_splitter_for_mode(window)

    timer = QTimer(window)
    timer.setSingleShot(True)
    timer.setInterval(SPLITTER_DEBOUNCE_MS)
    timer.timeout.connect(lambda: _persist_workflow_footer_splitter_for_mode(window))

    def _on_moved(_pos: int, _index: int) -> None:
        try:
            timer.start()
        except Exception:
            pass

    try:
        splitter.splitterMoved.connect(_on_moved)
    except Exception:
        pass

    timers = getattr(window, "_layout_splitter_pref_timers", None)
    if not isinstance(timers, dict):
        timers = {}
        window._layout_splitter_pref_timers = timers
    timers["workflow_footer_splitter"] = timer


__all__ = [
    "bind_layout_splitter_prefs",
    "bind_workflow_home_splitter_prefs",
    "bind_workflow_footer_splitter_prefs",
    "restore_workflow_home_splitter_for_mode",
    "restore_workflow_footer_splitter_for_mode",
    "SINGLE_MAIN_SPLITTER_KEY",
    "BATCH_MAIN_SPLITTER_KEY",
    "OFFICIAL_DOCS_TASK_VERTICAL_SPLITTER_KEY",
    "PREVIEW_TOP_BOTTOM_SPLITTER_KEY",
    "PREVIEW_LEFT_RIGHT_SPLITTER_KEY",
    "WORKFLOW_HOME_SPLITTER_SINGLE_KEY",
    "WORKFLOW_HOME_SPLITTER_BATCH_KEY",
    "WORKFLOW_FOOTER_SPLITTER_SINGLE_KEY",
    "WORKFLOW_FOOTER_SPLITTER_BATCH_KEY",
    "RESPONSE_PROCESSING_SPLITTER_KEY",
    "CORRECTION_PROCESSING_SPLITTER_KEY",
    "ACTIVE_RESPONSE_PROCESSING_SPLITTER_KEY",
    "ACTIVE_CORRECTION_PROCESSING_SPLITTER_KEY",
    "RESPONSE_PROCESSING_UPPER_HEIGHT_KEY",
    "CORRECTION_PROCESSING_UPPER_HEIGHT_KEY",
    "ACTIVE_RESPONSE_PROCESSING_UPPER_HEIGHT_KEY",
    "ACTIVE_CORRECTION_PROCESSING_UPPER_HEIGHT_KEY",
]
