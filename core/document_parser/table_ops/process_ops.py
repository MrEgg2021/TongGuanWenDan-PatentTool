from __future__ import annotations

from core.logging_utils import logger

from .process_steps.context import build_table_process_context
from .process_steps.finalize import finalize_table_process_result
from .process_steps.short_probe import try_short_table_direct_path
from .process_steps.split_flow import process_table_split_flow


def process_table(self, table, parent_node, current_section_key):  # type: ignore[override]
    try:
        clear_failure = getattr(self, "_clear_table_process_failure_context", None)
        if callable(clear_failure):
            clear_failure()
        clear_emit_summary = getattr(self, "_clear_table_emit_summary_context", None)
        if callable(clear_emit_summary):
            clear_emit_summary()

        risky_objects = []
        try:
            collector = getattr(self, "_collect_table_external_object_fallbacks", None)
            if callable(collector):
                risky_objects = collector(getattr(table, "Range", None), section_key=str(current_section_key))
        except Exception:
            risky_objects = []
        if risky_objects:
            logger.warning(
                "[TABLE_EXTERNAL_OBJECT_GUARD] section=%s risky_object_count=%s",
                str(current_section_key),
                len(risky_objects),
            )
            set_failure = getattr(self, "_set_table_process_failure_context", None)
            if callable(set_failure):
                set_failure(
                    error_code="table_external_object_guarded",
                    stage="process_table.external_object_guard",
                    error_message=f"table contains {len(risky_objects)} external object(s) that require safe fallback",
                    object_count=len(risky_objects),
                )
            record_fallback = getattr(self, "_record_object_fallback_failure", None)
            if callable(record_fallback):
                for item in risky_objects:
                    try:
                        record_fallback(
                            shape_obj=item.get("shape_obj"),
                            classification=item.get("classification"),
                            parent_node=parent_node,
                            section_key=str(current_section_key),
                            range_start=item.get("range_start"),
                            resolution_code="table_placeholder_inserted",
                            message="表格内存在外部对象激活风险，已跳过整表截图并保留表格占位提示。",
                        )
                    except Exception:
                        continue
            return False

        ctx = build_table_process_context(self, table, parent_node, current_section_key)
        short_result = try_short_table_direct_path(ctx)
        if short_result is not None:
            return finalize_table_process_result(short_result)
        result = process_table_split_flow(ctx.owner, ctx.table, ctx.parent_node, ctx.current_section_key)
        if not result:
            peek_failure = getattr(self, "_peek_table_process_failure_context", None)
            failure_ctx = peek_failure() if callable(peek_failure) else None
            if not failure_ctx:
                set_failure = getattr(self, "_set_table_process_failure_context", None)
                if callable(set_failure):
                    set_failure(
                        error_code="render_export_failed",
                        stage="process_table.unknown",
                        error_message="table processing returned false without a specific failure context",
                    )
        return finalize_table_process_result(result)
    except Exception as exc:
        rows = None
        cols = None
        rng_start = None
        rng_end = None
        try:
            rows = int(table.Rows.Count)
        except Exception:
            rows = None
        try:
            cols = int(table.Columns.Count)
        except Exception:
            cols = None
        try:
            rng_start = int(table.Range.Start)
        except Exception:
            rng_start = None
        try:
            rng_end = int(table.Range.End)
        except Exception:
            rng_end = None
        logger.warning(
            "[TABLE_PROCESS_GUARD] section=%s rows=%s cols=%s range_start=%s range_end=%s error_type=%s error=%s",
            str(current_section_key),
            rows,
            cols,
            rng_start,
            rng_end,
            type(exc).__name__,
            str(exc),
            exc_info=True,
        )
        set_failure = getattr(self, "_set_table_process_failure_context", None)
        if callable(set_failure):
            set_failure(
                error_code="render_export_failed",
                stage="process_table.guard",
                error_type=type(exc).__name__,
                error_message=str(exc),
                rows=rows,
                cols=cols,
                range_start=rng_start,
                range_end=rng_end,
            )
        return False
