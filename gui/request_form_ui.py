from __future__ import annotations

from gui.request_form_ui_parts.builder import build_request_form_payload
from gui.request_form_ui_parts.code_maps import ensure_request_form_code_maps_ready
from gui.request_form_ui_parts.extractors import ensure_request_form_extractors_ready


def build_request_form_initial_info(parsed_info, current_patent_type):
    ensure_request_form_extractors_ready()
    ensure_request_form_code_maps_ready()
    return build_request_form_payload(parsed_info, current_patent_type)
