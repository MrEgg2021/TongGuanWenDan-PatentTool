from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElideLabel(QLabel):
    def __init__(self, text: str = "", parent=None, *, elide_mode=Qt.ElideMiddle) -> None:
        super().__init__(parent)
        self._full_text = ""
        self._elide_mode = elide_mode
        try:
            self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.setMinimumWidth(0)
        except Exception:
            pass
        self.setText(text)

    def fullText(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = text or ""
        try:
            self.setToolTip(self._full_text)
        except Exception:
            pass
        self._update_elide()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        try:
            w = self.contentsRect().width()
        except Exception:
            w = 0
        if not w or w <= 0:
            w = 320
        if w < 30:
            w = 30
        try:
            metrics = QFontMetrics(self.font())
            elided = metrics.elidedText(self._full_text, self._elide_mode, int(w))
        except Exception:
            elided = self._full_text
        QLabel.setText(self, elided)
