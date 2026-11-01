from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _build_ui(self) -> None:
    overlay_layout = QVBoxLayout(self)
    overlay_layout.setContentsMargins(0, 0, 0, 0)
    overlay_layout.setSpacing(0)
    overlay_layout.setAlignment(Qt.AlignCenter)

    card = QFrame(self)
    card.setObjectName("ModalCard")
    self._card = card
    try:
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    except Exception:
        pass
    try:
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

    title = QLabel("数据管理：常用信息")
    title.setObjectName("ModalTitleText")
    title.setProperty("role", "h2")
    tl.addWidget(title, 1)

    btn_close_x = QPushButton("×")
    btn_close_x.setObjectName("ModalCloseButton")
    btn_close_x.setFixedSize(28, 28)
    btn_close_x.setFocusPolicy(Qt.NoFocus)
    btn_close_x.clicked.connect(self.reject)
    tl.addWidget(btn_close_x, 0, Qt.AlignTop)
    card_layout.addWidget(titlebar)

    scroll = QScrollArea(card)
    scroll.setObjectName("RequestFormScroll")
    scroll.setWidgetResizable(True)
    self._scroll_area = scroll
    try:
        scroll.setFrameShape(QFrame.NoFrame)
    except Exception:
        pass
    card_layout.addWidget(scroll, 1)

    content = QWidget()
    content.setObjectName("RequestFormBody")
    scroll.setWidget(content)

    form_layout = QVBoxLayout(content)
    form_layout.setContentsMargins(24, 24, 24, 24)
    form_layout.setSpacing(16)

    header = QLabel("来源：手动填写")
    header.setProperty("role", "caption")
    header.setProperty("emphasis", True)
    form_layout.addWidget(header)

    form_layout.addWidget(self._build_applicant_section())
    form_layout.addWidget(self._build_inventor_section())
    form_layout.addWidget(self._build_contact_section())
    form_layout.addWidget(self._build_agency_poa_section())
    form_layout.addWidget(self._build_group_section())
    form_layout.addStretch(1)

    footer = QFrame(card)
    footer.setObjectName("ModalFooter")
    fl = QHBoxLayout(footer)
    fl.setContentsMargins(16, 10, 16, 10)
    fl.setSpacing(10)
    fl.addStretch(1)

    self.btn_save = QPushButton("保存到常用信息")
    self.btn_save.setObjectName("secondaryButton")
    self.btn_close = QPushButton("关闭")
    self.btn_close.setObjectName("secondaryButton")
    fl.addWidget(self.btn_save)
    fl.addWidget(self.btn_close)
    card_layout.addWidget(footer)

    overlay_layout.addWidget(card, 0, Qt.AlignCenter)


def _new_group(self, title: str) -> QGroupBox:
    group = QGroupBox(title, self)
    group.setObjectName("RequestSection")
    try:
        group.setFlat(True)
    except Exception:
        pass
    return group


def _build_applicant_section(self) -> QWidget:
    group = self._new_group("申请人")
    lay = QVBoxLayout(group)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(10)

    self.applicant_name_edit = QLineEdit(self)

    self.applicant_type_combo = QComboBox(self)
    self.applicant_type_combo.setEditable(True)
    self.applicant_type_combo.addItem("工矿企业", "3")
    self.applicant_type_combo.addItem("个人", "1")
    self.applicant_type_combo.addItem("事业单位/科研机构", "2")
    self.applicant_type_combo.setCurrentIndex(-1)

    self.applicant_id_type_combo = QComboBox(self)
    self.applicant_id_type_combo.setEditable(True)
    self.applicant_id_type_combo.addItem("统一社会信用代码", "F")
    self.applicant_id_type_combo.addItem("居民身份证", "I")
    self.applicant_id_type_combo.addItem("其他", "0")
    self.applicant_id_type_combo.setCurrentIndex(-1)

    self.applicant_id_no_edit = QLineEdit(self)
    self.applicant_phone_edit = QLineEdit(self)
    self.applicant_email_edit = QLineEdit(self)

    self.applicant_province_combo = QComboBox(self)
    self.applicant_city_combo = QComboBox(self)

    self.applicant_address_edit = QLineEdit(self)
    self.applicant_zip_edit = QLineEdit(self)

    r = 0
    grid.addWidget(QLabel("名称："), r, 0)
    grid.addWidget(self.applicant_name_edit, r, 1, 1, 3)
    r += 1

    grid.addWidget(QLabel("类型："), r, 0)
    grid.addWidget(self.applicant_type_combo, r, 1)
    grid.addWidget(QLabel("证件类型："), r, 2)
    grid.addWidget(self.applicant_id_type_combo, r, 3)
    r += 1

    grid.addWidget(QLabel("证件号码："), r, 0)
    grid.addWidget(self.applicant_id_no_edit, r, 1)
    grid.addWidget(QLabel("电话："), r, 2)
    grid.addWidget(self.applicant_phone_edit, r, 3)
    r += 1

    grid.addWidget(QLabel("电子邮箱："), r, 0)
    grid.addWidget(self.applicant_email_edit, r, 1)
    grid.addWidget(QLabel("邮编："), r, 2)
    grid.addWidget(self.applicant_zip_edit, r, 3)
    r += 1

    grid.addWidget(QLabel("省："), r, 0)
    grid.addWidget(self.applicant_province_combo, r, 1)
    grid.addWidget(QLabel("市："), r, 2)
    grid.addWidget(self.applicant_city_combo, r, 3)
    r += 1

    grid.addWidget(QLabel("详细地址："), r, 0)
    grid.addWidget(self.applicant_address_edit, r, 1, 1, 3)

    lay.addLayout(grid)
    return group


def _build_agency_poa_section(self) -> QWidget:
    group = self._new_group("委托代理/POA")
    lay = QVBoxLayout(group)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(10)

    self.power_of_attorney_no_edit = QLineEdit(self)
    self.agency_ref_name_edit = QLineEdit(self)
    self.agency_ref_code_edit = QLineEdit(self)

    r = 0
    grid.addWidget(QLabel("总委托书编号："), r, 0)
    grid.addWidget(self.power_of_attorney_no_edit, r, 1)
    grid.addWidget(QLabel("关联代理机构名称："), r, 2)
    grid.addWidget(self.agency_ref_name_edit, r, 3)
    r += 1

    grid.addWidget(QLabel("关联代理机构代码："), r, 0)
    grid.addWidget(self.agency_ref_code_edit, r, 1)
    grid.addWidget(QLabel(""), r, 2)
    grid.addWidget(QLabel(""), r, 3)

    lay.addLayout(grid)
    return group


def _build_inventor_section(self) -> QWidget:
    group = self._new_group("发明人")
    lay = QVBoxLayout(group)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(10)

    self.inventor_name_edit = QLineEdit(self)

    self.inventor_id_type_combo = QComboBox(self)
    self.inventor_id_type_combo.setEditable(True)
    self.inventor_id_type_combo.addItem("居民身份证")
    self.inventor_id_type_combo.addItem("护照")
    self.inventor_id_type_combo.addItem("其他")
    self.inventor_id_type_combo.setCurrentIndex(-1)

    self.inventor_id_no_edit = QLineEdit(self)
    self.inventor_nationality_edit = QLineEdit(self)
    try:
        self.inventor_nationality_edit.setText("CN")
    except Exception:
        pass

    r = 0
    grid.addWidget(QLabel("姓名："), r, 0)
    grid.addWidget(self.inventor_name_edit, r, 1, 1, 3)
    r += 1

    grid.addWidget(QLabel("证件类型："), r, 0)
    grid.addWidget(self.inventor_id_type_combo, r, 1)
    grid.addWidget(QLabel("证件号码："), r, 2)
    grid.addWidget(self.inventor_id_no_edit, r, 3)
    r += 1

    grid.addWidget(QLabel("国籍代码："), r, 0)
    grid.addWidget(self.inventor_nationality_edit, r, 1)
    grid.addWidget(QLabel(""), r, 2)
    grid.addWidget(QLabel(""), r, 3)

    lay.addLayout(grid)
    return group


def _build_contact_section(self) -> QWidget:
    group = self._new_group("联系人")
    lay = QVBoxLayout(group)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(10)

    self.contact_name_edit = QLineEdit(self)
    self.contact_phone_edit = QLineEdit(self)
    self.contact_email_edit = QLineEdit(self)

    self.contact_province_combo = QComboBox(self)
    self.contact_city_combo = QComboBox(self)

    self.contact_street_edit = QLineEdit(self)
    self.contact_zip_edit = QLineEdit(self)

    r = 0
    grid.addWidget(QLabel("姓名："), r, 0)
    grid.addWidget(self.contact_name_edit, r, 1)
    grid.addWidget(QLabel("电话："), r, 2)
    grid.addWidget(self.contact_phone_edit, r, 3)
    r += 1

    grid.addWidget(QLabel("电子邮箱："), r, 0)
    grid.addWidget(self.contact_email_edit, r, 1)
    grid.addWidget(QLabel("邮编："), r, 2)
    grid.addWidget(self.contact_zip_edit, r, 3)
    r += 1

    grid.addWidget(QLabel("省："), r, 0)
    grid.addWidget(self.contact_province_combo, r, 1)
    grid.addWidget(QLabel("市："), r, 2)
    grid.addWidget(self.contact_city_combo, r, 3)
    r += 1

    grid.addWidget(QLabel("街道门牌号："), r, 0)
    grid.addWidget(self.contact_street_edit, r, 1, 1, 3)

    lay.addLayout(grid)
    return group


def _build_group_section(self) -> QWidget:
    group = self._new_group("分组")
    lay = QVBoxLayout(group)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)

    self.group_name_edit = QLineEdit(self)
    row.addWidget(QLabel("分组名称："), 0)
    row.addWidget(self.group_name_edit, 1)
    lay.addLayout(row)

    return group
