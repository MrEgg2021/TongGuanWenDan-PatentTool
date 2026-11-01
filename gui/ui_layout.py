
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QScrollArea, QSplitter

from gui.ui_layout_impl import (
    APP_STYLESHEET,
    build_modern_shell,
    load_theme_stylesheet,
    build_batch_panel,
    build_run_panel,
    build_single_panel,
    build_preview_page,
    build_data_management_page,
    build_official_docs_page,
    build_active_correction_page,
    build_active_response_page,
    build_correction_page,
    build_response_page,
    build_formal_review_page,
    build_settings_page,
)
from gui.about_ui import build_about_page
from gui.widgets import ElideLabel


def setup_mainwindow_ui(self):
    # 主内容区
    central = QFrame()
    central.setObjectName("MainSurface")
    central_layout = QVBoxLayout(central)
    central_layout.setContentsMargins(0, 0, 0, 0)
    central_layout.setSpacing(0)

    central.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # --- 1. 滚动区域 ---
    scroll_area = QScrollArea()
    scroll_area.setObjectName("MainScrollArea")
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.NoFrame)
    
    scroll_content = QWidget()
    scroll_content.setObjectName("ScrollContent")
    scroll_content_layout = QVBoxLayout(scroll_content)
    scroll_content_layout.setContentsMargins(18, 4, 18, 12)
    scroll_content_layout.setSpacing(12)
    
    # 页面组件构建
    single_path_widget, single_type_widget = build_single_panel(self)
    batch_widget, output_layout = build_batch_panel(self)
    preview_page = build_preview_page(self)
    data_management_page = build_data_management_page(self)
    official_docs_page = build_official_docs_page(self)
    response_page = build_response_page(self)
    correction_page = build_correction_page(self)
    active_response_page = build_active_response_page(self)
    active_correction_page = build_active_correction_page(self)
    formal_review_page = build_formal_review_page(self)
    settings_page = build_settings_page(self)
    about_page = build_about_page(self) # 构建关于页
    about_page.setVisible(False)

    request_form_page = QFrame()
    request_form_page.setObjectName("requestFormPage")
    request_form_page.setVisible(False)
    request_form_root = QVBoxLayout(request_form_page)
    request_form_root.setContentsMargins(0, 0, 0, 0)

    # 组装首页内容 (Home Content)
    content_row = QFrame()
    content_layout = QHBoxLayout(content_row)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(16)

    home_splitter = QSplitter(Qt.Vertical)
    home_splitter.setObjectName("WorkflowHomeSplitter")
    home_splitter.setChildrenCollapsible(False)
    home_splitter.setHandleWidth(8)
    workflow_footer_splitter = QSplitter(Qt.Vertical)
    workflow_footer_splitter.setObjectName("WorkflowFooterSplitter")
    workflow_footer_splitter.setChildrenCollapsible(False)
    workflow_footer_splitter.setHandleWidth(8)
    
    left_card = QFrame()
    left_card.setObjectName("Card")
    left_layout = QVBoxLayout(left_card)
    left_layout.setContentsMargins(16, 16, 16, 16)
    left_layout.addWidget(single_path_widget)
    left_layout.addWidget(batch_widget)
    left_layout.addLayout(output_layout)
    content_layout.addWidget(left_card, 1)

    bottom_card = QFrame()
    bottom_card.setObjectName("Card")
    bottom_layout = QVBoxLayout(bottom_card)
    bottom_layout.setContentsMargins(16, 12, 16, 12)
    bottom_layout.addWidget(single_type_widget)
    home_splitter.addWidget(content_row)
    home_splitter.addWidget(bottom_card)
    home_splitter.setSizes([7, 3])

    # Footer (提示条 + 按钮) - 放在 ScrollArea 内部
    # 这样内容少时跟随内容，内容多时可滚动查看
    warn_frame = QFrame()
    warn_frame.setObjectName("WarningBar")
    warn_layout = QHBoxLayout(warn_frame)
    warn_layout.setContentsMargins(12, 10, 12, 10)
    warn_text = ElideLabel("请选择 Word 文件和转换范围；转换期间会使用 Word 和剪贴板。")
    warn_text.setObjectName("warningBarText")
    warn_text.setAlignment(Qt.AlignCenter)
    warn_layout.addWidget(QLabel("⚠"))
    warn_layout.addWidget(warn_text, 1)
    self.clipboard_warning_label = warn_text

    actions = QFrame()
    actions_layout = QHBoxLayout(actions)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    btn_layout = build_run_panel(self)
    actions_layout.addLayout(btn_layout, 1)
    workflow_footer_panel = QWidget()
    workflow_footer_layout = QVBoxLayout(workflow_footer_panel)
    workflow_footer_layout.setContentsMargins(0, 0, 0, 0)
    workflow_footer_layout.setSpacing(10)
    workflow_footer_layout.addWidget(warn_frame)
    workflow_footer_layout.addWidget(actions)

    workflow_footer_splitter.addWidget(home_splitter)
    workflow_footer_splitter.addWidget(workflow_footer_panel)
    workflow_footer_splitter.setSizes([8, 2])

    # 添加所有页面到滚动布局
    scroll_content_layout.addWidget(workflow_footer_splitter)
    # 注意：这些“整页”组件需要能吃满剩余高度，否则会出现“下方大空白区域未利用”的体验问题。
    # 这里给它们一个较大的 stretch，让它们在可见时优先占用额外空间。
    scroll_content_layout.addWidget(preview_page, 100)
    scroll_content_layout.addWidget(data_management_page, 100)
    scroll_content_layout.addWidget(official_docs_page, 100)
    scroll_content_layout.addWidget(response_page, 100)
    scroll_content_layout.addWidget(correction_page, 100)
    scroll_content_layout.addWidget(active_response_page, 100)
    scroll_content_layout.addWidget(active_correction_page, 100)
    scroll_content_layout.addWidget(formal_review_page, 100)
    scroll_content_layout.addWidget(settings_page, 100)
    scroll_content_layout.addWidget(about_page, 100)  # 关键修正：放入滚动区
    scroll_content_layout.addWidget(request_form_page, 100)
    
    scroll_area.setWidget(scroll_content)
    central_layout.addWidget(scroll_area, 1)

    # 关键属性赋值
    self.about_page = about_page
    self.workflow_home_splitter = home_splitter
    self.workflow_footer_splitter = workflow_footer_splitter
    self._main_scroll_area = scroll_area
    # _workflow_widgets 控制“首页模式”下显示的组件
    # 当切换到 Preview/Settings/About 时，这些组件会被隐藏
    self._workflow_widgets = [workflow_footer_splitter]
    
    self._status_frame = None
    self._conversion_widgets = [workflow_footer_splitter]
    self._preview_page = preview_page
    self._data_management_page = data_management_page
    self._official_docs_page = official_docs_page
    self._response_page = response_page
    self._correction_page = correction_page
    self._active_response_page = active_response_page
    self._active_correction_page = active_correction_page
    self._formal_review_page = formal_review_page
    self._settings_page = settings_page
    self._request_form_page = request_form_page

    shell = build_modern_shell(parent=self, central=central, header_title="", header_subtitle="")
    root_layout = QVBoxLayout()
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)
    root_layout.addWidget(shell)
    self.setLayout(root_layout)
    self._modern_shell = shell

    self._exec_request_form_embedded = None

    # 绑定导航事件
    shell.nav_home.clicked.connect(self._nav_to_home)
    shell.nav_batch.clicked.connect(self._nav_to_batch)
    shell.nav_preview.clicked.connect(self._nav_to_preview)
    shell.nav_response.clicked.connect(self._nav_to_response)
    shell.nav_correction.clicked.connect(self._nav_to_correction)
    shell.nav_active_response.clicked.connect(self._nav_to_active_response)
    shell.nav_active_correction.clicked.connect(self._nav_to_active_correction)
    shell.nav_data_management.clicked.connect(self._nav_to_data_management)
    shell.nav_official_docs.clicked.connect(self._nav_to_official_docs)
    shell.nav_formal_review.clicked.connect(self._nav_to_formal_review)
    shell.nav_settings.clicked.connect(self._nav_to_settings)
    shell.nav_about.clicked.connect(self._nav_to_about)

    theme = load_theme_stylesheet()
    self.setStyleSheet(theme if theme else APP_STYLESHEET)
    self.resize(1000, 720)
    self.on_mode_changed()
    self._batch_total_files = 0
    self._batch_current_index = 0
