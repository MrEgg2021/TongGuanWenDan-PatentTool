from gui.main_window.mixins.tgd_data_management_ops import (
    on_tgd_excel_export,
    on_tgd_excel_export_masked,
    on_tgd_excel_export_template,
    on_tgd_excel_import,
    on_tgd_request_manual_entry,
    on_tgd_request_zip_import,
    on_tgd_request_zip_folder_import,
    on_tgd_request_zips_dropped,
)


class TgdDataManagementMixin:
    def _on_tgd_excel_export_template(self) -> None:
        on_tgd_excel_export_template(self)

    def _on_tgd_excel_import(self) -> None:
        on_tgd_excel_import(self)

    def _on_tgd_excel_export(self) -> None:
        on_tgd_excel_export(self)

    def _on_tgd_excel_export_masked(self) -> None:
        on_tgd_excel_export_masked(self)

    def on_tgd_request_zip_import(self) -> None:
        on_tgd_request_zip_import(self)

    def on_tgd_request_zip_folder_import(self) -> None:
        on_tgd_request_zip_folder_import(self)

    def on_tgd_request_manual_entry(self) -> None:
        on_tgd_request_manual_entry(self)

    def on_tgd_request_zips_dropped(self, paths) -> None:
        on_tgd_request_zips_dropped(self, paths)
