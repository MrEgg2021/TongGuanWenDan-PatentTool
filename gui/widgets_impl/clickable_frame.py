from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame


class ClickableFrame(QFrame):
    clicked = Signal()

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
