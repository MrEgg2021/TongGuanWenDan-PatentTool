from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from .settings_panel import build_settings_panel
from .task_panel import build_task_panel


def build_official_docs_page(window):
    page = QWidget()
    page.setObjectName("officialDocsPage")
    page.setVisible(False)

    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(8)

    title = QLabel("官文处理")
    title.setProperty("role", "h1")
    root.addWidget(title)

    tabs = QTabWidget()
    tabs.setObjectName("OfficialDocsTabs")
    root.addWidget(tabs, 1)


    task_ctx = build_task_panel(window, tabs)
    settings_ctx = build_settings_panel(window, tabs)

    drop_zone = task_ctx["drop_zone"]
    btn_choose_zip = task_ctx["btn_choose_zip"]
    btn_choose_folder = task_ctx["btn_choose_folder"]
    btn_clear_items = task_ctx["btn_clear_items"]
    btn_toggle_task_details = task_ctx["btn_toggle_task_details"]
    search_edit = task_ctx["search_edit"]
    tree = task_ctx["tree"]
    btn_start = task_ctx["btn_start"]
    list_count = task_ctx["list_count"]
    body_splitter = task_ctx["body_splitter"]
    task_vertical_splitter = task_ctx["task_vertical_splitter"]
    current_label = task_ctx["current_label"]
    meta_label = task_ctx["meta_label"]
    pdf_sources_text = task_ctx["pdf_sources_text"]
    one_line_preview = task_ctx["one_line_preview"]
    error_label = task_ctx["error_label"]
    task_footer = task_ctx["task_footer"]

    summary_button = settings_ctx["summary_button"]
    archive_button = settings_ctx["archive_button"]
    btn_save_settings = settings_ctx["btn_save_settings"]
    type_tree = settings_ctx["type_tree"]
    type_search_edit = settings_ctx["type_search_edit"]
    btn_create_group = settings_ctx["btn_create_group"]
    btn_rename_group = settings_ctx["btn_rename_group"]
    btn_delete_group = settings_ctx["btn_delete_group"]
    btn_add_member = settings_ctx["btn_add_member"]
    btn_join_group = settings_ctx["btn_join_group"]
    btn_move_group = settings_ctx["btn_move_group"]
    btn_remove_group = settings_ctx["btn_remove_group"]
    chk_archive = settings_ctx["chk_archive"]
    chk_summary = settings_ctx["chk_summary"]
    chk_confirm = settings_ctx["chk_confirm"]
    mode_no_list_multi_pdf = settings_ctx["mode_no_list_multi_pdf"]
    chk_exam_pdf_parse = settings_ctx["chk_exam_pdf_parse"]
    summary_edit = settings_ctx["summary_edit"]
    archive_edit = settings_ctx["archive_edit"]
    chk_pdf_applicant = settings_ctx["chk_pdf_applicant"]
    chk_pdf_inventor = settings_ctx["chk_pdf_inventor"]
    chk_pdf_agent = settings_ctx["chk_pdf_agent"]
    chk_pdf_agency_raw = settings_ctx["chk_pdf_agency_raw"]
    chk_pdf_department = settings_ctx["chk_pdf_department"]
    chk_pdf_center = settings_ctx["chk_pdf_center"]
    chk_pdf_examiner = settings_ctx["chk_pdf_examiner"]
    chk_pdf_panel = settings_ctx["chk_pdf_panel"]
    chk_pdf_reject_reason = settings_ctx["chk_pdf_reject_reason"]
    chk_pdf_prior_art = settings_ctx["chk_pdf_prior_art"]
    chk_pdf_dossier_no = settings_ctx["chk_pdf_dossier_no"]
    chk_pdf_authorization_pub_no = settings_ctx["chk_pdf_authorization_pub_no"]
    chk_pdf_authorization_pub_date = settings_ctx["chk_pdf_authorization_pub_date"]
    chk_pdf_certificate_no = settings_ctx["chk_pdf_certificate_no"]
    chk_pdf_qrcode_link = settings_ctx["chk_pdf_qrcode_link"]
    chk_pdf_qrcode_image = settings_ctx["chk_pdf_qrcode_image"]
    mode_combo = settings_ctx["mode_combo"]
    separator_edit = settings_ctx["separator_edit"]
    btn_insert_field = settings_ctx["btn_insert_field"]
    btn_move_field_up = settings_ctx["btn_move_field_up"]
    btn_move_field_down = settings_ctx["btn_move_field_down"]
    btn_remove_field = settings_ctx["btn_remove_field"]
    btn_clear_fields = settings_ctx["btn_clear_fields"]
    filename_fields_list = settings_ctx["filename_fields_list"]
    alias_table = settings_ctx["alias_table"]
    btn_add_alias = settings_ctx["btn_add_alias"]
    btn_remove_alias = settings_ctx["btn_remove_alias"]
    filename_preview_label = settings_ctx["filename_preview_label"]
    config_scope_label = settings_ctx["config_scope_label"]
    config_hint_label = settings_ctx["config_hint_label"]
    settings_error_label = settings_ctx["settings_error_label"]
    filename_card = settings_ctx["filename_card"]
    alias_card = settings_ctx["alias_card"]
    alias_title = settings_ctx["alias_title"]
    naming_splitter = settings_ctx["naming_splitter"]
    settings_splitter = settings_ctx["settings_splitter"]
    pdf_parse_tab = settings_ctx["pdf_parse_tab"]
    pdf_parse_fields_wrap = settings_ctx["pdf_parse_fields_wrap"]

    try:
        drop_zone.filesDropped.connect(window.on_official_docs_paths_dropped)
    except Exception:
        pass
    try:
        drop_zone.clicked.connect(window.on_official_docs_choose_zips)
    except Exception:
        pass
    try:
        btn_choose_zip.clicked.connect(window.on_official_docs_choose_zips)
    except Exception:
        pass
    try:
        btn_choose_folder.clicked.connect(window.on_official_docs_choose_folder)
    except Exception:
        pass
    try:
        btn_clear_items.clicked.connect(window.on_official_docs_clear_items)
    except Exception:
        pass
    try:
        btn_toggle_task_details.clicked.connect(window.on_official_docs_toggle_task_details_visibility)
    except Exception:
        pass
    try:
        search_edit.textChanged.connect(window.on_official_docs_search_changed)
    except Exception:
        pass
    try:
        tree.currentItemChanged.connect(window.on_official_docs_selection_changed)
    except Exception:
        pass
    try:
        tree.itemChanged.connect(window.on_official_docs_item_check_changed)
    except Exception:
        pass
    try:
        tree.itemExpanded.connect(window.on_official_docs_item_expanded)
    except Exception:
        pass
    try:
        tree.itemCollapsed.connect(window.on_official_docs_item_collapsed)
    except Exception:
        pass
    try:
        btn_start.clicked.connect(window.on_official_docs_start_processing)
    except Exception:
        pass

    try:
        summary_button.clicked.connect(window.on_official_docs_browse_summary_root)
    except Exception:
        pass
    try:
        archive_button.clicked.connect(window.on_official_docs_browse_archive_root)
    except Exception:
        pass
    try:
        btn_save_settings.clicked.connect(window.on_official_docs_save_settings)
    except Exception:
        pass
    try:
        type_tree.currentItemChanged.connect(window.on_official_docs_type_selection_changed)
    except Exception:
        pass
    try:
        type_tree.itemChanged.connect(window.on_official_docs_type_tree_item_changed)
    except Exception:
        pass
    try:
        type_search_edit.textChanged.connect(window.on_official_docs_type_search_changed)
    except Exception:
        pass
    try:
        type_tree.customContextMenuRequested.connect(window.on_official_docs_type_tree_context_menu)
    except Exception:
        pass
    try:
        btn_create_group.clicked.connect(window.on_official_docs_create_naming_group)
    except Exception:
        pass
    try:
        btn_rename_group.clicked.connect(window.on_official_docs_rename_naming_group)
    except Exception:
        pass
    try:
        btn_delete_group.clicked.connect(window.on_official_docs_delete_naming_group)
    except Exception:
        pass
    try:
        btn_add_member.clicked.connect(window.on_official_docs_add_group_member)
    except Exception:
        pass
    try:
        btn_join_group.clicked.connect(window.on_official_docs_move_type_to_group)
    except Exception:
        pass
    try:
        btn_move_group.clicked.connect(window.on_official_docs_move_type_to_group)
    except Exception:
        pass
    try:
        btn_remove_group.clicked.connect(window.on_official_docs_remove_type_from_group)
    except Exception:
        pass
    try:
        tabs.currentChanged.connect(window.on_official_docs_tab_changed)
    except Exception:
        pass
    try:
        chk_archive.toggled.connect(window.on_official_docs_archive_checkbox_toggled)
    except Exception:
        pass

    for widget in (
        chk_summary,
        chk_archive,
        chk_confirm,
        chk_exam_pdf_parse,
        summary_edit,
        archive_edit,
        chk_pdf_applicant,
        chk_pdf_inventor,
        chk_pdf_agent,
        chk_pdf_agency_raw,
        chk_pdf_department,
        chk_pdf_center,
        chk_pdf_examiner,
        chk_pdf_panel,
        chk_pdf_reject_reason,
        chk_pdf_prior_art,
        chk_pdf_dossier_no,
        chk_pdf_authorization_pub_no,
        chk_pdf_authorization_pub_date,
        chk_pdf_certificate_no,
        chk_pdf_qrcode_link,
        chk_pdf_qrcode_image,
    ):
        try:
            signal = widget.stateChanged if hasattr(widget, "stateChanged") else widget.textChanged
            signal.connect(window.on_official_docs_settings_changed)
        except Exception:
            pass

    try:
        mode_no_list_multi_pdf.currentIndexChanged.connect(window.on_official_docs_settings_changed)
    except Exception:
        pass
    try:
        mode_combo.currentIndexChanged.connect(window.on_official_docs_settings_changed)
    except Exception:
        pass
    try:
        separator_edit.textChanged.connect(window.on_official_docs_settings_changed)
    except Exception:
        pass
    try:
        btn_insert_field.clicked.connect(window.on_official_docs_insert_field_card)
    except Exception:
        pass
    try:
        btn_move_field_up.clicked.connect(window.on_official_docs_move_field_up)
    except Exception:
        pass
    try:
        btn_move_field_down.clicked.connect(window.on_official_docs_move_field_down)
    except Exception:
        pass
    try:
        btn_remove_field.clicked.connect(window.on_official_docs_remove_selected_field)
    except Exception:
        pass
    try:
        btn_clear_fields.clicked.connect(window.on_official_docs_clear_fields)
    except Exception:
        pass
    try:
        filename_fields_list.model().rowsMoved.connect(window.on_official_docs_settings_changed)
    except Exception:
        pass
    try:
        alias_table.itemChanged.connect(window.on_official_docs_alias_table_changed)
    except Exception:
        pass
    try:
        btn_add_alias.clicked.connect(window.on_official_docs_add_alias_rule)
    except Exception:
        pass
    try:
        btn_remove_alias.clicked.connect(window.on_official_docs_remove_alias_rule)
    except Exception:
        pass
    try:
        naming_splitter.splitterMoved.connect(window.on_official_docs_naming_splitter_moved)
    except Exception:
        pass

    window.official_docs_page = page
    window.official_docs_tabs = tabs

    window.official_docs_drop_zone = drop_zone
    window.official_docs_list_count_label = list_count
    window.official_docs_search_edit = search_edit
    window.official_docs_tree = tree
    window.official_docs_task_splitter = body_splitter
    window.official_docs_task_vertical_splitter = task_vertical_splitter
    window.official_docs_toggle_task_details_button = btn_toggle_task_details

    window.official_docs_current_label = current_label
    window.official_docs_meta_label = meta_label
    window.official_docs_pdf_sources_text = pdf_sources_text
    window.official_docs_output_preview = one_line_preview
    window.official_docs_validation_error = error_label
    window.official_docs_start_button = btn_start
    window.official_docs_task_footer = task_footer

    window.official_docs_chk_summary = chk_summary
    window.official_docs_chk_archive = chk_archive
    window.official_docs_chk_confirm = chk_confirm
    window.official_docs_no_list_multi_pdf_mode_combo = mode_no_list_multi_pdf
    window.official_docs_chk_exam_pdf_parse = chk_exam_pdf_parse
    window.official_docs_pdf_parse_fields_wrap = pdf_parse_fields_wrap
    window.official_docs_pdf_parse_field_checks = {
        "applicant": chk_pdf_applicant,
        "inventor": chk_pdf_inventor,
        "agent": chk_pdf_agent,
        "agency_raw": chk_pdf_agency_raw,
        "department": chk_pdf_department,
        "center": chk_pdf_center,
        "examiner": chk_pdf_examiner,
        "panel": chk_pdf_panel,
        "reject_reason": chk_pdf_reject_reason,
        "prior_art": chk_pdf_prior_art,
        "dossier_no": chk_pdf_dossier_no,
        "authorization_pub_no": chk_pdf_authorization_pub_no,
        "authorization_pub_date": chk_pdf_authorization_pub_date,
        "certificate_no": chk_pdf_certificate_no,
        "qrcode_link": chk_pdf_qrcode_link,
        "qrcode_image": chk_pdf_qrcode_image,
    }
    window.official_docs_summary_root_edit = summary_edit
    window.official_docs_archive_root_edit = archive_edit

    window.official_docs_settings_line_preview = filename_preview_label
    window.official_docs_filename_preview_label = filename_preview_label
    window.official_docs_settings_type_search_edit = type_search_edit
    window.official_docs_settings_type_tree = type_tree
    window.official_docs_settings_type_list = type_tree
    window.official_docs_create_group_button = btn_create_group
    window.official_docs_rename_group_button = btn_rename_group
    window.official_docs_delete_group_button = btn_delete_group
    window.official_docs_add_group_member_button = btn_add_member
    window.official_docs_join_group_button = btn_join_group
    window.official_docs_move_group_button = btn_move_group
    window.official_docs_remove_group_button = btn_remove_group
    window.official_docs_naming_mode_combo = mode_combo
    window.official_docs_filename_separator_edit = separator_edit
    window.official_docs_filename_fields_list = filename_fields_list
    window.official_docs_btn_move_field_up = btn_move_field_up
    window.official_docs_btn_move_field_down = btn_move_field_down
    window.official_docs_alias_table = alias_table
    window.official_docs_add_alias_button = btn_add_alias
    window.official_docs_remove_alias_button = btn_remove_alias
    window.official_docs_naming_scope_label = config_scope_label
    window.official_docs_naming_scope_hint_label = config_hint_label
    window.official_docs_alias_title_label = alias_title
    window.official_docs_alias_card = alias_card
    window.official_docs_settings_error_label = settings_error_label
    window.official_docs_settings_save_button = btn_save_settings
    window.official_docs_filename_fields_card = filename_card
    window.official_docs_naming_splitter = naming_splitter
    window.official_docs_settings_splitter = settings_splitter
    window.official_docs_pdf_parse_tab = pdf_parse_tab

    return page



__all__ = ["build_official_docs_page"]
