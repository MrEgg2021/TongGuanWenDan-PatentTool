from __future__ import annotations

from gui.widgets_impl.request_form.regions import (
    get_region_code_from_combo,
    populate_city_combo,
    populate_province_combo,
)


def _norm_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _init_region_widgets(self) -> None:
    populate_province_combo(self, self.applicant_province_combo, "")
    populate_city_combo(self, self.applicant_city_combo, "", "")
    populate_province_combo(self, self.contact_province_combo, "")
    populate_city_combo(self, self.contact_city_combo, "", "")

    try:
        self.applicant_province_combo.currentIndexChanged.connect(self._on_applicant_province_changed)
    except Exception:
        pass
    try:
        self.contact_province_combo.currentIndexChanged.connect(self._on_contact_province_changed)
    except Exception:
        pass


def _on_applicant_province_changed(self) -> None:
    prov = _norm_text(get_region_code_from_combo(self, self.applicant_province_combo))
    populate_city_combo(self, self.applicant_city_combo, prov, "")


def _on_contact_province_changed(self) -> None:
    prov = _norm_text(get_region_code_from_combo(self, self.contact_province_combo))
    populate_city_combo(self, self.contact_city_combo, prov, "")
