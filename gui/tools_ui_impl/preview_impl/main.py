from core.app_preferences import get_pdf_preview_mode
from core.cnipa_preview.runtime import get_default_runtime_manager

from .legacy_run import preview_single_case_legacy
from .run import inspect_preview_case, preview_single_case as preview_single_case_full
from .runtime_setup import configure_installed_client


def preview_single_case(window, zip_path: str, *, documents=None, selected_document_ids=None, mode: str | None = None) -> None:
    selected_mode = str(mode or get_pdf_preview_mode())
    if selected_mode == "legacy":
        preview_single_case_legacy(window, zip_path)
        return
    manager = get_default_runtime_manager()
    if (not manager.configured_path() or manager.configuration_error()) and getattr(window, "_preview_warmup_thread", None) is None:
        if not configure_installed_client(window, automatic=True):
            return
    preview_single_case_full(
        window,
        zip_path,
        documents=documents,
        selected_document_ids=selected_document_ids,
    )

__all__ = ["inspect_preview_case", "preview_single_case"]
