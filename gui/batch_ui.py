import os

from PySide6.QtWidgets import QFileDialog, QListWidgetItem
from PySide6.QtCore import Qt

from gui.widgets import BatchFileItemWidget


def browse_files(window) -> None:
    """选择多个文件，添加到批量列表。"""
    files, _ = QFileDialog.getOpenFileNames(
        window,
        "选择多个 DOC/DOCX 文件",
        os.getcwd(),
        "Word 文档 (*.doc *.docx)",
    )
    if not files:
        return
    append_batch_files(window, files)


def browse_folder(window) -> None:
    """选择文件夹，批量添加 DOCX 文件到列表。"""
    folder = QFileDialog.getExistingDirectory(
        window,
        "选择包含 DOC/DOCX 文件的文件夹",
        os.getcwd(),
    )
    if not folder:
        return

    # 遍历文件夹找到所有 .docx 文件
    docx_files = []
    for filename in os.listdir(folder):
        lower = filename.lower()
        if lower.endswith((".doc", ".docx")) and not filename.startswith("~"):
            file_path = os.path.join(folder, filename)
            docx_files.append(file_path)
    if docx_files:
        append_batch_files(window, docx_files)


def clear_list(window) -> None:
    """清空批量文件列表。"""
    window._selected_files.clear()
    window._batch_file_types.clear()
    window.file_list_widget.clear()
    update_batch_selection_stats(window)
    try:
        window._apply_batch_filter()
    except Exception:
        pass


def batch_item_clicked(window, item) -> None:
    """点击批量列表某一行时，切换该行 widget 的复选框状态。"""
    if item is None:
        return
    widget = window.file_list_widget.itemWidget(item)
    if isinstance(widget, BatchFileItemWidget):
        widget.checkbox.setChecked(not widget.checkbox.isChecked())


def batch_item_changed(window, item) -> None:
    """批量列表中单个条目勾选状态变化时更新统计。"""
    # 防止在刷新条目文字时触发递归
    if window._suppress_batch_item_changed:
        return
    # 仅根据当前整体状态刷新统计，不在这里修改勾选本身
    update_batch_selection_stats(window)


def update_batch_selection_stats(window) -> None:
    """更新批量模式下的文件数量与类型统计。"""
    total_files = window.file_list_widget.count()

    # 1. 统计当前勾选数量（用于右上角临时反馈）
    current_checked_count = 0

    window._suppress_batch_item_changed = True
    try:
        for i in range(total_files):
            item = window.file_list_widget.item(i)

            file_path = item.data(Qt.UserRole)
            base_name = item.data(Qt.UserRole + 1)
            if not isinstance(base_name, str):
                if isinstance(file_path, str):
                    base_name = os.path.basename(file_path)
                else:
                    base_name = item.text()

            # 从 widget 获取勾选状态
            widget = window.file_list_widget.itemWidget(item)
            if isinstance(widget, BatchFileItemWidget) and widget.checkbox.isChecked():
                current_checked_count += 1

            # 仅显示纯文件名，不再在前缀处展示“发明/实用新型/不处理”
            display_text = base_name
            if isinstance(widget, BatchFileItemWidget):
                current_text = None
                try:
                    current_text = widget.label.fullText()  # type: ignore[attr-defined]
                except Exception:
                    current_text = None
                if current_text is None:
                    try:
                        current_text = widget.label.text()
                    except Exception:
                        current_text = ""
                if current_text != display_text:
                    widget.label.setText(display_text)
                    try:
                        widget.setToolTip(str(display_text or ""))
                    except Exception:
                        pass
    finally:
        window._suppress_batch_item_changed = False

    # 右下角：仅显示文件总数与当前已选数量
    bottom_text = f"共{total_files}个文件  已选中{current_checked_count}个"
    if hasattr(window, "batch_stats_label"):
        window.batch_stats_label.setText(bottom_text)
        window.batch_stats_label.setVisible(True)

    # 右上角：显示当前勾选数量
    if hasattr(window, "batch_type_toolbar_label"):
        window.batch_type_toolbar_label.setText(f"已选中 ({current_checked_count})")

def get_batch_checked_files(window):
    """返回当前勾选的批量处理文件路径列表。"""
    files = []
    for i in range(window.file_list_widget.count()):
        item = window.file_list_widget.item(i)
        widget = window.file_list_widget.itemWidget(item)
        if isinstance(widget, BatchFileItemWidget) and widget.checkbox.isChecked():
            file_path = item.data(Qt.UserRole)
            if isinstance(file_path, str):
                files.append(file_path)
    return files


def append_batch_files(window, file_paths) -> int:
    """将给定文件路径列表追加到批量列表，返回新增数量。"""
    added = 0

    for file_path in file_paths:
        if not isinstance(file_path, str):
            continue
        normalized = os.path.normpath(file_path)
        if normalized in window._selected_files:
            continue
        if not os.path.isfile(normalized):
            continue
        window._selected_files.append(normalized)
        basename = os.path.basename(normalized)
        item = QListWidgetItem()
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setData(Qt.UserRole, normalized)
        item.setData(Qt.UserRole + 1, basename)
        window.file_list_widget.addItem(item)

        widget = BatchFileItemWidget(basename)
        widget.checkbox.setChecked(True)
        widget.checkbox.toggled.connect(
            lambda checked, it=item: window.on_batch_item_changed(it)
        )
        item.setSizeHint(widget.sizeHint())
        window.file_list_widget.setItemWidget(item, widget)
        added += 1

    if added:
        update_batch_selection_stats(window)
        try:
            window._apply_batch_filter()
        except Exception:
            pass
    return added
