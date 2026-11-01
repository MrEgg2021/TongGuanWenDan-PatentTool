from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
import os
import sys

from gui.tgd_request_form_tour import (
    build_data_management_request_guide_steps,
    get_data_management_request_guide_summary,
    has_auto_opened_data_management_request_guide,
    mark_data_management_request_guide_auto_opened,
)
from gui.widgets import GraphicCheckBox, SingleFileDropWidget, TgdFactRecordManagerDialog, TgdZipImportReviewDialog


def build_data_management_page(window):
    """构建“数据管理”页面（侧边栏同级入口）。"""

    page = QWidget()
    page.setObjectName("dataManagementPage")
    page.setVisible(False)

    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    stack = QStackedWidget(page)
    root.addWidget(stack, 1)

    home = QWidget(stack)
    home_root = QVBoxLayout(home)
    home_root.setContentsMargins(0, 0, 0, 0)
    home_root.setSpacing(12)

    header_row = QHBoxLayout()
    header_row.setContentsMargins(0, 0, 0, 0)
    header_row.setSpacing(12)

    header_text_col = QVBoxLayout()
    header_text_col.setContentsMargins(0, 0, 0, 0)
    header_text_col.setSpacing(4)
    title = QLabel("数据管理")
    title.setProperty("role", "h1")
    subtitle = QLabel("集中维护请求书会复用的常用信息，支持批量导入历史案卷包、二次编辑，并可从请求书写回更新。")
    subtitle.setProperty("role", "caption")
    subtitle.setProperty("emphasis", True)
    subtitle.setWordWrap(True)
    header_text_col.addWidget(title)
    header_text_col.addWidget(subtitle)

    header_actions = QHBoxLayout()
    header_actions.setContentsMargins(0, 0, 0, 0)
    header_actions.setSpacing(8)

    btn_manual = QPushButton("管理常用信息")
    btn_manual.setObjectName("tgdRequestZipManual")
    btn_manual.setProperty("class", "Secondary")

    btn_guide = QPushButton("如何复用到请求书")
    btn_guide.setObjectName("tgdDataManagementGuide")
    btn_guide.setProperty("class", "Ghost")

    header_actions.addWidget(btn_manual, 0)
    header_actions.addWidget(btn_guide, 0)

    header_row.addLayout(header_text_col, 1)
    header_row.addLayout(header_actions, 0)
    home_root.addLayout(header_row)

    guide_card = QFrame()
    guide_card.setObjectName("Card")
    guide_card.setVisible(False)
    guide_layout = QVBoxLayout(guide_card)
    guide_layout.setContentsMargins(12, 12, 12, 12)
    guide_layout.setSpacing(10)

    guide_header_row = QHBoxLayout()
    guide_header_row.setContentsMargins(0, 0, 0, 0)
    guide_header_row.setSpacing(8)

    guide_title = QLabel("这些信息如何在请求书中复用")
    guide_title.setProperty("role", "h2")

    btn_hide_guide = QPushButton("收起")
    btn_hide_guide.setObjectName("tgdDataManagementGuideHide")
    btn_hide_guide.setProperty("class", "Ghost")

    guide_header_row.addWidget(guide_title, 1)
    guide_header_row.addWidget(btn_hide_guide, 0)
    guide_layout.addLayout(guide_header_row)

    guide_summary = QLabel(get_data_management_request_guide_summary())
    guide_summary.setProperty("role", "caption")
    guide_summary.setWordWrap(True)
    guide_layout.addWidget(guide_summary)

    for index, (step_title, step_body) in enumerate(build_data_management_request_guide_steps(), start=1):
        step_frame = QFrame()
        step_layout = QHBoxLayout(step_frame)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_layout.setSpacing(10)

        step_badge = QLabel(str(index))
        step_badge.setAlignment(Qt.AlignCenter)
        step_badge.setMinimumWidth(26)
        step_badge.setMaximumWidth(26)
        step_badge.setProperty("class", "Secondary")

        step_text_col = QVBoxLayout()
        step_text_col.setContentsMargins(0, 0, 0, 0)
        step_text_col.setSpacing(2)

        step_title_label = QLabel(step_title)
        step_title_label.setProperty("role", "label")
        step_title_label.setProperty("emphasis", True)

        step_body_label = QLabel(step_body)
        step_body_label.setWordWrap(True)
        step_body_label.setProperty("role", "caption")

        step_text_col.addWidget(step_title_label)
        step_text_col.addWidget(step_body_label)

        step_layout.addWidget(step_badge, 0, Qt.AlignTop)
        step_layout.addLayout(step_text_col, 1)
        guide_layout.addWidget(step_frame)

    home_root.addWidget(guide_card)

    zip_card = QFrame()
    zip_card.setObjectName("Card")
    try:
        zip_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    except Exception:
        pass
    zip_layout = QVBoxLayout(zip_card)
    zip_layout.setContentsMargins(12, 12, 12, 12)
    zip_layout.setSpacing(8)

    zip_title = QLabel("ZIP 导入")
    zip_title.setProperty("role", "h2")
    zip_layout.addWidget(zip_title)

    zip_hint = QLabel("支持批量导入历史案卷包，快速提取申请人、发明人、联系人等常用信息，导入后仍可在本页二次编辑。")
    zip_hint.setProperty("role", "caption")
    zip_hint.setWordWrap(True)
    zip_layout.addWidget(zip_hint)

    zip_ctrl_row = QHBoxLayout()
    zip_ctrl_row.setContentsMargins(0, 0, 0, 0)
    zip_ctrl_row.setSpacing(10)

    chk_confirm_each = GraphicCheckBox("逐个弹窗确认")
    chk_confirm_each.setObjectName("tgdRequestZipConfirmEach")
    try:
        chk_confirm_each.setProperty("emphasis", True)
        chk_confirm_each.setChecked(False)
    except Exception:
        pass

    chk_parse_poa = GraphicCheckBox("解析总委托书编号(POA)")
    chk_parse_poa.setObjectName("tgdRequestZipParsePoa")
    try:
        chk_parse_poa.setProperty("emphasis", True)
        chk_parse_poa.setChecked(True)
    except Exception:
        pass

    btn_pick_folder = QPushButton("选择文件夹")
    btn_pick_folder.setObjectName("tgdRequestZipPickFolder")
    btn_pick_folder.setProperty("class", "Secondary")

    zip_ctrl_row.addWidget(chk_confirm_each, 0)
    zip_ctrl_row.addWidget(chk_parse_poa, 0)
    zip_ctrl_row.addStretch(1)
    zip_ctrl_row.addWidget(btn_pick_folder, 0)
    zip_layout.addLayout(zip_ctrl_row)

    dz = SingleFileDropWidget()
    dz.setObjectName("TgdRequestZipDropZone")
    try:
        dz.setMinimumHeight(88)
        dz.setMaximumHeight(110)
    except Exception:
        pass
    dz_layout = QVBoxLayout(dz)
    dz_layout.setContentsMargins(16, 8, 16, 8)
    dz_layout.setSpacing(8)

    dz_hint = QLabel("点击选择 ZIP 或 将 ZIP 拖拽至此")
    dz_hint.setAlignment(Qt.AlignCenter)
    dz_hint.setProperty("role", "label")
    dz_hint.setProperty("emphasis", True)

    dz_layout.addStretch(1)
    dz_layout.addWidget(dz_hint)
    dz_layout.addStretch(1)
    zip_layout.addWidget(dz)

    home_root.addWidget(zip_card)

    excel_card = QFrame()
    excel_card.setObjectName("Card")
    try:
        excel_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    except Exception:
        pass
    excel_layout = QVBoxLayout(excel_card)
    excel_layout.setContentsMargins(12, 12, 12, 12)
    excel_layout.setSpacing(8)

    excel_title = QLabel("Excel 工具")
    excel_title.setProperty("role", "h2")
    excel_layout.addWidget(excel_title)

    excel_hint = QLabel("支持模板导出、Excel 导入、全量导出和脱敏导出。")
    excel_hint.setProperty("role", "caption")
    excel_hint.setWordWrap(True)
    excel_layout.addWidget(excel_hint)

    excel_row = QHBoxLayout()
    excel_row.setContentsMargins(0, 0, 0, 0)
    excel_row.setSpacing(10)

    btn_export_tpl = QPushButton("导出模板")
    btn_export_tpl.setObjectName("tgdExcelExportTemplate")
    btn_export_tpl.setProperty("class", "Secondary")

    btn_import = QPushButton("导入 Excel")
    btn_import.setObjectName("tgdExcelImport")
    btn_import.setProperty("class", "Secondary")

    btn_export = QPushButton("导出 Excel")
    btn_export.setObjectName("tgdExcelExport")
    btn_export.setProperty("class", "Secondary")

    btn_export_masked = QPushButton("脱敏导出")
    btn_export_masked.setObjectName("tgdExcelExportMasked")
    btn_export_masked.setProperty("class", "Ghost")

    excel_row.addWidget(btn_export_tpl, 0)
    excel_row.addWidget(btn_import, 0)
    excel_row.addWidget(btn_export, 0)
    excel_row.addWidget(btn_export_masked, 0)
    excel_row.addStretch(1)
    excel_layout.addLayout(excel_row)
    home_root.addWidget(excel_card)

    home_root.addStretch(1)

    def _set_guide_visible(visible: bool) -> None:
        try:
            guide_card.setVisible(bool(visible))
        except Exception:
            pass
        try:
            btn_guide.setText("收起说明" if bool(visible) else "如何复用到请求书")
        except Exception:
            pass

    def _toggle_guide() -> None:
        visible = False
        try:
            visible = bool(guide_card.isVisible())
        except Exception:
            visible = False
        _set_guide_visible(not visible)

    def _maybe_auto_expand_guide() -> bool:
        if has_auto_opened_data_management_request_guide():
            return False
        _set_guide_visible(True)
        mark_data_management_request_guide_auto_opened(True)
        return True

    try:
        btn_guide.clicked.connect(_toggle_guide)
    except Exception:
        pass
    try:
        btn_hide_guide.clicked.connect(lambda: _set_guide_visible(False))
    except Exception:
        pass

    manager_page = QWidget(stack)
    manager_root = QVBoxLayout(manager_page)
    manager_root.setContentsMargins(0, 0, 0, 0)
    manager_root.setSpacing(12)

    manager_top = QFrame()
    manager_top.setObjectName("Card")
    try:
        manager_top.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    except Exception:
        pass
    manager_top_layout = QHBoxLayout(manager_top)
    manager_top_layout.setContentsMargins(12, 12, 12, 12)
    manager_top_layout.setSpacing(10)

    btn_back = QPushButton("返回")
    btn_back.setObjectName("tgdFactManagerBack")
    btn_back.setProperty("class", "Ghost")

    manager_title = QLabel("常用信息管理")
    manager_title.setProperty("role", "h2")

    manager_top_layout.addWidget(btn_back, 0)
    manager_top_layout.addWidget(manager_title, 1)
    manager_top_layout.addStretch(1)
    manager_root.addWidget(manager_top)

    manager = TgdFactRecordManagerDialog(manager_page, embedded=True)
    try:
        manager.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    except Exception:
        pass
    manager_root.addWidget(manager, 1)

    import_review_page = QWidget(stack)
    import_review_root = QVBoxLayout(import_review_page)
    import_review_root.setContentsMargins(0, 0, 0, 0)
    import_review_root.setSpacing(0)

    stack.addWidget(home)
    stack.addWidget(manager_page)
    stack.addWidget(import_review_page)
    try:
        stack.setCurrentWidget(home)
    except Exception:
        pass

    def _show_home():
        try:
            stack.setCurrentWidget(home)
        except Exception:
            pass

    def _show_manager():
        try:
            stack.setCurrentWidget(manager_page)
        except Exception:
            pass

        def _apply_layout_try(attempt: int = 0) -> None:
            try:
                structural_mismatch, restore_failed = manager._load_layout_state()
            except Exception:
                structural_mismatch, restore_failed = False, True

            try:
                v = str(os.environ.get("TGD_DEBUG_LAYOUT") or "").strip().lower()
                if v and v not in {"0", "false", "no", "off"}:
                    print(
                        f"[TGD_LAYOUT] callsite attempt={int(attempt)} structural_mismatch={bool(structural_mismatch)} restore_failed={bool(restore_failed)}",
                        file=sys.stderr,
                        flush=True,
                    )
            except Exception:
                pass

            if bool(restore_failed) and int(attempt) < 2:
                try:
                    QTimer.singleShot(80, lambda: _apply_layout_try(attempt + 1))
                    return
                except Exception:
                    pass

        try:
            QTimer.singleShot(0, lambda: _apply_layout_try(0))
        except Exception:
            pass
        try:
            QTimer.singleShot(10, manager._refresh_current_tab)
        except Exception:
            pass
        try:
            QTimer.singleShot(160, lambda: _apply_layout_try(0))
        except Exception:
            pass

    try:
        dz.filesDropped.connect(window.on_tgd_request_zips_dropped)
    except Exception:
        pass
    try:
        dz.clicked.connect(window.on_tgd_request_zip_import)
    except Exception:
        pass
    try:
        btn_pick_folder.clicked.connect(window.on_tgd_request_zip_folder_import)
    except Exception:
        pass
    try:
        btn_manual.clicked.connect(window.on_tgd_request_manual_entry)
    except Exception:
        pass

    try:
        btn_back.clicked.connect(_show_home)
    except Exception:
        pass
    try:
        manager.backRequested.connect(_show_home)
    except Exception:
        pass

    def _exec_zip_import_review(*, initial_request_info: dict | None = None, source_path: str = ""):
        dlg = None
        try:
            prev = getattr(window, "_tgd_dm_import_review_dialog", None)
            if prev is not None:
                try:
                    import_review_root.removeWidget(prev)
                except Exception:
                    pass
                try:
                    prev.setParent(None)
                except Exception:
                    pass
                try:
                    prev.deleteLater()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            dlg = TgdZipImportReviewDialog(
                import_review_page,
                embedded=True,
                initial_request_info=initial_request_info,
                source_path=str(source_path or ""),
            )
            window._tgd_dm_import_review_dialog = dlg
            import_review_root.addWidget(dlg, 1)
            try:
                dlg_btn_back = getattr(dlg, "btn_back", None)
                if dlg_btn_back is not None:
                    dlg_btn_back.clicked.connect(dlg.reject)
            except Exception:
                pass

            try:
                stack.setCurrentWidget(import_review_page)
            except Exception:
                pass

            dlg.exec()
            action = int(dlg.get_action())
            ins, upd, skp, errs = dlg.get_import_result()
            return action, (int(ins), int(upd), int(skp), list(errs or []))
        finally:
            try:
                if dlg is not None:
                    try:
                        import_review_root.removeWidget(dlg)
                    except Exception:
                        pass
                    try:
                        dlg.setParent(None)
                    except Exception:
                        pass
                    try:
                        dlg.deleteLater()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                window._tgd_dm_import_review_dialog = None
            except Exception:
                pass
            try:
                stack.setCurrentWidget(home)
            except Exception:
                pass

    window.tgd_data_management_stack = stack
    window._tgd_dm_show_fact_manager = _show_manager
    window._tgd_dm_show_home = _show_home
    window._tgd_dm_exec_zip_import_review = _exec_zip_import_review
    window._tgd_dm_set_guide_visible = _set_guide_visible
    window._tgd_dm_maybe_auto_expand_guide = _maybe_auto_expand_guide

    try:
        btn_export_tpl.clicked.connect(window._on_tgd_excel_export_template)
    except Exception:
        pass
    try:
        btn_import.clicked.connect(window._on_tgd_excel_import)
    except Exception:
        pass
    try:
        btn_export.clicked.connect(window._on_tgd_excel_export)
    except Exception:
        pass
    try:
        btn_export_masked.clicked.connect(window._on_tgd_excel_export_masked)
    except Exception:
        pass

    window.tgd_db_page = page
    window.tgd_fact_record_manager_dialog = manager
    window.tgd_request_zip_drop_zone = dz
    window.tgd_request_zip_confirm_each_checkbox = chk_confirm_each
    window.tgd_request_zip_parse_poa_checkbox = chk_parse_poa
    window.tgd_request_zip_pick_folder_button = btn_pick_folder
    window.tgd_request_zip_manual_entry_button = btn_manual
    window.tgd_data_management_guide_button = btn_guide
    window.tgd_data_management_guide_card = guide_card
    window.tgd_excel_export_template_button = btn_export_tpl
    window.tgd_excel_import_button = btn_import
    window.tgd_excel_export_button = btn_export
    window.tgd_excel_export_masked_button = btn_export_masked

    try:
        page.setFocusPolicy(Qt.StrongFocus)
    except Exception:
        pass

    return page
