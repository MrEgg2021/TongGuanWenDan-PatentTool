from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import GraphicCheckBox
from gui.app_impl.mode import _format_tooltip_html
from gui.widgets_impl.combo_wheel_blocker import ComboWheelBlocker


def build_settings_page(window):
    page = QWidget()
    page.setObjectName("settingsPage")
    page.setVisible(False)

    page_row = QHBoxLayout(page)
    page_row.setContentsMargins(0, 0, 0, 0)
    page_row.setSpacing(0)

    content = QWidget(page)
    content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    root = QVBoxLayout(content)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(10)

    page_row.addWidget(content, 1)

    title = QLabel("其他设置")
    title.setProperty("role", "h1")
    subtitle = QLabel("调整全局偏好：公式居中、段号分配、转图缩放倍数等")
    subtitle.setProperty("role", "caption")
    subtitle.setProperty("emphasis", True)
    subtitle.setWordWrap(True)
    root.addWidget(title)
    root.addWidget(subtitle)

    card = QFrame()
    card.setObjectName("Card")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(12, 12, 12, 12)
    card_layout.setSpacing(10)


    chk_opt = GraphicCheckBox("优化公式居中")
    try:
        chk_opt.setProperty("emphasis", True)
    except Exception:
        pass
    chk_opt.setObjectName("settingsOptCenter")
    try:
        chk_opt.setToolTip(
            _format_tooltip_html(
                "仅支持原生的、单行、单段的公式（右侧+编号）的，行内公式和图片格式的公式或者宽度过大的公式不支持/效果不明显",
                420,
            )
        )
    except Exception:
        pass
    chk_table_center = GraphicCheckBox("表格转图居中")
    try:
        chk_table_center.setProperty("emphasis", True)
    except Exception:
        pass
    chk_table_center.setObjectName("settingsTableImgCenter")
    try:
        chk_table_center.setToolTip(
            _format_tooltip_html(
                "若表格宽度过大可能不支持或效果不明显，表格转图暂不支持跨页超长表格，请在word中手动拆分后再进行转档处理",
                420,
            )
        )
    except Exception:
        pass

    chk_req_form_skip_tip = GraphicCheckBox('启用“未勾选请求书”提示弹窗（单/批共用）')
    try:
        chk_req_form_skip_tip.setProperty("emphasis", True)
    except Exception:
        pass
    chk_req_form_skip_tip.setObjectName("settingsReqFormSkipTip")
    try:
        chk_opt.setChecked(False)
        chk_table_center.setChecked(False)
        chk_req_form_skip_tip.setChecked(True)
    except Exception:
        pass

    opt_row = QHBoxLayout()
    opt_row.setContentsMargins(0, 0, 0, 0)
    opt_row.setSpacing(10)
    opt_row.addWidget(chk_opt)
    opt_row.addWidget(chk_table_center)
    opt_row.addWidget(chk_req_form_skip_tip)
    opt_row.addStretch(1)
    card_layout.addLayout(opt_row)

    desc_row = QHBoxLayout()
    desc_row.setContentsMargins(0, 0, 0, 0)
    desc_row.setSpacing(4)
    desc_label = QLabel("说明书段号分配：")
    desc_label.setProperty("role", "label")
    desc_label.setProperty("emphasis", True)
    desc_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    desc_label.setStyleSheet("background: transparent; padding: 0px;")
    desc_row.addWidget(desc_label)

    desc_combo = QComboBox()
    desc_combo.setObjectName("settingsDescSplitMode")
    desc_combo.addItem("按Word段落", "word")
    desc_combo.addItem("按句号", "period")
    desc_combo.addItem("匹配官方客户端", "word_period_end")
    try:
        idx = desc_combo.findData("word_period_end")
        if idx >= 0:
            desc_combo.setCurrentIndex(idx)
    except Exception:
        pass

    wheel_blocker = ComboWheelBlocker(page)
    try:
        page._combo_wheel_blocker = wheel_blocker
    except Exception:
        pass
    wheel_blocker.register_combo(desc_combo)

    scale_label = QLabel("公式缩放倍数：")
    scale_label.setProperty("role", "label")
    scale_label.setProperty("emphasis", True)
    scale_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    scale_label.setStyleSheet("background: transparent; padding: 0px;")

    spin_ratio = QDoubleSpinBox()
    spin_ratio.setObjectName("settingsScaleRatio")
    spin_ratio.setDecimals(2)
    spin_ratio.setSingleStep(0.05)
    spin_ratio.setRange(0.4, 1.0)
    spin_ratio.setKeyboardTracking(False)
    spin_ratio.setFixedWidth(64)  # 收窄为原先约 0.6 倍
    try:
        spin_ratio.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    except Exception:
        pass
    try:
        wheel_blocker.register_widget(spin_ratio)
    except Exception:
        pass
    try:
        spin_ratio.setValue(0.8)
    except Exception:
        pass

    btn_minus = QPushButton("-")
    btn_minus.setObjectName("settingsScaleRatioMinus")
    btn_minus.setFocusPolicy(Qt.NoFocus)
    btn_minus.setFixedSize(30, 30)

    btn_plus = QPushButton("+")
    btn_plus.setObjectName("settingsScaleRatioPlus")
    btn_plus.setFocusPolicy(Qt.NoFocus)
    btn_plus.setFixedSize(30, 30)

    try:
        btn_minus.clicked.connect(spin_ratio.stepDown)
        btn_plus.clicked.connect(spin_ratio.stepUp)
    except Exception:
        pass

    scale_box = QWidget(card)
    scale_box_layout = QHBoxLayout(scale_box)
    scale_box_layout.setContentsMargins(0, 0, 0, 0)
    scale_box_layout.setSpacing(6)
    scale_box_layout.addWidget(btn_minus)
    scale_box_layout.addWidget(spin_ratio)
    scale_box_layout.addWidget(btn_plus)

    desc_row.addWidget(desc_combo)

    drawings_row = QHBoxLayout()
    drawings_row.setContentsMargins(0, 0, 0, 0)
    drawings_row.setSpacing(10)
    drawings_row.addLayout(desc_row, 0)
    drawings_row.addStretch(1)
    card_layout.addLayout(drawings_row)

    chk_id_validate_cn = GraphicCheckBox("身份证号码校验")
    try:
        chk_id_validate_cn.setProperty("emphasis", True)
    except Exception:
        pass
    chk_id_validate_cn.setObjectName("settingsIdValidationCn")
    try:
        chk_id_validate_cn.setChecked(False)
    except Exception:
        pass

    chk_id_validate_uscc = GraphicCheckBox("统一社会信用代码校验")
    try:
        chk_id_validate_uscc.setProperty("emphasis", True)
    except Exception:
        pass
    chk_id_validate_uscc.setObjectName("settingsIdValidationUscc")
    try:
        chk_id_validate_uscc.setChecked(False)
    except Exception:
        pass

    validate_row = QHBoxLayout()
    validate_row.setContentsMargins(0, 0, 0, 0)
    validate_row.setSpacing(6)
    validate_row.addWidget(chk_id_validate_cn)
    validate_row.addWidget(chk_id_validate_uscc)
    validate_row.addSpacing(8)
    validate_row.addWidget(scale_label)
    validate_row.addWidget(scale_box)
    validate_row.addStretch(1)
    card_layout.addLayout(validate_row)

    root.addWidget(card)

    env_card = QFrame()
    env_card.setObjectName("Card")
    env_layout = QVBoxLayout(env_card)
    env_layout.setContentsMargins(12, 12, 12, 12)
    env_layout.setSpacing(10)


    env_title = QLabel("环境检测")
    env_title.setProperty("role", "h2")
    btn_refresh = QPushButton("刷新检测")
    btn_refresh.setObjectName("settingsEnvRefreshButton")
    btn_refresh.setProperty("class", "Secondary")
    env_header = QHBoxLayout()
    env_header.setContentsMargins(0, 0, 0, 0)
    env_header.setSpacing(10)
    env_header.addWidget(env_title)
    env_header.addStretch(1)
    env_header.addWidget(btn_refresh, 0)
    env_layout.addLayout(env_header)

    windows_row = QHBoxLayout()
    windows_row.setContentsMargins(0, 0, 0, 0)
    windows_row.setSpacing(10)
    windows_label = QLabel("Windows 系统版本：")
    windows_label.setProperty("role", "label")
    windows_label.setProperty("emphasis", True)
    windows_row.addWidget(windows_label)
    windows_status = QLabel("未检测")
    windows_status.setObjectName("settingsEnvWindowsStatus")
    windows_status.setWordWrap(True)
    windows_row.addWidget(windows_status, 1)
    runtime_label = QLabel("关键运行库：")
    runtime_label.setProperty("role", "label")
    runtime_label.setProperty("emphasis", True)
    windows_row.addWidget(runtime_label)
    runtime_status = QLabel("未检测")
    runtime_status.setObjectName("settingsEnvRuntimeStatus")
    runtime_status.setWordWrap(True)
    windows_row.addWidget(runtime_status, 1)
    env_layout.addLayout(windows_row)

    word_row = QHBoxLayout()
    word_row.setContentsMargins(0, 0, 0, 0)
    word_row.setSpacing(10)
    word_label = QLabel("Word 版本：")
    word_label.setProperty("role", "label")
    word_label.setProperty("emphasis", True)
    word_row.addWidget(word_label)
    word_status = QLabel("未检测")
    word_status.setObjectName("settingsEnvWordStatus")
    word_status.setWordWrap(True)
    word_row.addWidget(word_status, 1)
    wps_label = QLabel("Word后台端口是否被其他软件劫持：")
    wps_label.setProperty("role", "label")
    wps_label.setProperty("emphasis", True)
    wps_status = QLabel("未检测")
    wps_status.setObjectName("settingsEnvWpsStatus")
    wps_status.setWordWrap(True)
    word_row.addWidget(wps_label)
    word_row.addWidget(wps_status, 1)
    btn_wps_help = QPushButton("查看处理建议")
    btn_wps_help.setObjectName("settingsEnvWpsHelpButton")
    btn_wps_help.setProperty("class", "Ghost")
    try:
        btn_wps_help.setEnabled(True)
    except Exception:
        pass
    word_row.addWidget(btn_wps_help, 0)
    env_layout.addLayout(word_row)

    pdf_row = QHBoxLayout()
    pdf_row.setContentsMargins(0, 0, 0, 0)
    pdf_row.setSpacing(10)
    pdf_label = QLabel("Word PDF 导出能力：")
    pdf_label.setProperty("role", "label")
    pdf_label.setProperty("emphasis", True)
    pdf_row.addWidget(pdf_label)
    pdf_status = QLabel("未检测")
    pdf_status.setObjectName("settingsEnvPdfExportStatus")
    pdf_status.setWordWrap(True)
    pdf_row.addWidget(pdf_status, 1)
    env_layout.addLayout(pdf_row)

    preview_row = QHBoxLayout()
    preview_row.setContentsMargins(0, 0, 0, 0)
    preview_row.setSpacing(6)
    preview_label = QLabel("轻量预览服务：")
    preview_label.setProperty("role", "label")
    preview_label.setProperty("emphasis", True)
    preview_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    preview_label.setStyleSheet("background: transparent; padding: 0px;")
    preview_row.addWidget(preview_label)
    preview_status = QLabel("未检测")
    preview_status.setObjectName("settingsEnvLegacyPreviewStatus")
    preview_status.setWordWrap(False)
    preview_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    preview_status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    preview_row.addWidget(preview_status, 1)
    btn_preview_port = QPushButton("修改端口")
    btn_preview_port.setObjectName("settingsLegacyPreviewPortButton")
    btn_preview_port.setProperty("class", "Secondary")
    preview_row.addWidget(btn_preview_port, 0)
    env_layout.addLayout(preview_row)

    full_preview_row = QHBoxLayout()
    full_preview_row.setContentsMargins(0, 0, 0, 0)
    full_preview_row.setSpacing(6)
    full_preview_label = QLabel("全量预览服务：")
    full_preview_label.setProperty("role", "label")
    full_preview_label.setProperty("emphasis", True)
    full_preview_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    full_preview_row.addWidget(full_preview_label)
    full_preview_status = QLabel("未配置")
    full_preview_status.setObjectName("settingsEnvPreviewStatus")
    full_preview_status.setWordWrap(True)
    full_preview_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    full_preview_row.addWidget(full_preview_status, 1)
    btn_full_preview = QPushButton("检测/选择路径")
    btn_full_preview.setObjectName("settingsFullPreviewRuntimeButton")
    btn_full_preview.setProperty("class", "Secondary")
    full_preview_row.addWidget(btn_full_preview, 0)
    env_layout.addLayout(full_preview_row)
    root.addWidget(env_card)

    export_card = QFrame()
    export_card.setObjectName("Card")
    export_card_layout = QVBoxLayout(export_card)
    export_card_layout.setContentsMargins(12, 12, 12, 12)
    export_card_layout.setSpacing(10)


    export_title = QLabel("导出模板")
    export_title.setProperty("role", "h2")
    export_card_layout.addWidget(export_title)

    export_row = QHBoxLayout()
    export_row.setContentsMargins(0, 0, 0, 0)
    export_row.setSpacing(10)
    btn_export_tpl = QPushButton("导出Docx文件模版")
    btn_export_tpl.setObjectName("otherSettingsExportTemplate")
    btn_export_tpl.setProperty("class", "Secondary")
    export_row.addWidget(btn_export_tpl, 0)
    export_row.addStretch(1)
    export_card_layout.addLayout(export_row)

    root.addWidget(export_card)

    footer = QFrame()
    fl = QHBoxLayout(footer)
    fl.setContentsMargins(0, 0, 0, 0)
    fl.setSpacing(8)
    fl.addStretch(1)
    btn_save = QPushButton("保存")
    btn_save.setObjectName("otherSettingsSave")
    btn_save.setProperty("class", "Primary")
    fl.addWidget(btn_save)
    root.addWidget(footer)

    try:
        btn_save.clicked.connect(window._on_other_settings_save)
    except Exception:
        pass
    try:
        btn_export_tpl.clicked.connect(window.on_export_template)
    except Exception:
        pass

    window.settings_page = page
    window.settings_opt_center = chk_opt
    window.settings_table_img_center = chk_table_center
    window.settings_req_form_skip_tip = chk_req_form_skip_tip
    window.settings_id_validation_cn = chk_id_validate_cn
    window.settings_id_validation_uscc = chk_id_validate_uscc
    window.settings_desc_split_mode = desc_combo
    window.settings_scale_ratio = spin_ratio
    window.settings_scale_ratio_minus_button = btn_minus
    window.settings_scale_ratio_plus_button = btn_plus
    window.settings_save_button = btn_save
    window.settings_env_refresh_button = btn_refresh
    window.settings_env_word_status = word_status
    window.settings_env_wps_status = wps_status
    window.settings_env_pdf_export_status = pdf_status
    window.settings_env_wps_help_button = btn_wps_help
    window.settings_env_legacy_preview_status = preview_status
    window.settings_env_preview_status = full_preview_status
    window.settings_legacy_preview_port_button = btn_preview_port
    window.settings_full_preview_runtime_button = btn_full_preview
    window.settings_env_windows_status = windows_status
    window.settings_env_runtime_status = runtime_status
    window.settings_export_template_button = btn_export_tpl

    try:
        btn_refresh.clicked.connect(window._on_settings_env_refresh)
    except Exception:
        pass
    try:
        btn_wps_help.clicked.connect(window._on_settings_env_wps_help)
    except Exception:
        pass
    try:
        btn_preview_port.clicked.connect(window._on_settings_legacy_preview_port)
        btn_full_preview.clicked.connect(window._on_settings_full_preview_runtime)
    except Exception:
        pass
    return page
