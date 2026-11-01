from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


def build_ui(dlg) -> None:
    overlay_layout = QVBoxLayout(dlg)
    overlay_layout.setContentsMargins(0, 0, 0, 0)
    overlay_layout.setSpacing(0)
    if not bool(getattr(dlg, "_embedded", False)):
        overlay_layout.setAlignment(Qt.AlignCenter)

    card = QFrame(dlg)
    card.setObjectName("ModalCard")
    dlg._card = card
    try:
        if bool(getattr(dlg, "_embedded", False)):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    except Exception:
        pass
    try:
        if not bool(getattr(dlg, "_embedded", False)):
            eff = QGraphicsDropShadowEffect(card)
            eff.setBlurRadius(28)
            eff.setOffset(0, 10)
            eff.setColor(QColor(15, 23, 42, 70))
            card.setGraphicsEffect(eff)
    except Exception:
        pass

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(0, 0, 0, 16)
    card_layout.setSpacing(12)

    titlebar = QFrame(card)
    titlebar.setObjectName("ModalTitleBar")
    tl = QHBoxLayout(titlebar)
    tl.setContentsMargins(16, 12, 12, 12)
    tl.setSpacing(8)

    try:
        if bool(getattr(dlg, "_embedded", False)):
            dlg.btn_back = QPushButton("返回")
            dlg.btn_back.setObjectName("tgdZipImportReviewBack")
            dlg.btn_back.setProperty("class", "Ghost")
            tl.addWidget(dlg.btn_back, 0)
    except Exception:
        pass

    title = QLabel("导入确认：数据管理")
    title.setObjectName("ModalTitleText")
    title.setProperty("role", "h2")
    tl.addWidget(title, 1)

    dlg.btn_close = QPushButton("×")
    dlg.btn_close.setObjectName("ModalCloseButton")
    dlg.btn_close.setFixedSize(28, 28)
    dlg.btn_close.setFocusPolicy(Qt.NoFocus)
    try:
        if bool(getattr(dlg, "_embedded", False)):
            dlg.btn_close.setVisible(False)
    except Exception:
        pass
    tl.addWidget(dlg.btn_close, 0, Qt.AlignTop)

    card_layout.addWidget(titlebar)

    scroll = QScrollArea(card)
    scroll.setObjectName("RequestFormScroll")
    scroll.setWidgetResizable(True)
    dlg._scroll_area = scroll
    try:
        scroll.setFrameShape(QFrame.NoFrame)
    except Exception:
        pass
    card_layout.addWidget(scroll, 1)

    content = QWidget()
    content.setObjectName("RequestFormBody")
    scroll.setWidget(content)

    body = QVBoxLayout(content)
    body.setContentsMargins(24, 24, 24, 24)
    body.setSpacing(12)

    dlg.file_label = QLabel("")
    dlg.file_label.setProperty("role", "caption")
    dlg.file_label.setProperty("emphasis", True)
    dlg.file_label.setWordWrap(True)
    body.addWidget(dlg.file_label)

    dlg.tabs = QTabWidget(content)
    dlg.tabs.setObjectName("requestAppTabs")
    tab_fact = QWidget(dlg.tabs)
    tab_agency = QWidget(dlg.tabs)
    dlg.tabs.addTab(tab_fact, "申请信息")
    dlg.tabs.addTab(tab_agency, "代理机构信息")
    body.addWidget(dlg.tabs, 1)

    build_fact_tab(dlg, tab_fact)
    build_agency_tab(dlg, tab_agency)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    dlg.btn_import_continue = QPushButton("导入并继续")
    dlg.btn_import_continue.setObjectName("primaryButton")
    dlg.btn_skip = QPushButton("跳过")
    dlg.btn_skip.setObjectName("secondaryButton")
    dlg.btn_import_stop = QPushButton("本条后停止")
    dlg.btn_import_stop.setObjectName("secondaryButton")
    btn_row.addWidget(dlg.btn_import_continue)
    btn_row.addWidget(dlg.btn_skip)
    btn_row.addWidget(dlg.btn_import_stop)
    body.addLayout(btn_row)

    if bool(getattr(dlg, "_embedded", False)):
        overlay_layout.addWidget(card, 1)
    else:
        overlay_layout.addWidget(card)


def build_fact_tab(dlg, tab: QWidget) -> None:
    lay = QVBoxLayout(tab)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    dlg._fact_tab_layout = lay

    dlg.fact_table = QTableWidget(tab)
    dlg.fact_table.setColumnCount(11)
    dlg.fact_table.setHorizontalHeaderLabels(
        [
            "申请人名称",
            "申请人类型",
            "证件类型",
            "证件号",
            "电话",
            "发明人姓名",
            "发明人证件号",
            "分组名称",
            "总委托书编号",
            "关联代理机构名称",
            "关联代理机构代码",
        ]
    )
    try:
        dlg.fact_table.setEditTriggers(QTableWidget.NoEditTriggers)
        dlg.fact_table.setSelectionBehavior(QTableWidget.SelectRows)
        dlg.fact_table.setSelectionMode(QTableWidget.SingleSelection)
    except Exception:
        pass
    lay.addWidget(dlg.fact_table, 1)

    editor = QFrame(tab)
    editor.setObjectName("RequestSection")
    dlg._fact_editor_frame = editor
    el = QGridLayout(editor)
    el.setContentsMargins(12, 12, 12, 12)
    el.setHorizontalSpacing(12)
    el.setVerticalSpacing(10)

    dlg.fact_applicant_name = QLineEdit(editor)

    dlg.fact_applicant_type = QComboBox(editor)
    dlg.fact_applicant_type.addItem("", "")
    dlg.fact_applicant_type.addItem("工矿企业", "工矿企业")
    dlg.fact_applicant_type.addItem("个人", "个人")
    dlg.fact_applicant_type.addItem("事业单位/科研机构", "事业单位/科研机构")

    dlg.fact_applicant_id_type = QComboBox(editor)
    dlg.fact_applicant_id_type.setEditable(True)
    dlg.fact_applicant_id_type.addItem("", "")
    dlg.fact_applicant_id_type.addItem("统一社会信用代码", "统一社会信用代码")
    dlg.fact_applicant_id_type.addItem("居民身份证", "居民身份证")
    dlg.fact_applicant_id_type.addItem("其他", "其他")

    dlg.fact_applicant_id_no = QLineEdit(editor)
    dlg.fact_applicant_phone = QLineEdit(editor)
    dlg.fact_applicant_email = QLineEdit(editor)
    dlg.fact_applicant_addr_full = QLineEdit(editor)

    dlg.fact_inventor_name = QLineEdit(editor)
    dlg.fact_inventor_id_type = QComboBox(editor)
    dlg.fact_inventor_id_type.setEditable(True)
    dlg.fact_inventor_id_type.addItem("", "")
    dlg.fact_inventor_id_type.addItem("居民身份证", "居民身份证")
    dlg.fact_inventor_id_type.addItem("护照", "护照")
    dlg.fact_inventor_id_type.addItem("其他", "其他")

    dlg.fact_inventor_id_no = QLineEdit(editor)
    dlg.fact_inventor_nat = QLineEdit(editor)

    dlg.fact_contact_name = QLineEdit(editor)
    dlg.fact_contact_phone = QLineEdit(editor)
    dlg.fact_contact_email = QLineEdit(editor)
    dlg.fact_contact_addr_full = QLineEdit(editor)
    dlg.fact_contact_zip = QLineEdit(editor)

    dlg.fact_group_name = QLineEdit(editor)
    dlg.fact_poa_no = QLineEdit(editor)
    dlg.fact_agency_name = QLineEdit(editor)
    dlg.fact_agency_code = QLineEdit(editor)

    row = 0
    el.addWidget(QLabel("申请人名称："), row, 0)
    el.addWidget(dlg.fact_applicant_name, row, 1)
    el.addWidget(QLabel("申请人类型："), row, 2)
    el.addWidget(dlg.fact_applicant_type, row, 3)
    row += 1

    el.addWidget(QLabel("申请人证件类型："), row, 0)
    el.addWidget(dlg.fact_applicant_id_type, row, 1)
    el.addWidget(QLabel("申请人证件号码："), row, 2)
    el.addWidget(dlg.fact_applicant_id_no, row, 3)
    row += 1

    el.addWidget(QLabel("申请人电话："), row, 0)
    el.addWidget(dlg.fact_applicant_phone, row, 1)
    el.addWidget(QLabel("申请人电子邮箱："), row, 2)
    el.addWidget(dlg.fact_applicant_email, row, 3)
    row += 1

    el.addWidget(QLabel("申请人地址（省/市/区+详细地址+邮编）："), row, 0)
    el.addWidget(dlg.fact_applicant_addr_full, row, 1, 1, 3)
    row += 1

    el.addWidget(QLabel("发明人姓名："), row, 0)
    el.addWidget(dlg.fact_inventor_name, row, 1)
    el.addWidget(QLabel("发明人证件类型："), row, 2)
    el.addWidget(dlg.fact_inventor_id_type, row, 3)
    row += 1

    el.addWidget(QLabel("发明人证件号码："), row, 0)
    el.addWidget(dlg.fact_inventor_id_no, row, 1)
    el.addWidget(QLabel("发明人国籍代码："), row, 2)
    el.addWidget(dlg.fact_inventor_nat, row, 3)
    row += 1

    el.addWidget(QLabel("联系人姓名："), row, 0)
    el.addWidget(dlg.fact_contact_name, row, 1)
    el.addWidget(QLabel("联系人电话："), row, 2)
    el.addWidget(dlg.fact_contact_phone, row, 3)
    row += 1

    el.addWidget(QLabel("联系人电子邮箱："), row, 0)
    el.addWidget(dlg.fact_contact_email, row, 1)
    el.addWidget(QLabel("联系人邮编："), row, 2)
    el.addWidget(dlg.fact_contact_zip, row, 3)
    row += 1

    el.addWidget(QLabel("联系人地址（省/市/区+街道门牌号）："), row, 0)
    el.addWidget(dlg.fact_contact_addr_full, row, 1, 1, 3)
    row += 1

    el.addWidget(QLabel("分组名称："), row, 0)
    el.addWidget(dlg.fact_group_name, row, 1)
    el.addWidget(QLabel("总委托书编号："), row, 2)
    el.addWidget(dlg.fact_poa_no, row, 3)
    row += 1

    el.addWidget(QLabel("关联代理机构名称："), row, 0)
    el.addWidget(dlg.fact_agency_name, row, 1)
    el.addWidget(QLabel("关联代理机构代码："), row, 2)
    el.addWidget(dlg.fact_agency_code, row, 3)

    lay.addWidget(editor)


def build_agency_tab(dlg, tab: QWidget) -> None:
    lay = QVBoxLayout(tab)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)

    btn_row = QHBoxLayout()
    btn_row.setContentsMargins(0, 0, 0, 0)
    btn_row.setSpacing(8)
    dlg.btn_add_agency_row = QPushButton("新增行")
    dlg.btn_add_agency_row.setObjectName("secondaryButton")
    dlg.btn_del_agency_row = QPushButton("删除行")
    dlg.btn_del_agency_row.setObjectName("secondaryButton")
    btn_row.addStretch(1)
    btn_row.addWidget(dlg.btn_add_agency_row)
    btn_row.addWidget(dlg.btn_del_agency_row)
    lay.addLayout(btn_row)

    dlg.agency_table = QTableWidget(tab)
    dlg.agency_table.setColumnCount(5)
    dlg.agency_table.setHorizontalHeaderLabels(
        [
            "代理机构名称",
            "代理机构代码",
            "代理师姓名",
            "代理师资格证号",
            "代理师电话",
        ]
    )
    lay.addWidget(dlg.agency_table, 1)
