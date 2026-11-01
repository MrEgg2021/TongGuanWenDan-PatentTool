from PySide6.QtWidgets import QHBoxLayout, QPushButton


def build_run_panel(window):
    btn_layout = QHBoxLayout()
    btn_layout.setSpacing(16)

    window.btn_run = QPushButton("开始转换")
    window.btn_run.setObjectName("RunButton")
    window.btn_run.setProperty("class", "Primary")
    window.btn_run.setMinimumWidth(360)
    window.btn_run.setFixedHeight(64)
    window.btn_run.clicked.connect(window.on_run)

    btn_layout.addStretch(1)
    btn_layout.addWidget(window.btn_run)
    btn_layout.addStretch(1)
    return btn_layout
