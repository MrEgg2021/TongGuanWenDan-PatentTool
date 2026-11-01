from __future__ import annotations

import hashlib
from datetime import datetime

from core.request_form_xml_impl.normalize import _normalize_applicant_type_code, _normalize_id_type_code
from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready
from gui.dialog_utils import show_blocking_alert_modal
from gui.widgets_impl.request_form.regions import get_region_code_from_combo


def _norm_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _make_record_hash(*parts) -> str:
    raw = "\x1f".join(_norm_text(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _coalesce_non_empty_str(new_val, old_val) -> str:
    nv = _norm_text(new_val)
    if nv:
        return nv
    return _norm_text(old_val)


def _coalesce_non_empty_int(new_val, old_val):
    if new_val is None:
        try:
            return int(old_val) if old_val is not None else None
        except Exception:
            return None
    try:
        return int(new_val)
    except Exception:
        try:
            return int(old_val) if old_val is not None else None
        except Exception:
            return None


def _collect_record(self):
    applicant_name = _norm_text(self.applicant_name_edit.text())
    applicant_type_code = _normalize_applicant_type_code(
        self.applicant_type_combo.currentData(),
        self.applicant_type_combo.currentText(),
        "",
    )
    applicant_id_type_code = _normalize_id_type_code(
        self.applicant_id_type_combo.currentData(),
        self.applicant_id_type_combo.currentText(),
        "",
    )
    applicant_id_no = _norm_text(self.applicant_id_no_edit.text())
    applicant_phone = _norm_text(self.applicant_phone_edit.text())
    applicant_email = _norm_text(self.applicant_email_edit.text())

    applicant_province_code = _norm_text(get_region_code_from_combo(self, self.applicant_province_combo))
    applicant_city_code = _norm_text(get_region_code_from_combo(self, self.applicant_city_combo))
    applicant_address = _norm_text(self.applicant_address_edit.text())
    applicant_zip = _norm_text(self.applicant_zip_edit.text())

    inventor_name = _norm_text(self.inventor_name_edit.text())
    inventor_id_type = _norm_text(self.inventor_id_type_combo.currentText())
    inventor_id_no = _norm_text(self.inventor_id_no_edit.text())
    inventor_nationality = _norm_text(self.inventor_nationality_edit.text()) or "CN"

    power_of_attorney_no = _norm_text(
        getattr(self, "power_of_attorney_no_edit", None).text()
        if getattr(self, "power_of_attorney_no_edit", None) is not None
        else ""
    )
    agency_ref_name = _norm_text(
        getattr(self, "agency_ref_name_edit", None).text()
        if getattr(self, "agency_ref_name_edit", None) is not None
        else ""
    )
    agency_ref_code = _norm_text(
        getattr(self, "agency_ref_code_edit", None).text()
        if getattr(self, "agency_ref_code_edit", None) is not None
        else ""
    )

    contact_name = _norm_text(self.contact_name_edit.text())
    contact_phone = _norm_text(self.contact_phone_edit.text())
    contact_email = _norm_text(self.contact_email_edit.text())
    contact_province_code = _norm_text(get_region_code_from_combo(self, self.contact_province_combo))
    contact_city_code = _norm_text(get_region_code_from_combo(self, self.contact_city_combo))
    contact_street = _norm_text(self.contact_street_edit.text())
    contact_zip = _norm_text(self.contact_zip_edit.text())

    group_name = _norm_text(self.group_name_edit.text())

    payload = {
        "applicant_name": applicant_name,
        "applicant_type_code": _norm_text(applicant_type_code),
        "applicant_id_type_code": _norm_text(applicant_id_type_code),
        "applicant_id_no": applicant_id_no,
        "applicant_province_code": applicant_province_code,
        "applicant_city_code": applicant_city_code,
        "applicant_address": applicant_address,
        "applicant_zip": applicant_zip,
        "applicant_phone": applicant_phone,
        "applicant_email": applicant_email,
        "inventor_name": inventor_name,
        "inventor_id_type": inventor_id_type,
        "inventor_id_no": inventor_id_no,
        "inventor_nationality_code": inventor_nationality,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "contact_email": contact_email,
        "contact_province_code": contact_province_code,
        "contact_city_code": contact_city_code,
        "contact_street": contact_street,
        "contact_zip": contact_zip,
        "power_of_attorney_no": power_of_attorney_no,
        "agency_ref_name": agency_ref_name,
        "agency_ref_code": agency_ref_code,
        "group_name": group_name,
    }
    return payload


def _is_empty_payload(self, payload: dict) -> bool:
    for _k, v in payload.items():
        if _norm_text(v):
            return False
    return True


def _on_save_clicked(self) -> None:
    payload = self._collect_record()
    if self._is_empty_payload(payload):
        show_blocking_alert_modal(self, "提示", "当前记录为空，未保存。", primary_text="关闭", secondary_text="关闭")
        return

    record_hash = _make_record_hash(
        payload.get("applicant_name"),
        payload.get("applicant_type_code"),
        payload.get("applicant_id_type_code"),
        payload.get("applicant_id_no"),
        payload.get("applicant_province_code"),
        payload.get("applicant_city_code"),
        payload.get("applicant_address"),
        payload.get("applicant_zip"),
        payload.get("applicant_phone"),
        payload.get("applicant_email"),
        payload.get("inventor_name"),
        payload.get("inventor_id_type"),
        payload.get("inventor_id_no"),
        payload.get("inventor_nationality_code"),
        payload.get("contact_name"),
        payload.get("contact_phone"),
        payload.get("contact_email"),
        payload.get("contact_province_code"),
        payload.get("contact_city_code"),
        payload.get("contact_street"),
        payload.get("contact_zip"),
        payload.get("group_name"),
        payload.get("power_of_attorney_no"),
        payload.get("agency_ref_code"),
    )

    db_path = get_db_path()
    try:
        ensure_db_ready(db_path)
    except Exception:
        pass

    inserted = 0
    updated = 0
    try:
        with db_session(db_path) as conn:
            existing = conn.execute(
                "SELECT * FROM tgd_fact_record WHERE record_hash = ? LIMIT 1",
                (record_hash,),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE tgd_fact_record
                    SET
                        applicant_name = ?,
                        applicant_type_code = ?,
                        applicant_id_type_code = ?,
                        applicant_id_no = ?,
                        applicant_province_code = ?,
                        applicant_city_code = ?,
                        applicant_address = ?,
                        applicant_zip = ?,
                        applicant_phone = ?,
                        applicant_email = ?,
                        inventor_name = ?,
                        inventor_id_type = ?,
                        inventor_id_no = ?,
                        inventor_nationality_code = ?,
                        contact_name = ?,
                        contact_phone = ?,
                        contact_email = ?,
                        contact_province_code = ?,
                        contact_city_code = ?,
                        contact_street = ?,
                        contact_zip = ?,
                        group_name = ?,
                        power_of_attorney_no = ?,
                        agency_ref_name = ?,
                        agency_ref_code = ?,
                        updated_at = ?,
                        source_type = ?,
                        source_ref = ?
                    WHERE record_hash = ?
                    """,
                    (
                        _coalesce_non_empty_str(payload.get("applicant_name"), existing["applicant_name"]),
                        _coalesce_non_empty_str(payload.get("applicant_type_code"), existing["applicant_type_code"]),
                        _coalesce_non_empty_str(payload.get("applicant_id_type_code"), existing["applicant_id_type_code"]),
                        _coalesce_non_empty_str(payload.get("applicant_id_no"), existing["applicant_id_no"]),
                        _coalesce_non_empty_str(payload.get("applicant_province_code"), existing["applicant_province_code"]),
                        _coalesce_non_empty_str(payload.get("applicant_city_code"), existing["applicant_city_code"]),
                        _coalesce_non_empty_str(payload.get("applicant_address"), existing["applicant_address"]),
                        _coalesce_non_empty_str(payload.get("applicant_zip"), existing["applicant_zip"]),
                        _coalesce_non_empty_str(payload.get("applicant_phone"), existing["applicant_phone"]),
                        _coalesce_non_empty_str(payload.get("applicant_email"), existing["applicant_email"]),
                        _coalesce_non_empty_str(payload.get("inventor_name"), existing["inventor_name"]),
                        _coalesce_non_empty_str(payload.get("inventor_id_type"), existing["inventor_id_type"]),
                        _coalesce_non_empty_str(payload.get("inventor_id_no"), existing["inventor_id_no"]),
                        _coalesce_non_empty_str(payload.get("inventor_nationality_code"), existing["inventor_nationality_code"]),
                        _coalesce_non_empty_str(payload.get("contact_name"), existing["contact_name"]),
                        _coalesce_non_empty_str(payload.get("contact_phone"), existing["contact_phone"]),
                        _coalesce_non_empty_str(payload.get("contact_email"), existing["contact_email"]),
                        _coalesce_non_empty_str(payload.get("contact_province_code"), existing["contact_province_code"]),
                        _coalesce_non_empty_str(payload.get("contact_city_code"), existing["contact_city_code"]),
                        _coalesce_non_empty_str(payload.get("contact_street"), existing["contact_street"]),
                        _coalesce_non_empty_str(payload.get("contact_zip"), existing["contact_zip"]),
                        _coalesce_non_empty_str(payload.get("group_name"), existing["group_name"]),
                        _coalesce_non_empty_str(payload.get("power_of_attorney_no"), existing["power_of_attorney_no"]),
                        _coalesce_non_empty_str(payload.get("agency_ref_name"), existing["agency_ref_name"]),
                        _coalesce_non_empty_str(payload.get("agency_ref_code"), existing["agency_ref_code"]),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "manual",
                        "data_mgmt_manual",
                        record_hash,
                    ),
                )
                updated = 1
            else:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    """
                    INSERT INTO tgd_fact_record(
                        record_hash,
                        applicant_name, applicant_type_code, applicant_id_type_code, applicant_id_no,
                        applicant_province_code, applicant_city_code, applicant_address, applicant_zip,
                        applicant_phone, applicant_email,
                        inventor_name, inventor_id_type, inventor_id_no, inventor_nationality_code,
                        contact_name, contact_phone, contact_email, contact_province_code, contact_city_code, contact_street, contact_zip,
                        power_of_attorney_no, agency_ref_name, agency_ref_code,
                        group_name,
                        created_at, updated_at, source_type, source_ref
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_hash,
                        payload.get("applicant_name"),
                        payload.get("applicant_type_code"),
                        payload.get("applicant_id_type_code"),
                        payload.get("applicant_id_no"),
                        payload.get("applicant_province_code"),
                        payload.get("applicant_city_code"),
                        payload.get("applicant_address"),
                        payload.get("applicant_zip"),
                        payload.get("applicant_phone"),
                        payload.get("applicant_email"),
                        payload.get("inventor_name"),
                        payload.get("inventor_id_type"),
                        payload.get("inventor_id_no"),
                        payload.get("inventor_nationality_code"),
                        payload.get("contact_name"),
                        payload.get("contact_phone"),
                        payload.get("contact_email"),
                        payload.get("contact_province_code"),
                        payload.get("contact_city_code"),
                        payload.get("contact_street"),
                        payload.get("contact_zip"),
                        payload.get("power_of_attorney_no"),
                        payload.get("agency_ref_name"),
                        payload.get("agency_ref_code"),
                        payload.get("group_name"),
                        now,
                        now,
                        "manual",
                        "data_mgmt_manual",
                    ),
                )
                inserted = 1
    except Exception as e:
        show_blocking_alert_modal(self, "错误", f"保存失败：{e}", primary_text="关闭", secondary_text="关闭")
        return

    msg = f"保存完成：新增 {inserted}，更新 {updated}" if (inserted or updated) else "未保存"
    show_blocking_alert_modal(self, "完成", msg, primary_text="关闭", secondary_text="关闭")
