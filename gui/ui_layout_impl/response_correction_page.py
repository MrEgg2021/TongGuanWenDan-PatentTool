from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from gui.widgets_impl.drag_drop import SingleFileDropWidget


_OUTPUT_BOX_FIXED_HEIGHT = 160
_PROCESSING_HANDLE_HEIGHT = 12
_MATERIALS_TABLE_MIN_HEIGHT = 200
_MATERIALS_TABLE_ROW_HEIGHT = 52
_UPPER_PANE_MIN_HEIGHT = {
    "response": 300,
    "correction": 340,
    "active_response": 300,
    "active_correction": 340,
}
_UPPER_PANE_DEFAULT_HEIGHT = {
    "response": 520,
    "correction": 560,
    "active_response": 520,
    "active_correction": 560,
}


class _ResponseCorrectionProcessingHandle(QFrame):
    dragDelta = Signal(int)

    def __init__(self, object_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setCursor(Qt.SplitVCursor)
        self.setFixedHeight(_PROCESSING_HANDLE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._dragging = False
        self._last_global_y = 0

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_global_y = event.globalPosition().toPoint().y()
            self.setProperty("dragging", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging:
            current_y = event.globalPosition().toPoint().y()
            delta = int(current_y - self._last_global_y)
            self._last_global_y = current_y
            if delta:
                self.dragDelta.emit(delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self.setProperty("dragging", False)
            self.style().unpolish(self)
            self.style().polish(self)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _ResponseCorrectionProcessingPane(QWidget):
    upperHeightChanged = Signal(int)

    def __init__(
        self,
        prefix: str,
        *upper_parts: QWidget,
        output_box: QWidget,
        default_upper_height: int,
        min_upper_height: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{prefix.title()}ProcessingPane")
        self._min_upper_height = int(min_upper_height)
        self._upper_content_target_height = max(int(default_upper_height), self._min_upper_height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._upper_content = QFrame()
        self._upper_content.setObjectName(f"{prefix.title()}ProcessingUpper")
        self._upper_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._upper_content.setMinimumHeight(self._min_upper_height)
        upper_layout = QVBoxLayout(self._upper_content)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(12)
        for index, part in enumerate(upper_parts):
            upper_layout.addWidget(part, 3 if index == 0 else 2)
        layout.addWidget(self._upper_content, 0)

        self._handle = _ResponseCorrectionProcessingHandle(f"{prefix.title()}ProcessingHandle")
        self._handle.dragDelta.connect(self._adjust_upper_content_height)
        layout.addWidget(self._handle, 0)

        self._output_box = output_box
        self._output_box.setFixedHeight(_OUTPUT_BOX_FIXED_HEIGHT)
        self._output_box.setMinimumHeight(_OUTPUT_BOX_FIXED_HEIGHT)
        self._output_box.setMaximumHeight(_OUTPUT_BOX_FIXED_HEIGHT)
        layout.addWidget(self._output_box, 0)
        layout.addStretch(1)

        self._apply_upper_content_height()

    @property
    def processing_handle(self) -> _ResponseCorrectionProcessingHandle:
        return self._handle

    @property
    def output_box(self) -> QWidget:
        return self._output_box

    def upper_content_height(self) -> int:
        return int(self._upper_content_target_height)

    def set_upper_content_height(self, height: int) -> None:
        next_height = max(int(height), self._min_upper_height)
        if next_height == self._upper_content_target_height:
            self._apply_upper_content_height()
            return
        self._upper_content_target_height = next_height
        self._apply_upper_content_height()
        self.upperHeightChanged.emit(self._upper_content_target_height)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_upper_content_height()

    def _adjust_upper_content_height(self, delta: int) -> None:
        self.set_upper_content_height(self._upper_content_target_height + int(delta))

    def _max_upper_content_height(self) -> int:
        available = self.height() - self._handle.height() - self._output_box.height()
        return max(self._min_upper_height, int(available))

    def _apply_upper_content_height(self) -> None:
        actual_height = min(self._upper_content_target_height, self._max_upper_content_height())
        self._upper_content.setFixedHeight(max(actual_height, self._min_upper_height))


class _ResponseCorrectionMaterialsTable(QTableWidget):
    def __init__(self, rows: int, columns: int, parent: QWidget | None = None) -> None:
        super().__init__(rows, columns, parent)
        self._syncing_right_edge = False
        header = self.horizontalHeader()
        if header is not None:
            header.sectionResized.connect(self._ensure_right_edge_filled)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._ensure_right_edge_filled()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._ensure_right_edge_filled()

    def _ensure_right_edge_filled(self, *_args) -> None:
        if self._syncing_right_edge or self.columnCount() <= 0:
            return
        last_visible_index = -1
        total_width = 0
        for index in range(self.columnCount()):
            if self.isColumnHidden(index):
                continue
            total_width += self.columnWidth(index)
            last_visible_index = index
        if last_visible_index < 0:
            return
        gap = int(self.viewport().width() - total_width)
        if gap <= 0:
            return
        self._syncing_right_edge = True
        try:
            self.setColumnWidth(last_visible_index, max(self.columnWidth(last_visible_index) + gap, 1))
        finally:
            self._syncing_right_edge = False


def _line_edit(placeholder: str = "") -> QLineEdit:
    edit = QLineEdit()
    if placeholder:
        edit.setPlaceholderText(placeholder)
    return edit


def _path_row(window, attr: str, button_text: str, handler_name: str) -> QHBoxLayout:
    edit = _line_edit()
    btn = QPushButton(button_text)
    setattr(window, attr, edit)
    handler = getattr(window, handler_name, None)
    if callable(handler):
        btn.clicked.connect(handler)
    row = QHBoxLayout()
    row.addWidget(edit, 1)
    row.addWidget(btn)
    return row


def _add_patent_type_combo(window, prefix: str, layout: QFormLayout) -> None:
    combo = QComboBox()
    combo.addItem("发明", "invention")
    combo.addItem("实用新型", "utility_model")
    setattr(window, f"{prefix}_patent_type_combo", combo)
    layout.addRow("专利类型", combo)


def _build_notice_fields_box(window, prefix: str, *, show_notice_box: bool = True) -> QGroupBox:
    notice_box = QGroupBox("通知书与案件字段" if show_notice_box else "案件基础信息")
    notice_layout = QVBoxLayout(notice_box)
    if show_notice_box:
        notice_layout.addLayout(_path_row(window, f"{prefix}_notice_edit", "选择 ZIP/PDF", f"on_{prefix}_browse_notice"))

    patent_form = QFormLayout()
    _add_patent_type_combo(window, prefix, patent_form)
    notice_layout.addLayout(patent_form)

    field_layout = QGridLayout()
    fields = [
        ("申请号", f"{prefix}_application_no_edit"),
        ("发明名称", f"{prefix}_title_edit"),
        ("申请人", f"{prefix}_applicant_edit"),
    ]
    if show_notice_box:
        fields.extend(
            (
                ("通知书名称", f"{prefix}_notice_name_edit"),
                ("发文日", f"{prefix}_issue_date_edit"),
                ("发文序列号", f"{prefix}_doc_serial_edit"),
            )
        )
    for index, (label, attr) in enumerate(fields):
        edit = _line_edit()
        setattr(window, attr, edit)
        field_layout.addWidget(QLabel(label), index // 2, (index % 2) * 2)
        field_layout.addWidget(edit, index // 2, (index % 2) * 2 + 1)
    notice_layout.addLayout(field_layout)
    return notice_box


def _set_notice_toggle_text(toggle: QPushButton, expanded: bool) -> None:
    toggle.setText(f"通知书与字段 {'▼' if expanded else '▶'}")


def _add_notice_box(
    window,
    prefix: str,
    *,
    show_notice_box: bool = True,
    enable_collapsible_notice: bool = False,
    default_expanded: bool = True,
) -> QWidget:
    body = _build_notice_fields_box(window, prefix, show_notice_box=show_notice_box)
    setattr(window, f"{prefix}_notice_section_body", body)
    setattr(window, f"{prefix}_notice_section_toggle", None)
    if not enable_collapsible_notice:
        body.setVisible(True)
        return body

    wrapper = QFrame()
    wrapper.setObjectName("Card")
    wrapper_layout = QVBoxLayout(wrapper)
    wrapper_layout.setContentsMargins(12, 12, 12, 12)
    wrapper_layout.setSpacing(8)

    notice_section_toggle = QPushButton()
    notice_section_toggle.setCheckable(True)
    notice_section_toggle.setProperty("class", "Secondary")
    notice_section_toggle.setChecked(bool(default_expanded))
    _set_notice_toggle_text(notice_section_toggle, bool(default_expanded))
    setattr(window, f"{prefix}_notice_section_toggle", notice_section_toggle)

    handler = getattr(window, "on_toggle_notice_section", None)
    if callable(handler):
        notice_section_toggle.clicked.connect(lambda checked, flow=prefix: handler(flow, checked))

    body.setVisible(bool(default_expanded))
    wrapper_layout.addWidget(notice_section_toggle, 0, Qt.AlignLeft)
    wrapper_layout.addWidget(body)
    return wrapper


def _configure_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    header = table.horizontalHeader()
    if header is not None:
        header.setStretchLastSection(True)


def _configure_materials_table(table: QTableWidget) -> None:
    _configure_table(table)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setWordWrap(False)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    try:
        table.horizontalScrollBar().setSingleStep(12)
        table.verticalScrollBar().setSingleStep(12)
    except Exception:
        pass
    header = table.horizontalHeader()
    if header is not None:
        header.setStretchLastSection(False)
        for index in range(table.columnCount()):
            header.setSectionResizeMode(index, QHeaderView.Interactive)
    try:
        table.setColumnWidth(0, 360)
        table.setColumnWidth(1, 108)
        table.setColumnWidth(2, 96)
        table.setColumnWidth(3, 210)
        table.setColumnWidth(4, 90)
        table.setColumnWidth(5, 132)
        table.setColumnWidth(6, 240)
        table.verticalHeader().setDefaultSectionSize(_MATERIALS_TABLE_ROW_HEIGHT)
    except Exception:
        pass


def _add_slot_upload_box(window, prefix: str, *, supports_notice_auto_import: bool = False) -> QGroupBox:
    docs_box = QGroupBox("材料导入与关联")
    docs_layout = QVBoxLayout(docs_box)

    import_drop_widget = SingleFileDropWidget()
    import_drop_widget.setObjectName("SingleDropZone")
    setattr(window, f"{prefix}_import_drop_widget", import_drop_widget)
    drop_handler = getattr(window, f"on_{prefix}_import_paths_dropped", None)
    if callable(drop_handler):
        import_drop_widget.filesDropped.connect(drop_handler)
    click_handler = getattr(window, f"on_{prefix}_browse_import_files", None)
    if callable(click_handler):
        import_drop_widget.clicked.connect(click_handler)

    drop_layout = QVBoxLayout(import_drop_widget)
    drop_layout.setContentsMargins(16, 16, 16, 16)
    drop_layout.setSpacing(8)

    drop_title = QLabel("拖拽多个文件或一个文件夹到这里")
    drop_title.setProperty("role", "h2")
    drop_layout.addWidget(drop_title, 0, Qt.AlignCenter)

    if supports_notice_auto_import:
        drop_hint_text = "支持通知书 ZIP/PDF，以及 DOC、DOCX、PDF、ZIP 材料。通知书会自动解析，文件夹默认只扫描顶层文件。"
    else:
        drop_hint_text = "支持 DOC、DOCX、PDF、ZIP。文件夹默认只扫描顶层文件。"
    drop_hint = QLabel(drop_hint_text)
    drop_hint.setProperty("role", "caption")
    drop_layout.addWidget(drop_hint, 0, Qt.AlignCenter)

    import_actions = QHBoxLayout()
    import_actions.addStretch(1)
    browse_import_files_btn = QPushButton("选择文件")
    browse_import_folder_btn = QPushButton("选择文件夹")
    clear_staged_files_btn = QPushButton("清空列表")
    browse_import_files_btn.setProperty("class", "Secondary")
    browse_import_folder_btn.setProperty("class", "Secondary")
    clear_staged_files_btn.setProperty("class", "Ghost")
    setattr(window, f"{prefix}_browse_import_files_btn", browse_import_files_btn)
    setattr(window, f"{prefix}_browse_import_folder_btn", browse_import_folder_btn)
    setattr(window, f"{prefix}_clear_staged_files_btn", clear_staged_files_btn)
    handler = getattr(window, f"on_{prefix}_browse_import_files", None)
    if callable(handler):
        browse_import_files_btn.clicked.connect(handler)
    handler = getattr(window, f"on_{prefix}_browse_import_folder", None)
    if callable(handler):
        browse_import_folder_btn.clicked.connect(handler)
    handler = getattr(window, f"on_{prefix}_clear_staged_files", None)
    if callable(handler):
        clear_staged_files_btn.clicked.connect(handler)
    import_actions.addWidget(browse_import_files_btn)
    import_actions.addWidget(browse_import_folder_btn)
    import_actions.addWidget(clear_staged_files_btn)
    import_actions.addStretch(1)
    drop_layout.addLayout(import_actions)
    docs_layout.addWidget(import_drop_widget)

    materials_label = QLabel("材料列表")
    materials_label.setProperty("role", "label")
    docs_layout.addWidget(materials_label)

    materials_table = _ResponseCorrectionMaterialsTable(0, 7)
    materials_table.setHorizontalHeaderLabels(["原文件名", "操作", "建议映射", "当前映射", "上传状态", "上传时间", "处理结果"])
    materials_table.setMinimumHeight(_MATERIALS_TABLE_MIN_HEIGHT)
    setattr(window, f"{prefix}_materials_table", materials_table)
    _configure_materials_table(materials_table)
    docs_layout.addWidget(materials_table, 1)

    confirm_actions = QHBoxLayout()
    confirm_actions.addStretch(1)
    confirm_imports_btn = QPushButton("上传/更新已关联材料")
    confirm_imports_btn.setProperty("class", "Primary")
    setattr(window, f"{prefix}_confirm_imports_btn", confirm_imports_btn)
    handler = getattr(window, f"on_{prefix}_confirm_imports", None)
    if callable(handler):
        confirm_imports_btn.clicked.connect(handler)
    confirm_actions.addWidget(confirm_imports_btn)
    confirm_actions.addStretch(1)
    docs_layout.addLayout(confirm_actions)
    return docs_box


def _add_output_box(window, prefix: str, *, start_text: str, handler_name: str) -> QGroupBox:
    output_box = QGroupBox("输出")
    output_box.setFixedHeight(160)
    output_layout = QVBoxLayout(output_box)
    output_layout.addLayout(_path_row(window, f"{prefix}_output_dir_edit", "选择文件夹", f"on_{prefix}_browse_output_dir"))
    status_label = QLabel("等待开始")
    status_label.setProperty("role", "caption")
    setattr(window, f"{prefix}_status_label", status_label)
    output_layout.addWidget(status_label)
    actions = QHBoxLayout()
    actions.addStretch(1)
    start_btn = QPushButton(start_text)
    start_btn.setObjectName("RunButton")
    start_btn.setProperty("class", "Primary")
    start_btn.setMinimumWidth(360)
    start_btn.setFixedHeight(64)
    setattr(window, f"{prefix}_start_btn", start_btn)
    handler = getattr(window, handler_name, None)
    if callable(handler):
        start_btn.clicked.connect(handler)
    actions.addWidget(start_btn)
    actions.addStretch(1)
    output_layout.addLayout(actions)
    return output_box


def _add_processing_pane(window, prefix: str, *parts: QWidget) -> QWidget:
    output_box = parts[-1]
    processing_pane = _ResponseCorrectionProcessingPane(
        prefix,
        *parts[:-1],
        output_box=output_box,
        default_upper_height=_UPPER_PANE_DEFAULT_HEIGHT.get(prefix, 520),
        min_upper_height=_UPPER_PANE_MIN_HEIGHT.get(prefix, 300),
    )
    setattr(window, f"{prefix}_processing_pane", processing_pane)
    setattr(window, f"{prefix}_processing_handle", processing_pane.processing_handle)
    setattr(window, f"{prefix}_output_box", processing_pane.output_box)
    return processing_pane


def _make_page(title_text: str, subtitle_text: str) -> tuple[QFrame, QVBoxLayout]:
    page = QFrame()
    page.setVisible(False)
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(12)

    title = QLabel(title_text)
    title.setProperty("role", "h1")
    root.addWidget(title)

    subtitle = QLabel(subtitle_text)
    subtitle.setProperty("role", "caption")
    root.addWidget(subtitle)
    return page, root


def _add_correction_items_box(window, *, table_attr: str, add_handler_name: str, remove_handler_name: str) -> QGroupBox:
    correction_box = QGroupBox("修改内容明细")
    correction_layout = QVBoxLayout(correction_box)
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["文件", "位置", "修改前", "修改后"])
    setattr(window, table_attr, table)
    _configure_table(table)
    correction_layout.addWidget(table)

    row_buttons = QHBoxLayout()
    add_btn = QPushButton("新增一行")
    remove_btn = QPushButton("删除选中行")
    add_handler = getattr(window, add_handler_name, None)
    remove_handler = getattr(window, remove_handler_name, None)
    if callable(add_handler):
        add_btn.clicked.connect(add_handler)
    if callable(remove_handler):
        remove_btn.clicked.connect(remove_handler)
    row_buttons.addWidget(add_btn)
    row_buttons.addWidget(remove_btn)
    row_buttons.addStretch(1)
    correction_layout.addLayout(row_buttons)
    return correction_box


def build_response_page(window) -> QFrame:
    page, root = _make_page("答复审查意见", "先导入通知书，再批量导入意见陈述书和四书，确认关联后生成答复包。")
    page.setObjectName("ResponsePage")
    root.addWidget(
        _add_notice_box(
            window,
            "response",
            show_notice_box=True,
            enable_collapsible_notice=True,
            default_expanded=False,
        )
    )
    root.addWidget(
        _add_processing_pane(
            window,
            "response",
            _add_slot_upload_box(window, "response", supports_notice_auto_import=True),
            _add_output_box(window, "response", start_text="生成审查意见答复包", handler_name="on_response_start"),
        ),
        1,
    )
    return page


def build_correction_page(window) -> QFrame:
    page, root = _make_page("答复补正", "先导入通知书，再批量导入四书，确认关联后生成补正包。")
    page.setObjectName("CorrectionPage")
    root.addWidget(
        _add_notice_box(
            window,
            "correction",
            show_notice_box=True,
            enable_collapsible_notice=True,
            default_expanded=False,
        )
    )
    root.addWidget(
        _add_processing_pane(
            window,
            "correction",
            _add_slot_upload_box(window, "correction", supports_notice_auto_import=True),
            _add_correction_items_box(
                window,
                table_attr="correction_items_table",
                add_handler_name="on_correction_add_item",
                remove_handler_name="on_correction_remove_item",
            ),
            _add_output_box(window, "correction", start_text="生成补正答复包", handler_name="on_correction_start"),
        ),
        1,
    )
    return page


def build_active_response_page(window) -> QFrame:
    page, root = _make_page("主动答复", "支持从导入区自动识别通知书 ZIP/PDF 并回填基础信息，再批量导入意见陈述书和四书，确认关联后生成答复包。")
    page.setObjectName("ActiveResponsePage")
    root.addWidget(_add_notice_box(window, "active_response", show_notice_box=False))
    root.addWidget(
        _add_processing_pane(
            window,
            "active_response",
            _add_slot_upload_box(window, "active_response", supports_notice_auto_import=True),
            _add_output_box(window, "active_response", start_text="生成主动答复包", handler_name="on_active_response_start"),
        ),
        1,
    )
    return page


def build_active_correction_page(window) -> QFrame:
    page, root = _make_page("主动补正", "支持从导入区自动识别通知书 ZIP/PDF 并回填基础信息，再批量导入四书，确认关联后生成补正包。")
    page.setObjectName("ActiveCorrectionPage")
    root.addWidget(_add_notice_box(window, "active_correction", show_notice_box=False))
    root.addWidget(
        _add_processing_pane(
            window,
            "active_correction",
            _add_slot_upload_box(window, "active_correction", supports_notice_auto_import=True),
            _add_correction_items_box(
                window,
                table_attr="active_correction_items_table",
                add_handler_name="on_active_correction_add_item",
                remove_handler_name="on_active_correction_remove_item",
            ),
            _add_output_box(window, "active_correction", start_text="生成主动补正包", handler_name="on_active_correction_start"),
        ),
        1,
    )
    return page


def build_response_correction_page(window) -> QFrame:
    return build_response_page(window)


__all__ = [
    "build_active_correction_page",
    "build_active_response_page",
    "build_correction_page",
    "build_response_correction_page",
    "build_response_page",
]
