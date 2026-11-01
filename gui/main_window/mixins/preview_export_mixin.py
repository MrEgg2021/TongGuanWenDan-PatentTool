from gui.main_window.mixins.preview_export_impl import ops as preview_export_ops


class PreviewExportMixin:
    def _reset_preview_export_ui(self) -> None:
        return preview_export_ops.reset_preview_export_ui(self)

    def on_preview_render_completed(self, result, zip_path: str) -> None:
        return preview_export_ops.on_preview_render_completed(self, result, zip_path)

    def on_preview_manifest_completed(self, result, zip_path: str) -> None:
        return preview_export_ops.on_preview_manifest_completed(self, result, zip_path)

    def on_preview_legacy_completed(self, result, zip_path: str) -> None:
        return preview_export_ops.on_preview_legacy_completed(self, result, zip_path)

    def _on_preview_doc_check_toggled(self, document_id: str, checked: bool) -> None:
        return preview_export_ops.on_preview_doc_check_toggled(self, document_id, checked)

    def _on_preview_documents_reordered(self) -> None:
        return preview_export_ops.on_preview_documents_reordered(self)

    def _apply_preview_export_state(self) -> None:
        return preview_export_ops.apply_preview_export_state(self)

    def on_preview_start_selected_case(self) -> None:
        return preview_export_ops.on_preview_start_selected_case(self)

    def on_preview_export_merged_pdf(self) -> None:
        return preview_export_ops.on_preview_export_merged_pdf(self)
