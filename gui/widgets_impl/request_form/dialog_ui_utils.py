from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QWidget


def mark_field_label(lbl: QLabel) -> None:
    try:
        lbl.setProperty("role", "label")
        lbl.setProperty("emphasis", True)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    except Exception:
        pass


_SAMPLE_PATTERN_MAP = {
    "digits": "0",
    "cjk": "汉",
    "upper": "A",
    "lower": "a",
    "alnum": "A0",
    "alnum_upper": "A0",
    "alnum_symbol": "A0@",
    "cjk_alnum": "汉A0",
    "cjk_digit": "汉0",
}


@dataclass(frozen=True)
class AdaptiveWidthSpec:
    sample_chars: int
    max_chars: int
    kind: str
    extra: int | None = None
    min_width: int = 40


def build_sample_text(kind: str, length: int) -> str:
    pattern = _SAMPLE_PATTERN_MAP.get(kind, "0")
    try:
        length = max(0, int(length))
    except Exception:
        length = 0
    if length <= 0:
        return ""
    if len(pattern) == 1:
        return pattern * length
    times = (length + len(pattern) - 1) // len(pattern)
    return (pattern * times)[:length]


def _default_extra_for_widget(widget: QWidget) -> int:
    if isinstance(widget, QComboBox):
        return 56
    return 26


def _calc_width_by_text(widget: QWidget, text: str, extra: int, min_width: int) -> int:
    try:
        fm = QFontMetrics(widget.font())
        w = fm.horizontalAdvance(text)
        return int(max(min_width, w + extra))
    except Exception:
        return int(max(min_width, len(text) * 9 + extra))


def _get_widget_text(widget: QWidget) -> str:
    if isinstance(widget, QComboBox):
        try:
            if widget.isEditable():
                line_edit = widget.lineEdit()
                if line_edit is not None:
                    return line_edit.text()
        except Exception:
            pass
        try:
            return widget.currentText()
        except Exception:
            return ""
    if isinstance(widget, QLineEdit):
        try:
            return widget.text()
        except Exception:
            return ""
    try:
        return str(widget.text())
    except Exception:
        return ""


def calc_adaptive_width(widget: QWidget, spec: AdaptiveWidthSpec, text: str | None = None) -> int:
    sample_text = build_sample_text(spec.kind, spec.sample_chars)
    max_text = build_sample_text(spec.kind, spec.max_chars)
    if text is None:
        current_text = _get_widget_text(widget)
    else:
        current_text = str(text)
    if not current_text:
        current_text = sample_text
    extra = spec.extra if spec.extra is not None else _default_extra_for_widget(widget)
    min_w = _calc_width_by_text(widget, sample_text, extra, spec.min_width)
    max_w = _calc_width_by_text(widget, max_text, extra, spec.min_width)
    cur_w = _calc_width_by_text(widget, current_text, extra, spec.min_width)
    return int(max(min_w, min(max_w, cur_w)))


class _AdaptiveWidthFilter(QObject):
    def __init__(self, update_fn, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._update_fn = update_fn

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.FocusIn, QEvent.FocusOut):
            try:
                self._update_fn()
            except Exception:
                pass
        return False


def _install_adaptive_filter(widget: QWidget, update_fn) -> None:
    try:
        filt = _AdaptiveWidthFilter(update_fn, widget)
        widget.installEventFilter(filt)
        setattr(widget, "_adaptive_width_filter", filt)
    except Exception:
        pass


def bind_adaptive_width(widget: QWidget, spec: AdaptiveWidthSpec) -> None:
    if widget is None:
        return

    def _apply() -> None:
        try:
            width = calc_adaptive_width(widget, spec)
            widget.setMinimumWidth(int(width))
        except Exception:
            pass

    _apply()

    try:
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _t: _apply())
            widget.editingFinished.connect(lambda: _apply())
        elif isinstance(widget, QComboBox):
            try:
                widget.currentTextChanged.connect(lambda _t: _apply())
            except Exception:
                pass
            try:
                if widget.isEditable():
                    widget.editTextChanged.connect(lambda _t: _apply())
                    line_edit = widget.lineEdit()
                    if line_edit is not None:
                        line_edit.textEdited.connect(lambda _t: _apply())
            except Exception:
                pass
        else:
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(lambda _t: _apply())
    except Exception:
        pass

    _install_adaptive_filter(widget, _apply)
    if isinstance(widget, QComboBox):
        try:
            line_edit = widget.lineEdit()
        except Exception:
            line_edit = None
        if line_edit is not None:
            _install_adaptive_filter(line_edit, _apply)
