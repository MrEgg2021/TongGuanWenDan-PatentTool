from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import SingleFileDropWidget
from gui.widgets import install_drop_card_proxy
def build_task_panel(window, tabs):
    task_tab = QWidget()
    task_root = QVBoxLayout(task_tab)
    task_root.setContentsMargins(0, 0, 0, 0)
    task_root.setSpacing(8)

    task_vertical_splitter = QSplitter(Qt.Vertical)
    task_vertical_splitter.setObjectName("OfficialDocsTaskVerticalSplitter")
    task_vertical_splitter.setChildrenCollapsible(False)
    task_root.addWidget(task_vertical_splitter, 1)

    top_section = QWidget()
    top_layout = QVBoxLayout(top_section)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(0)

    drop_card = QFrame()
    drop_card.setObjectName("Card")
    drop_layout = QVBoxLayout(drop_card)
    drop_layout.setContentsMargins(8, 8, 8, 8)
    drop_layout.setSpacing(6)

    drop_zone = SingleFileDropWidget()
    drop_zone.setObjectName("OfficialDocsDropZone")
    drop_zone.setMinimumHeight(64)
    drop_zone.setMaximumHeight(88)

    drop_zone_layout = QVBoxLayout(drop_zone)
    drop_zone_layout.setContentsMargins(12, 6, 12, 6)
    drop_zone_layout.setSpacing(6)
    drop_hint = QLabel("拖拽 ZIP/文件夹到此处，或点击选择 ZIP")
    drop_hint.setAlignment(Qt.AlignCenter)
    drop_hint.setProperty("role", "label")
    drop_hint.setProperty("emphasis", True)
    drop_zone_layout.addStretch(1)
    drop_zone_layout.addWidget(drop_hint)
    drop_zone_layout.addStretch(1)
    drop_layout.addWidget(drop_zone)

    drop_actions = QHBoxLayout()
    drop_actions.setContentsMargins(0, 0, 0, 0)
    drop_actions.setSpacing(6)
    btn_choose_zip = QPushButton("选择ZIP...")
    btn_choose_zip.setObjectName("Secondary")
    btn_choose_folder = QPushButton("选择文件夹...")
    btn_choose_folder.setObjectName("Secondary")
    btn_toggle_task_details = QPushButton("显示列表/详情（0）")
    btn_toggle_task_details.setObjectName("Secondary")
    drop_actions.addWidget(btn_choose_zip)
    drop_actions.addWidget(btn_choose_folder)
    drop_actions.addWidget(btn_toggle_task_details)
    drop_actions.addStretch(1)
    drop_layout.addLayout(drop_actions)
    top_layout.addWidget(drop_card)
    task_vertical_splitter.addWidget(top_section)

    bottom_section = QWidget()
    bottom_layout = QVBoxLayout(bottom_section)
    bottom_layout.setContentsMargins(0, 0, 0, 0)
    bottom_layout.setSpacing(8)

    body_splitter = QSplitter(Qt.Horizontal)
    body_splitter.setObjectName("OfficialDocsTaskSplitter")
    body_splitter.setChildrenCollapsible(False)

    list_card = QFrame()
    list_card.setObjectName("Card")
    list_layout = QVBoxLayout(list_card)
    list_layout.setContentsMargins(8, 8, 8, 8)
    list_layout.setSpacing(6)

    list_header = QHBoxLayout()
    list_header.setContentsMargins(0, 0, 0, 0)
    list_header.setSpacing(6)
    list_title = QLabel("通知书列表")
    list_title.setProperty("role", "label")
    list_title.setProperty("emphasis", True)
    list_count = QLabel("0 项")
    list_count.setProperty("role", "caption")
    list_count.setProperty("emphasis", True)
    btn_clear_items = QPushButton("清空")
    btn_clear_items.setObjectName("Secondary")
    list_header.addWidget(list_title)
    list_header.addWidget(list_count)
    list_header.addStretch(1)
    list_header.addWidget(btn_clear_items)
    list_layout.addLayout(list_header)

    search_edit = QLineEdit()
    search_edit.setObjectName("OfficialDocsSearch")
    search_edit.setPlaceholderText("搜索（文件名/申请号/通知书名称）")
    list_layout.addWidget(search_edit)

    tree = QTreeWidget()
    tree.setObjectName("OfficialDocsTree")
    tree.setHeaderHidden(True)
    tree.setSelectionMode(QAbstractItemView.SingleSelection)
    tree.setUniformRowHeights(False)
    tree.setIndentation(6)
    tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    tree.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    tree.setTextElideMode(Qt.ElideNone)
    header = tree.header()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(0, QHeaderView.Interactive)
    list_layout.addWidget(tree, 1)
    list_card.setMinimumWidth(320)
    body_splitter.addWidget(list_card)

    detail_card = QFrame()
    detail_card.setObjectName("Card")
    detail_layout = QVBoxLayout(detail_card)
    detail_layout.setContentsMargins(8, 8, 8, 8)
    detail_layout.setSpacing(6)

    detail_header = QHBoxLayout()
    detail_header.setContentsMargins(0, 0, 0, 0)
    detail_header.setSpacing(6)
    detail_title = QLabel("命名预览 / 处理结果")
    detail_title.setProperty("role", "label")
    detail_title.setProperty("emphasis", True)
    detail_header.addWidget(detail_title)
    detail_header.addStretch(1)
    detail_layout.addLayout(detail_header)

    current_label = QLabel("未选择通知书")
    current_label.setProperty("role", "caption")
    detail_layout.addWidget(current_label)

    meta_label = QLabel("")
    meta_label.setObjectName("OfficialDocsMetaText")
    meta_label.setProperty("role", "caption")
    meta_label.setWordWrap(True)
    meta_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    detail_layout.addWidget(meta_label)

    pdf_sources_title = QLabel("PDF来源")
    pdf_sources_title.setProperty("role", "caption")
    pdf_sources_title.setProperty("emphasis", True)
    detail_layout.addWidget(pdf_sources_title)

    pdf_sources_text = QLabel("")
    pdf_sources_text.setObjectName("OfficialDocsPdfSourcesText")
    pdf_sources_text.setProperty("role", "caption")
    pdf_sources_text.setWordWrap(True)
    pdf_sources_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
    detail_layout.addWidget(pdf_sources_text)

    one_line_preview = QLabel("")
    one_line_preview.setObjectName("OfficialDocsOneLinePreview")
    one_line_preview.setProperty("role", "caption")
    one_line_preview.setWordWrap(True)
    one_line_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
    detail_layout.addWidget(one_line_preview)

    error_label = QLabel("")
    error_label.setObjectName("OfficialDocsValidationError")
    error_label.setProperty("role", "caption")
    error_label.setWordWrap(True)
    error_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    detail_layout.addWidget(error_label)

    detail_card.setMinimumWidth(420)
    body_splitter.addWidget(detail_card)
    body_splitter.setStretchFactor(0, 2)
    body_splitter.setStretchFactor(1, 3)
    body_splitter.setSizes([520, 860])
    body_splitter.setVisible(False)
    bottom_layout.addWidget(body_splitter, 1)
    task_footer = QFrame()
    task_footer.setObjectName("OfficialDocsTaskFooter")
    task_footer_row = QHBoxLayout(task_footer)
    task_footer_row.setContentsMargins(0, 0, 0, 0)
    task_footer_row.setSpacing(8)
    task_footer_row.addStretch(1)
    btn_start = QPushButton("开始处理")
    btn_start.setObjectName("Primary")
    btn_start.setMinimumWidth(220)
    task_footer_row.addWidget(btn_start, 0)
    task_footer_row.addStretch(1)
    bottom_layout.addWidget(task_footer, 0)

    task_vertical_splitter.addWidget(bottom_section)
    try:
        task_vertical_splitter.setSizes([2, 8])
    except Exception:
        pass

    try:
        proxy = install_drop_card_proxy(drop_card, drop_zone)
        proxies = getattr(window, "_drop_card_proxies", None)
        if not isinstance(proxies, list):
            proxies = []
            window._drop_card_proxies = proxies
        proxies.append(proxy)
    except Exception:
        pass
    window.official_docs_task_vertical_splitter = task_vertical_splitter
    window.official_docs_task_drop_card = drop_card

    tabs.addTab(task_tab, "处理任务")

    return {
        "drop_zone": drop_zone,
        "btn_choose_zip": btn_choose_zip,
        "btn_choose_folder": btn_choose_folder,
        "btn_clear_items": btn_clear_items,
        "btn_toggle_task_details": btn_toggle_task_details,
        "search_edit": search_edit,
        "tree": tree,
        "btn_start": btn_start,
        "list_count": list_count,
        "body_splitter": body_splitter,
        "current_label": current_label,
        "meta_label": meta_label,
        "pdf_sources_text": pdf_sources_text,
        "one_line_preview": one_line_preview,
        "error_label": error_label,
        "task_footer": task_footer,
        "task_vertical_splitter": task_vertical_splitter,
    }


__all__ = ["build_task_panel"]
