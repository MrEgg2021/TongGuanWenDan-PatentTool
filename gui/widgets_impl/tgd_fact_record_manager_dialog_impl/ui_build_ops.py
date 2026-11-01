from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from gui.widgets_impl.tgd_fact_record_manager_widgets import (
    AutoWrapHeaderView,
    FilterComboBox,
    SmartTableDelegate,
    _PressableWidthSplitter,
)


class _UIBuildOpsMixin:
    def _apply_target_geometry(self, target: QWidget | None) -> None:
        if target is None:
            return
        try:
            pos = target.mapToGlobal(QPoint(0, 0))
            self.setGeometry(QRect(pos, target.size()))
        except Exception:
            try:
                self.setGeometry(target.rect())
            except Exception:
                pass

        try:
            card = getattr(self, "_card", None)
            if card is None:
                return
            if self._embedded:
                return
            tw = int(target.size().width())
            th = int(target.size().height())
            w = min(max(1000, int(tw * 0.96)), max(800, tw - 40)) # Wider default
            h = min(max(700, int(th * 0.94)), max(600, th - 40))
            card.setFixedSize(int(w), int(h))
        except Exception:
            pass

    def _init_filter_row_lock(self, table: QTableWidget | None, filter_columns: set[int]) -> None:
        if table is None:
            return
        try:
            col_count = int(table.columnCount())
            if col_count <= 0:
                return
        except Exception:
            return

        try:
            if int(table.rowCount()) < 1:
                table.setRowCount(1)
        except Exception:
            return

        filter_set = set(int(c) for c in (filter_columns or set()))

        try:
            search_item = table.item(0, 0)
            if search_item is None:
                search_item = QTableWidgetItem("")
                table.setItem(0, 0, search_item)
            search_item.setFlags(Qt.ItemIsEnabled)
        except Exception:
            pass

        for col in range(1, col_count):
            if col in filter_set:
                continue
            try:
                w = table.cellWidget(0, col)
                if w is not None:
                    table.removeCellWidget(0, col)
                    try:
                        w.deleteLater()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                item = table.item(0, col)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(0, col, item)
                else:
                    item.setText("")
                item.setFlags(Qt.ItemIsEnabled)
                item.setToolTip("")
            except Exception:
                pass

    def _build_ui(self) -> None:
        overlay_layout = QVBoxLayout(self)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)
        if not self._embedded:
            overlay_layout.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("ModalCard")
        self._card = card
        try:
            if self._embedded:
                card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            else:
                card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        except Exception:
            pass
        # 移除阴影
        # try:
        #     eff = QGraphicsDropShadowEffect(card)
        #     eff.setBlurRadius(28)
        #     eff.setOffset(0, 10)
        #     eff.setColor(QColor(15, 23, 42, 70))
        #     card.setGraphicsEffect(eff)
        # except Exception:
        #     pass

        card_layout = QVBoxLayout(card)

        card_layout.setContentsMargins(0, 0, 0, 16)
        card_layout.setSpacing(0)

        # Title Bar
        titlebar = QFrame(card)
        titlebar.setObjectName("ModalTitleBar")
        tl = QHBoxLayout(titlebar)
        tl.setContentsMargins(16, 12, 12, 12)
        tl.setSpacing(8)

        title = QLabel("常用信息管理")
        title.setObjectName("ModalTitleText")
        title.setProperty("role", "h2")
        tl.addWidget(title, 1)

        btn_close_x = QPushButton("×")
        btn_close_x.setObjectName("ModalCloseButton")
        btn_close_x.setFixedSize(28, 28)
        btn_close_x.setFocusPolicy(Qt.NoFocus)
        try:
            if self._embedded:
                btn_close_x.setVisible(False)
                btn_close_x.clicked.connect(self.backRequested.emit)
            else:
                btn_close_x.clicked.connect(self.reject)
        except Exception:
            pass
        tl.addWidget(btn_close_x, 0, Qt.AlignTop)

        if not self._embedded:
            card_layout.addWidget(titlebar)

        # Main Tabs
        self.tabs = QTabWidget(card)
        self.tabs.setObjectName("requestAppTabs")
        card_layout.addWidget(self.tabs, 1)

        tab_fact = QWidget(self.tabs)
        tab_agency = QWidget(self.tabs)
        self.tabs.addTab(tab_fact, "申请信息")
        self.tabs.addTab(tab_agency, "代理机构信息")

        self._build_fact_tab(tab_fact)
        self._build_agency_tab(tab_agency)

        try:
            self.tabs.currentChanged.connect(self._on_tab_changed)
        except Exception:
            pass

        self._init_tab_actions()

        if self._embedded:
            overlay_layout.addWidget(card, 1)
        else:
            overlay_layout.addWidget(card)

    def _init_tab_actions(self) -> None:
        actions = QWidget(self.tabs)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.btn_refresh = QPushButton("刷新/查询")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.clicked.connect(self._on_query_clicked)

        self.btn_add = QPushButton("新增记录")
        self.btn_add.setObjectName("secondaryButton")
        self.btn_add.clicked.connect(self._on_add_clicked)

        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setObjectName("secondaryButton")
        self.btn_select_all.clicked.connect(self._on_select_all_clicked)

        self.btn_deselect_all = QPushButton("反选")
        self.btn_deselect_all.setObjectName("secondaryButton")
        self.btn_deselect_all.clicked.connect(self._on_deselect_all_clicked)

        self.btn_export = QPushButton("导出")
        self.btn_export.setObjectName("secondaryButton")
        self.btn_export.clicked.connect(self._on_export_clicked)

        self.btn_delete = QPushButton("删除记录")
        self.btn_delete.setObjectName("secondaryButton")
        self.btn_delete.clicked.connect(self._on_delete_clicked)

        self.btn_save = QPushButton("保存修改")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self._on_save_clicked)

        actions_layout.addWidget(self.btn_refresh)
        actions_layout.addWidget(self.btn_add)
        actions_layout.addWidget(self.btn_select_all)
        actions_layout.addWidget(self.btn_deselect_all)
        actions_layout.addWidget(self.btn_export)
        actions_layout.addWidget(self.btn_delete)
        actions_layout.addWidget(self.btn_save)

        # Removed fixed height to allow auto-layout
        # actions.setFixedHeight(40)
        
        try:
            self.tabs.setCornerWidget(actions, Qt.TopRightCorner)

        except Exception:
            try:
                self.tabs.setCornerWidget(actions)
            except Exception:
                pass

    def _build_fact_tab(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = _PressableWidthSplitter(Qt.Horizontal, tab, normal_width=3, pressed_width=4)
        self.splitter.setStyleSheet(
            "QSplitter::handle { background-color: #475569; }"
            "QSplitter::handle:hover { background-color: #334155; }"
            "QSplitter::handle:pressed { background-color: #1f2937; }"
        )
        self.splitter.splitterMoved.connect(lambda *_: self._save_layout_state())
        layout.addWidget(self.splitter, 1)

        # Left Table
        self.fact_table_left = QTableWidget()
        self.fact_table_left.setObjectName("tgdFactManagerLeftTable")
        self.fact_table_left.setColumnCount(15)
        self.fact_table_left.setHorizontalHeaderLabels(
            [
                "",
                "分组名称",
                "申请人名称",
                "申请人类型",
                "证件类型",
                "证件号",
                "地址",
                "邮编",
                "电话",
                "邮箱",
                "联系人姓名",
                "联系人电话",
                "联系人邮箱",
                "联系人地址",
                "联系人邮编",
            ]
        )
        self.fact_table_left.setFrameShape(QFrame.NoFrame)
        self.fact_table_left.setAlternatingRowColors(True)
        self.fact_table_left.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.fact_table_left.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.fact_table_left.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Right Table
        self.fact_table_right = QTableWidget()
        self.fact_table_right.setObjectName("tgdFactManagerRightTable")
        self.fact_table_right.setColumnCount(8)
        self.fact_table_right.setHorizontalHeaderLabels(
            [
                "",
                "发明人姓名",
                "发明人证件类型",
                "发明人证件号",
                "国籍",
                "总委托书编号",
                "代理机构名称",
                "代理机构代码",
            ]
        )
        self.fact_table_right.setFrameShape(QFrame.NoFrame)
        self.fact_table_right.setAlternatingRowColors(True)
        self.fact_table_right.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.fact_table_right.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.splitter.addWidget(self.fact_table_left)
        self.splitter.addWidget(self.fact_table_right)

        # Common Table Setup
        for t in [self.fact_table_left, self.fact_table_right]:
            t.verticalHeader().setVisible(False)
            t.verticalHeader().setDefaultSectionSize(42)
            try:
                t.setViewportMargins(0, 0, 0, 0)
            except Exception:
                pass

            border_left = "1px solid #CBD5E1"
            border_right = "1px solid #CBD5E1"
            if t is self.fact_table_left:
                border_right = "0px"
            elif t is self.fact_table_right:
                border_left = "0px"

            tid = t.objectName()
            header_extra = ""
            if t is self.fact_table_left:
                header_extra = f"QTableWidget#{tid} QHeaderView::section:last {{ border-right: 0px; }}"
            elif t is self.fact_table_right:
                header_extra = f"QTableWidget#{tid} QHeaderView::section:first {{ border-left: 0px; }}"

            t.setStyleSheet(
                f"""
                 QTableWidget#{tid} {{
                     gridline-color: #CBD5E1;
                     border-top: 1px solid #CBD5E1;
                     border-bottom: 1px solid #CBD5E1;
                     border-left: {border_left};
                     border-right: {border_right};
                     padding: 0px;
                     font-size: 13px;
                 }}
                 QTableWidget#{tid} QHeaderView::section {{
                     background-color: #f8fafc;
                     border: 1px solid #CBD5E1;
                     padding: 4px;
                     font-weight: bold;
                 }}
                {header_extra}
                QTableWidget#{tid} QScrollBar:vertical {{
                    margin: 0px;
                }}
                QTableWidget#{tid} QScrollBar:horizontal {{
                    margin: 0px;
                }}
                QTableWidget#{tid}::item {{
                    padding-left: 6px;
                }}
            """
            )

            h = AutoWrapHeaderView(Qt.Horizontal, t)
            t.setHorizontalHeader(h)

            h.setSectionsMovable(True)
            h.setContextMenuPolicy(Qt.CustomContextMenu)
            h.customContextMenuRequested.connect(lambda pos, tbl=t: self._show_header_menu(pos, tbl))
            h.sectionResized.connect(lambda *_: self._save_layout_state())
            h.sectionMoved.connect(lambda *_: self._save_layout_state())

            if t is self.fact_table_left:
                h.setStretchLastSection(True)
            else:
                h.setStretchLastSection(False)
            h.setDefaultSectionSize(100)
            h.setMinimumSectionSize(60)

            t.setColumnWidth(0, 50)
            h.setSectionResizeMode(0, QHeaderView.Fixed)

            t.setRowCount(1)
            search_item = QTableWidgetItem("🔍")
            search_item.setTextAlignment(Qt.AlignCenter)
            search_item.setFlags(Qt.ItemIsEnabled)
            t.setItem(0, 0, search_item)
            t.setRowHeight(0, 48)

            t.itemChanged.connect(self._on_item_changed)
            t.setContextMenuPolicy(Qt.CustomContextMenu)
            t.customContextMenuRequested.connect(lambda pos, tbl=t: self._show_row_menu(pos, tbl))

        sb_left = self.fact_table_left.verticalScrollBar()
        sb_right = self.fact_table_right.verticalScrollBar()
        sb_left.valueChanged.connect(sb_right.setValue)
        sb_right.valueChanged.connect(sb_left.setValue)

        self.fact_table_left.itemSelectionChanged.connect(self._sync_selection_left)
        self.fact_table_right.itemSelectionChanged.connect(self._sync_selection_right)

        self._fact_left_filter_columns = {1, 2, 5}
        self._fact_right_filter_columns = {1, 3, 5, 6, 7}

        self._fact_filter_widgets = {}
        for c, scope, col in [(1, "fact", "group_name"), (2, "fact", "applicant_name"), (5, "fact", "applicant_id_no")]:
            cb = FilterComboBox(self.fact_table_left, scope=scope, col=col)
            cb.filterChanged.connect(self._on_query_clicked)
            self.fact_table_left.setCellWidget(0, c, cb)
            self._fact_filter_widgets[c] = cb

        right_defs = [
            (1, "fact", "inventor_name"),
            (3, "fact", "inventor_id_no"),
            (5, "fact", "power_of_attorney_no"),
            (6, "fact", "agency_ref_name"),
            (7, "fact", "agency_ref_code"),
        ]
        for c, scope, col in right_defs:
            cb = FilterComboBox(self.fact_table_right, scope=scope, col=col)
            cb.filterChanged.connect(self._on_query_clicked)
            self.fact_table_right.setCellWidget(0, c, cb)
            self._fact_filter_widgets[100 + c] = cb

        self._init_filter_row_lock(self.fact_table_left, self._fact_left_filter_columns)
        self._init_filter_row_lock(self.fact_table_right, self._fact_right_filter_columns)

        self.fact_table_left.setItemDelegateForColumn(
            3,
            SmartTableDelegate(self.fact_table_left, ["", "工矿企业", "个人", "事业单位/科研机构"]),
        )
        self.fact_table_left.setItemDelegateForColumn(
            4,
            SmartTableDelegate(self.fact_table_left, ["", "统一社会信用代码", "居民身份证", "其他"]),
        )
        self.fact_table_right.setItemDelegateForColumn(
            2,
            SmartTableDelegate(self.fact_table_right, ["", "居民身份证", "护照", "其他"]),
        )

        self.splitter.setSizes([850, 950])

    def _build_agency_tab(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        self.agency_table = QTableWidget(tab)
        self.agency_table.setColumnCount(6)
        self.agency_table.setHorizontalHeaderLabels(
            ["", "代理机构名称", "代理机构代码", "代理师姓名", "代理师资格证号", "代理师电话"]
        )
        self.agency_table.setFrameShape(QFrame.NoFrame)
        self.agency_table.setAlternatingRowColors(True)
        self.agency_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.agency_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.agency_table, 1)

        t = self.agency_table
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(42)

        t.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #CBD5E1;
                border: 1px solid #CBD5E1;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                border: 1px solid #CBD5E1;
                padding: 4px;
                font-weight: bold;
            }
            QTableWidget::item {
                padding-left: 6px;
            }
        """
        )

        h = AutoWrapHeaderView(Qt.Horizontal, t)
        t.setHorizontalHeader(h)
        h.setSectionsMovable(True)
        h.setContextMenuPolicy(Qt.CustomContextMenu)
        h.customContextMenuRequested.connect(lambda pos, tbl=t: self._show_header_menu(pos, tbl))
        h.sectionResized.connect(lambda *_: self._save_layout_state())
        h.sectionMoved.connect(lambda *_: self._save_layout_state())
        h.setStretchLastSection(False)
        h.setDefaultSectionSize(120)
        h.setMinimumSectionSize(60)

        t.setColumnWidth(0, 50)
        h.setSectionResizeMode(0, QHeaderView.Fixed)

        t.setRowCount(1)
        search_item = QTableWidgetItem("🔍")
        search_item.setTextAlignment(Qt.AlignCenter)
        search_item.setFlags(Qt.ItemIsEnabled)
        t.setItem(0, 0, search_item)
        t.setRowHeight(0, 48)

        t.itemChanged.connect(self._on_item_changed)
        t.setContextMenuPolicy(Qt.CustomContextMenu)
        t.customContextMenuRequested.connect(lambda pos, tbl=t: self._show_row_menu(pos, tbl))

        self._agency_filter_columns = {1, 2, 3}
        self._agency_filter_widgets = {}
        for c, col in [(1, "agency_name"), (2, "agency_code"), (3, "agent_name")]:
            cb = FilterComboBox(t, scope="agency", col=col)
            cb.filterChanged.connect(self._on_query_clicked)
            t.setCellWidget(0, c, cb)
            self._agency_filter_widgets[c] = cb

        self._init_filter_row_lock(t, self._agency_filter_columns)

    def _sync_selection_left(self):
        self._sync_selection(self.fact_table_left, self.fact_table_right)

    def _sync_selection_right(self):
        self._sync_selection(self.fact_table_right, self.fact_table_left)

    def _sync_selection(self, source, target):
        if not source or not target:
            return
        source_rows = set(i.row() for i in source.selectedItems())
        target_rows = set(i.row() for i in target.selectedItems())
        if source_rows == target_rows:
            return

        target.blockSignals(True)
        target.clearSelection()
        for r in source_rows:
            target.selectRow(r)
        target.blockSignals(False)
