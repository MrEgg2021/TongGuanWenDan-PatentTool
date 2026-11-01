from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import BatchFileListWidget, SingleFileDropWidget, install_drop_card_proxy


def build_batch_panel(window):
    window.batch_widget = QWidget()
    window.batch_widget.setObjectName("batchWidget")
    window.batch_widget.setVisible(False)
    batch_layout = QVBoxLayout(window.batch_widget)
    batch_layout.setContentsMargins(0, 0, 0, 0)
    batch_layout.setSpacing(6)

    batch_main_splitter = QSplitter(Qt.Vertical)
    batch_main_splitter.setObjectName("BatchMainSplitter")
    batch_main_splitter.setChildrenCollapsible(False)
    batch_layout.addWidget(batch_main_splitter, 1)

    top_section = QWidget()
    top_section_layout = QVBoxLayout(top_section)
    top_section_layout.setContentsMargins(0, 0, 0, 0)
    top_section_layout.setSpacing(0)

    drop_card = QFrame()
    drop_card.setObjectName("Card")
    drop_card_layout = QVBoxLayout(drop_card)
    drop_card_layout.setContentsMargins(12, 6, 12, 6)
    drop_card_layout.setSpacing(4)

    window.batch_drop_zone = SingleFileDropWidget()
    window.batch_drop_zone.setObjectName("BatchDropZone")
    try:
        window.batch_drop_zone.setMinimumHeight(56)
        window.batch_drop_zone.setMaximumHeight(72)
        window.batch_drop_zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    except Exception:
        pass
    dz_layout = QVBoxLayout(window.batch_drop_zone)
    dz_layout.setContentsMargins(16, 6, 16, 6)
    dz_layout.setSpacing(0)

    window.batch_drop_hint = QLabel("点击选择文件/文件夹 或 将 Word 拖拽至此")
    window.batch_drop_hint.setObjectName("batchDropHint")
    window.batch_drop_hint.setAlignment(Qt.AlignCenter)
    window.batch_drop_hint.setProperty("role", "caption")
    window.batch_drop_hint.setProperty("emphasis", True)
    try:
        window.batch_drop_hint.setWordWrap(False)
    except Exception:
        pass
    dz_layout.addWidget(window.batch_drop_hint)
    try:
        window.batch_drop_zone.filesDropped.connect(window.on_batch_files_dropped)
    except Exception:
        pass
    try:
        window.batch_drop_zone.clicked.connect(window._show_batch_pick_menu)
    except Exception:
        pass

    drop_card_layout.addWidget(window.batch_drop_zone)
    top_section_layout.addWidget(drop_card)
    batch_main_splitter.addWidget(top_section)

    bottom_section = QWidget()
    bottom_layout = QVBoxLayout(bottom_section)
    bottom_layout.setContentsMargins(0, 0, 0, 0)
    bottom_layout.setSpacing(6)

    list_card = QFrame()
    list_card.setObjectName("Card")
    list_card_layout = QVBoxLayout(list_card)
    list_card_layout.setContentsMargins(12, 8, 12, 8)
    list_card_layout.setSpacing(6)

    header_row = QHBoxLayout()

    header_row.setContentsMargins(0, 0, 0, 0)
    header_row.setSpacing(10)
    label_selected = QLabel("已选择的文件")
    label_selected.setProperty("role", "caption")
    label_selected.setProperty("emphasis", True)
    header_row.addWidget(label_selected)
    header_row.addStretch(1)

    window.batch_type_toolbar_label = QLabel("已选中 (0)")
    window.batch_type_toolbar_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    window.batch_type_toolbar_label.setProperty("role", "caption")
    window.batch_type_toolbar_label.setProperty("emphasis", True)
    header_row.addWidget(window.batch_type_toolbar_label)

    window.btn_clear_list = QPushButton("清空列表")
    window.btn_clear_list.setObjectName("BatchClearButton")
    window.btn_clear_list.clicked.connect(window.on_clear_list)
    header_row.addWidget(window.btn_clear_list)

    list_card_layout.addLayout(header_row)

    window.batch_filter_edit = QLineEdit()
    window.batch_filter_edit.setObjectName("BatchFileFilter")
    window.batch_filter_edit.setPlaceholderText("筛选文件")
    try:
        window.batch_filter_edit.textChanged.connect(window.on_batch_filter_changed)
    except Exception:
        pass
    list_card_layout.addWidget(window.batch_filter_edit)

    window.file_list_widget = BatchFileListWidget()
    window.file_list_widget.setObjectName("CardList")
    window.file_list_widget.setMinimumHeight(120)
    # Removed fixed max height to allow expansion in ScrollArea
    # try:
    #     window.file_list_widget.setMaximumHeight(220)
    # except Exception:
    #     pass
    window.file_list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)

    window.file_list_widget.itemClicked.connect(window.on_batch_item_clicked)
    window.file_list_widget.itemChanged.connect(window.on_batch_item_changed)
    window.file_list_widget.pathsDropped.connect(window.on_batch_files_dropped)
    list_card_layout.addWidget(window.file_list_widget)

    window.batch_stats_label = QLabel("")
    window.batch_stats_label.setAlignment(Qt.AlignLeft)
    window.batch_stats_label.setProperty("role", "caption")
    window.batch_stats_label.setProperty("emphasis", True)
    window.batch_stats_label.setObjectName("BatchStatsLabel")
    window.batch_stats_label.setVisible(False)

    list_card_layout.addWidget(window.batch_stats_label)

    case_layout = QHBoxLayout()
    case_layout.setSpacing(8)

    window.batch_name_frame = QFrame()
    window.batch_name_frame.setObjectName("batchNameFrame")
    name_layout = QHBoxLayout(window.batch_name_frame)
    name_layout.setContentsMargins(0, 0, 0, 0)
    name_layout.setSpacing(8)
    case_label = QLabel("输出文件的名称：")
    case_label.setProperty("role", "label")
    case_label.setProperty("emphasis", True)
    window.batch_zip_name_edit = QLineEdit()
    window.batch_zip_name_edit.setPlaceholderText("例如：20251129批量案卷")
    name_layout.addWidget(case_label, 0)
    name_layout.addWidget(window.batch_zip_name_edit, 1)

    output_anchor = QWidget()
    output_anchor.setFixedSize(0, 0)
    output_anchor.setVisible(False)

    window._batch_output_anchor = output_anchor
    window._batch_case_output_layout = case_layout

    case_layout.addWidget(window.batch_name_frame, 1)
    case_layout.addWidget(output_anchor)

    bottom_layout.addWidget(list_card)
    bottom_layout.addLayout(case_layout)

    batch_main_splitter.addWidget(bottom_section)
    try:
        batch_main_splitter.setSizes([3, 7])
    except Exception:
        pass

    try:
        proxy = install_drop_card_proxy(drop_card, window.batch_drop_zone)
        proxies = getattr(window, "_drop_card_proxies", None)
        if not isinstance(proxies, list):
            proxies = []
            window._drop_card_proxies = proxies
        proxies.append(proxy)
    except Exception:
        pass

    window.batch_main_splitter = batch_main_splitter
    window.batch_drop_card = drop_card

    output_layout = QHBoxLayout()
    output_layout.setSpacing(0)
    return window.batch_widget, output_layout
