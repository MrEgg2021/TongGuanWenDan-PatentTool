from __future__ import annotations

import os
from datetime import datetime

from core.request_form_impl.region_infer import _infer_region_from_single_address
from core.request_form_xml_impl.normalize import _normalize_applicant_type_code
from core.tgd_data_management_impl.pinyin_utils import get_pinyin_full, get_pinyin_initials

from .debug import excel_dbg
from .models import SheetImportResult
from .sheet_utils import _build_header_map, _make_row_getter, _pick_fact_sheet, _read_header_row
from .text_utils import (
    _coalesce_non_empty_str,
    _infer_applicant_id_type_from_id_no,
    _is_uscc,
    _make_record_hash,
    _normalize_applicant_id_type_code,
    _normalize_text,
)


def _import_fact_records_sheet(conn, wb, result: SheetImportResult, src_path: str) -> None:
    ws = _pick_fact_sheet(wb)
    if ws is None:
        result.errors.append("未找到 Sheet：申请信息")
        return
    try:
        excel_dbg(f"import_fact sheet={_normalize_text(getattr(ws, 'title', ''))}")
    except Exception:
        pass

    header_row = _read_header_row(ws)
    if not header_row:
        result.errors.append("常用信息：表头为空")
        return

    header_map = _build_header_map(header_row)
    _get = _make_row_getter(header_map)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base = os.path.basename(str(src_path or ""))

    has_old_inventor_flag = (
        "发明人公开/不公开" in header_map
        or "发明人请求不公开" in header_map
        or "发明人请求不公开(0/1)" in header_map
    )

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        applicant_name = _normalize_text(_get(row, "申请人名称"))
        applicant_type_code_raw = _normalize_text(_get(row, "申请人类型"))
        applicant_id_type_code = _normalize_applicant_id_type_code(_get(row, "申请人证件类型"))
        applicant_id_no = _normalize_text(_get(row, "申请人证件号码"))
        applicant_phone = _normalize_text(_get(row, "申请人电话"))
        applicant_email = _normalize_text(_get(row, "申请人电子邮箱"))
        applicant_addr_only = _normalize_text(_get(row, "申请人地址（省/市/区+详细地址）"))
        applicant_zip_in = _normalize_text(_get(row, "申请人邮编"))

        applicant_type_code = _normalize_text(
            _normalize_applicant_type_code(applicant_type_code_raw, applicant_type_code_raw, "")
        )

        inventor_name = _normalize_text(_get(row, "发明人姓名"))
        inventor_id_type = _normalize_text(_get(row, "发明人证件类型"))
        inventor_id_no = _normalize_text(_get(row, "发明人证件号码"))
        inventor_nationality = _normalize_text(_get(row, "发明人国籍代码")) or "CN"
        old_inventor_flag = _normalize_text(
            _get(row, "发明人公开/不公开")
            or _get(row, "发明人请求不公开(0/1)")
            or _get(row, "发明人请求不公开")
        )
        if has_old_inventor_flag and old_inventor_flag:
            result.errors.append(f"常用信息 第{i}行：已忽略旧列‘发明人公开/不公开’（S1 不入库）")

        contact_name = _normalize_text(_get(row, "联系人姓名"))
        contact_phone = _normalize_text(_get(row, "联系人电话"))
        contact_email = _normalize_text(_get(row, "联系人电子邮箱"))
        contact_addr_full = _normalize_text(_get(row, "联系人地址（省/市/区+街道门牌号）"))
        contact_zip = _normalize_text(_get(row, "联系人邮编"))

        group_name = _normalize_text(_get(row, "分组名称"))

        poa_no = _normalize_text(_get(row, "总委托书编号"))
        agency_ref_name = _normalize_text(_get(row, "关联代理机构名称"))
        agency_ref_code = _normalize_text(_get(row, "关联代理机构代码"))

        if poa_no and (not agency_ref_name or not agency_ref_code):
            result.skipped += 1
            result.errors.append(f"常用信息 第{i}行：总委托书编号已填写，但关联代理机构名称/代码缺失，已跳过")
            continue
        if (agency_ref_name or agency_ref_code) and (not poa_no):
            result.errors.append(f"常用信息 第{i}行：已填写关联代理机构信息但总委托书编号为空（仍继续导入）")

        if not any(
            [
                applicant_name,
                applicant_type_code,
                applicant_id_no,
                applicant_phone,
                applicant_addr_only,
                applicant_zip_in,
                inventor_name,
                inventor_id_no,
                contact_name,
                contact_phone,
                contact_addr_full,
                contact_zip,
                group_name,
            ]
        ):
            continue

        required_missing = []
        if not applicant_name:
            required_missing.append("申请人名称")
        if not applicant_type_code:
            required_missing.append("申请人类型")
        if required_missing:
            result.skipped += 1
            result.errors.append(f"常用信息 第{i}行：关键字段不能为空：" + "、".join(required_missing))
            continue

        warn_missing = []
        if not applicant_phone:
            warn_missing.append("申请人电话")
        if not applicant_addr_only:
            warn_missing.append("申请人地址")
        if not applicant_zip_in:
            warn_missing.append("申请人邮编")
        if not inventor_name:
            warn_missing.append("发明人姓名")
        if not inventor_id_no:
            warn_missing.append("发明人证件号码")
        if warn_missing:
            result.errors.append(f"常用信息 第{i}行：以下字段为空（仍继续导入）：" + "、".join(warn_missing))

        if not applicant_id_type_code:
            applicant_id_type_code = _infer_applicant_id_type_from_id_no(applicant_id_no)
        if applicant_id_type_code == "F" and (not _is_uscc(applicant_id_no)):
            result.errors.append(f"常用信息 第{i}行：统一社会信用代码疑似不合法（仍继续导入）")

        applicant_province_code = ""
        applicant_city_code = ""
        applicant_address = ""
        applicant_zip = applicant_zip_in
        if applicant_addr_only:
            app_rec = {"province": "", "city": "", "address": applicant_addr_only}
            try:
                _infer_region_from_single_address(app_rec, "address")
            except Exception:
                pass
            applicant_province_code = _normalize_text(app_rec.get("province_code"))
            applicant_city_code = _normalize_text(app_rec.get("city_code"))
            applicant_address = _normalize_text(app_rec.get("address")) or _normalize_text(applicant_addr_only)

            if not applicant_province_code or not applicant_city_code:
                result.errors.append(f"常用信息 第{i}行：无法从申请人地址解析省/市代码（仍继续导入）")
            if not applicant_zip:
                result.errors.append(f"常用信息 第{i}行：申请人邮编为空（仍继续导入）")
            if not applicant_address:
                result.errors.append(f"常用信息 第{i}行：申请人详细地址为空（仍继续导入）")

        contact_province_code = ""
        contact_city_code = ""
        contact_street = ""
        if contact_addr_full:
            c_rec = {"province": "", "city": "", "street": contact_addr_full}
            try:
                _infer_region_from_single_address(c_rec, "street")
            except Exception:
                pass
            contact_province_code = _normalize_text(c_rec.get("province_code"))
            contact_city_code = _normalize_text(c_rec.get("city_code"))
            contact_street = _normalize_text(c_rec.get("street")) or contact_addr_full

        record_hash = _make_record_hash(
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
            inventor_nationality,
            contact_name,
            contact_phone,
            contact_email,
            contact_province_code,
            contact_city_code,
            contact_street,
            contact_zip,
            group_name,
            poa_no,
            agency_ref_code,
        )

        # Precompute pinyin for search
        applicant_name_pinyin = get_pinyin_full(applicant_name)
        applicant_name_initials = get_pinyin_initials(applicant_name)
        inventor_name_pinyin = get_pinyin_full(inventor_name)
        inventor_name_initials = get_pinyin_initials(inventor_name)
        contact_name_pinyin = get_pinyin_full(contact_name)
        contact_name_initials = get_pinyin_initials(contact_name)
        agency_ref_name_pinyin = get_pinyin_full(agency_ref_name)
        agency_ref_name_initials = get_pinyin_initials(agency_ref_name)
        group_name_pinyin = get_pinyin_full(group_name)
        group_name_initials = get_pinyin_initials(group_name)

        existing = None
        try:
            existing = conn.execute(
                "SELECT * FROM tgd_fact_record WHERE record_hash = ? LIMIT 1", (record_hash,)
            ).fetchone()
        except Exception as e:
            result.skipped += 1
            result.errors.append(f"常用信息 第{i}行：查询失败：{e}")
            continue

        source_type = "excel_import"
        source_ref = f"{base}#row{i}"

        if existing:
            try:
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
                        source_ref = ?,

                        applicant_name_pinyin = ?, applicant_name_initials = ?,
                        inventor_name_pinyin = ?, inventor_name_initials = ?,
                        contact_name_pinyin = ?, contact_name_initials = ?,
                        agency_ref_name_pinyin = ?, agency_ref_name_initials = ?,
                        group_name_pinyin = ?, group_name_initials = ?
                    WHERE record_hash = ?
                    """,
                    (
                        _coalesce_non_empty_str(applicant_name, existing["applicant_name"]),
                        _coalesce_non_empty_str(applicant_type_code, existing["applicant_type_code"]),
                        _coalesce_non_empty_str(applicant_id_type_code, existing["applicant_id_type_code"]),
                        _coalesce_non_empty_str(applicant_id_no, existing["applicant_id_no"]),
                        _coalesce_non_empty_str(applicant_province_code, existing["applicant_province_code"]),
                        _coalesce_non_empty_str(applicant_city_code, existing["applicant_city_code"]),
                        _coalesce_non_empty_str(applicant_address, existing["applicant_address"]),
                        _coalesce_non_empty_str(applicant_zip, existing["applicant_zip"]),
                        _coalesce_non_empty_str(applicant_phone, existing["applicant_phone"]),
                        _coalesce_non_empty_str(applicant_email, existing["applicant_email"]),
                        _coalesce_non_empty_str(inventor_name, existing["inventor_name"]),
                        _coalesce_non_empty_str(inventor_id_type, existing["inventor_id_type"]),
                        _coalesce_non_empty_str(inventor_id_no, existing["inventor_id_no"]),
                        _coalesce_non_empty_str(inventor_nationality, existing["inventor_nationality_code"]),
                        _coalesce_non_empty_str(contact_name, existing["contact_name"]),
                        _coalesce_non_empty_str(contact_phone, existing["contact_phone"]),
                        _coalesce_non_empty_str(contact_email, existing["contact_email"]),
                        _coalesce_non_empty_str(contact_province_code, existing["contact_province_code"]),
                        _coalesce_non_empty_str(contact_city_code, existing["contact_city_code"]),
                        _coalesce_non_empty_str(contact_street, existing["contact_street"]),
                        _coalesce_non_empty_str(contact_zip, existing["contact_zip"]),
                        _coalesce_non_empty_str(group_name, existing["group_name"]),
                        _coalesce_non_empty_str(poa_no, existing["power_of_attorney_no"]),
                        _coalesce_non_empty_str(agency_ref_name, existing["agency_ref_name"]),
                        _coalesce_non_empty_str(agency_ref_code, existing["agency_ref_code"]),
                        now,
                        source_type,
                        source_ref,
                        _coalesce_non_empty_str(applicant_name_pinyin, existing.get("applicant_name_pinyin")),
                        _coalesce_non_empty_str(applicant_name_initials, existing.get("applicant_name_initials")),
                        _coalesce_non_empty_str(inventor_name_pinyin, existing.get("inventor_name_pinyin")),
                        _coalesce_non_empty_str(inventor_name_initials, existing.get("inventor_name_initials")),
                        _coalesce_non_empty_str(contact_name_pinyin, existing.get("contact_name_pinyin")),
                        _coalesce_non_empty_str(contact_name_initials, existing.get("contact_name_initials")),
                        _coalesce_non_empty_str(agency_ref_name_pinyin, existing.get("agency_ref_name_pinyin")),
                        _coalesce_non_empty_str(agency_ref_name_initials, existing.get("agency_ref_name_initials")),
                        _coalesce_non_empty_str(group_name_pinyin, existing.get("group_name_pinyin")),
                        _coalesce_non_empty_str(group_name_initials, existing.get("group_name_initials")),
                        record_hash,
                    ),
                )
                result.updated += 1
            except Exception as e:
                result.skipped += 1
                result.errors.append(f"常用信息 第{i}行：更新失败：{e}")
        else:
            try:
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
                        created_at, updated_at, source_type, source_ref,
                        applicant_name_pinyin, applicant_name_initials,
                        inventor_name_pinyin, inventor_name_initials,
                        contact_name_pinyin, contact_name_initials,
                        agency_ref_name_pinyin, agency_ref_name_initials,
                        group_name_pinyin, group_name_initials
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_hash,
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
                        inventor_nationality,
                        contact_name,
                        contact_phone,
                        contact_email,
                        contact_province_code,
                        contact_city_code,
                        contact_street,
                        contact_zip,
                        poa_no,
                        agency_ref_name,
                        agency_ref_code,
                        group_name,
                        now,
                        now,
                        source_type,
                        source_ref,
                        applicant_name_pinyin, applicant_name_initials,
                        inventor_name_pinyin, inventor_name_initials,
                        contact_name_pinyin, contact_name_initials,
                        agency_ref_name_pinyin, agency_ref_name_initials,
                        group_name_pinyin, group_name_initials,
                    ),
                )
                result.inserted += 1
            except Exception as e:
                result.skipped += 1
                result.errors.append(f"常用信息 第{i}行：新增失败：{e}")

    try:
        excel_dbg(
            f"import_fact_done inserted={int(result.inserted)} updated={int(result.updated)} skipped={int(result.skipped)} errors={len(result.errors or [])}"
        )
    except Exception:
        pass
