from __future__ import annotations

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from core.cnipa_preview.installed_client import CLIENT_MISSING
from core.cnipa_preview.runtime import get_default_runtime_manager


class ClientDetectionWorker(QObject):
    completed = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, path: str | None = None):
        super().__init__()
        self.path = path

    @Slot()
    def run(self):
        try:
            client = get_default_runtime_manager().configure(self.path, detect=self.path is None)
            self.completed.emit(str(client.root))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class RuntimeSetupDialog(QDialog):
    """Installed-client detection only; case ZIP input remains on the preview page."""

    def __init__(self, parent=None, *, automatic=False):
        super().__init__(parent)
        self.setWindowTitle("全量预览服务：检测专利业务办理系统客户端（CNIPA）")
        self.resize(640, 260)
        self._thread = None
        self._worker = None
        self._automatic = automatic
        manager = get_default_runtime_manager()
        path = manager.configured_path()
        layout = QVBoxLayout(self)
        intro = QLabel("全量预览需要已安装的专利业务办理系统客户端（CNIPA）。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.path_label = QLabel(path or "尚未记录客户端目录")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.path_label)
        self.status_label = QLabel(manager.configuration_error() or ("已记录客户端路径，可直接使用。" if path else "正在自动检测客户端……"))
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.detect_button = QPushButton("重新检测")
        self.browse_button = QPushButton("选择客户端目录…")
        self.close_button = QPushButton("完成" if path and not manager.configuration_error() else "取消")
        self._success = bool(path and not manager.configuration_error())
        actions.addWidget(self.detect_button)
        actions.addWidget(self.browse_button)
        actions.addStretch()
        actions.addWidget(self.close_button)
        layout.addLayout(actions)
        self.detect_button.clicked.connect(lambda: self._detect(None))
        self.browse_button.clicked.connect(self._browse)
        self.close_button.clicked.connect(self._finish)
        if not path:
            QTimer.singleShot(0, lambda: self._detect(None))

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择已安装的 CNIPAClient 根目录", self.path_label.text())
        if path:
            self._detect(path)

    def _detect(self, path):
        if self._thread is not None:
            return
        self._success = False
        self.status_label.setText("正在检查客户端渲染组件……")
        self.progress.show()
        self.detect_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.close_button.setEnabled(False)
        thread = QThread(self)
        worker = ClientDetectionWorker(path)
        worker.moveToThread(thread)
        worker.completed.connect(self._completed, Qt.QueuedConnection)
        worker.failed.connect(self._failed, Qt.QueuedConnection)
        worker.finished.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._finished)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._thread = thread
        thread.start()

    @Slot(str)
    def _completed(self, path):
        self._success = True
        self.path_label.setText(path)
        self.status_label.setText("已检测到客户端并记住路径。后续直接使用，组件失效或更新时才重新检查。")
        self.close_button.setText("完成")

    @Slot(str)
    def _failed(self, message):
        self.status_label.setText(CLIENT_MISSING + "\n" + message if CLIENT_MISSING not in message else message)
        self.close_button.setText("取消")

    @Slot()
    def _finished(self):
        self._thread = None
        self._worker = None
        self.progress.hide()
        self.detect_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.close_button.setEnabled(True)
        if self._automatic and self._success:
            self.accept()

    def _finish(self):
        self.accept() if self._success else self.reject()

    def reject(self):
        if self._thread is None:
            super().reject()


def configure_installed_client(parent=None, *, automatic=False) -> bool:
    return RuntimeSetupDialog(parent, automatic=automatic).exec() == QDialog.Accepted
