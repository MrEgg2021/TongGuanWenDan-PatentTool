from __future__ import annotations

import os
from datetime import datetime
from typing import Dict

from .debug import excel_dbg
from .models import SheetImportResult
from .sheet_utils import _build_header_map, _make_row_getter, _pick_agency_sheet, _read_header_row
from .text_utils import _normalize_text
from core.tgd_data_management_impl.pinyin_utils import get_pinyin_full, get_pinyin_initials


def _import_agency_agents_sheet(conn, wb, result: SheetImportResult, src_path: str) -> None:
    ws = _pick_agency_sheet(wb)

    if ws is None:
        result.errors.append("未找到 Sheet：代理机构信息")
        return
    try:
        excel_dbg(f"import_agency sheet={_normalize_text(getattr(ws, 'title', ''))}")
    except Exception:
        pass

    header_row = _read_header_row(ws)
    if not header_row:
        result.errors.append("代理机构信息：表头为空")
        return

    header_map = _build_header_map(header_row)
    _get = _make_row_getter(header_map)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base = os.path.basename(str(src_path or ""))
    per_agency_counter: Dict[str, int] = {}

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        agency_name = _normalize_text(_get(row, "代理机构名称"))
        agency_code = _normalize_text(_get(row, "代理机构代码"))
        agent_name = _normalize_text(_get(row, "代理师姓名"))
        agent_cert_no = _normalize_text(_get(row, "代理师资格证号"))
        agent_phone = _normalize_text(_get(row, "代理师电话"))

        if not any([agency_name, agency_code, agent_name, agent_cert_no, agent_phone]):
            continue

        missing = []
        if not agency_name:
            missing.append("代理机构名称")
        if not agency_code:
            missing.append("代理机构代码")
        if not agent_name:
            missing.append("代理师姓名")
        if not agent_cert_no:
            missing.append("代理师资格证号")
        if not agent_phone:
            missing.append("代理师电话")
        if missing:
            result.skipped += 1
            result.errors.append(f"代理机构信息 第{i}行：关键字段不能为空：" + "、".join(missing))
            continue

        cnt = int(per_agency_counter.get(agency_code, 0)) + 1
        per_agency_counter[agency_code] = cnt
        sort_order = cnt

        # Precompute pinyin
        agency_name_pinyin = get_pinyin_full(agency_name)
        agency_name_initials = get_pinyin_initials(agency_name)
        agent_name_pinyin = get_pinyin_full(agent_name)
        agent_name_initials = get_pinyin_initials(agent_name)

        try:
            existing = conn.execute(
                """
                SELECT * FROM tgd_agency_agent
                WHERE agency_code = ? AND agent_cert_no = ?
                LIMIT 1
                """,
                (agency_code, agent_cert_no),
            ).fetchone()
        except Exception as e:
            result.skipped += 1
            result.errors.append(f"代理机构信息 第{i}行：查询失败：{e}")
            continue

        source_type = "excel_import"
        source_ref = f"{base}#agency_row{i}"

        if existing:
            try:
                conn.execute(
                    """
                    UPDATE tgd_agency_agent
                    SET
                        agency_name = ?,
                        agent_name = ?,
                        agent_phone = ?,
                        sort_order = ?,
                        updated_at = ?,
                        source_type = ?,
                        source_ref = ?,
                        agency_name_pinyin = ?, agency_name_initials = ?,
                        agent_name_pinyin = ?, agent_name_initials = ?
                    WHERE id = ?
                    """,
                    (
                        agency_name,
                        agent_name,
                        agent_phone,
                        int(sort_order),
                        now,
                        source_type,
                        source_ref,
                        agency_name_pinyin, agency_name_initials,
                        agent_name_pinyin, agent_name_initials,
                        int(existing["id"]),
                    ),
                )
                result.updated += 1
            except Exception as e:
                result.skipped += 1
                result.errors.append(f"代理机构信息 第{i}行：更新失败：{e}")
        else:
            try:
                conn.execute(
                    """
                    INSERT INTO tgd_agency_agent(
                        agency_name, agency_code, agent_name, agent_cert_no, agent_phone,
                        sort_order,
                        created_at, updated_at, source_type, source_ref,
                        agency_name_pinyin, agency_name_initials,
                        agent_name_pinyin, agent_name_initials
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        agency_name,
                        agency_code,
                        agent_name,
                        agent_cert_no,
                        agent_phone,
                        int(sort_order),
                        now,
                        now,
                        source_type,
                        source_ref,
                        agency_name_pinyin, agency_name_initials,
                        agent_name_pinyin, agent_name_initials,
                    ),
                )
                result.inserted += 1
            except Exception as e:
                result.skipped += 1
                result.errors.append(f"代理机构信息 第{i}行：新增失败：{e}")

    try:
        excel_dbg(
            f"import_agency_done inserted={int(result.inserted)} updated={int(result.updated)} skipped={int(result.skipped)} errors={len(result.errors or [])}"
        )
    except Exception:
        pass
