from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)


def build_request_form_dialog_shell(self):
    overlay_layout = QVBoxLayout(self)
    overlay_layout.setContentsMargins(0, 0, 0, 0)
    overlay_layout.setSpacing(0)
    if not bool(getattr(self, "_embedded", False)):
        overlay_layout.setAlignment(Qt.AlignCenter)

    card = QFrame(self)
    card.setObjectName("ModalCard")
    self._card = card
    try:
        if bool(getattr(self, "_embedded", False)):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    except Exception:
        pass
    try:
        if not bool(getattr(self, "_embedded", False)):
            eff = QGraphicsDropShadowEffect(card)
            eff.setBlurRadius(28)
            eff.setOffset(0, 10)
            eff.setColor(QColor(15, 23, 42, 70))
            card.setGraphicsEffect(eff)
    except Exception:
        pass

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(0, 0, 0, 16)
    card_layout.setSpacing(8)

    titlebar = QFrame(card)
    titlebar.setObjectName("ModalTitleBar")
    tl = QHBoxLayout(titlebar)
    tl.setContentsMargins(16, 12, 12, 12)
    tl.setSpacing(8)

    try:
        if bool(getattr(self, "_embedded", False)):
            self.btn_back = QPushButton("返回", titlebar)
            self.btn_back.setObjectName("requestFormBack")
            self.btn_back.setProperty("class", "Ghost")
            tl.addWidget(self.btn_back, 0)
    except Exception:
        pass
    title = QLabel("请求书信息", titlebar)
    title.setObjectName("ModalTitleText")
    title.setProperty("role", "h2")
    tl.addWidget(title, 1)
    btn_close_x = QPushButton("×", titlebar)
    btn_close_x.setObjectName("ModalCloseButton")
    btn_close_x.setFixedSize(28, 28)
    btn_close_x.setFocusPolicy(Qt.NoFocus)
    btn_close_x.clicked.connect(self.reject)
    try:
        if bool(getattr(self, "_embedded", False)):
            btn_close_x.setVisible(False)
    except Exception:
        pass
    tl.addWidget(btn_close_x, 0, Qt.AlignTop)
    card_layout.addWidget(titlebar)

    scroll_area = QScrollArea(card)
    scroll_area.setObjectName("RequestFormScroll")
    scroll_area.setWidgetResizable(True)
    try:
        scroll_area.setFrameShape(QFrame.NoFrame)
    except Exception:
        pass
    self._scroll_area = scroll_area
    card_layout.addWidget(scroll_area, 1)

    content_widget = QWidget()
    content_widget.setObjectName("RequestFormBody")
    scroll_area.setWidget(content_widget)
    form_layout = QVBoxLayout(content_widget)
    form_layout.setContentsMargins(16, 16, 16, 24)
    form_layout.setSpacing(6)

    return overlay_layout, card, card_layout, form_layout
