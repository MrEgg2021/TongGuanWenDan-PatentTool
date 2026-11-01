from PySide6.QtWidgets import QComboBox

from core.regions_cn import CITIES_BY_PROVINCE, PROVINCES


def get_region_code_from_combo(self, combo: QComboBox) -> str:
    if combo is None:
        return ""
    data = combo.currentData()
    if isinstance(data, str) and data.strip():
        return data.strip()

    text = combo.currentText().strip()
    if not text:
        return ""
    if "(" in text and text.endswith(")"):
        inner = text[text.rfind("(") + 1 : -1].strip()
        if inner.isdigit() and len(inner) == 6:
            return inner
    return text


def populate_province_combo(self, combo: QComboBox, selected_code: str = "") -> None:
    if combo is None:
        return
    combo.blockSignals(True)
    combo.clear()
    combo.setEditable(True)
    for item in PROVINCES:
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        if not code or not name:
            continue
        text = f"{name} ({code})"
        combo.addItem(text, code)

    if selected_code:
        idx = combo.findData(selected_code)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(-1)
            combo.setEditText(selected_code)
    else:
        combo.setCurrentIndex(-1)
        combo.setEditText("")
    combo.blockSignals(False)


def populate_city_combo(self, combo: QComboBox, province_code: str, selected_code: str = "") -> None:
    if combo is None:
        return
    combo.blockSignals(True)
    combo.clear()
    combo.setEditable(True)

    cities = CITIES_BY_PROVINCE.get(province_code) or []
    for item in cities:
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        if not code or not name:
            continue
        text = f"{name} ({code})"
        combo.addItem(text, code)

    if selected_code:
        idx = combo.findData(selected_code)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(-1)
            combo.setEditText(selected_code)
    else:
        combo.setCurrentIndex(-1)
        combo.setEditText("")
    combo.blockSignals(False)


def init_contact_region_widgets(self, province_code: str = "", city_code: str = "") -> None:
    self._populate_province_combo(self.contact_province_combo, province_code)
    prov_code = province_code or self._get_region_code_from_combo(self.contact_province_combo)
    self._populate_city_combo(self.contact_city_combo, prov_code, city_code)
    if not getattr(self, "_contact_region_initialized", False):
        self.contact_province_combo.currentIndexChanged.connect(self._on_contact_province_changed)
        self._contact_region_initialized = True


def on_contact_province_changed(self) -> None:
    prov_code = self._get_region_code_from_combo(self.contact_province_combo)
    self._populate_city_combo(self.contact_city_combo, prov_code, "")


def init_applicant_region_widgets(self, tab=None, province_code: str = "", city_code: str = "") -> None:
    if tab is None:
        return
    prov_combo = getattr(tab, "province_combo", None)
    city_combo = getattr(tab, "city_combo", None)
    if prov_combo is None or city_combo is None:
        return

    self._populate_province_combo(prov_combo, province_code)
    prov_code = province_code or self._get_region_code_from_combo(prov_combo)
    self._populate_city_combo(city_combo, prov_code, city_code)

    if not getattr(tab, "_region_inited", False):
        prov_combo.currentIndexChanged.connect(lambda _idx, t=tab: self._on_applicant_province_changed(t))
        tab._region_inited = True


def on_applicant_province_changed(self, tab) -> None:
    prov_combo = getattr(tab, "province_combo", None)
    city_combo = getattr(tab, "city_combo", None)
    if prov_combo is None or city_combo is None:
        return
    prov_code = self._get_region_code_from_combo(prov_combo)
    self._populate_city_combo(city_combo, prov_code, "")


__all__ = [
    "get_region_code_from_combo",
    "populate_province_combo",
    "populate_city_combo",
    "init_contact_region_widgets",
    "on_contact_province_changed",
    "init_applicant_region_widgets",
    "on_applicant_province_changed",
]
