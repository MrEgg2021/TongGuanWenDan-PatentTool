from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QAbstractScrollArea, QComboBox


class ComboWheelBlocker(QObject):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._targets: set[QObject] = set()
        self._strict_scroll_areas: list[tuple[QAbstractScrollArea, QObject | None]] = []
        self._app_filter_installed: bool = False

    def _ensure_app_filter(self) -> None:
        if self._app_filter_installed:
            return
        app = None
        try:
            app = QApplication.instance()
        except Exception:
            app = None
        if app is None:
            return
        try:
            app.installEventFilter(self)
            self._app_filter_installed = True
        except Exception:
            pass

    def _is_descendant_of(self, obj: QObject | None, root: QObject | None) -> bool:
        if obj is None or root is None:
            return False
        node = obj
        for _ in range(40):
            if node is None:
                return False
            if node is root:
                return True
            try:
                node = node.parent()
            except Exception:
                return False
        return False

    def register_strict_scroll_area(self, scroll_area: QAbstractScrollArea | None) -> None:
        if scroll_area is None:
            return
        try:
            vbar = scroll_area.verticalScrollBar()
        except Exception:
            vbar = None
        try:
            self._strict_scroll_areas.append((scroll_area, vbar))
        except Exception:
            pass
        self._ensure_app_filter()

    def register_combo(self, combo: QComboBox | None) -> None:
        if combo is None:
            return

        try:
            combo.installEventFilter(self)
            self._targets.add(combo)
        except Exception:
            pass

        try:
            view = combo.view()
            if view is not None:
                try:
                    view.installEventFilter(self)
                    self._targets.add(view)
                except Exception:
                    pass

                try:
                    vp = view.viewport()
                    if vp is not None:
                        vp.installEventFilter(self)
                        self._targets.add(vp)
                except Exception:
                    pass
        except Exception:
            pass

    def register_widget(self, widget: QObject | None) -> None:
        if widget is None:
            return
        try:
            widget.installEventFilter(self)
            self._targets.add(widget)
        except Exception:
            pass

    def eventFilter(self, obj, event):  # type: ignore[override]
        try:
            if event.type() == QEvent.Wheel:
                for scroll_area, vbar in self._strict_scroll_areas:
                    if self._is_descendant_of(obj, vbar):
                        return False
                    if self._is_descendant_of(obj, scroll_area):
                        return True
            if event.type() == QEvent.Wheel and obj in self._targets:
                return True
        except Exception:
            pass
        return super().eventFilter(obj, event)
