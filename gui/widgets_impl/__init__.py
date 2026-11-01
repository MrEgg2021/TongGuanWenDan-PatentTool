from .elide_label import ElideLabel
from .drag_drop import SingleFileDropWidget, BatchFileListWidget, DropCardProxy, install_drop_card_proxy
from .graphic_checkbox import GraphicCheckBox
from .batch_item import BatchFileItemWidget
from .clickable_frame import ClickableFrame


def __getattr__(name: str):
    if name == "RequestFormDialog":
        from .request_form_dialog import RequestFormDialog

        return RequestFormDialog
    if name == "TgdFactRecordDialog":
        from .tgd_fact_record_dialog import TgdFactRecordDialog

        return TgdFactRecordDialog
    if name == "TgdFactRecordManagerDialog":
        from .tgd_fact_record_manager_dialog import TgdFactRecordManagerDialog

        return TgdFactRecordManagerDialog
    if name == "TgdZipImportReviewDialog":
        from .tgd_zip_import_review_dialog import TgdZipImportReviewDialog

        return TgdZipImportReviewDialog
    if name == "ImportAction":
        from .tgd_zip_import_review_dialog import ImportAction

        return ImportAction
    raise AttributeError(name)

__all__ = [
    "ElideLabel",
    "SingleFileDropWidget",
    "BatchFileListWidget",
    "DropCardProxy",
    "install_drop_card_proxy",
    "GraphicCheckBox",
    "BatchFileItemWidget",
    "ClickableFrame",
    "RequestFormDialog",
    "TgdFactRecordDialog",
    "TgdFactRecordManagerDialog",
    "TgdZipImportReviewDialog",
    "ImportAction",
]
