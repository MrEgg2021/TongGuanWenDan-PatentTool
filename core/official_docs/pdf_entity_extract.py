from __future__ import annotations

# Compatibility layer: keep legacy import path stable while delegating to V3.
from .pdf_entity_extract_v3 import (
    PdfEntityExtractResult,
    PdfFieldMatrixHealth,
    clear_pdf_field_matrix_cache,
    extract_pdf_entity_fields,
    get_pdf_field_matrix_health,
    resolve_pdf_applicable_fields,
)

__all__ = [
    "PdfFieldMatrixHealth",
    "PdfEntityExtractResult",
    "clear_pdf_field_matrix_cache",
    "extract_pdf_entity_fields",
    "get_pdf_field_matrix_health",
    "resolve_pdf_applicable_fields",
]
