from PySide6.QtCore import Qt, Signal, QObject, QEvent
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QListWidget, QWidget


class SingleFileDropWidget(QWidget):
    """支持拖拽本地文件的轻量容器，拖入/拖出时切换 dragActive 样式属性。"""

    filesDropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drag_active = False
        self.setProperty("dragActive", False)
        self.setProperty("class", "DropZone")


    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if self._has_local_files(event.mimeData()):
            event.acceptProposedAction()
            self._set_drag_state(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_drag_state(False)
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if self._has_local_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        paths = self._extract_local_paths(event)
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()
        self._set_drag_state(False)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        try:
            if event is not None and event.button() == Qt.LeftButton:
                self.clicked.emit()
        except Exception:
            pass
        try:
            super().mouseReleaseEvent(event)
        except Exception:
            pass

    def _has_local_files(self, mime) -> bool:
        if not mime or not mime.hasUrls():
            return False
        for url in mime.urls():
            if url.isLocalFile():
                return True
        return False

    def _extract_local_paths(self, event: QDropEvent) -> list[str]:
        paths: list[str] = []
        mime = event.mimeData()
        if not mime or not mime.hasUrls():
            return paths
        for url in mime.urls():
            if url.isLocalFile():
                local_path = url.toLocalFile().strip()
                if local_path:
                    paths.append(local_path)
        return paths

    def _set_drag_state(self, active: bool) -> None:
        if self._drag_active == active:
            return
        self._drag_active = active
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class BatchFileListWidget(QListWidget):
    """支持拖拽文件列表的 QListWidget，专用于批量模式。"""

    pathsDropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drag_active = False
        self.setProperty("dragActive", False)
        self.setProperty("class", "DropZone")


    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if self._has_local_files(event.mimeData()):
            event.acceptProposedAction()
            self._set_drag_state(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_drag_state(False)
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if self._has_local_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        paths = self._extract_local_paths(event)
        if paths:
            self.pathsDropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()
        self._set_drag_state(False)

    def _has_local_files(self, mime) -> bool:
        if not mime or not mime.hasUrls():
            return False
        for url in mime.urls():
            if url.isLocalFile():
                return True
        return False

    def _extract_local_paths(self, event: QDropEvent) -> list[str]:
        paths: list[str] = []
        mime = event.mimeData()
        if not mime or not mime.hasUrls():
            return paths
        for url in mime.urls():
            if url.isLocalFile():
                local_path = url.toLocalFile().strip()
                if local_path:
                    paths.append(local_path)
        return paths

    def _set_drag_state(self, active: bool) -> None:
        if self._drag_active == active:
            return
        self._drag_active = active
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class DropCardProxy(QObject):
    """让外层卡片在整块区域支持拖拽，并把 drop 事件转发给既有 drop widget。"""

    def __init__(self, card: QWidget, drop_widget: QWidget) -> None:
        super().__init__(card)
        self._card = card
        self._drop_widget = drop_widget
        self._signal_name = self._resolve_signal_name(drop_widget)
        try:
            self._card.setAcceptDrops(True)
            self._card.installEventFilter(self)
        except Exception:
            pass

    def eventFilter(self, watched, event):  # type: ignore[override]
        if watched is not self._card or event is None:
            return super().eventFilter(watched, event)

        et = event.type()
        if et in (QEvent.DragEnter, QEvent.DragMove):
            mime = event.mimeData() if hasattr(event, "mimeData") else None
            if self._has_local_files(mime):
                event.acceptProposedAction()
                self._set_drag_state(True)
            else:
                event.ignore()
                self._set_drag_state(False)
            return True

        if et == QEvent.DragLeave:
            self._set_drag_state(False)
            return False

        if et == QEvent.Drop:
            paths = self._extract_local_paths(event)
            if paths:
                self._emit_paths(paths)
                event.acceptProposedAction()
            else:
                event.ignore()
            self._set_drag_state(False)
            return True

        return super().eventFilter(watched, event)

    @staticmethod
    def _resolve_signal_name(drop_widget: QWidget) -> str:
        if hasattr(drop_widget, "filesDropped"):
            return "filesDropped"
        if hasattr(drop_widget, "pathsDropped"):
            return "pathsDropped"
        return ""

    @staticmethod
    def _has_local_files(mime) -> bool:
        if not mime or not mime.hasUrls():
            return False
        for url in mime.urls():
            if url.isLocalFile():
                return True
        return False

    @staticmethod
    def _extract_local_paths(event) -> list[str]:
        paths: list[str] = []
        mime = event.mimeData() if hasattr(event, "mimeData") else None
        if not mime or not mime.hasUrls():
            return paths
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            local_path = str(url.toLocalFile() or "").strip()
            if local_path:
                paths.append(local_path)
        return paths

    def _emit_paths(self, paths: list[str]) -> None:
        if not paths or not self._signal_name:
            return
        signal = getattr(self._drop_widget, self._signal_name, None)
        if signal is None:
            return
        try:
            signal.emit(list(paths))
        except Exception:
            pass

    def _set_drag_state(self, active: bool) -> None:
        self._set_widget_drag_state(self._card, active)
        self._set_widget_drag_state(self._drop_widget, active)

    @staticmethod
    def _set_widget_drag_state(widget: QWidget | None, active: bool) -> None:
        if widget is None:
            return
        try:
            old = bool(widget.property("dragActive"))
        except Exception:
            old = False
        if old == bool(active):
            return
        try:
            widget.setProperty("dragActive", bool(active))
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        except Exception:
            pass


def install_drop_card_proxy(card: QWidget, drop_widget: QWidget) -> DropCardProxy:
    return DropCardProxy(card, drop_widget)
