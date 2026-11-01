from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
)

from gui.widgets_impl.graphic_checkbox import GraphicCheckBox

from .dialog_ui_utils import AdaptiveWidthSpec, bind_adaptive_width, mark_field_label


def build_request_form_bottom_sections(self, form_layout: QVBoxLayout, card: QFrame, card_layout: QVBoxLayout) -> None:
    applicants_group = QGroupBox("申请人", self)
    applicants_group.setObjectName("RequestSection")
    try:
        applicants_group.setFlat(True)
    except Exception:
        pass
    app_group_layout = QVBoxLayout(applicants_group)
    app_group_layout.setContentsMargins(8, 24, 8, 8)
    app_group_layout.setSpacing(8)
    self.app_tabs = QTabWidget(self)
    self.app_tabs.setObjectName("requestAppTabs")
    try:
        self.app_tabs.currentChanged.connect(lambda _idx: self._renumber_applicant_tabs())
    except Exception:
        pass
    try:
        app_tab_bar = self.app_tabs.tabBar()
        if app_tab_bar is not None:
            app_tab_bar.setMovable(True)
            app_tab_bar.tabMoved.connect(lambda _from, _to: self._renumber_applicant_tabs())
    except Exception:
        pass
    app_group_layout.addWidget(self.app_tabs)

    app_btn_row = QHBoxLayout()
    app_btn_row.setSpacing(8)
    self.fee_reduction_checkbox = GraphicCheckBox("所有申请人均符合费减条件（统一费减备案）", self)
    try:
        self.fee_reduction_checkbox.setProperty("emphasis", True)
    except Exception:
        pass
    self.btn_add_applicant = QPushButton("新增申请人", self)
    self.btn_remove_applicant = QPushButton("删除当前申请人", self)
    self.btn_add_applicant.setObjectName("primaryButton")
    self.btn_remove_applicant.setObjectName("secondaryButton")
    app_btn_row.addWidget(self.fee_reduction_checkbox, 0, Qt.AlignVCenter)
    app_btn_row.addStretch()
    app_btn_row.addWidget(self.btn_add_applicant, 0, Qt.AlignVCenter)
    app_btn_row.addWidget(self.btn_remove_applicant, 0, Qt.AlignVCenter)
    app_group_layout.addLayout(app_btn_row)
    form_layout.addWidget(applicants_group)

    inventors_group = QGroupBox("发明人", self)
    inventors_group.setObjectName("RequestSection")
    try:
        inventors_group.setFlat(True)
    except Exception:
        pass
    inv_group_layout = QVBoxLayout(inventors_group)
    inv_group_layout.setContentsMargins(8, 24, 8, 8)
    inv_group_layout.setSpacing(8)
    self.inv_tabs = QTabWidget(self)
    self.inv_tabs.setObjectName("requestInvTabs")
    try:
        self.inv_tabs.currentChanged.connect(lambda _idx: self._renumber_inventor_tabs())
    except Exception:
        pass
    try:
        inv_tab_bar = self.inv_tabs.tabBar()
        if inv_tab_bar is not None:
            inv_tab_bar.setMovable(True)
            inv_tab_bar.tabMoved.connect(lambda _from, _to: self._renumber_inventor_tabs())
    except Exception:
        pass
    inv_group_layout.addWidget(self.inv_tabs)

    inv_btn_row = QHBoxLayout()
    inv_btn_row.setSpacing(8)
    self.btn_add_inventor = QPushButton("新增发明人", self)
    self.btn_remove_inventor = QPushButton("删除当前发明人", self)
    self.btn_add_inventor.setObjectName("primaryButton")
    self.btn_remove_inventor.setObjectName("secondaryButton")
    inv_btn_row.addStretch()
    inv_btn_row.addWidget(self.btn_add_inventor)
    inv_btn_row.addWidget(self.btn_remove_inventor)
    inv_group_layout.addLayout(inv_btn_row)
    form_layout.addWidget(inventors_group)

    contact_group = QGroupBox("联系人", self)
    contact_group.setObjectName("RequestSection")
    try:
        contact_group.setFlat(True)
    except Exception:
        pass
    contact_layout = QVBoxLayout(contact_group)
    contact_layout.setContentsMargins(8, 24, 8, 8)
    contact_layout.setSpacing(8)

    contact_row1 = QHBoxLayout()
    contact_row1.setSpacing(8)
    contact_name_label = QLabel("联系人姓名：", self)
    mark_field_label(contact_name_label)
    self.contact_name_edit = QComboBox(self)
    self.contact_name_edit.setEditable(True)
    self.contact_name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    contact_phone_label = QLabel("联系人电话：", self)
    mark_field_label(contact_phone_label)
    self.contact_phone_edit = QComboBox(self)
    self.contact_phone_edit.setEditable(True)
    self.contact_phone_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    contact_email_label = QLabel("联系人电子邮箱：", self)
    mark_field_label(contact_email_label)
    self.contact_email_edit = QComboBox(self)
    self.contact_email_edit.setEditable(True)
    self.contact_email_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    try:
        bind_adaptive_width(self.contact_name_edit, AdaptiveWidthSpec(sample_chars=20, max_chars=28, kind="cjk"))
        bind_adaptive_width(self.contact_phone_edit, AdaptiveWidthSpec(sample_chars=22, max_chars=22, kind="digits"))
        bind_adaptive_width(self.contact_email_edit, AdaptiveWidthSpec(sample_chars=20, max_chars=40, kind="alnum_symbol"))
    except Exception:
        pass

    contact_row1.addWidget(contact_name_label, 0)
    contact_row1.addWidget(self.contact_name_edit, 0)
    contact_row1.addWidget(contact_phone_label, 0)
    contact_row1.addWidget(self.contact_phone_edit, 0)
    contact_row1.addWidget(contact_email_label, 0)
    contact_row1.addWidget(self.contact_email_edit, 0)
    contact_row1.addStretch(1)
    contact_layout.addLayout(contact_row1)

    contact_row3 = QHBoxLayout()
    contact_row3.setSpacing(8)
    contact_province_label = QLabel("联系人省：", self)
    mark_field_label(contact_province_label)
    self.contact_province_combo = QComboBox(self)
    self.contact_province_combo.setEditable(True)
    self.contact_province_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    contact_city_label = QLabel("联系人市：", self)
    mark_field_label(contact_city_label)
    self.contact_city_combo = QComboBox(self)
    self.contact_city_combo.setEditable(True)
    self.contact_city_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    try:
        bind_adaptive_width(self.contact_province_combo, AdaptiveWidthSpec(sample_chars=10, max_chars=23, kind="cjk_digit"))
        bind_adaptive_width(self.contact_city_combo, AdaptiveWidthSpec(sample_chars=10, max_chars=23, kind="cjk_digit"))
    except Exception:
        pass
    contact_row3.addWidget(contact_province_label, 0)
    contact_row3.addWidget(self.contact_province_combo, 0)
    contact_row3.addWidget(contact_city_label, 0)
    contact_row3.addWidget(self.contact_city_combo, 0)
    contact_row3.addStretch(1)
    contact_layout.addLayout(contact_row3)

    contact_row4 = QHBoxLayout()
    contact_row4.setSpacing(8)
    contact_street_label = QLabel("联系人详细地址：", self)
    mark_field_label(contact_street_label)
    self.contact_street_edit = QComboBox(self)
    self.contact_street_edit.setEditable(True)
    self.contact_street_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    contact_zip_label = QLabel("联系人邮编：", self)
    mark_field_label(contact_zip_label)
    self.contact_zip_edit = QComboBox(self)
    self.contact_zip_edit.setEditable(True)
    self.contact_zip_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    try:
        bind_adaptive_width(self.contact_street_edit, AdaptiveWidthSpec(sample_chars=35, max_chars=60, kind="cjk"))
        bind_adaptive_width(self.contact_zip_edit, AdaptiveWidthSpec(sample_chars=12, max_chars=12, kind="digits"))
    except Exception:
        pass

    contact_row4.addWidget(contact_street_label, 0)
    contact_row4.addWidget(self.contact_street_edit, 0)
    contact_row4.addWidget(contact_zip_label, 0)
    contact_row4.addWidget(self.contact_zip_edit, 0)
    contact_row4.addStretch(1)
    contact_layout.addLayout(contact_row4)
    form_layout.addWidget(contact_group)

    abstract_group = QGroupBox("摘要附图", self)
    abstract_group.setObjectName("RequestSection")
    try:
        abstract_group.setFlat(True)
    except Exception:
        pass
    abstract_layout = QHBoxLayout(abstract_group)
    abstract_layout.setSpacing(8)
    abstract_layout.setContentsMargins(8, 24, 8, 8)
    abstract_label = QLabel("摘要附图图号：", self)
    mark_field_label(abstract_label)
    self.abstract_figure_no_edit = QLineEdit(self)
    try:
        bind_adaptive_width(self.abstract_figure_no_edit, AdaptiveWidthSpec(sample_chars=5, max_chars=5, kind="alnum"))
    except Exception:
        pass
    abstract_layout.addWidget(abstract_label)
    abstract_layout.addWidget(self.abstract_figure_no_edit, 0)
    abstract_layout.addStretch(1)
    form_layout.addWidget(abstract_group)

    self._add_applicant_tab({})
    self._add_inventor_tab({})

    self.btn_add_applicant.clicked.connect(lambda: self._add_applicant_tab({}))
    self.btn_remove_applicant.clicked.connect(self._remove_current_applicant_tab)
    self.btn_add_inventor.clicked.connect(lambda: self._add_inventor_tab({}))
    self.btn_remove_inventor.clicked.connect(self._remove_current_inventor_tab)

    footer = QFrame(card)
    footer.setObjectName("ModalFooter")
    footer_layout = QHBoxLayout(footer)
    footer_layout.setContentsMargins(16, 10, 16, 10)
    footer_layout.setSpacing(10)
    footer_layout.addStretch(1)

    self.btn_save = QPushButton("保存（仅本次转档有效）", card)
    self.btn_import_to_data_mgmt = QPushButton("保存到常用信息", card)
    self.btn_cancel = QPushButton("返回修改", card)
    self.btn_ok = QPushButton("确认并生成 XML", card)
    self.btn_ok.clicked.connect(self.accept)
    self.btn_cancel.clicked.connect(self.reject)
    self.btn_ok.setObjectName("primaryButton")
    self.btn_cancel.setObjectName("secondaryButton")
    self.btn_save.setObjectName("secondaryButton")
    self.btn_import_to_data_mgmt.setObjectName("secondaryButton")
    footer_layout.addWidget(self.btn_save)
    footer_layout.addWidget(self.btn_import_to_data_mgmt)
    footer_layout.addWidget(self.btn_cancel)
    footer_layout.addWidget(self.btn_ok)
    card_layout.addWidget(footer)

    try:
        setup_fn = getattr(self, "_setup_inline_fact_dropdowns_for_contact", None)
        if callable(setup_fn):
            setup_fn()
    except Exception:
        pass

    # 下拉框滚轮禁用：包含联系信息的省市下拉
    self._register_combo_wheel_block(self.contact_province_combo)
    self._register_combo_wheel_block(self.contact_city_combo)
    try:
        self._register_combo_wheel_block(self.contact_name_edit)
        self._register_combo_wheel_block(self.contact_phone_edit)
        self._register_combo_wheel_block(self.contact_email_edit)
        self._register_combo_wheel_block(self.contact_street_edit)
        self._register_combo_wheel_block(self.contact_zip_edit)
    except Exception:
        pass
