from PySide6.QtCore import QEvent, QPoint, QRect, QSize, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QButtonGroup, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QStyledItemDelegate, QVBoxLayout, QWidget, QLineEdit, QScrollArea, QSplitter

from core.app_preferences import get_pdf_preview_mode
from gui.widgets import SingleFileDropWidget, install_drop_card_proxy


_PREVIEW_CODE_ROLE = Qt.UserRole + 1
_PREVIEW_STATUS_ROLE = Qt.UserRole + 2
_PREVIEW_STATUS_TONE_ROLE = Qt.UserRole + 3


class _PreviewDocumentDelegate(QStyledItemDelegate):
    """Paint rich rows while keeping every document a native draggable item."""

    def __init__(self, document_list: QListWidget) -> None:
        super().__init__(document_list)
        self._document_list = document_list

    @staticmethod
    def _checkbox_rect(row_rect: QRect) -> QRect:
        return QRect(row_rect.left() + 38, row_rect.center().y() - 9, 18, 18)

    def sizeHint(self, option, index) -> QSize:  # type: ignore[override]
        return QSize(max(1, option.rect.width()), 66)

    def paint(self, painter: QPainter, option, index) -> None:  # type: ignore[override]
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        row_rect = option.rect.adjusted(4, 2, -4, -2)
        is_target = index.row() == int(getattr(self._document_list, "_drag_target_row", -1))
        is_selected = bool(option.state & option.state.State_Selected)
        is_hovered = bool(option.state & option.state.State_MouseOver)
        if is_target:
            background, border = QColor("#DBEAFE"), QColor("#3B82F6")
        elif is_selected:
            background, border = QColor("#EAF2FF"), QColor("#60A5FA")
        elif is_hovered:
            background, border = QColor("#F8FAFC"), QColor("#93C5FD")
        else:
            background, border = QColor("#FFFFFF"), QColor("#E2E8F0")
        painter.setBrush(background)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(row_rect, 7, 7)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#64748B"))
        grip_x = row_rect.left() + 16
        for column in range(2):
            for grip_row in range(3):
                painter.drawEllipse(QPoint(grip_x + column * 5, row_rect.center().y() - 5 + grip_row * 5), 1, 1)

        enabled = bool(index.flags() & Qt.ItemIsEnabled)
        checked = int(index.data(Qt.CheckStateRole) or 0) == Qt.Checked.value
        checkbox_rect = self._checkbox_rect(row_rect)
        painter.setBrush(QColor("#FFFFFF") if enabled else QColor("#F1F5F9"))
        painter.setPen(QPen(QColor("#2563EB") if checked else QColor("#64748B"), 1))
        painter.drawRoundedRect(checkbox_rect, 3, 3)
        if checked:
            painter.setPen(QPen(QColor("#1D4ED8"), 2))
            painter.drawLine(checkbox_rect.left() + 4, checkbox_rect.center().y(), checkbox_rect.left() + 8, checkbox_rect.bottom() - 4)
            painter.drawLine(checkbox_rect.left() + 8, checkbox_rect.bottom() - 4, checkbox_rect.right() - 3, checkbox_rect.top() + 4)

        status_text = str(index.data(_PREVIEW_STATUS_ROLE) or "待生成")
        status_tone = str(index.data(_PREVIEW_STATUS_TONE_ROLE) or "pending")
        status_color = {
            "success": QColor("#2E7D32"),
            "error": QColor("#C62828"),
            "info": QColor("#0369A1"),
        }.get(status_tone, QColor("#64748B"))
        status_rect = QRect(row_rect.right() - 88, row_rect.top() + 8, 78, 20)
        text_left = checkbox_rect.right() + 12
        text_right = status_rect.left() - 10

        name_font = option.font
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor("#1E293B") if enabled else QColor("#94A3B8"))
        name = str(index.data(Qt.DisplayRole) or "")
        name_rect = QRect(text_left, row_rect.top() + 6, max(20, text_right - text_left), 24)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, painter.fontMetrics().elidedText(name, Qt.ElideRight, name_rect.width()))

        caption_font = option.font
        caption_font.setPointSize(max(8, option.font.pointSize() - 1))
        caption_font.setBold(False)
        painter.setFont(caption_font)
        painter.setPen(QColor("#64748B") if enabled else QColor("#94A3B8"))
        code = f"文件代码：{str(index.data(_PREVIEW_CODE_ROLE) or '未提供')}"
        code_rect = QRect(text_left, row_rect.top() + 31, max(20, text_right - text_left), 21)
        painter.drawText(code_rect, Qt.AlignLeft | Qt.AlignVCenter, code)

        status_font = caption_font
        status_font.setBold(status_tone in {"success", "error"})
        painter.setFont(status_font)
        painter.setPen(status_color)
        painter.drawText(status_rect, Qt.AlignRight | Qt.AlignVCenter, status_text)
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:  # type: ignore[override]
        if (
            event.type() == QEvent.MouseButtonRelease
            and event.button() == Qt.LeftButton
            and bool(index.flags() & Qt.ItemIsEnabled)
            and self._checkbox_rect(option.rect.adjusted(4, 2, -4, -2)).contains(event.position().toPoint())
        ):
            checked = int(index.data(Qt.CheckStateRole) or 0) == Qt.Checked.value
            return bool(model.setData(index, Qt.Unchecked if checked else Qt.Checked, Qt.CheckStateRole))
        return False


class _PreviewDocumentList(QListWidget):
    """Native internal-move list matching the official-doc naming editor."""

    def __init__(self, window, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_window = window
        self._drag_target_row = -1

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        item = self.itemAt(event.position().toPoint())
        target_row = self.row(item) if item is not None else -1
        if target_row != self._drag_target_row:
            self._drag_target_row = target_row
            self.viewport().update()
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._drag_target_row = -1
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        super().dropEvent(event)
        self._drag_target_row = -1
        self.viewport().update()
        _queue_preview_document_reorder(self._preview_window)


def _queue_preview_document_reorder(window) -> None:
    """Wait until QListWidget finishes its internal move before reading its rows."""
    if bool(getattr(window, "_preview_reorder_refresh_pending", False)):
        return
    window._preview_reorder_refresh_pending = True

    def apply_reorder() -> None:
        window._preview_reorder_refresh_pending = False
        callback = getattr(window, "_on_preview_documents_reordered", None)
        if callable(callback):
            callback()

    QTimer.singleShot(0, apply_reorder)


def rebuild_preview_document_rows(window, documents) -> None:
    """Rebuilds the selectable, drag-sortable manifest document list."""

    document_list = getattr(window, "preview_document_list", None)
    if document_list is None:
        return
    items: dict[str, QListWidgetItem] = {}
    with QSignalBlocker(document_list):
        document_list.clear()
        for document in tuple(documents or ()):
            document_id = str(document.id)
            item = QListWidgetItem(str(document.display_name))
            item.setData(Qt.UserRole, document_id)
            item.setData(_PREVIEW_CODE_ROLE, str(document.code or "未提供"))
            item.setData(_PREVIEW_STATUS_ROLE, "待生成")
            item.setData(_PREVIEW_STATUS_TONE_ROLE, "pending")
            item.setCheckState(Qt.Unchecked)
            # This mirrors the official-doc filename editor: each row is a
            # native draggable item, but never a container for another row.
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsUserCheckable)
            item.setSizeHint(QSize(1, 66))
            item.setToolTip(f"{document.display_name}\n文件代码：{document.code or '未提供'}")
            document_list.addItem(item)
            items[document_id] = item

    window.preview_doc_items = items


def build_preview_page(window):
    page = QWidget()
    page.setObjectName("previewPage")
    page.setVisible(False)

    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(6)


    title = QLabel("预览/导出PDF")
    title.setProperty("role", "h1")
    subtitle = QLabel("轻量预览：需安装并启动官方预览插件，仅支持四书。")
    subtitle.setProperty("role", "caption")
    subtitle.setProperty("emphasis", True)
    subtitle.setWordWrap(True)

    root.addWidget(title)
    root.addWidget(subtitle)

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(0)
    legacy_mode_button = QPushButton("轻量预览（四书）")
    legacy_mode_button.setCheckable(True)
    legacy_mode_button.setProperty("segment", True)
    full_mode_button = QPushButton("全量预览（官方渲染）")
    full_mode_button.setCheckable(True)
    full_mode_button.setProperty("segment", True)
    mode_group = QButtonGroup(page)
    mode_group.setExclusive(True)
    mode_group.addButton(legacy_mode_button)
    mode_group.addButton(full_mode_button)
    selected_mode = get_pdf_preview_mode()
    legacy_mode_button.setChecked(selected_mode == "legacy")
    full_mode_button.setChecked(selected_mode == "full")
    mode_row.addWidget(legacy_mode_button)
    mode_row.addWidget(full_mode_button)
    mode_row.addStretch(1)

    legacy_connection_label = QLabel("轻量预览：正在检测…")
    legacy_connection_label.setProperty("role", "caption")
    full_connection_label = QLabel("全量预览：正在检测…")
    full_connection_label.setProperty("role", "caption")
    mode_row.addWidget(legacy_connection_label)
    mode_row.addSpacing(12)
    mode_row.addWidget(full_connection_label)
    root.addLayout(mode_row)

    main_vertical_splitter = QSplitter(Qt.Vertical)
    main_vertical_splitter.setObjectName("PreviewMainVerticalSplitter")
    main_vertical_splitter.setChildrenCollapsible(False)
    root.addWidget(main_vertical_splitter, 1)

    top_section = QWidget()
    top_layout = QVBoxLayout(top_section)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(0)

    drop_card = QFrame()
    drop_card.setObjectName("Card")
    drop_card_layout = QVBoxLayout(drop_card)
    drop_card_layout.setContentsMargins(8, 8, 8, 8)
    drop_card_layout.setSpacing(4)


    dz = SingleFileDropWidget()
    dz.setObjectName("PreviewZipDropZone")
    try:
        dz.setMinimumHeight(68)
        dz.setMaximumHeight(84)
    except Exception:
        pass
    dz_layout = QVBoxLayout(dz)
    dz_layout.setContentsMargins(12, 4, 12, 4)
    dz_layout.setSpacing(4)


    dz_hint = QLabel("点击选择 ZIP 或 将 ZIP 拖拽至此")
    dz_hint.setAlignment(Qt.AlignCenter)
    dz_hint.setProperty("role", "label")
    dz_hint.setProperty("emphasis", True)

    dz_layout.addStretch(1)
    dz_layout.addWidget(dz_hint)
    dz_layout.addStretch(1)

    try:
        dz.filesDropped.connect(window.on_preview_zips_dropped)
    except Exception:
        pass
    try:
        dz.clicked.connect(window.on_preview_import_zips)
    except Exception:
        pass

    drop_card_layout.addWidget(dz)
    top_layout.addWidget(drop_card)
    main_vertical_splitter.addWidget(top_section)

    bottom_section = QWidget()
    bottom_layout = QVBoxLayout(bottom_section)
    bottom_layout.setContentsMargins(0, 0, 0, 0)
    bottom_layout.setSpacing(0)

    main_horizontal_splitter = QSplitter(Qt.Horizontal)
    main_horizontal_splitter.setObjectName("PreviewMainHorizontalSplitter")
    main_horizontal_splitter.setChildrenCollapsible(False)
    bottom_layout.addWidget(main_horizontal_splitter, 1)

    # 左：案件列表
    list_card = QFrame()
    list_card.setObjectName("PreviewCaseCard")
    try:
        list_card.setMinimumWidth(280)
    except Exception:
        pass
    list_layout = QVBoxLayout(list_card)
    list_layout.setContentsMargins(10, 10, 10, 10)
    list_layout.setSpacing(6)


    list_title_row = QHBoxLayout()
    list_title_row.setContentsMargins(0, 0, 0, 0)
    list_title_row.setSpacing(8)
    list_title = QLabel("案件列表")
    list_title.setProperty("role", "label")
    list_title.setProperty("emphasis", True)
    list_count = QLabel("0 项")
    list_count.setProperty("role", "caption")
    list_count.setProperty("emphasis", True)
    list_title_row.addWidget(list_title)
    list_title_row.addWidget(list_count)
    list_title_row.addStretch(1)

    btn_clear = QPushButton("清空列表")
    btn_clear.setObjectName("PreviewCaseClearButton")
    try:
        btn_clear.clicked.connect(window.on_preview_clear_cases)
    except Exception:
        pass
    list_title_row.addWidget(btn_clear)
    list_layout.addLayout(list_title_row)

    search_edit = QLineEdit()
    search_edit.setObjectName("PreviewCaseSearch")
    search_edit.setPlaceholderText("搜索案件")
    list_layout.addWidget(search_edit)

    scroll = QScrollArea()
    scroll.setObjectName("PreviewCaseScroll")
    try:
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
    except Exception:
        pass

    body = QWidget()
    body.setObjectName("PreviewCaseListBody")
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(6)
    try:
        body_layout.addStretch(1)
    except Exception:
        pass

    try:
        scroll.setWidget(body)
    except Exception:
        pass
    list_layout.addWidget(scroll, 1)

    try:
        search_edit.textChanged.connect(window.on_preview_case_search_changed)
    except Exception:
        pass

    # 右：预览与导出
    detail_card = QFrame()
    detail_card.setObjectName("Card")
    detail_card.setMinimumWidth(440)
    detail_layout = QVBoxLayout(detail_card)
    detail_layout.setContentsMargins(10, 10, 10, 10)
    detail_layout.setSpacing(6)


    detail_title = QLabel("文件清单与 PDF 输出")
    detail_title.setProperty("role", "label")
    detail_title.setProperty("emphasis", True)
    current_name = QLabel("未选择案件")
    current_name.setProperty("role", "caption")
    current_name.setWordWrap(True)
    detail_title_row = QHBoxLayout()
    detail_title_row.setContentsMargins(0, 0, 0, 0)
    detail_title_row.setSpacing(8)
    detail_title_row.addWidget(detail_title)
    detail_title_row.addWidget(current_name, 1)
    detail_layout.addLayout(detail_title_row)

    action_box = QFrame()
    action_box.setObjectName("PreviewActionBox")
    action_box_layout = QVBoxLayout(action_box)
    action_box_layout.setContentsMargins(8, 8, 8, 8)
    action_box_layout.setSpacing(6)

    action_row = QHBoxLayout()
    action_row.setContentsMargins(0, 0, 0, 0)
    action_row.setSpacing(10)
    btn_preview = QPushButton("解析文件清单")
    btn_preview.setObjectName("Primary")
    action_row.addWidget(btn_preview)
    action_summary = QLabel("全量预览会直接打开 PDF；需要留存时可在阅读器中另存。")
    action_summary.setObjectName("PreviewActionSummary")
    action_summary.setProperty("role", "caption")
    action_summary.setWordWrap(True)
    action_row.addWidget(action_summary, 1)
    action_box_layout.addLayout(action_row)
    detail_layout.addWidget(action_box)

    export_box = QFrame()
    export_box.setObjectName("PreviewExportBox")
    export_box_layout = QVBoxLayout(export_box)
    export_box_layout.setContentsMargins(8, 8, 8, 8)
    export_box_layout.setSpacing(6)

    export_title = QLabel("案卷文件（勾选并拖动排序）")
    export_title.setProperty("role", "caption")
    export_title.setProperty("emphasis", True)
    export_title.setWordWrap(True)
    export_box_layout.addWidget(export_title)

    document_list = _PreviewDocumentList(window)
    document_list.setObjectName("PreviewDocumentList")
    document_list.setItemDelegate(_PreviewDocumentDelegate(document_list))
    document_list.setDragDropMode(QAbstractItemView.InternalMove)
    document_list.setDefaultDropAction(Qt.MoveAction)
    document_list.setDragDropOverwriteMode(False)
    document_list.setDropIndicatorShown(True)
    document_list.setSelectionMode(QAbstractItemView.SingleSelection)
    document_list.setMouseTracking(True)
    document_list.setUniformItemSizes(True)
    document_list.setSpacing(4)
    document_list.setMinimumHeight(220)
    document_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    document_list.setFrameShape(QFrame.NoFrame)
    export_box_layout.addWidget(document_list, 1)

    export_row = QHBoxLayout()
    export_row.setContentsMargins(0, 0, 0, 0)
    export_row.setSpacing(8)
    export_row.addStretch(1)
    btn_export = QPushButton("导出所选 PDF…")
    btn_export.setObjectName("primaryButton")
    try:
        btn_export.setEnabled(False)
    except Exception:
        pass
    export_row.addWidget(btn_export)
    export_box_layout.addLayout(export_row)
    detail_layout.addWidget(export_box)

    try:
        btn_preview.clicked.connect(window.on_preview_start_selected_case)
    except Exception:
        pass
    try:
        btn_export.clicked.connect(window.on_preview_export_merged_pdf)
    except Exception:
        pass
    try:
        document_list.model().rowsMoved.connect(lambda *_args: _queue_preview_document_reorder(window))
    except Exception:
        pass
    try:
        document_list.itemChanged.connect(
            lambda item: window._on_preview_doc_check_toggled(
                str(item.data(Qt.UserRole) or ""),
                item.checkState() == Qt.Checked,
            )
        )
    except Exception:
        pass

    main_horizontal_splitter.addWidget(list_card)
    main_horizontal_splitter.addWidget(detail_card)
    try:
        main_horizontal_splitter.setSizes([380, 820])
    except Exception:
        pass

    main_vertical_splitter.addWidget(bottom_section)
    try:
        main_vertical_splitter.setSizes([1, 9])
    except Exception:
        pass

    try:
        proxy = install_drop_card_proxy(drop_card, dz)
        proxies = getattr(window, "_drop_card_proxies", None)
        if not isinstance(proxies, list):
            proxies = []
            window._drop_card_proxies = proxies
        proxies.append(proxy)
    except Exception:
        pass

    window.preview_page = page
    window.preview_subtitle_label = subtitle
    window.preview_mode_button_group = mode_group
    window.preview_legacy_mode_button = legacy_mode_button
    window.preview_full_mode_button = full_mode_button
    window.preview_legacy_connection_label = legacy_connection_label
    window.preview_full_connection_label = full_connection_label
    window.preview_zip_drop_zone = dz
    window.preview_zip_drop_hint = dz_hint
    window.preview_zip_drop_card = drop_card
    window.preview_case_count_label = list_count
    window.preview_clear_button = btn_clear
    window.preview_current_case_label = current_name
    window.preview_start_button = btn_preview
    window.preview_action_summary_label = action_summary
    window.preview_export_button = btn_export
    window.preview_doc_rows_layout = None
    window.preview_document_list = document_list
    window.preview_doc_items = {}
    window.preview_case_search_edit = search_edit
    window.preview_case_scroll = scroll
    window.preview_case_list_body = body
    window.preview_case_list_layout = body_layout
    window.preview_main_vertical_splitter = main_vertical_splitter
    window.preview_main_horizontal_splitter = main_horizontal_splitter

    try:
        legacy_mode_button.clicked.connect(lambda: window.on_preview_mode_changed("legacy"))
        full_mode_button.clicked.connect(lambda: window.on_preview_mode_changed("full"))
        QTimer.singleShot(0, window._apply_preview_mode_ui)
    except Exception:
        pass

    return page
