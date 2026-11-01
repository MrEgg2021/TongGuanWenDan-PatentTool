from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QLayout,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import GraphicCheckBox

TOPBAR_ROW_HEIGHT = 34


class _FlowLayout(QLayout):
    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 8, v_spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._h_spacing = int(h_spacing)
        self._v_spacing = int(v_spacing)
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):  # type: ignore[override]
        self._items.append(item)

    def count(self):  # type: ignore[override]
        return len(self._items)

    def itemAt(self, index):  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # type: ignore[override]
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):  # type: ignore[override]
        return True

    def heightForWidth(self, width):  # type: ignore[override]
        return self._do_layout(QRect(0, 0, int(width), 0), test_only=True)

    def setGeometry(self, rect):  # type: ignore[override]
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):  # type: ignore[override]
        return self.minimumSize()

    def minimumSize(self):  # type: ignore[override]
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0
        available_width = max(1, int(effective.width()))
        max_right = int(effective.x()) + available_width
        for item in self._items:
            hint = item.sizeHint()
            item_w = min(max(1, int(hint.width())), available_width)
            item_h = int(hint.height())
            try:
                if bool(item.hasHeightForWidth()):
                    item_h = max(item_h, int(item.heightForWidth(item_w)))
            except Exception:
                pass
            widget = None
            try:
                widget = item.widget()
            except Exception:
                widget = None
            if widget is not None:
                try:
                    if bool(widget.hasHeightForWidth()):
                        item_h = max(item_h, int(widget.heightForWidth(item_w)))
                except Exception:
                    pass
            next_x = x + item_w
            if line_height > 0 and next_x > max_right and x > effective.x():
                x = effective.x()
                y += line_height + self._v_spacing
                next_x = x + item_w
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(item_w, item_h)))
            x = next_x + self._h_spacing
            line_height = max(line_height, item_h)
        return int(y + line_height - rect.y() + margins.bottom())


def _build_table(columns: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.verticalHeader().setVisible(False)
    try:
        table.horizontalHeader().setStretchLastSection(True)
    except Exception:
        pass
    return table


def _build_text_view(placeholder: str = "") -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    if placeholder:
        edit.setPlaceholderText(placeholder)
    return edit


def _build_readonly_plain(placeholder: str = "") -> QPlainTextEdit:
    edit = QPlainTextEdit()
    edit.setReadOnly(True)
    if placeholder:
        edit.setPlaceholderText(placeholder)
    return edit


def build_formal_review_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("formalReviewPage")
    page.setProperty("dense", True)
    page.setVisible(False)

    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(8)

    title = QLabel("形式审查")
    title.setProperty("role", "h1")
    root.addWidget(title)

    top_bar = QFrame()
    top_bar.setObjectName("Card")
    top_bar_layout = QVBoxLayout(top_bar)
    top_bar_layout.setContentsMargins(10, 8, 10, 8)
    top_bar_layout.setSpacing(6)

    top_controls = QWidget(top_bar)
    top_layout = _FlowLayout(top_controls, margin=0, h_spacing=8, v_spacing=6)
    top_layout.setContentsMargins(0, 0, 0, 0)

    mode_word_radio = GraphicCheckBox("Word 文件")
    mode_plain_radio = GraphicCheckBox("纯文本输入")
    mode_word_radio.setChecked(True)
    mode_plain_radio.setChecked(False)
    mode_word_radio.setFixedHeight(TOPBAR_ROW_HEIGHT)
    mode_plain_radio.setFixedHeight(TOPBAR_ROW_HEIGHT)

    mode_group = QButtonGroup(top_bar)
    mode_group.setExclusive(True)
    mode_group.addButton(mode_word_radio)
    mode_group.addButton(mode_plain_radio)

    mode_hint = QLabel("输入模式：")
    profile_label = QLabel("词库方案：")
    mode_hint.setFixedHeight(TOPBAR_ROW_HEIGHT)
    profile_label.setFixedHeight(TOPBAR_ROW_HEIGHT)
    mode_hint.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    profile_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    profile_combo = QComboBox()
    profile_combo.setObjectName("FormalReviewWordlistProfileCombo")
    profile_combo.setMinimumWidth(96)
    profile_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    profile_combo.setFixedHeight(TOPBAR_ROW_HEIGHT)

    file_edit = QLineEdit()
    file_edit.setReadOnly(True)
    file_edit.setPlaceholderText("请选择 Word 文件（伴侣模式）或切换到纯文本输入模式")
    file_edit.setMinimumWidth(0)
    file_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    file_edit.setFixedHeight(TOPBAR_ROW_HEIGHT)

    choose_btn = QPushButton("选择文件")
    parse_btn = QPushButton("解析")
    btn_start = QPushButton("开始审查")
    btn_export_report = QPushButton("导出报告")
    btn_settings = QPushButton("设置")
    for _btn in (choose_btn, parse_btn, btn_start, btn_export_report, btn_settings):
        _btn.setMinimumWidth(0)
        _btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        _btn.setFixedHeight(TOPBAR_ROW_HEIGHT)
    word_state_label = QLabel("Word状态：未连接")
    dirty_state_label = QLabel("文档变更：未知")
    word_state_label.setWordWrap(True)
    dirty_state_label.setWordWrap(True)
    word_state_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    dirty_state_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    word_state_label.setMinimumHeight(TOPBAR_ROW_HEIGHT)
    dirty_state_label.setMinimumHeight(TOPBAR_ROW_HEIGHT)
    word_state_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    dirty_state_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    top_layout.addWidget(mode_hint)
    top_layout.addWidget(mode_word_radio)
    top_layout.addWidget(mode_plain_radio)
    top_layout.addWidget(profile_label)
    top_layout.addWidget(profile_combo)
    top_layout.addWidget(file_edit)
    top_layout.addWidget(choose_btn)
    top_layout.addWidget(parse_btn)
    top_layout.addWidget(btn_start)
    top_layout.addWidget(btn_export_report)
    top_layout.addWidget(btn_settings)

    top_status = QWidget(top_bar)
    top_status_layout = QVBoxLayout(top_status)
    top_status_layout.setContentsMargins(0, 0, 0, 0)
    top_status_layout.setSpacing(2)
    top_status_layout.addWidget(word_state_label)
    top_status_layout.addWidget(dirty_state_label)

    top_bar_layout.addWidget(top_controls)
    top_bar_layout.addWidget(top_status)
    root.addWidget(top_bar)

    workspace_splitter = QSplitter(Qt.Horizontal)
    workspace_splitter.setObjectName("FormalReviewWorkspaceSplitter")
    root.addWidget(workspace_splitter, 1)

    left_panel = QFrame()
    left_panel.setObjectName("Card")
    left_layout = QVBoxLayout(left_panel)
    left_layout.setContentsMargins(10, 10, 10, 10)
    left_layout.setSpacing(6)
    left_layout.addWidget(QLabel("审查结果"))

    results_tree = QTreeWidget()
    results_tree.setObjectName("FormalReviewResultsTree")
    results_tree.setHeaderLabels(["类型/位置", "严重度", "原因", "忽略"])
    results_tree.setIndentation(10)
    results_tree.setRootIsDecorated(True)
    results_tree.setItemsExpandable(True)
    results_tree.setExpandsOnDoubleClick(False)
    results_tree.setUniformRowHeights(False)
    results_tree.setWordWrap(True)
    results_tree.setTextElideMode(Qt.ElideNone)
    results_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    results_tree.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
    try:
        header = results_tree.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(36)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        results_tree.setColumnWidth(0, 120)
        results_tree.setColumnWidth(1, 80)
        results_tree.setColumnWidth(2, 220)
        results_tree.setColumnWidth(3, 80)
    except Exception:
        pass
    left_layout.addWidget(results_tree, 1)
    workspace_splitter.addWidget(left_panel)

    center_panel = QFrame()
    center_panel.setObjectName("Card")
    center_layout = QVBoxLayout(center_panel)
    center_layout.setContentsMargins(10, 10, 10, 10)
    center_layout.setSpacing(6)

    tabs = QTabWidget()

    claims_tab = QWidget()
    claims_layout = QVBoxLayout(claims_tab)
    claims_layout.setContentsMargins(0, 0, 0, 0)
    claims_layout.setSpacing(6)

    claims_input_label = QLabel("权利要求书原文输入（纯文本模式）")
    claims_input_text = _build_text_view("在纯文本模式下输入权利要求书，按句号“。”切分")
    claims_tree_label = QLabel("权利要求折叠视图（可展开/收起）")

    claims_header_row = QHBoxLayout()
    claims_header_row.setContentsMargins(0, 0, 0, 0)
    claims_header_row.setSpacing(6)
    claims_header_row.addWidget(claims_tree_label)
    claims_header_row.addStretch(1)

    claims_tree = QTreeWidget()
    claims_tree.setObjectName("FormalReviewClaimsTree")
    claims_tree.setHeaderHidden(True)
    claims_tree.setColumnCount(1)
    claims_tree.setRootIsDecorated(True)
    claims_tree.setItemsExpandable(True)
    claims_tree.setAlternatingRowColors(True)
    claims_tree.setUniformRowHeights(False)
    claims_tree.setIndentation(12)

    claims_layout.addWidget(claims_input_label)
    claims_layout.addWidget(claims_input_text, 1)
    claims_layout.addLayout(claims_header_row)
    claims_layout.addWidget(claims_tree, 2)

    desc_tab = QWidget()
    desc_layout = QVBoxLayout(desc_tab)
    desc_layout.setContentsMargins(0, 0, 0, 0)
    desc_layout.setSpacing(6)
    desc_text = _build_text_view("说明书正文")
    desc_layout.addWidget(desc_text, 1)

    abstract_tab = QWidget()
    abstract_layout = QVBoxLayout(abstract_tab)
    abstract_layout.setContentsMargins(0, 0, 0, 0)
    abstract_layout.setSpacing(6)
    abstract_count_label = QLabel("摘要字数：0/300（合规）")
    abstract_count_label.setObjectName("FormalReviewAbstractCountLabel")
    abstract_header_row = QHBoxLayout()
    abstract_header_row.setContentsMargins(0, 0, 0, 0)
    abstract_header_row.setSpacing(6)
    abstract_header_row.addWidget(abstract_count_label)
    abstract_text = _build_text_view("说明书摘要")
    abstract_layout.addLayout(abstract_header_row)
    abstract_layout.addWidget(abstract_text, 1)

    drawings_tab = QWidget()
    drawings_layout = QVBoxLayout(drawings_tab)
    drawings_layout.setContentsMargins(0, 0, 0, 0)
    drawings_layout.setSpacing(6)
    drawings_text = _build_text_view("说明书附图")
    drawings_layout.addWidget(drawings_text, 1)

    tabs.addTab(claims_tab, "权利要求书")
    tabs.addTab(desc_tab, "说明书")
    tabs.addTab(abstract_tab, "说明书摘要")
    tabs.addTab(drawings_tab, "说明书附图")
    center_layout.addWidget(tabs, 1)

    claims_metrics_label = QLabel("权利要求统计（字数 / 附图标记）")
    claims_table = _build_table(["序号", "字数", "附图标记"])
    claims_table.setVisible(False)
    claims_metrics_label.setVisible(False)
    center_layout.addWidget(claims_metrics_label)
    center_layout.addWidget(claims_table)

    hidden_container = QWidget()
    hidden_container.setVisible(False)
    hidden_layout = QVBoxLayout(hidden_container)
    hidden_layout.setContentsMargins(0, 0, 0, 0)
    hidden_layout.setSpacing(0)
    claims_rule_table = _build_table(["规则/位置", "严重度", "说明", "忽略"])
    claims_forbidden_table = _build_table(["词语", "位置", "说明", "忽略"])
    claims_sensitive_table = _build_table(["词语", "位置", "说明", "忽略"])
    desc_rule_table = _build_table(["规则/位置", "严重度", "说明", "忽略"])
    desc_forbidden_table = _build_table(["词语", "位置", "说明", "忽略"])
    desc_sensitive_table = _build_table(["词语", "位置", "说明", "忽略"])
    abstract_rule_table = _build_table(["规则/位置", "严重度", "说明", "忽略"])
    summary_table = _build_table(["规则/位置", "严重度", "描述", "忽略"])
    for table in (
        claims_rule_table,
        claims_forbidden_table,
        claims_sensitive_table,
        desc_rule_table,
        desc_forbidden_table,
        desc_sensitive_table,
        abstract_rule_table,
        summary_table,
    ):
        hidden_layout.addWidget(table)
    center_layout.addWidget(hidden_container, 0)

    workspace_splitter.addWidget(center_panel)

    right_panel = QFrame()
    right_panel.setObjectName("Card")
    right_layout = QVBoxLayout(right_panel)
    right_layout.setContentsMargins(10, 10, 10, 10)
    right_layout.setSpacing(6)

    right_splitter = QSplitter(Qt.Vertical)
    right_splitter.setObjectName("FormalReviewRightPanelSplitter")
    right_layout.addWidget(right_splitter, 1)

    marker_section = QWidget()
    marker_layout = QVBoxLayout(marker_section)
    marker_layout.setContentsMargins(0, 0, 0, 0)
    marker_layout.setSpacing(6)

    marker_label = QLabel("标号说明")
    marker_edit = QPlainTextEdit()
    marker_edit.setPlaceholderText("图例说明格式：1、XXX；2、XXX；3、XXX")
    marker_edit.setMinimumHeight(80)
    marker_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    marker_apply_btn = QPushButton("生成附图标记修订")
    marker_apply_btn.setMinimumWidth(0)
    marker_apply_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    marker_layout.addWidget(marker_label)
    marker_layout.addWidget(marker_edit, 1)
    marker_layout.addWidget(marker_apply_btn)
    right_splitter.addWidget(marker_section)

    detail_section = QWidget()
    detail_layout = QVBoxLayout(detail_section)
    detail_layout.setContentsMargins(0, 0, 0, 0)
    detail_layout.setSpacing(6)

    issue_meta_label = QLabel("未选择问题")
    issue_meta_label.setWordWrap(True)
    issue_ignore_toggle = QCheckBox("误查（忽略此问题）")
    sync_digest_label = QLabel("最近同步：暂无")
    sync_digest_label.setObjectName("FormalReviewSyncDigestLabel")
    sync_digest_label.setWordWrap(True)
    sync_digest_label.setStyleSheet("color:#64748B; font-size:12px;")

    issue_preview = QTextBrowser()
    issue_preview.setOpenExternalLinks(False)
    issue_preview.setPlaceholderText("点击左侧审查结果后显示命中前后文与精确定位")
    context_before = _build_readonly_plain("问题前文")
    context_hit = QTextBrowser()
    context_after = _build_readonly_plain("问题后文")
    context_before.setVisible(False)
    context_hit.setVisible(False)
    context_after.setVisible(False)

    detail_layout.addWidget(QLabel("问题详情"))
    detail_layout.addWidget(issue_meta_label)
    detail_layout.addWidget(issue_ignore_toggle)
    detail_layout.addWidget(sync_digest_label)
    detail_layout.addWidget(QLabel("命中预览"))
    detail_layout.addWidget(issue_preview, 1)
    right_splitter.addWidget(detail_section)

    try:
        right_splitter.setSizes([220, 280])
    except Exception:
        pass

    workspace_splitter.addWidget(right_panel)

    try:
        workspace_splitter.setSizes([260, 520, 300])
    except Exception:
        pass

    try:
        choose_btn.clicked.connect(window.on_formal_review_choose_file)
    except Exception:
        pass
    try:
        parse_btn.clicked.connect(window.on_formal_review_parse)
    except Exception:
        pass
    try:
        btn_start.clicked.connect(window.on_formal_review_start_check)
    except Exception:
        pass
    try:
        btn_export_report.clicked.connect(window.on_formal_review_export_report)
    except Exception:
        pass
    try:
        marker_apply_btn.clicked.connect(window.on_formal_review_apply_marker_revision_direct)
    except Exception:
        pass
    try:
        btn_settings.clicked.connect(window.on_formal_review_open_settings)
    except Exception:
        pass
    try:
        profile_combo.currentTextChanged.connect(window.on_formal_review_wordlist_profile_changed)
    except Exception:
        pass
    try:
        mode_word_radio.toggled.connect(window.on_formal_review_mode_changed)
    except Exception:
        pass
    try:
        mode_plain_radio.toggled.connect(window.on_formal_review_mode_changed)
    except Exception:
        pass
    try:
        tabs.currentChanged.connect(window.on_formal_review_tab_changed)
    except Exception:
        pass
    try:
        results_tree.itemClicked.connect(window.on_formal_review_summary_item_clicked)
    except Exception:
        pass
    try:
        claims_tree.itemClicked.connect(window.on_formal_review_claim_tree_item_clicked)
    except Exception:
        pass

    for table in (
        claims_rule_table,
        claims_forbidden_table,
        claims_sensitive_table,
        desc_rule_table,
        desc_forbidden_table,
        desc_sensitive_table,
        abstract_rule_table,
    ):
        try:
            table.cellClicked.connect(window.on_formal_review_issue_table_cell_clicked)
        except Exception:
            pass
    try:
        summary_table.cellClicked.connect(window.on_formal_review_summary_table_cell_clicked)
    except Exception:
        pass
    try:
        claims_table.cellClicked.connect(window.on_formal_review_claim_row_clicked)
    except Exception:
        pass

    window.formal_review_page = page
    window.formal_review_top_toolbar = top_bar
    window.formal_review_workspace_splitter = workspace_splitter
    window.formal_review_main_splitter = workspace_splitter
    window.formal_review_left_panel = left_panel
    window.formal_review_center_panel = center_panel
    window.formal_review_plain_center_panel = center_panel
    window.formal_review_center_panel_attached = True
    window.formal_review_right_panel = right_panel
    window.formal_review_right_splitter = right_splitter
    window.formal_review_marker_section = marker_section
    window.formal_review_detail_section = detail_section
    window.formal_review_tabs = tabs

    window.formal_review_file_edit = file_edit
    window.formal_review_choose_button = choose_btn
    window.formal_review_connect_word_button = None
    window.formal_review_parse_button = parse_btn
    window.formal_review_refresh_button = None
    window.formal_review_reparse_button = parse_btn
    window.formal_review_diff_preview_toggle = None
    window.formal_review_start_button = btn_start
    window.formal_review_export_report_button = btn_export_report
    window.formal_review_build_revision_plan_button = None
    window.formal_review_apply_revision_plan_button = None
    window.formal_review_apply_marker_button = marker_apply_btn
    window.formal_review_manage_wordlists_button = None
    window.formal_review_settings_button = btn_settings
    window.formal_review_toggle_left_button = None
    window.formal_review_toggle_right_button = None
    window.formal_review_mode_word_radio = mode_word_radio
    window.formal_review_mode_plain_radio = mode_plain_radio
    window.formal_review_mode_group = mode_group
    window.formal_review_wordlist_profile_combo = profile_combo
    window.formal_review_companion_review_radio = None
    window.formal_review_companion_apply_radio = None
    window.formal_review_companion_mode_group = None
    window.formal_review_word_state_label = word_state_label
    window.formal_review_dirty_state_label = dirty_state_label

    window.formal_review_marker_edit = marker_edit
    window.formal_review_companion_marker_edit = marker_edit
    window.formal_review_companion_apply_marker_button = marker_apply_btn
    window.formal_review_author_edit = None

    window.formal_review_results_tree = results_tree
    window.formal_review_companion_results_tree = results_tree
    window.formal_review_summary_tree = results_tree
    window.formal_review_summary_table = summary_table
    window.formal_review_summary_tabs = None

    window.formal_review_issue_meta_label = issue_meta_label
    window.formal_review_issue_ignore_toggle = issue_ignore_toggle
    window.formal_review_sync_digest_label = sync_digest_label
    window.formal_review_issue_preview = issue_preview
    window.formal_review_issue_context_before = context_before
    window.formal_review_issue_context_hit = context_hit
    window.formal_review_issue_context_after = context_after

    window.formal_review_claims_input_label = claims_input_label
    window.formal_review_claims_input_text = claims_input_text
    window.formal_review_claims_changed_only_toggle = None
    window.formal_review_claims_tree = claims_tree
    window.formal_review_claims_text = claims_input_text
    window.formal_review_claims_table = claims_table
    window.formal_review_claim_metrics_table = claims_table
    window.formal_review_claim_metrics_label = claims_metrics_label

    window.formal_review_description_text = desc_text
    window.formal_review_description_changed_only_toggle = None
    window.formal_review_description_stack = None
    window.formal_review_description_preview = None
    window.formal_review_description_no_change_label = None

    window.formal_review_abstract_text = abstract_text
    window.formal_review_abstract_changed_only_toggle = None
    window.formal_review_abstract_stack = None
    window.formal_review_abstract_preview = None
    window.formal_review_abstract_no_change_label = None
    window.formal_review_abstract_count_label = abstract_count_label

    window.formal_review_drawings_text = drawings_text
    window.formal_review_drawings_changed_only_toggle = None
    window.formal_review_drawings_stack = None
    window.formal_review_drawings_preview = None
    window.formal_review_drawings_no_change_label = None

    window.formal_review_claims_rule_table = claims_rule_table
    window.formal_review_claims_forbidden_table = claims_forbidden_table
    window.formal_review_claims_sensitive_table = claims_sensitive_table
    window.formal_review_description_rule_table = desc_rule_table
    window.formal_review_description_forbidden_table = desc_forbidden_table
    window.formal_review_description_sensitive_table = desc_sensitive_table
    window.formal_review_abstract_rule_table = abstract_rule_table

    return page
