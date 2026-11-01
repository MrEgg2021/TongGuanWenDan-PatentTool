from datetime import datetime

from gui.progress_ui import update_progress_ui, progress_callback


def update_progress_safe(window, percent: int, primary_text: str | None = None, detail_text: str | None = None, batch_info: str | None = None):
    update_progress_ui(window, percent, primary_text, detail_text, batch_info)


def progress_callback_safe(window, stage: str, payload: dict):
    progress_callback(window, stage, payload)


def generate_case_number():
    return datetime.now().strftime("%Y%m%d001")
