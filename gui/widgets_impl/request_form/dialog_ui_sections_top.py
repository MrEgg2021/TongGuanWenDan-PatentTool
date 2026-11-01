from PySide6.QtWidgets import (
     QComboBox,
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.widgets_impl.graphic_checkbox import GraphicCheckBox

from .dialog_ui_utils import AdaptiveWidthSpec, bind_adaptive_width, mark_field_label


def build_request_form_top_sections(self, form_layout: QVBoxLayout) -> None:
    self._file_label = QLabel("", self)
    self._file_label.setWordWrap(True)
    self._file_label.setStyleSheet("color: #222222; font-size: 14pt; font-weight: bold;")
    self._file_label.setVisible(False)
    form_layout.addWidget(self._file_label)

    title_row = QHBoxLayout()
    title_row.setSpacing(8)
    title_label = QLabel("专利名称：", self)
    mark_field_label(title_label)
    self.title_edit = QLineEdit(self)
    try:
        self.title_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    except Exception:
        pass
    try:
        bind_adaptive_width(self.title_edit, AdaptiveWidthSpec(sample_chars=8, max_chars=15, kind="cjk_alnum"))
    except Exception:
        pass
    title_row.addWidget(title_label)
    title_row.addWidget(self.title_edit, 1)
    form_layout.addLayout(title_row)

    type_row = QHBoxLayout()
    type_row.setSpacing(8)
    type_label = QLabel("专利类型：", self)
    mark_field_label(type_label)
    self.radio_invention = GraphicCheckBox("发明", self)
    self.radio_utility_model = GraphicCheckBox("实用新型", self)
    try:
        self.radio_invention.setProperty("emphasis", True)
        self.radio_utility_model.setProperty("emphasis", True)
    except Exception:
        pass
    self.type_group = QButtonGroup(self)
    self.type_group.addButton(self.radio_invention)
    self.type_group.addButton(self.radio_utility_model)
    self.type_group.setExclusive(True)
    self.radio_invention.setChecked(True)
    type_row.addWidget(type_label)
    type_row.addWidget(self.radio_invention)
    type_row.addWidget(self.radio_utility_model)
    type_row.addStretch()
    form_layout.addLayout(type_row)

    group_row = QHBoxLayout()
    group_row.setSpacing(8)
    group_label = QLabel("分组名称：", self)
    mark_field_label(group_label)
    self.group_name_edit = QLineEdit(self)
    try:
        self.group_name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    except Exception:
        pass
    try:
        bind_adaptive_width(self.group_name_edit, AdaptiveWidthSpec(sample_chars=8, max_chars=15, kind="cjk_alnum"))
    except Exception:
        pass
    group_row.addWidget(group_label)
    group_row.addWidget(self.group_name_edit, 1)
    form_layout.addLayout(group_row)

    try:
        self.group_name_edit.textEdited.connect(lambda _t: setattr(self, "_fact_candidates_cache_dirty", True))
    except Exception:
        pass

    options_group = QGroupBox("请求书选项", self)
    options_group.setObjectName("RequestSection")
    try:
        options_group.setFlat(True)
    except Exception:
        pass
    options_layout = QVBoxLayout(options_group)
    options_layout.setContentsMargins(8, 24, 8, 8)
    options_layout.setSpacing(8)

    options_row1 = QHBoxLayout()
    options_row1.setSpacing(8)
    self.agency_enabled_checkbox = GraphicCheckBox("是否委托代理", self)
    self.early_publication_checkbox = GraphicCheckBox("请求提前公开", self)
    self.substantive_exam_checkbox = GraphicCheckBox("实质审查请求", self)
    try:
        self.agency_enabled_checkbox.setProperty("emphasis", True)
        self.early_publication_checkbox.setProperty("emphasis", True)
        self.substantive_exam_checkbox.setProperty("emphasis", True)
    except Exception:
        pass
    self.agency_enabled_checkbox.setChecked(False)
    self.early_publication_checkbox.setChecked(True)
    self.substantive_exam_checkbox.setChecked(True)
    options_row1.addWidget(self.agency_enabled_checkbox)
    options_row1.addWidget(self.early_publication_checkbox)
    options_row1.addWidget(self.substantive_exam_checkbox)
    options_row1.addStretch(1)
    options_layout.addLayout(options_row1)

    options_row2_widget = QWidget(self)
    options_row2 = QHBoxLayout(options_row2_widget)
    options_row2.setContentsMargins(0, 0, 0, 0)
    options_row2.setSpacing(8)
    options_row2.addStretch(1)
    options_layout.addWidget(options_row2_widget)

    def _sync_poa_enabled() -> None:
        try:
            enabled = bool(self.agency_enabled_checkbox.isChecked())
        except Exception:
            enabled = False
        try:
            options_row2_widget.setVisible(enabled)
        except Exception:
            pass
        try:
            tabs = getattr(self, "app_tabs", None)
        except Exception:
            tabs = None
        if tabs is not None:
            try:
                for i in range(tabs.count()):
                    tab = tabs.widget(i)
                    poa_row = getattr(tab, "poa_row_widget", None)
                    poa_edit = getattr(tab, "poa_edit", None)
                    if poa_row is not None:
                        try:
                            poa_row.setVisible(enabled)
                        except Exception:
                            pass
                    if not enabled and poa_edit is not None:
                        try:
                            poa_edit.setEditText("")
                        except Exception:
                            try:
                                poa_edit.setText("")
                            except Exception:
                                pass
                    if not enabled and tab is not None:
                        try:
                            exact_map = getattr(self, "_fact_selected_exact_by_ctx", None)
                            if isinstance(exact_map, dict):
                                poa_ctx_key = f"poa@{id(tab)}"
                                poa_exact = exact_map.get(poa_ctx_key)
                                if isinstance(poa_exact, dict) and "power_of_attorney_no" in poa_exact:
                                    del poa_exact["power_of_attorney_no"]
                        except Exception:
                            pass
            except Exception:
                pass

    self.agency_enabled_checkbox.toggled.connect(lambda _checked: _sync_poa_enabled())
    _sync_poa_enabled()

    agency_info_group = QGroupBox("代理机构/代理师信息", self)
    agency_info_group.setObjectName("RequestSection")
    try:
        agency_info_group.setFlat(True)
    except Exception:
        pass
    self.agency_info_group = agency_info_group
    agency_info_layout = QVBoxLayout(agency_info_group)
    agency_info_layout.setContentsMargins(8, 24, 8, 8)
    agency_info_layout.setSpacing(8)

    agency_row = QHBoxLayout()
    agency_row.setSpacing(8)
    agency_name_label = QLabel("代理机构名称：", self)
    mark_field_label(agency_name_label)
    self.agency_org_name_edit = QComboBox(self)
    self.agency_org_name_edit.setEditable(True)
    agency_code_label = QLabel("代理机构代码：", self)
    mark_field_label(agency_code_label)
    self.agency_org_code_edit = QComboBox(self)
    self.agency_org_code_edit.setEditable(True)
    try:
        bind_adaptive_width(self.agency_org_name_edit, AdaptiveWidthSpec(sample_chars=15, max_chars=34, kind="cjk"))
        bind_adaptive_width(self.agency_org_code_edit, AdaptiveWidthSpec(sample_chars=9, max_chars=9, kind="digits"))
    except Exception:
        pass

    agency_row.addWidget(agency_name_label, 0)
    agency_row.addWidget(self.agency_org_name_edit, 1)
    agency_row.addWidget(agency_code_label, 0)
    agency_row.addWidget(self.agency_org_code_edit, 0)
    agency_row.addStretch(1)
    agency_info_layout.addLayout(agency_row)

    try:
        self._register_combo_wheel_block(self.agency_org_name_edit)
        self._register_combo_wheel_block(self.agency_org_code_edit)
    except Exception:
        pass

    def _build_agent_row(prefix_text: str):
        row = QHBoxLayout()
        row.setSpacing(8)

        name_label = QLabel(f"{prefix_text}姓名：", self)
        mark_field_label(name_label)
        name_edit = QComboBox(self)
        name_edit.setEditable(True)
        try:
            bind_adaptive_width(name_edit, AdaptiveWidthSpec(sample_chars=5, max_chars=8, kind="cjk"))
        except Exception:
            pass

        cert_label = QLabel(f"{prefix_text}资格证号：", self)
        mark_field_label(cert_label)
        cert_edit = QComboBox(self)
        cert_edit.setEditable(True)
        try:
            bind_adaptive_width(cert_edit, AdaptiveWidthSpec(sample_chars=11, max_chars=17, kind="digits"))
        except Exception:
            pass

        phone_label = QLabel(f"{prefix_text}电话：", self)
        mark_field_label(phone_label)
        phone_edit = QComboBox(self)
        phone_edit.setEditable(True)
        try:
            bind_adaptive_width(phone_edit, AdaptiveWidthSpec(sample_chars=14, max_chars=14, kind="digits"))
        except Exception:
            pass

        row.addWidget(name_label, 0)
        row.addWidget(name_edit, 0)
        row.addWidget(cert_label, 0)
        row.addWidget(cert_edit, 0)
        row.addWidget(phone_label, 0)
        row.addWidget(phone_edit, 0)
        row.addStretch(1)

        try:
            self._register_combo_wheel_block(name_edit)
            self._register_combo_wheel_block(cert_edit)
            self._register_combo_wheel_block(phone_edit)
        except Exception:
            pass
        return name_edit, cert_edit, phone_edit, row

    (
        self.agency_agent1_name_edit,
        self.agency_agent1_cert_edit,
        self.agency_agent1_phone_edit,
        agent1_row,
    ) = _build_agent_row("代理师1")
    (
        self.agency_agent2_name_edit,
        self.agency_agent2_cert_edit,
        self.agency_agent2_phone_edit,
        agent2_row,
    ) = _build_agent_row("代理师2")
    agency_info_layout.addLayout(agent1_row)
    agency_info_layout.addLayout(agent2_row)

    form_layout.addWidget(options_group)
    form_layout.addWidget(agency_info_group)

    def _sync_agency_info_visible() -> None:
        try:
            visible = bool(self.agency_enabled_checkbox.isChecked())
        except Exception:
            visible = False
        try:
            agency_info_group.setVisible(visible)
        except Exception:
            pass

    self.agency_enabled_checkbox.toggled.connect(lambda _checked: _sync_agency_info_visible())
    _sync_agency_info_visible()

    def _sync_substantive_exam_visible() -> None:
        try:
            is_utility = bool(self.radio_utility_model.isChecked())
        except Exception:
            is_utility = False
        try:
            self.substantive_exam_checkbox.setVisible(not is_utility)
        except Exception:
            pass
        if is_utility:
            try:
                self.substantive_exam_checkbox.setChecked(False)
            except Exception:
                pass
        else:
            try:
                self.substantive_exam_checkbox.setChecked(True)
            except Exception:
                pass

    def _sync_early_publication_visible() -> None:
        try:
            is_utility = bool(self.radio_utility_model.isChecked())
        except Exception:
            is_utility = False
        try:
            self.early_publication_checkbox.setVisible(not is_utility)
        except Exception:
            pass
        if is_utility:
            try:
                self.early_publication_checkbox.setChecked(False)
            except Exception:
                pass
        else:
            try:
                self.early_publication_checkbox.setChecked(True)
            except Exception:
                pass

    try:
        self.radio_invention.toggled.connect(lambda _checked: _sync_substantive_exam_visible())
        self.radio_utility_model.toggled.connect(lambda _checked: _sync_substantive_exam_visible())
        self.radio_invention.toggled.connect(lambda _checked: _sync_early_publication_visible())
        self.radio_utility_model.toggled.connect(lambda _checked: _sync_early_publication_visible())
    except Exception:
        pass
    _sync_substantive_exam_visible()
    _sync_early_publication_visible()
