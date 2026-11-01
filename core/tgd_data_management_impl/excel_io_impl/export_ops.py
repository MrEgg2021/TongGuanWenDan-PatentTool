from __future__ import annotations

from typing import List, Optional

from core.excel_text import append_text_row
from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready

from .constants import _AGENCY_HEADERS, _AGENCY_SHEET_NAME, _FACT_HEADERS, _FACT_SHEET_NAME
from .debug import excel_dbg
from .openpyxl_utils import _require_openpyxl
from .text_utils import (
    _applicant_id_type_text_from_code,
    _applicant_type_text_from_code,
    _mask_email,
    _mask_id_number,
    _mask_phone,
    _normalize_text,
    _format_merged_address,
    mask_text,
)


def export_tgd_excel_template(dest_path: str) -> None:
    Workbook, _ = _require_openpyxl()
    wb = Workbook()
    excel_dbg(f"export_template dest={_normalize_text(dest_path)}")

    ws = wb.active
    ws.title = _FACT_SHEET_NAME
    ws.append(_FACT_HEADERS)

    try:
        from openpyxl.worksheet.datavalidation import DataValidation

        def _add_list_validation(col: str, items: List[str], prompt: str) -> None:
            formula = '"' + ",".join(str(x) for x in items) + '"'
            dv = DataValidation(type="list", formula1=formula, allow_blank=True)
            dv.errorStyle = "warning"
            dv.errorTitle = "提示"
            dv.error = "建议从下拉选择；也可手动输入其他内容。"
            dv.showErrorMessage = True
            dv.promptTitle = "提示"
            dv.prompt = prompt
            dv.showInputMessage = True
            ws.add_data_validation(dv)
            dv.add(f"{col}2:{col}1048576")

        _add_list_validation(
            "B",
            ["工矿企业", "个人", "事业单位/科研机构"],
            "建议从下拉选择；也可手动输入其他内容。",
        )
        _add_list_validation(
            "C",
            ["统一社会信用代码", "居民身份证", "其他"],
            "建议从下拉选择；也可手动输入其他内容。",
        )
        _add_list_validation(
            "J",
            ["居民身份证", "护照", "其他"],
            "可下拉选择，也可手动输入其他内容。",
        )
        _add_list_validation(
            "L",
            ["CN"],
            "可下拉选择，也可手动输入其他国家代码。",
        )
    except Exception:
        pass

    ws2 = wb.create_sheet(_AGENCY_SHEET_NAME)
    ws2.append(_AGENCY_HEADERS)

    wb.save(dest_path)


def export_tgd_excel_data(
    dest_path: str,
    *,
    masked: bool = False,
    fact_record_ids: Optional[List[int]] = None,
    agency_agent_ids: Optional[List[int]] = None,
) -> None:
    Workbook, _ = _require_openpyxl()
    db_path = get_db_path()
    ensure_db_ready(db_path)
    try:
        excel_dbg(
            f"export_data dest={_normalize_text(dest_path)} masked={bool(masked)} facts={('all' if fact_record_ids is None else len(fact_record_ids or []))} agencies={('all' if agency_agent_ids is None else len(agency_agent_ids or []))}"
        )
    except Exception:
        pass

    wb = Workbook()

    with db_session(db_path) as conn:
        ws = wb.active
        ws.title = _FACT_SHEET_NAME
        ws.append(_FACT_HEADERS)

        fact_rows = []
        if fact_record_ids is None:
            cur = conn.execute(
                """
                SELECT
                    applicant_name,
                    applicant_type_code,
                    applicant_id_type_code,
                    applicant_id_no,
                    applicant_province_code,
                    applicant_city_code,
                    applicant_address,
                    applicant_zip,
                    applicant_phone,
                    applicant_email,

                    inventor_name,
                    inventor_id_type,
                    inventor_id_no,
                    inventor_nationality_code,

                    contact_name,
                    contact_phone,
                    contact_email,
                    contact_province_code,
                    contact_city_code,
                    contact_street,
                    contact_zip,

                    power_of_attorney_no,
                    agency_ref_name,
                    agency_ref_code,

                    group_name
                FROM tgd_fact_record
                ORDER BY id ASC
                """
            )
            fact_rows = cur.fetchall() or []
        else:
            ids = [int(x) for x in (fact_record_ids or []) if x is not None]
            if ids:
                placeholders = ",".join(["?"] * len(ids))
                cur = conn.execute(
                    f"""
                    SELECT
                        applicant_name,
                        applicant_type_code,
                        applicant_id_type_code,
                        applicant_id_no,
                        applicant_province_code,
                        applicant_city_code,
                        applicant_address,
                        applicant_zip,
                        applicant_phone,
                        applicant_email,

                        inventor_name,
                        inventor_id_type,
                        inventor_id_no,
                        inventor_nationality_code,

                        contact_name,
                        contact_phone,
                        contact_email,
                        contact_province_code,
                        contact_city_code,
                        contact_street,
                        contact_zip,

                        power_of_attorney_no,
                        agency_ref_name,
                        agency_ref_code,

                        group_name
                    FROM tgd_fact_record
                    WHERE id IN ({placeholders})
                    ORDER BY id ASC
                    """,
                    tuple(ids),
                )
                fact_rows = cur.fetchall() or []
            else:
                fact_rows = []

        for row in fact_rows:
            applicant_id_no = _normalize_text(row["applicant_id_no"])
            if masked:
                applicant_id_no = mask_text(applicant_id_no)

            applicant_phone = _normalize_text(row["applicant_phone"])
            if masked:
                applicant_phone = _mask_phone(applicant_phone)

            applicant_email = _normalize_text(row["applicant_email"])
            if masked:
                applicant_email = _mask_email(applicant_email)

            inventor_id_no = _normalize_text(row["inventor_id_no"])
            if masked:
                inventor_id_no = _mask_id_number(inventor_id_no)

            contact_phone = _normalize_text(row["contact_phone"])
            if masked:
                contact_phone = _mask_phone(contact_phone)

            contact_email = _normalize_text(row["contact_email"])
            if masked:
                contact_email = _mask_email(contact_email)

            app_addr = _format_merged_address(
                province_code=_normalize_text(row["applicant_province_code"]),
                city_code=_normalize_text(row["applicant_city_code"]),
                detail=_normalize_text(row["applicant_address"]),
                zip_code="",
                masked=masked,
            )
            app_zip = _normalize_text(row["applicant_zip"])
            contact_addr = _format_merged_address(
                province_code=_normalize_text(row["contact_province_code"]),
                city_code=_normalize_text(row["contact_city_code"]),
                detail=_normalize_text(row["contact_street"]),
                zip_code="",
                masked=masked,
            )

            append_text_row(
                ws,
                [
                    _normalize_text(row["applicant_name"]),
                    _applicant_type_text_from_code(row["applicant_type_code"]),
                    _applicant_id_type_text_from_code(row["applicant_id_type_code"]),
                    applicant_id_no,
                    applicant_phone,
                    applicant_email,
                    app_addr,
                    app_zip,
                    _normalize_text(row["inventor_name"]),
                    _normalize_text(row["inventor_id_type"]),
                    inventor_id_no,
                    _normalize_text(row["inventor_nationality_code"]) or "CN",
                    _normalize_text(row["contact_name"]),
                    contact_phone,
                    contact_email,
                    contact_addr,
                    _normalize_text(row["contact_zip"]),
                    _normalize_text(row["group_name"]),
                    _normalize_text(row["power_of_attorney_no"]),
                    _normalize_text(row["agency_ref_name"]),
                    _normalize_text(row["agency_ref_code"]),
                ]
            )

        try:
            excel_dbg(f"export_data fact_rows={len(fact_rows or [])}")
        except Exception:
            pass

        ws2 = wb.create_sheet(_AGENCY_SHEET_NAME)
        ws2.append(_AGENCY_HEADERS)

        try:
            agency_rows = []
            if agency_agent_ids is None:
                cur2 = conn.execute(
                    """
                    SELECT agency_name, agency_code, agent_name, agent_cert_no, agent_phone
                    FROM tgd_agency_agent
                    ORDER BY agency_code ASC, sort_order ASC, id ASC
                    """
                )
                agency_rows = cur2.fetchall() or []
            else:
                ids = [int(x) for x in (agency_agent_ids or []) if x is not None]
                if ids:
                    placeholders = ",".join(["?"] * len(ids))
                    cur2 = conn.execute(
                        f"""
                        SELECT agency_name, agency_code, agent_name, agent_cert_no, agent_phone
                        FROM tgd_agency_agent
                        WHERE id IN ({placeholders})
                        ORDER BY agency_code ASC, sort_order ASC, id ASC
                        """,
                        tuple(ids),
                    )
                    agency_rows = cur2.fetchall() or []
                else:
                    agency_rows = []

            for row in agency_rows:
                append_text_row(
                    ws2,
                    [
                        _normalize_text(row["agency_name"]),
                        _normalize_text(row["agency_code"]),
                        _normalize_text(row["agent_name"]),
                        _normalize_text(row["agent_cert_no"]),
                        _normalize_text(row["agent_phone"]),
                    ]
                )
            try:
                excel_dbg(f"export_data agency_rows={len(agency_rows or [])}")
            except Exception:
                pass
        except Exception:
            pass

    wb.save(dest_path)
