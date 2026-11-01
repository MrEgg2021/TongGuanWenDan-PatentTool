from PySide6.QtCore import Qt

from .dialog_ui_shell import build_request_form_dialog_shell
from .dialog_ui_sections_bottom import build_request_form_bottom_sections
from .dialog_ui_sections_top import build_request_form_top_sections


def build_request_form_dialog_ui(self) -> None:
    overlay_layout, card, card_layout, form_layout = build_request_form_dialog_shell(self)
    build_request_form_top_sections(self, form_layout)
    build_request_form_bottom_sections(self, form_layout, card, card_layout)
    if bool(getattr(self, "_embedded", False)):
        overlay_layout.addWidget(card, 1)
    else:
        overlay_layout.addWidget(card, 0, Qt.AlignCenter)
