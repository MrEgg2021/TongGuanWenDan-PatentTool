from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)
from gui.dialog_utils import show_blocking_alert_modal

from .dialog_ui_utils import AdaptiveWidthSpec, bind_adaptive_width


def _mark_field_label(lbl: QLabel) -> None:
    try:
        lbl.setProperty("role", "label")
        lbl.setProperty("emphasis", True)
    except Exception:
        pass


_INVENTOR_ID_TYPE_OPTIONS = ("\u5c45\u6c11\u8eab\u4efd\u8bc1", "\u62a4\u7167", "\u5176\u4ed6")


def _normalize_inventor_id_type_value(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return _INVENTOR_ID_TYPE_OPTIONS[0]
    upper = text.upper()
    compact = text.replace(" ", "")
    if compact in _INVENTOR_ID_TYPE_OPTIONS:
        return compact
    if upper in {"I", "ID", "IDCARD"} or ("\u8eab\u4efd\u8bc1" in text):
        return _INVENTOR_ID_TYPE_OPTIONS[0]
    if upper in {"P", "PASSPORT"} or ("\u62a4\u7167" in text):
        return _INVENTOR_ID_TYPE_OPTIONS[1]
    if upper in {"O", "OTHER", "0"} or ("\u5176\u4ed6" in text):
        return _INVENTOR_ID_TYPE_OPTIONS[2]
    return _INVENTOR_ID_TYPE_OPTIONS[0]

def create_applicant_tab(self, data: dict, index: int) -> QWidget:
    tab = QWidget(self)
    layout = QGridLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(8)

    # Row 0
    name_label = QLabel("申请人名称：", tab)
    _mark_field_label(name_label)
    name_edit = QComboBox(tab)
    name_edit.setEditable(True)
    name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    try:
        bind_adaptive_width(name_edit, AdaptiveWidthSpec(sample_chars=12, max_chars=28, kind="cjk"))
    except Exception:
        pass

    type_label = QLabel("类型：", tab)
    _mark_field_label(type_label)
    type_combo = QComboBox(tab)
    type_combo.setEditable(True)
    type_combo.addItem("3 - 工矿企业", "3")
    type_combo.addItem("1 - 个人", "1")
    type_combo.addItem("2 - 事业单位/科研机构", "2")
    try:
        bind_adaptive_width(type_combo, AdaptiveWidthSpec(sample_chars=8, max_chars=12, kind="cjk"))
    except Exception:
        pass

    layout.addWidget(name_label, 0, 0)
    layout.addWidget(name_edit, 0, 1, 1, 3)  # Span 3 cols
    layout.addWidget(type_label, 0, 4)
    layout.addWidget(type_combo, 0, 5)

    # Row 1
    id_type_label = QLabel("证件类型：", tab)
    _mark_field_label(id_type_label)
    id_type_combo = QComboBox(tab)
    id_type_combo.setEditable(True)
    id_type_combo.addItem("F - 统一社会信用代码", "F")
    id_type_combo.addItem("身份证")
    id_type_combo.addItem("其他")
    try:
        bind_adaptive_width(id_type_combo, AdaptiveWidthSpec(sample_chars=10, max_chars=19, kind="cjk"))
    except Exception:
        pass

    id_label = QLabel("证件号码：", tab)
    _mark_field_label(id_label)
    id_edit = QComboBox(tab)
    id_edit.setEditable(True)
    id_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    try:
        bind_adaptive_width(id_edit, AdaptiveWidthSpec(sample_chars=20, max_chars=20, kind="alnum_upper"))
    except Exception:
        pass

    phone_label = QLabel("电话：", tab)
    _mark_field_label(phone_label)
    phone_edit = QComboBox(tab)
    phone_edit.setEditable(True)
    try:
        bind_adaptive_width(phone_edit, AdaptiveWidthSpec(sample_chars=14, max_chars=14, kind="digits"))
    except Exception:
        pass

    layout.addWidget(id_type_label, 1, 0)
    layout.addWidget(id_type_combo, 1, 1)
    layout.addWidget(id_label, 1, 2)
    layout.addWidget(id_edit, 1, 3)
    layout.addWidget(phone_label, 1, 4)
    layout.addWidget(phone_edit, 1, 5)

    # Row 2
    prov_label = QLabel("省代码：", tab)
    _mark_field_label(prov_label)
    province_combo = QComboBox(tab)
    province_combo.setEditable(True)
    province_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    city_label = QLabel("市/区代码：", tab)
    _mark_field_label(city_label)
    city_combo = QComboBox(tab)
    city_combo.setEditable(True)
    city_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    try:
        bind_adaptive_width(province_combo, AdaptiveWidthSpec(sample_chars=10, max_chars=23, kind="cjk_digit"))
        bind_adaptive_width(city_combo, AdaptiveWidthSpec(sample_chars=10, max_chars=23, kind="cjk_digit"))
    except Exception:
        pass

    zip_label = QLabel("邮编：", tab)
    _mark_field_label(zip_label)
    zip_edit = QComboBox(tab)
    zip_edit.setEditable(True)
    try:
        bind_adaptive_width(zip_edit, AdaptiveWidthSpec(sample_chars=7, max_chars=11, kind="digits"))
    except Exception:
        pass

    layout.addWidget(prov_label, 2, 0)
    layout.addWidget(province_combo, 2, 1)
    layout.addWidget(city_label, 2, 2)
    layout.addWidget(city_combo, 2, 3)
    layout.addWidget(zip_label, 2, 4)
    layout.addWidget(zip_edit, 2, 5)

    # Row 3
    addr_label = QLabel("详细地址：", tab)
    _mark_field_label(addr_label)
    address_edit = QComboBox(tab)
    address_edit.setEditable(True)
    address_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    try:
        bind_adaptive_width(address_edit, AdaptiveWidthSpec(sample_chars=15, max_chars=40, kind="cjk"))
    except Exception:
        pass

    email_label = QLabel("电子邮箱：", tab)
    # _mark_field_label(email_label)
    email_edit = QComboBox(tab)
    email_edit.setEditable(True)
    try:
        bind_adaptive_width(email_edit, AdaptiveWidthSpec(sample_chars=12, max_chars=28, kind="alnum_symbol"))
    except Exception:
        pass

    layout.addWidget(addr_label, 3, 0)
    layout.addWidget(address_edit, 3, 1, 1, 3)  # Span 3 cols
    layout.addWidget(email_label, 3, 4)
    layout.addWidget(email_edit, 3, 5)

    # Row 4 (POA)
    poa_row_widget = QWidget(tab)
    poa_row = QHBoxLayout(poa_row_widget)
    poa_row.setContentsMargins(0, 0, 0, 0)
    poa_row.setSpacing(4)
    poa_label = QLabel("总委托书编号：", tab)
    _mark_field_label(poa_label)
    poa_edit = QComboBox(tab)
    poa_edit.setEditable(True)
    try:
        bind_adaptive_width(poa_edit, AdaptiveWidthSpec(sample_chars=10, max_chars=21, kind="alnum"))
    except Exception:
        pass
    poa_row.addWidget(poa_label, 0)
    poa_row.addWidget(poa_edit, 1)

    layout.addWidget(poa_row_widget, 4, 0, 1, 2)  # Place at bottom left, span 2

    # Column Stretch
    layout.setColumnStretch(1, 0)
    layout.setColumnStretch(3, 0)
    layout.setColumnStretch(5, 0)
    layout.setColumnStretch(6, 1)

    # Register wheel blocks
    try:
        self._register_combo_wheel_block(type_combo)
        self._register_combo_wheel_block(id_type_combo)
        self._register_combo_wheel_block(poa_edit)
        self._register_combo_wheel_block(province_combo)
        self._register_combo_wheel_block(city_combo)
    except Exception:
        pass

    tab.name_edit = name_edit
    tab.poa_row_widget = poa_row_widget
    tab.poa_edit = poa_edit
    tab.type_combo = type_combo
    tab.id_type_combo = id_type_combo
    tab.id_edit = id_edit
    tab.province_combo = province_combo
    tab.city_combo = city_combo
    tab.address_edit = address_edit
    tab.zip_edit = zip_edit
    tab.phone_edit = phone_edit
    tab.email_edit = email_edit

    name_edit.setEditText(str(data.get("name") or ""))
    poa_edit.setEditText(str(data.get("power_of_attorney_no") or ""))
    type_code_raw = data.get("type_code")
    if type_code_raw:
        code_str = str(type_code_raw)
        idx = type_combo.findData(code_str)
        if idx >= 0:
            type_combo.setCurrentIndex(idx)
        else:
            type_combo.setEditText(code_str)
    else:
        type_text_raw = data.get("type", "") or ""
        if type_text_raw:
            idx = type_combo.findText(str(type_text_raw))
            if idx >= 0:
                type_combo.setCurrentIndex(idx)
            else:
                type_combo.setEditText(str(type_text_raw))

    id_type_code_raw = data.get("id_type_code")
    if id_type_code_raw:
        code_str = str(id_type_code_raw)
        idx = id_type_combo.findData(code_str)
        if idx >= 0:
            id_type_combo.setCurrentIndex(idx)
        else:
            id_type_combo.setEditText(code_str)
    else:
        id_type_text_raw = data.get("id_type", "") or ""
        if id_type_text_raw:
            idx = id_type_combo.findText(str(id_type_text_raw))
            if idx >= 0:
                id_type_combo.setCurrentIndex(idx)
            else:
                id_type_combo.setEditText(str(id_type_text_raw))

    id_edit.setEditText(str(data.get("id_no") or ""))
    prov_raw = data.get("province_code", data.get("province", "")) or ""
    city_raw = data.get("city_code", data.get("city", "")) or ""
    district_raw = data.get("district_code", data.get("district", "")) or ""
    if district_raw and not city_raw:
        city_raw = district_raw
    try:
        init_region = getattr(self, "_init_applicant_region_widgets", None)
        if callable(init_region):
            init_region(tab, province_code=str(prov_raw), city_code=str(city_raw))
        else:
            set_region = getattr(self, "_set_region_combo_value", None)
            if callable(set_region):
                set_region(getattr(tab, "province_combo", None), str(prov_raw), kind="province")
                set_region(getattr(tab, "city_combo", None), str(city_raw), kind="city")
    except Exception:
        pass

    address_edit.setEditText(str(data.get("address") or ""))
    zip_edit.setEditText(str(data.get("zip") or ""))
    phone_edit.setEditText(str(data.get("phone") or ""))
    email_edit.setEditText(str(data.get("email") or ""))

    enabled_poa = False
    try:
        chk = getattr(self, "agency_enabled_checkbox", None)
        if chk is not None:
            enabled_poa = bool(chk.isChecked())
    except Exception:
        enabled_poa = False
    try:
        poa_row_widget.setVisible(bool(enabled_poa))
    except Exception:
        pass

    tab_title = f"申请人{index}"
    self.app_tabs.addTab(tab, tab_title)

    try:
        setup_fn = getattr(self, "_setup_inline_fact_dropdowns_for_applicant_tab", None)
        if callable(setup_fn):
            setup_fn(tab)
    except Exception:
        pass
    return tab


def add_applicant_tab(self, data: dict) -> None:
    index = self.app_tabs.count() + 1
    if index > 5:
        show_blocking_alert_modal(self, "提示", "申请人数量已达到上限（5 个）", primary_text="关闭", secondary_text="关闭")
        return
    self._create_applicant_tab(data, index)
    try:
        self._renumber_applicant_tabs()
    except Exception:
        pass


def remove_current_applicant_tab(self) -> None:
    if self.app_tabs.count() <= 1:
        show_blocking_alert_modal(self, "提示", "至少需要保留一个申请人", primary_text="关闭", secondary_text="关闭")
        return
    idx = self.app_tabs.currentIndex()
    if idx >= 0:
        self.app_tabs.removeTab(idx)
    try:
        self._renumber_applicant_tabs()
    except Exception:
        pass


def renumber_applicant_tabs(self) -> None:
    tabs = getattr(self, "app_tabs", None)
    if tabs is None:
        return
    try:
        cnt = int(tabs.count())
    except Exception:
        return
    for i in range(cnt):
        try:
            tabs.setTabText(i, f"申请人{i + 1}")
        except Exception:
            pass


def create_inventor_tab(self, data: dict, index: int) -> QWidget:
    tab = QWidget(self)
    layout = QGridLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(8)

    # Row 0
    name_label = QLabel("发明人姓名：", tab)
    _mark_field_label(name_label)
    name_edit = QComboBox(tab)
    name_edit.setEditable(True)
    name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    try:
        bind_adaptive_width(name_edit, AdaptiveWidthSpec(sample_chars=20, max_chars=28, kind="cjk"))
    except Exception:
        pass

    nat_label = QLabel("国籍代码：", tab)
    _mark_field_label(nat_label)
    nationality_combo = QComboBox(tab)
    nationality_combo.setEditable(True)
    nationality_combo.addItem("CN")
    try:
        bind_adaptive_width(nationality_combo, AdaptiveWidthSpec(sample_chars=4, max_chars=6, kind="upper"))
    except Exception:
        pass

    layout.addWidget(name_label, 0, 0)
    layout.addWidget(name_edit, 0, 1)
    layout.addWidget(nat_label, 0, 2)
    layout.addWidget(nationality_combo, 0, 3)

    # Row 1
    id_type_label = QLabel("证件类型：", tab)
    _mark_field_label(id_type_label)
    id_type_combo = QComboBox(tab)
    id_type_combo.setEditable(False)
    for text in _INVENTOR_ID_TYPE_OPTIONS:
        id_type_combo.addItem(text)
    id_type_combo.setCurrentIndex(0)
    try:
        bind_adaptive_width(id_type_combo, AdaptiveWidthSpec(sample_chars=10, max_chars=19, kind="cjk"))
    except Exception:
        pass

    id_label = QLabel("证件号码：", tab)
    _mark_field_label(id_label)
    id_edit = QComboBox(tab)
    id_edit.setEditable(True)
    id_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    try:
        bind_adaptive_width(id_edit, AdaptiveWidthSpec(sample_chars=20, max_chars=20, kind="alnum_upper"))
    except Exception:
        pass

    layout.addWidget(id_type_label, 1, 0)
    layout.addWidget(id_type_combo, 1, 1)
    layout.addWidget(id_label, 1, 2)
    layout.addWidget(id_edit, 1, 3)

    # Column Stretch
    layout.setColumnStretch(1, 0)
    layout.setColumnStretch(3, 0)
    layout.setColumnStretch(4, 1)

    try:
        self._register_combo_wheel_block(id_type_combo)
        self._register_combo_wheel_block(nationality_combo)
    except Exception:
        pass

    tab.name_edit = name_edit
    tab.id_type_combo = id_type_combo
    tab.id_edit = id_edit
    tab.nationality_combo = nationality_combo

    name_edit.setEditText(str(data.get("name") or ""))
    id_type_raw = data.get("id_type_code", data.get("id_type", "")) or ""
    inventor_id_type = _normalize_inventor_id_type_value(id_type_raw)
    idx = id_type_combo.findText(inventor_id_type)
    if idx < 0:
        idx = 0
    id_type_combo.setCurrentIndex(idx)
    id_edit.setEditText(str(data.get("id_no") or ""))
    nat_raw = data.get("nationality_code", "CN") or "CN"
    idx_nat = nationality_combo.findText(str(nat_raw))
    if idx_nat >= 0:
        nationality_combo.setCurrentIndex(idx_nat)
    else:
        nationality_combo.setEditText(str(nat_raw))

    tab_title = f"发明人{index}"
    self.inv_tabs.addTab(tab, tab_title)

    try:
        setup_fn = getattr(self, "_setup_inline_fact_dropdowns_for_inventor_tab", None)
        if callable(setup_fn):
            setup_fn(tab)
    except Exception:
        pass
    return tab


def add_inventor_tab(self, data: dict) -> None:
    index = self.inv_tabs.count() + 1
    if index > 15:
        show_blocking_alert_modal(self, "提示", "发明人数量已达到上限（15 个）", primary_text="关闭", secondary_text="关闭")
        return
    self._create_inventor_tab(data, index)
    try:
        self._renumber_inventor_tabs()
    except Exception:
        pass


def remove_current_inventor_tab(self) -> None:
    if self.inv_tabs.count() <= 1:
        show_blocking_alert_modal(self, "提示", "至少需要保留一个发明人", primary_text="关闭", secondary_text="关闭")
        return
    idx = self.inv_tabs.currentIndex()
    if idx >= 0:
        self.inv_tabs.removeTab(idx)
    try:
        self._renumber_inventor_tabs()
    except Exception:
        pass


def renumber_inventor_tabs(self) -> None:
    tabs = getattr(self, "inv_tabs", None)
    if tabs is None:
        return
    try:
        cnt = int(tabs.count())
    except Exception:
        return
    for i in range(cnt):
        try:
            tabs.setTabText(i, f"发明人{i + 1}")
        except Exception:
            pass


__all__ = [
    "create_applicant_tab",
    "add_applicant_tab",
    "remove_current_applicant_tab",
    "renumber_applicant_tabs",
    "create_inventor_tab",
    "add_inventor_tab",
    "remove_current_inventor_tab",
    "renumber_inventor_tabs",
]
