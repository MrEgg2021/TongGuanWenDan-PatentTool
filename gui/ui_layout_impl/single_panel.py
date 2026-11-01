import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QWidget,
)

from core.paths_utils import get_resource_path
from gui.widgets import GraphicCheckBox, SingleFileDropWidget, ElideLabel, install_drop_card_proxy


def build_single_panel(window):
    # 单文档输入路径行
    window.single_path_widget = QWidget()
    single_path_layout = QVBoxLayout(window.single_path_widget)
    single_path_layout.setContentsMargins(0, 0, 0, 0)
    single_path_layout.setSpacing(8)

    single_main_splitter = QSplitter(Qt.Vertical)
    single_main_splitter.setObjectName("SingleMainSplitter")
    single_main_splitter.setChildrenCollapsible(False)
    single_path_layout.addWidget(single_main_splitter, 1)

    window.path_edit = QLineEdit(window.single_path_widget)
    window.path_edit.setVisible(False)
    window.path_edit.setPlaceholderText("请选择要转换的 DOC/DOCX 文件...（支持文件拖拽至此）")
    try:
        window.path_edit.textChanged.connect(window._refresh_single_file_card)
    except Exception:
        pass

    top_card = QFrame()
    top_card.setObjectName("Card")
    top_card_layout = QVBoxLayout(top_card)
    top_card_layout.setContentsMargins(12, 8, 12, 8)
    top_card_layout.setSpacing(6)

    window.single_drop_zone = SingleFileDropWidget()
    window.single_drop_zone.setObjectName("SingleDropZone")
    # Removed hardcoded height limits to allow QSS/Layout control
    # try:
    #     window.single_drop_zone.setMinimumHeight(92)
    #     window.single_drop_zone.setMaximumHeight(108)
    #     window.single_drop_zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    # except Exception:
    #     pass
    dz_layout = QVBoxLayout(window.single_drop_zone)
    dz_layout.setContentsMargins(18, 8, 18, 8)
    dz_layout.setSpacing(8)

    dz_hint = QLabel("点击选择文件 或 将 Word 文件拖拽至此")
    dz_hint.setAlignment(Qt.AlignCenter)
    dz_hint.setProperty("role", "label")
    dz_hint.setProperty("emphasis", True)
    dz_layout.addWidget(dz_hint)
    window.single_drop_zone.filesDropped.connect(window.on_single_files_dropped)
    try:
        window.single_drop_zone.clicked.connect(window.on_browse_single)
    except Exception:
        pass
    top_card_layout.addWidget(window.single_drop_zone)
    single_main_splitter.addWidget(top_card)

    path_section = QWidget()
    path_section_layout = QVBoxLayout(path_section)
    path_section_layout.setContentsMargins(0, 0, 0, 0)
    path_section_layout.setSpacing(8)
    window._single_path_layout = path_section_layout

    window.single_file_card = QFrame()
    window.single_file_card.setObjectName("Card")
    file_card_layout = QHBoxLayout(window.single_file_card)
    file_card_layout.setContentsMargins(16, 12, 16, 12)
    file_card_layout.setSpacing(12)

    icon = QFrame()
    icon.setObjectName("WordIcon")
    try:
        icon.setAttribute(Qt.WA_StyledBackground, True)
    except Exception:
        pass
    icon.setFixedSize(40, 40)
    icon_layout = QVBoxLayout(icon)
    icon_layout.setContentsMargins(0, 0, 0, 0)
    icon_layout.setSpacing(0)
    icon_label = QLabel()
    icon_label.setAlignment(Qt.AlignCenter)
    icon_pix = None
    try:
        candidates = [get_resource_path(os.path.join("assets", "Word.png"))]
        for p in candidates:
            if p and os.path.exists(p):
                pix0 = QPixmap(p)
                if not pix0.isNull():
                    icon_pix = pix0
                    break
    except Exception:
        icon_pix = None

    if icon_pix is not None:
        try:
            icon_label.setPixmap(icon_pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            icon_label.setPixmap(icon_pix)
    else:
        icon_label.setText("W")
        icon_label.setProperty("role", "label")
        icon_label.setObjectName("WordIconPlaceholder")
    icon_layout.addWidget(icon_label)


    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(2)
    window.single_file_name_label = ElideLabel("")
    window.single_file_name_label.setProperty("role", "label")
    window.single_file_path_label = ElideLabel("", elide_mode=Qt.ElideMiddle)
    window.single_file_path_label.setProperty("role", "caption")
    text_col.addWidget(window.single_file_name_label)
    text_col.addWidget(window.single_file_path_label)

    window.single_file_status = QLabel("准备就绪")
    window.single_file_status.setObjectName("SingleFileChip")

    window.btn_clear_single = QPushButton("×")
    window.btn_clear_single.setObjectName("SingleClearButton")
    window.btn_clear_single.setFixedSize(28, 28)
    window.btn_clear_single.clicked.connect(window.on_clear_single)

    file_card_layout.addWidget(icon, 0, Qt.AlignVCenter)
    file_card_layout.addLayout(text_col, 1)
    file_card_layout.addWidget(window.single_file_status, 0, Qt.AlignVCenter)
    file_card_layout.addWidget(window.btn_clear_single, 0, Qt.AlignVCenter)

    window.single_file_card.setVisible(False)
    path_section_layout.addWidget(window.single_file_card)

    window.output_dir_frame = QFrame()
    window.output_dir_frame.setObjectName("outputDirFrame")
    output_dir_layout = QHBoxLayout(window.output_dir_frame)
    output_dir_layout.setContentsMargins(0, 0, 0, 0)
    output_dir_layout.setSpacing(8)
    window.output_dir_layout = output_dir_layout
    window.output_dir_edit = QLineEdit()
    window.output_dir_edit.setPlaceholderText("未选择时每次处理后需要手动选择保存位置")
    window.btn_browse_output_dir = QPushButton("选择输出目录")
    window.btn_browse_output_dir.setObjectName("Secondary")
    window.btn_browse_output_dir.clicked.connect(window.on_browse_output_dir)
    output_dir_layout.addWidget(window.output_dir_edit, 1)
    output_dir_layout.addWidget(window.btn_browse_output_dir)

    path_section_layout.addWidget(window.output_dir_frame)

    single_main_splitter.addWidget(path_section)
    try:
        single_main_splitter.setSizes([7, 3])
    except Exception:
        pass

    try:
        proxy = install_drop_card_proxy(top_card, window.single_drop_zone)
        proxies = getattr(window, "_drop_card_proxies", None)
        if not isinstance(proxies, list):
            proxies = []
            window._drop_card_proxies = proxies
        proxies.append(proxy)
    except Exception:
        pass

    window.single_main_splitter = single_main_splitter
    window.single_drop_card = top_card

    # 单文件专利类型选择
    window.single_type_widget = QWidget()
    single_type_layout = QVBoxLayout(window.single_type_widget)
    single_type_layout.setContentsMargins(0, 0, 0, 0)
    single_type_layout.setSpacing(6)
    type_label = QLabel("生成XML文件：")
    type_label.setProperty("role", "label")
    type_label.setProperty("emphasis", True)
    window.chk_claims = GraphicCheckBox("权利要求书")
    window.chk_description = GraphicCheckBox("说明书")
    window.chk_drawings = GraphicCheckBox("说明书附图")
    window.chk_abstract = GraphicCheckBox("说明书摘要")
    window.chk_request_form = GraphicCheckBox("请求书")
    try:
        for cb in (
            window.chk_claims,
            window.chk_description,
            window.chk_drawings,
            window.chk_abstract,
            window.chk_request_form,
        ):
            cb.setProperty("emphasis", True)
    except Exception:
        pass
    for cb in (
        window.chk_claims,
        window.chk_description,
        window.chk_drawings,
        window.chk_abstract,
    ):
        cb.setChecked(True)
    window.chk_request_form.setChecked(False)
    window.chk_request_form.toggled.connect(window.on_request_form_toggled)

    window.single_type_group = QButtonGroup(window)
    window.radio_invention = GraphicCheckBox("发明")
    window.radio_invention.setObjectName("singleInventionType")
    window.radio_utility_model = GraphicCheckBox("实用新型")
    window.radio_utility_model.setObjectName("singleUtilityType")
    window.single_type_group.addButton(window.radio_invention)
    window.single_type_group.addButton(window.radio_utility_model)
    window.single_type_group.setExclusive(True)
    window.radio_invention.setChecked(True)
    window.radio_invention.hide()
    window.radio_utility_model.hide()

    type_row = QFrame()
    type_row_layout = QHBoxLayout(type_row)
    type_row_layout.setContentsMargins(0, 0, 0, 0)
    type_row_layout.setSpacing(8)
    type_row_layout.addWidget(type_label)
    type_row_layout.addWidget(window.chk_claims)
    type_row_layout.addWidget(window.chk_description)
    type_row_layout.addWidget(window.chk_drawings)
    type_row_layout.addWidget(window.chk_abstract)
    type_row_layout.addWidget(window.chk_request_form)
    type_row_layout.addStretch(1)
    single_type_layout.addWidget(type_row)

    window.batch_chk_confirm_req = GraphicCheckBox("使用弹窗确认请求书信息")
    window.batch_chk_confirm_req.setObjectName("batchConfirmReqCheck")
    window.batch_chk_confirm_req.setChecked(False)
    try:
        window.batch_chk_confirm_req.setProperty("emphasis", True)
    except Exception:
        pass
    window.batch_options_frame = QFrame()
    window.batch_options_frame.setObjectName("batchOptionsFrame")
    batch_opt_layout = QHBoxLayout(window.batch_options_frame)
    batch_opt_layout.setContentsMargins(0, 0, 0, 0)
    batch_opt_layout.setSpacing(8)

    batch_confirm_frame = QFrame()
    batch_confirm_frame.setObjectName("batchConfirmFrame")
    batch_confirm_layout = QHBoxLayout(batch_confirm_frame)
    batch_confirm_layout.setContentsMargins(10, 2, 10, 2)
    batch_confirm_layout.setSpacing(6)
    batch_confirm_layout.addWidget(window.batch_chk_confirm_req)
    window.batch_confirm_frame = batch_confirm_frame
    batch_opt_layout.addWidget(window.batch_confirm_frame)
    window.batch_options_frame.setVisible(False)

    window.chk_auto_open_preview = GraphicCheckBox("转换且保存成功后自动打开 PDF 预览")
    window.chk_auto_open_preview.setObjectName("singleAutoOpenPreview")
    try:
        window.chk_auto_open_preview.setProperty("emphasis", True)
    except Exception:
        pass
    window.chk_auto_open_preview.setChecked(False)
    window.single_auto_preview_frame = QFrame()
    window.single_auto_preview_frame.setObjectName("singleAutoPreviewFrame")
    auto_preview_layout = QHBoxLayout(window.single_auto_preview_frame)
    auto_preview_layout.setContentsMargins(10, 2, 10, 2)
    auto_preview_layout.setSpacing(6)
    auto_preview_layout.addWidget(window.chk_auto_open_preview)

    options_row = QFrame()
    options_row_layout = QHBoxLayout(options_row)
    options_row_layout.setContentsMargins(0, 0, 0, 0)
    options_row_layout.setSpacing(8)
    options_row_layout.addWidget(window.single_auto_preview_frame)
    options_row_layout.addWidget(window.batch_options_frame)
    options_row_layout.addStretch(1)
    single_type_layout.addWidget(options_row)

    return window.single_path_widget, window.single_type_widget
