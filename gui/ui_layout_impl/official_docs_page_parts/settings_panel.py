from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class OfficialDocsNamingTypeTree(QTreeWidget):
    def _branch_click_rect(self, item: QTreeWidgetItem):
        option = QStyleOptionViewItem()
        option.initFrom(self)
        option.rect = self.visualItemRect(item)
        if not option.rect.isValid():
            return option.rect
        branch_width = max(12, min(self.indentation(), option.rect.left()))
        branch_left = max(0, option.rect.left() - branch_width)
        return option.rect.adjusted(-(option.rect.left() - branch_left), 0, -(option.rect.width() - branch_width), 0)

    def _checkbox_hit_item(self, pos) -> QTreeWidgetItem | None:
        item = self.itemAt(pos)
        if item is None or not bool(item.flags() & Qt.ItemIsUserCheckable):
            return None

        option = QStyleOptionViewItem()
        option.initFrom(self)
        option.rect = self.visualItemRect(item)
        if not option.rect.isValid():
            return None
        option.features |= QStyleOptionViewItem.HasCheckIndicator
        indicator_rect = self.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, option, self)
        if indicator_rect.contains(pos):
            return item
        return None

    def _branch_hit_item(self, pos) -> QTreeWidgetItem | None:
        item = self.itemAt(pos)
        if item is None or item.childCount() <= 0:
            return None

        disclosure_rect = self._branch_click_rect(item)
        if disclosure_rect.contains(pos):
            return item
        return None

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)

        preserve_item = self._branch_hit_item(pos)
        if preserve_item is not None:
            current_item = self.currentItem()
            self._suppress_focus_selection_change = True
            try:
                super().mousePressEvent(event)
                with QSignalBlocker(self):
                    self.clearSelection()
                    if current_item is not None:
                        current_item.setSelected(True)
                        self.setCurrentItem(current_item)
            finally:
                self._suppress_focus_selection_change = False
            return

        checkbox_item = self._checkbox_hit_item(pos)
        super().mousePressEvent(event)
        if checkbox_item is not None and self.currentItem() is not checkbox_item:
            self.setCurrentItem(checkbox_item)


class _AliasNoticeNameDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):  # type: ignore[override]
        if index.column() != 1:
            return super().createEditor(parent, option, index)
        combo = QComboBox(parent)
        combo.setEditable(False)
        combo.setInsertPolicy(QComboBox.NoInsert)
        options = index.data(Qt.UserRole)
        if isinstance(options, (list, tuple)):
            for option_text in options:
                text = str(option_text or "").strip()
                if text and combo.findText(text) < 0:
                    combo.addItem(text)
        return combo

    def setEditorData(self, editor, index):  # type: ignore[override]
        if isinstance(editor, QComboBox):
            current = str(index.data(Qt.EditRole) or index.data(Qt.DisplayRole) or "").strip()
            if current and editor.findText(current) < 0:
                editor.addItem(current)
            with QSignalBlocker(editor):
                editor.setCurrentIndex(max(0, editor.findText(current)))
            return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):  # type: ignore[override]
        if isinstance(editor, QComboBox):
            model.setData(index, str(editor.currentText() or "").strip(), Qt.EditRole)
            return
        super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):  # type: ignore[override]
        editor.setGeometry(option.rect)


def _build_filename_fields_editor():
    card = QFrame()
    card.setObjectName("Card")
    card.setProperty("officialDocsFilenameCard", True)
    root = QVBoxLayout(card)
    root.setContentsMargins(6, 6, 6, 6)
    root.setSpacing(4)

    title = QLabel("文件名预览：-")
    title.setObjectName("OfficialDocsFilenamePreviewLabel")
    title.setProperty("role", "label")
    title.setProperty("emphasis", True)
    root.addWidget(title)

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)

    field_list = QListWidget()
    field_list.setObjectName("OfficialDocsFilenameFieldsList")
    field_list.setSelectionMode(QAbstractItemView.SingleSelection)
    field_list.setDragDropMode(QAbstractItemView.InternalMove)
    field_list.setDefaultDropAction(Qt.MoveAction)
    field_list.setSpacing(0)
    field_list.setMinimumHeight(220)
    row.addWidget(field_list, 1)

    actions = QVBoxLayout()
    actions.setContentsMargins(0, 0, 0, 0)
    actions.setSpacing(4)
    btn_insert = QPushButton("插入字段")
    btn_insert.setObjectName("Secondary")
    btn_move_up = QPushButton("⬆")
    btn_move_up.setObjectName("Secondary")
    btn_move_down = QPushButton("⬇")
    btn_move_down.setObjectName("Secondary")
    btn_remove = QPushButton("删除选中")
    btn_remove.setObjectName("Secondary")
    btn_clear = QPushButton("清空")
    btn_clear.setObjectName("Secondary")
    actions.addWidget(btn_insert)
    actions.addWidget(btn_move_up)
    actions.addWidget(btn_move_down)
    actions.addWidget(btn_remove)
    actions.addWidget(btn_clear)
    actions.addStretch(1)
    row.addLayout(actions, 0)

    root.addLayout(row)
    return card, title, field_list, btn_insert, btn_move_up, btn_move_down, btn_remove, btn_clear


def _build_alias_editor():
    card = QFrame()
    card.setObjectName("Card")
    root = QVBoxLayout(card)
    root.setContentsMargins(8, 8, 8, 8)
    root.setSpacing(6)

    alias_title = QLabel("通知书简称规则")
    alias_title.setObjectName("OfficialDocsAliasTitleLabel")
    alias_title.setProperty("role", "label")
    alias_title.setProperty("emphasis", True)
    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(8)
    title_row.addWidget(alias_title, 1)
    btn_add = QPushButton("新增规则")
    btn_add.setObjectName("Secondary")
    btn_remove = QPushButton("删除选中规则")
    btn_remove.setObjectName("Secondary")
    title_row.addWidget(btn_add, 0)
    title_row.addWidget(btn_remove, 0)
    root.addLayout(title_row)

    table = QTableWidget(0, 3)
    table.setObjectName("OfficialDocsAliasTable")
    table.setHorizontalHeaderLabels(["启用", "通知书全称", "简称"])
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
    table.setItemDelegateForColumn(1, _AliasNoticeNameDelegate(table))
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.Stretch)
    header.setSectionResizeMode(2, QHeaderView.Stretch)
    table.setMinimumHeight(120)
    root.addWidget(table, 1)

    return card, alias_title, table, btn_add, btn_remove


def build_settings_panel(window, tabs):
    settings_tab = QWidget()
    settings_root = QVBoxLayout(settings_tab)
    settings_root.setContentsMargins(0, 0, 0, 0)
    settings_root.setSpacing(8)

    runtime_card = QFrame()
    runtime_card.setObjectName("Card")
    runtime_layout = QGridLayout(runtime_card)
    runtime_layout.setContentsMargins(6, 6, 6, 6)
    runtime_layout.setHorizontalSpacing(8)
    runtime_layout.setVerticalSpacing(4)

    runtime_title = QLabel("运行设置")
    runtime_title.setProperty("role", "label")
    runtime_title.setProperty("emphasis", True)
    runtime_layout.addWidget(runtime_title, 0, 0, 1, 1)

    btn_save_settings = QPushButton("保存设置")
    btn_save_settings.setObjectName("Primary")
    btn_save_settings.setProperty("officialDocsBigSave", True)
    btn_save_settings.setMinimumWidth(150)
    btn_save_settings.setMinimumHeight(36)
    runtime_layout.addWidget(btn_save_settings, 0, 1, 2, 1, Qt.AlignRight | Qt.AlignTop)

    check_row = QHBoxLayout()
    check_row.setContentsMargins(0, 0, 0, 0)
    check_row.setSpacing(8)
    chk_summary = QCheckBox("输出单次汇总")
    chk_archive = QCheckBox("输出长期归档")
    chk_confirm = QCheckBox("逐个确认")
    for chk in (chk_summary, chk_archive, chk_confirm):
        chk.setProperty("class", "OfficialDocsCheck")
    chk_summary.setChecked(True)
    chk_archive.setChecked(False)
    chk_confirm.setChecked(False)
    check_row.addWidget(chk_summary)
    check_row.addWidget(chk_archive)
    check_row.addWidget(chk_confirm)
    check_row.addStretch(1)
    runtime_layout.addLayout(check_row, 1, 0, 1, 1)

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(6)
    mode_no_list_multi_pdf_label = QLabel("无 list.xml 多 PDF：")
    mode_no_list_multi_pdf_label.setProperty("role", "caption")
    mode_no_list_multi_pdf = QComboBox()
    mode_no_list_multi_pdf.setObjectName("OfficialDocsNoListMultiPdfModeCombo")
    mode_no_list_multi_pdf.addItem("逐个 PDF 输出（默认）", "split_each_pdf")
    mode_no_list_multi_pdf.addItem("整包合并输出", "merge_all")
    mode_row.addWidget(mode_no_list_multi_pdf_label, 0)
    mode_row.addWidget(mode_no_list_multi_pdf, 0)
    mode_row.addStretch(1)
    runtime_layout.addLayout(mode_row, 2, 0, 1, 1)

    def _dir_row(label_text: str):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        label = QLabel(label_text)
        label.setProperty("role", "caption")
        edit = QLineEdit()
        edit.setPlaceholderText("请选择目录")
        button = QPushButton("浏览...")
        button.setObjectName("Secondary")
        row.addWidget(label, 0)
        row.addWidget(edit, 1)
        row.addWidget(button, 0)
        return row, edit, button

    summary_row, summary_edit, summary_button = _dir_row("汇总根目录：")
    archive_row, archive_edit, archive_button = _dir_row("归档根目录：")
    dirs_row = QHBoxLayout()
    dirs_row.setContentsMargins(0, 0, 0, 0)
    dirs_row.setSpacing(10)
    dirs_row.addLayout(summary_row, 1)
    dirs_row.addLayout(archive_row, 1)
    runtime_layout.addLayout(dirs_row, 3, 0, 1, 2)

    settings_error_label = QLabel("")
    settings_error_label.setObjectName("OfficialDocsValidationError")
    settings_error_label.setProperty("role", "caption")
    settings_error_label.setWordWrap(True)
    settings_error_label.setVisible(False)
    runtime_layout.addWidget(settings_error_label, 4, 0, 1, 2)
    runtime_layout.setColumnStretch(0, 1)
    runtime_layout.setColumnStretch(1, 0)

    settings_root.addWidget(runtime_card)

    settings_splitter = QSplitter(Qt.Horizontal)
    settings_splitter.setObjectName("OfficialDocsSettingsSplitter")
    settings_splitter.setChildrenCollapsible(False)

    type_card = QFrame()
    type_card.setObjectName("Card")
    type_layout = QVBoxLayout(type_card)
    type_layout.setContentsMargins(8, 8, 8, 8)
    type_layout.setSpacing(6)
    type_title = QLabel("通知书类型")
    type_title.setProperty("role", "label")
    type_title.setProperty("emphasis", True)
    type_layout.addWidget(type_title)
    type_search_edit = QLineEdit()
    type_search_edit.setObjectName("OfficialDocsTypeSearch")
    type_search_edit.setPlaceholderText("搜索类型（中文/拼音/代码）")
    type_layout.addWidget(type_search_edit)
    type_guide_label = QLabel("先选分组或类型，再在下方管理。")
    type_guide_label.setObjectName("OfficialDocsTypeGuideLabel")
    type_guide_label.setProperty("role", "caption")
    type_layout.addWidget(type_guide_label)
    type_tree = OfficialDocsNamingTypeTree()
    type_tree.setObjectName("OfficialDocsTypeTree")
    type_tree.setHeaderHidden(True)
    type_tree.setSelectionMode(QAbstractItemView.SingleSelection)
    type_tree.setRootIsDecorated(True)
    type_tree.setItemsExpandable(True)
    type_tree.setIndentation(18)
    type_tree.setContextMenuPolicy(Qt.CustomContextMenu)
    type_layout.addWidget(type_tree, 1)

    group_actions_card = QFrame()
    group_actions_card.setObjectName("OfficialDocsGroupActionsCard")
    group_actions_layout = QVBoxLayout(group_actions_card)
    group_actions_layout.setContentsMargins(8, 8, 8, 8)
    group_actions_layout.setSpacing(6)

    group_scope_title = QLabel("分组操作")
    group_scope_title.setObjectName("OfficialDocsGroupScopeTitleLabel")
    group_scope_title.setProperty("role", "caption")
    group_scope_title.setProperty("emphasis", True)
    group_actions_layout.addWidget(group_scope_title)
    group_actions_row1 = QHBoxLayout()
    group_actions_row1.setContentsMargins(0, 0, 0, 0)
    group_actions_row1.setSpacing(4)
    btn_create_group = QPushButton("新建")
    btn_rename_group = QPushButton("改名")
    btn_delete_group = QPushButton("删除")
    for button, tooltip in (
        (btn_create_group, "新建分组"),
        (btn_rename_group, "重命名分组"),
        (btn_delete_group, "删除分组"),
    ):
        button.setObjectName("Secondary")
        button.setProperty("officialDocsGroupAction", True)
        button.setToolTip(tooltip)
    group_actions_row1.addWidget(btn_create_group)
    group_actions_row1.addWidget(btn_rename_group)
    group_actions_row1.addWidget(btn_delete_group)
    group_actions_layout.addLayout(group_actions_row1)

    group_member_title = QLabel("成员操作")
    group_member_title.setObjectName("OfficialDocsGroupMemberTitleLabel")
    group_member_title.setProperty("role", "caption")
    group_member_title.setProperty("emphasis", True)
    group_actions_layout.addWidget(group_member_title)
    group_actions_row2 = QHBoxLayout()
    group_actions_row2.setContentsMargins(0, 0, 0, 0)
    group_actions_row2.setSpacing(4)
    btn_add_member = QPushButton("加成员...")
    btn_join_group = QPushButton("加入组...")
    btn_move_group = QPushButton("移至组...")
    btn_remove_group = QPushButton("移出组")
    for button, tooltip in (
        (btn_add_member, "添加成员到当前分组"),
        (btn_join_group, "将选中类型加入分组"),
        (btn_move_group, "将选中类型移动到其他分组"),
        (btn_remove_group, "将选中类型移出分组"),
    ):
        button.setObjectName("Secondary")
        button.setProperty("officialDocsGroupAction", True)
        button.setToolTip(tooltip)
    group_actions_row2.addWidget(btn_add_member)
    group_actions_row2.addWidget(btn_join_group)
    group_actions_row2.addWidget(btn_move_group)
    group_actions_row2.addWidget(btn_remove_group)
    group_actions_layout.addLayout(group_actions_row2)
    type_layout.addWidget(group_actions_card)
    type_card.setMinimumWidth(340)
    settings_splitter.addWidget(type_card)

    config_column = QVBoxLayout()
    config_column.setContentsMargins(0, 0, 0, 0)
    config_column.setSpacing(8)

    mode_card = QFrame()
    mode_card.setObjectName("Card")
    mode_layout = QVBoxLayout(mode_card)
    mode_layout.setContentsMargins(8, 8, 8, 8)
    mode_layout.setSpacing(6)
    config_scope_label = QLabel("当前编辑：请先选择左侧对象")
    config_scope_label.setObjectName("OfficialDocsNamingScopeLabel")
    config_scope_label.setProperty("role", "caption")
    config_scope_label.setProperty("emphasis", True)
    config_scope_label.setWordWrap(True)
    mode_layout.addWidget(config_scope_label)

    config_hint_label = QLabel("")
    config_hint_label.setObjectName("OfficialDocsNamingScopeHint")
    config_hint_label.setProperty("role", "caption")
    config_hint_label.setWordWrap(True)
    config_hint_label.setVisible(False)
    mode_layout.addWidget(config_hint_label)

    separator_row = QHBoxLayout()
    separator_row.setContentsMargins(0, 0, 0, 0)
    separator_row.setSpacing(6)
    separator_label = QLabel("字段连接符：")
    separator_label.setProperty("role", "caption")
    separator_edit = QLineEdit()
    separator_edit.setObjectName("OfficialDocsFilenameSeparatorEdit")
    separator_edit.setPlaceholderText("空输入按 +；支持 _、-、空格等安全字符")
    separator_row.addWidget(separator_label, 0)
    separator_row.addWidget(separator_edit, 1)
    mode_layout.addLayout(separator_row)

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(6)
    mode_label = QLabel("命名模式：")
    mode_label.setProperty("role", "caption")
    mode_combo = QComboBox()
    mode_combo.setObjectName("OfficialDocsNamingModeCombo")
    mode_combo.addItem("默认（专利类型+发明名称+申请号+通知书名称+发文日）", "default")
    mode_combo.addItem("自定义（按下方字段构成）", "custom")
    mode_row.addWidget(mode_label, 0)
    mode_row.addWidget(mode_combo, 1)
    mode_layout.addLayout(mode_row)
    config_column.addWidget(mode_card)

    (
        filename_card,
        filename_preview_label,
        filename_fields_list,
        btn_insert_field,
        btn_move_field_up,
        btn_move_field_down,
        btn_remove_field,
        btn_clear_fields,
    ) = _build_filename_fields_editor()
    alias_card, alias_title, alias_table, btn_add_alias, btn_remove_alias = _build_alias_editor()

    naming_splitter = QSplitter(Qt.Vertical)
    naming_splitter.setObjectName("OfficialDocsNamingConfigSplitter")
    naming_splitter.setChildrenCollapsible(False)
    filename_card.setMinimumHeight(220)
    alias_card.setMinimumHeight(140)
    naming_splitter.addWidget(filename_card)
    naming_splitter.addWidget(alias_card)
    naming_splitter.setStretchFactor(0, 3)
    naming_splitter.setStretchFactor(1, 2)
    naming_splitter.setSizes([3, 2])
    config_column.addWidget(naming_splitter, 1)

    config_container = QWidget()
    config_container.setMinimumWidth(520)
    config_container.setLayout(config_column)
    settings_splitter.addWidget(config_container)

    settings_splitter.setStretchFactor(0, 1)
    settings_splitter.setStretchFactor(1, 3)
    settings_splitter.setSizes([430, 930])
    settings_root.addWidget(settings_splitter, 1)

    tabs.addTab(settings_tab, "命名归档")

    pdf_parse_tab = QWidget()
    pdf_parse_root = QVBoxLayout(pdf_parse_tab)
    pdf_parse_root.setContentsMargins(0, 0, 0, 0)
    pdf_parse_root.setSpacing(8)

    pdf_parse_card = QFrame()
    pdf_parse_card.setObjectName("Card")
    pdf_parse_layout = QVBoxLayout(pdf_parse_card)
    pdf_parse_layout.setContentsMargins(8, 8, 8, 8)
    pdf_parse_layout.setSpacing(8)

    pdf_parse_title = QLabel("PDF解析设置")
    pdf_parse_title.setProperty("role", "label")
    pdf_parse_title.setProperty("emphasis", True)
    pdf_parse_layout.addWidget(pdf_parse_title)

    chk_exam_pdf_parse = QCheckBox("解析PDF文件内容")
    chk_exam_pdf_parse.setProperty("class", "OfficialDocsCheck")
    chk_exam_pdf_parse.setChecked(False)
    pdf_parse_layout.addWidget(chk_exam_pdf_parse)

    pdf_parse_fields_wrap = QFrame()
    pdf_parse_fields_wrap.setObjectName("OfficialDocsPdfParseFieldsWrap")
    pdf_parse_fields_grid = QGridLayout(pdf_parse_fields_wrap)
    pdf_parse_fields_grid.setContentsMargins(0, 0, 0, 0)
    pdf_parse_fields_grid.setHorizontalSpacing(12)
    pdf_parse_fields_grid.setVerticalSpacing(6)

    def _make_pdf_field_check(text: str) -> QCheckBox:
        checkbox = QCheckBox(text)
        checkbox.setProperty("class", "OfficialDocsCheck")
        checkbox.setChecked(False)
        return checkbox

    chk_pdf_applicant = _make_pdf_field_check("申请人信息")
    chk_pdf_inventor = _make_pdf_field_check("发明人信息")
    chk_pdf_agent = _make_pdf_field_check("代理人信息")
    chk_pdf_agency_raw = _make_pdf_field_check("代理信息原文")
    chk_pdf_department = _make_pdf_field_check("审查部门信息")
    chk_pdf_center = _make_pdf_field_check("审查协作中心信息")
    chk_pdf_examiner = _make_pdf_field_check("审查员信息")
    chk_pdf_panel = _make_pdf_field_check("合议组信息")
    chk_pdf_reject_reason = _make_pdf_field_check("驳回理由")
    chk_pdf_prior_art = _make_pdf_field_check("对比件信息")
    chk_pdf_dossier_no = _make_pdf_field_check("申请方案卷号")
    chk_pdf_authorization_pub_no = _make_pdf_field_check("授权公告号")
    chk_pdf_authorization_pub_date = _make_pdf_field_check("授权公告日")
    chk_pdf_certificate_no = _make_pdf_field_check("证书号")
    chk_pdf_qrcode_link = _make_pdf_field_check("公告二维码链接")
    chk_pdf_qrcode_image = _make_pdf_field_check("公告二维码图片")

    pdf_field_checks = [
        chk_pdf_applicant,
        chk_pdf_inventor,
        chk_pdf_agent,
        chk_pdf_agency_raw,
        chk_pdf_department,
        chk_pdf_center,
        chk_pdf_examiner,
        chk_pdf_panel,
        chk_pdf_reject_reason,
        chk_pdf_prior_art,
        chk_pdf_dossier_no,
        chk_pdf_authorization_pub_no,
        chk_pdf_authorization_pub_date,
        chk_pdf_certificate_no,
        chk_pdf_qrcode_link,
        chk_pdf_qrcode_image,
    ]
    for index, checkbox in enumerate(pdf_field_checks):
        pdf_parse_fields_grid.addWidget(checkbox, index // 2, index % 2, 1, 1)
    pdf_parse_fields_grid.setColumnStretch(0, 1)
    pdf_parse_fields_grid.setColumnStretch(1, 1)
    pdf_parse_layout.addWidget(pdf_parse_fields_wrap)
    pdf_parse_layout.addStretch(1)
    pdf_parse_root.addWidget(pdf_parse_card, 1)

    tabs.addTab(pdf_parse_tab, "PDF解析")

    return {
        "summary_button": summary_button,
        "archive_button": archive_button,
        "btn_save_settings": btn_save_settings,
        "type_tree": type_tree,
        "type_search_edit": type_search_edit,
        "btn_create_group": btn_create_group,
        "btn_rename_group": btn_rename_group,
        "btn_delete_group": btn_delete_group,
        "btn_add_member": btn_add_member,
        "btn_join_group": btn_join_group,
        "btn_move_group": btn_move_group,
        "btn_remove_group": btn_remove_group,
        "chk_archive": chk_archive,
        "chk_summary": chk_summary,
        "chk_confirm": chk_confirm,
        "mode_no_list_multi_pdf": mode_no_list_multi_pdf,
        "chk_exam_pdf_parse": chk_exam_pdf_parse,
        "summary_edit": summary_edit,
        "archive_edit": archive_edit,
        "chk_pdf_applicant": chk_pdf_applicant,
        "chk_pdf_inventor": chk_pdf_inventor,
        "chk_pdf_agent": chk_pdf_agent,
        "chk_pdf_agency_raw": chk_pdf_agency_raw,
        "chk_pdf_department": chk_pdf_department,
        "chk_pdf_center": chk_pdf_center,
        "chk_pdf_examiner": chk_pdf_examiner,
        "chk_pdf_panel": chk_pdf_panel,
        "chk_pdf_reject_reason": chk_pdf_reject_reason,
        "chk_pdf_prior_art": chk_pdf_prior_art,
        "chk_pdf_dossier_no": chk_pdf_dossier_no,
        "chk_pdf_authorization_pub_no": chk_pdf_authorization_pub_no,
        "chk_pdf_authorization_pub_date": chk_pdf_authorization_pub_date,
        "chk_pdf_certificate_no": chk_pdf_certificate_no,
        "chk_pdf_qrcode_link": chk_pdf_qrcode_link,
        "chk_pdf_qrcode_image": chk_pdf_qrcode_image,
        "mode_combo": mode_combo,
        "separator_edit": separator_edit,
        "btn_insert_field": btn_insert_field,
        "btn_move_field_up": btn_move_field_up,
        "btn_move_field_down": btn_move_field_down,
        "btn_remove_field": btn_remove_field,
        "btn_clear_fields": btn_clear_fields,
        "filename_fields_list": filename_fields_list,
        "alias_table": alias_table,
        "btn_add_alias": btn_add_alias,
        "btn_remove_alias": btn_remove_alias,
        "filename_preview_label": filename_preview_label,
        "config_scope_label": config_scope_label,
        "config_hint_label": config_hint_label,
        "settings_error_label": settings_error_label,
        "filename_card": filename_card,
        "alias_card": alias_card,
        "alias_title": alias_title,
        "naming_splitter": naming_splitter,
        "settings_splitter": settings_splitter,
        "pdf_parse_tab": pdf_parse_tab,
        "pdf_parse_fields_wrap": pdf_parse_fields_wrap,
    }

__all__ = ["OfficialDocsNamingTypeTree", "build_settings_panel", "_AliasNoticeNameDelegate"]
