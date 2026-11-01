from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from gui.widgets_impl.elide_label import ElideLabel
from gui.widgets_impl.graphic_checkbox import GraphicCheckBox


class BatchFileItemWidget(QWidget):
    """自定义批量文件列表项控件，使用 GraphicCheckBox 以确保视觉清晰度。"""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(6)

        self.checkbox = GraphicCheckBox()
        self.label = ElideLabel(text)
        self.label.setStyleSheet("background-color: transparent;")
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        try:
            self.setToolTip(str(text or ""))
        except Exception:
            pass

        layout.addWidget(self.checkbox)
        layout.addWidget(self.label, 1)

        self.setStyleSheet("background-color: transparent;")
        try:
            self.setMinimumHeight(26)
        except Exception:
            pass
