from __future__ import annotations

from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready

from .debug import excel_dbg
from .import_agency_ops import _import_agency_agents_sheet
from .import_fact_ops import _import_fact_records_sheet
from .models import ExcelImportSummary
from .openpyxl_utils import _require_openpyxl
from .text_utils import _normalize_text


def import_tgd_excel_data(src_path: str) -> ExcelImportSummary:
    _, load_workbook = _require_openpyxl()
    db_path = get_db_path()
    ensure_db_ready(db_path)

    wb = load_workbook(src_path, data_only=True)
    summary = ExcelImportSummary()
    try:
        excel_dbg(
            f"import_start src={_normalize_text(src_path)} sheets={len(getattr(wb, 'sheetnames', []) or [])}"
        )
    except Exception:
        pass

    with db_session(db_path) as conn:
        _import_fact_records_sheet(conn, wb, summary.fact_records, src_path)
        _import_agency_agents_sheet(conn, wb, summary.agency_agents, src_path)

    try:
        excel_dbg(
            f"import_done fact_ins={int(summary.fact_records.inserted)} fact_upd={int(summary.fact_records.updated)} fact_skp={int(summary.fact_records.skipped)} fact_errs={len(summary.fact_records.errors or [])} agency_ins={int(summary.agency_agents.inserted)} agency_upd={int(summary.agency_agents.updated)} agency_skp={int(summary.agency_agents.skipped)} agency_errs={len(summary.agency_agents.errors or [])}"
        )
    except Exception:
        pass

    return summary
