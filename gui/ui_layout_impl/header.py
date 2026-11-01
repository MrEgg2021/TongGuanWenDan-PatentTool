import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.paths_utils import get_resource_path
from core.config import get_app_display_title


def build_header_area(window):
    header_frame = QFrame()
    header_frame.setObjectName("headerFrame")
    header_frame.setFixedHeight(56)
    header_layout = QHBoxLayout(header_frame)
    header_layout.setContentsMargins(4, 4, 4, 4)
    header_layout.setSpacing(8)

    window.logo_label = QLabel()
    try:
        logo_path = get_resource_path(os.path.join("assets", "logo_round.png"))
        if not os.path.exists(logo_path):
            logo_path = get_resource_path(os.path.join("assets", "logo.png"))
    except Exception:
        logo_path = None
    if logo_path and os.path.exists(logo_path):
        pix = QPixmap(logo_path)
        if not pix.isNull():
            pix = pix.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            window.logo_label.setPixmap(pix)

    header_title = QLabel(get_app_display_title())
    header_title.setStyleSheet("font-weight: bold; font-size: 16pt;")
    header_layout.addWidget(window.logo_label)
    header_layout.addWidget(header_title)
    header_layout.addStretch()

    return header_frame
