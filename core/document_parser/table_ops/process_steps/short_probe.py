from __future__ import annotations

from .types import TableCaptureResult, TableProcessContext


def try_short_table_direct_path(ctx: TableProcessContext):
    owner = getattr(ctx, 'owner', None)
    if owner is None:
        return None

    get_width = getattr(owner, '_get_table_width_point', None)
    capture = getattr(owner, '_capture_table_pdf_first_result', None)
    emit_fragments = getattr(owner, '_emit_fragments', None)
    set_failure = getattr(owner, '_set_table_process_failure_context', None)
    if not callable(capture) or not callable(emit_fragments):
        return None

    width_point = None
    if callable(get_width):
        try:
            width_point = get_width(ctx.table)
        except Exception:
            width_point = None

    try:
        result = capture(
            ctx.table.Range,
            current_section_key=ctx.current_section_key,
            width_point=width_point,
        )
    except Exception as exc:
        if callable(set_failure):
            set_failure(
                error_code='render_export_failed',
                stage='pdf_first.capture',
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        return None

    if not isinstance(result, TableCaptureResult):
        return None

    if not result.fragments:
        if callable(set_failure) and result.failure_code:
            set_failure(
                error_code=str(result.failure_code),
                stage='pdf_first.capture',
                error_message='pdf-first table capture did not yield legal fragments',
                hard_table=bool(result.hard_table),
                used_blank_doc_fallback=bool(result.used_blank_doc_fallback),
            )
        return None

    fragment_payload = [
        (str(fragment.file), float(fragment.width_mm), float(fragment.height_mm))
        for fragment in list(result.fragments)
    ]
    emit_result = emit_fragments(fragment_payload, ctx.parent_node, ctx.current_section_key, ctx.table)
    if emit_result is False and callable(set_failure):
        set_failure(
            error_code='final_emit_rejected',
            stage='pdf_first.emit',
            error_message='pdf-first table fragments were rejected during final emission',
            hard_table=bool(result.hard_table),
            used_blank_doc_fallback=bool(result.used_blank_doc_fallback),
        )
    return emit_result
