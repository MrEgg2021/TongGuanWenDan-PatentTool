"""现代化主界面骨架（侧边栏 + 主内容），仅布局占位，不改动现有逻辑。

遵循设计稿：深色侧栏、浅色工作区、拖拽区卡片、文件列表卡片、底部操作区。
"""

from PySide6.QtCore import (
    Qt, 
    QPropertyAnimation, 
    QEasingCurve, 
    QParallelAnimationGroup
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from gui.windowing import overlay_controller as overlay_controller_api

SIDEBAR_WIDTH_EXPANDED = 200
SIDEBAR_WIDTH_COLLAPSED = 64


def _set_sidebar_text_visible(sidebar: QFrame, visible: bool):
    """设置侧边栏按钮文字的可见性"""
    try:
        # Nav group buttons
        group = getattr(sidebar, "nav_group", None)
        if group:
            for btn in group.buttons():
                full_text = getattr(btn, "_full_text", "")
                btn.setText(full_text if visible else "")
        
        # Env status button
        env_btn = getattr(sidebar, "env_status", None)
        if env_btn:
            full_text = getattr(env_btn, "_full_text", "")
            env_btn.setText(full_text if visible else "")

        domestic_header = getattr(sidebar, "domestic_conversion_header", None)
        if domestic_header:
            full_text = getattr(domestic_header, "_full_text", "")
            domestic_header.setText(full_text if visible else "")

        response_header = getattr(sidebar, "response_correction_header", None)
        if response_header:
            full_text = getattr(response_header, "_full_text", "")
            response_header.setText(full_text if visible else "")
            
    except Exception:
        pass


def _sync_collapsible_group(
    sidebar: QFrame,
    *,
    header_attr: str,
    container_attr: str,
    expanded_attr: str,
    default_base_text: str,
) -> None:
    header = getattr(sidebar, header_attr, None)
    container = getattr(sidebar, container_attr, None)
    if not header or not container:
        return
    expanded = bool(getattr(sidebar, expanded_attr, True))
    collapsed = bool(getattr(sidebar, "_collapsed", False))
    base_text = getattr(header, "_base_text", default_base_text)
    header_text = f"{base_text} {'▾' if expanded else '▸'}"
    header._full_text = header_text
    header.setText("" if collapsed else header_text)
    container.setVisible(expanded and not collapsed)
    header.setProperty("collapsed", collapsed)
    header.setProperty("expanded", expanded)
    header.setToolTip(header_text if collapsed else "")
    try:
        header.style().unpolish(header)
        header.style().polish(header)
        header.update()
    except Exception:
        pass


def _toggle_collapsible_group(
    sidebar: QFrame,
    *,
    expanded_attr: str,
    exclusive_other_attr: str | None = None,
) -> None:
    expanded = bool(getattr(sidebar, expanded_attr, True))
    next_expanded = not expanded
    setattr(sidebar, expanded_attr, next_expanded)
    if bool(next_expanded) and exclusive_other_attr:
        setattr(sidebar, exclusive_other_attr, False)
    _sync_all_sidebar_groups(sidebar)


def _sync_domestic_conversion_group(sidebar: QFrame) -> None:
    _sync_collapsible_group(
        sidebar,
        header_attr="domestic_conversion_header",
        container_attr="domestic_conversion_container",
        expanded_attr="_domestic_conversion_expanded",
        default_base_text="国内申请转档",
    )


def _toggle_domestic_conversion_group(sidebar: QFrame) -> None:
    _toggle_collapsible_group(
        sidebar,
        expanded_attr="_domestic_conversion_expanded",
    )


def _sync_response_correction_group(sidebar: QFrame) -> None:
    _sync_collapsible_group(
        sidebar,
        header_attr="response_correction_header",
        container_attr="response_correction_container",
        expanded_attr="_response_correction_expanded",
        default_base_text="答复/补正",
    )


def _toggle_response_correction_group(sidebar: QFrame) -> None:
    _toggle_collapsible_group(
        sidebar,
        expanded_attr="_response_correction_expanded",
    )


def _sync_all_sidebar_groups(sidebar: QFrame) -> None:
    _sync_domestic_conversion_group(sidebar)
    _sync_response_correction_group(sidebar)


def _toggle_sidebar(sidebar: QFrame) -> None:
    collapsed = bool(getattr(sidebar, "_collapsed", False))
    collapsed = not collapsed
    sidebar._collapsed = collapsed
    
    # Update properties and text here so the width animation stays smooth.
    
    current_width = sidebar.width()
    target_width = SIDEBAR_WIDTH_COLLAPSED if collapsed else SIDEBAR_WIDTH_EXPANDED
    
    # 1. Update button visual properties (icons, styles) but NOT text yet if collapsing
    sidebar.setProperty("collapsed", collapsed)
    sidebar.style().unpolish(sidebar)
    sidebar.style().polish(sidebar)

    buttons = (
        getattr(sidebar, "domestic_conversion_header", None),
        getattr(sidebar, "response_correction_header", None),
        getattr(sidebar, "nav_response", None),
        getattr(sidebar, "nav_correction", None),
        getattr(sidebar, "nav_active_response", None),
        getattr(sidebar, "nav_active_correction", None),
        getattr(sidebar, "nav_home", None),
        getattr(sidebar, "nav_batch", None),
        getattr(sidebar, "nav_preview", None),
        getattr(sidebar, "nav_data_management", None),
        getattr(sidebar, "nav_official_docs", None),
        getattr(sidebar, "nav_formal_review", None),
        getattr(sidebar, "nav_settings", None),
        getattr(sidebar, "nav_about", None),
        getattr(sidebar, "env_status", None),
    )
    for btn in buttons:
        if not btn:
            continue
        btn.setProperty("collapsed", collapsed)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
    
    # 2. Handle Text Visibility
    if not collapsed:
        # Expanding: Show text immediately so it appears as width grows
        _set_sidebar_text_visible(sidebar, True)
    else:
        # Collapsing: Hide text immediately prevents overflow issues? 
        # Or hide after? Hiding after looks better if text clips, but Qt might center-align icon weirdly.
        # Let's hide text immediately for smoother icon movement.
        _set_sidebar_text_visible(sidebar, False)
    _sync_all_sidebar_groups(sidebar)

    # 3. Animate Width
    if hasattr(sidebar, "_anim_group"):
        sidebar._anim_group.stop()
    try:
        overlay_controller_api.relayout("all", reason="sidebar_toggle_start")
    except Exception:
        pass

    anim_min = QPropertyAnimation(sidebar, b"minimumWidth")
    anim_min.setDuration(250)
    anim_min.setStartValue(current_width)
    anim_min.setEndValue(target_width)
    anim_min.setEasingCurve(QEasingCurve.InOutQuad)

    anim_max = QPropertyAnimation(sidebar, b"maximumWidth")
    anim_max.setDuration(250)
    anim_max.setStartValue(current_width)
    anim_max.setEndValue(target_width)
    anim_max.setEasingCurve(QEasingCurve.InOutQuad)
    
    group = QParallelAnimationGroup(sidebar)
    group.addAnimation(anim_min)
    group.addAnimation(anim_max)
    try:
        anim_min.valueChanged.connect(lambda _v: overlay_controller_api.relayout("all", reason="sidebar_toggle_tick"))
    except Exception:
        pass
    
    def on_finished():
        sidebar.setFixedWidth(target_width)
        # Ensure final state is clean
        if collapsed:
             _set_sidebar_text_visible(sidebar, False)
        else:
             _set_sidebar_text_visible(sidebar, True)
        _sync_all_sidebar_groups(sidebar)
        
        # Update tooltips
        for btn in buttons:
            if not btn:
                continue
            full_text = getattr(btn, "_full_text", "")
            btn.setToolTip(full_text if collapsed else "")
        try:
            overlay_controller_api.relayout("all", reason="sidebar_toggle_finished")
        except Exception:
            pass

    group.finished.connect(on_finished)
    sidebar._anim_group = group
    group.start()


def _build_sidebar() -> QFrame:
    sidebar = QFrame()
    sidebar.setObjectName("Sidebar")
    sidebar.setFixedWidth(SIDEBAR_WIDTH_EXPANDED)

    layout = QVBoxLayout(sidebar)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(8)

    sidebar._collapsed = False

    toggle_btn = QPushButton("☰")
    toggle_btn.setObjectName("SidebarToggle")
    toggle_btn.setFixedSize(36, 36)
    toggle_btn.setToolTip("折叠/展开侧边栏")
    toggle_btn.clicked.connect(lambda: _toggle_sidebar(sidebar))
    layout.addWidget(toggle_btn, 0, Qt.AlignLeft)

    btn_group = QButtonGroup(sidebar)
    style = QApplication.style()

    nav_home = QPushButton("单文档处理")
    nav_home.setObjectName("SidebarItem")
    nav_home.setCheckable(True)
    nav_home.setChecked(True)
    try:
        nav_home.setIcon(style.standardIcon(QStyle.SP_FileIcon))
    except Exception:
        pass

    nav_batch = QPushButton("批量处理")
    nav_batch.setObjectName("SidebarItem")
    nav_batch.setCheckable(True)
    try:
        nav_batch.setIcon(style.standardIcon(QStyle.SP_DirIcon))
    except Exception:
        pass

    domestic_conversion_header = QPushButton("国内申请转档 ▾")
    domestic_conversion_header.setObjectName("SidebarGroupHeader")
    domestic_conversion_header.setCheckable(False)
    domestic_conversion_header._base_text = "国内申请转档"
    domestic_conversion_header._full_text = "国内申请转档 ▾"
    try:
        domestic_conversion_header.setIcon(style.standardIcon(QStyle.SP_DirIcon))
    except Exception:
        pass
    domestic_conversion_header.clicked.connect(lambda: _toggle_domestic_conversion_group(sidebar))

    domestic_conversion_container = QFrame()
    domestic_conversion_container.setObjectName("SidebarSubItems")
    domestic_conversion_layout = QVBoxLayout(domestic_conversion_container)
    domestic_conversion_layout.setContentsMargins(8, 0, 0, 0)
    domestic_conversion_layout.setSpacing(4)
    nav_home.setProperty("subItem", True)
    nav_batch.setProperty("subItem", True)
    domestic_conversion_layout.addWidget(nav_home)
    domestic_conversion_layout.addWidget(nav_batch)

    response_correction_header = QPushButton("答复/补正 ▾")
    response_correction_header.setObjectName("SidebarGroupHeader")
    response_correction_header.setCheckable(False)
    response_correction_header._base_text = "答复/补正"
    response_correction_header._full_text = "答复/补正 ▾"
    try:
        response_correction_header.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
    except Exception:
        pass
    response_correction_header.clicked.connect(lambda: _toggle_response_correction_group(sidebar))

    response_correction_container = QFrame()
    response_correction_container.setObjectName("SidebarSubItems")
    response_correction_layout = QVBoxLayout(response_correction_container)
    response_correction_layout.setContentsMargins(8, 0, 0, 0)
    response_correction_layout.setSpacing(4)
    nav_response = QPushButton("答复审查意见")
    nav_response.setObjectName("SidebarItem")
    nav_response.setCheckable(True)
    nav_response.setProperty("subItem", True)
    nav_correction = QPushButton("答复补正")
    nav_correction.setObjectName("SidebarItem")
    nav_correction.setCheckable(True)
    nav_correction.setProperty("subItem", True)
    nav_active_response = QPushButton("主动答复")
    nav_active_response.setObjectName("SidebarItem")
    nav_active_response.setCheckable(True)
    nav_active_response.setProperty("subItem", True)
    nav_active_correction = QPushButton("主动补正")
    nav_active_correction.setObjectName("SidebarItem")
    nav_active_correction.setCheckable(True)
    nav_active_correction.setProperty("subItem", True)
    try:
        nav_response.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
        nav_correction.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
        nav_active_response.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
        nav_active_correction.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
    except Exception:
        pass
    response_correction_layout.addWidget(nav_response)
    response_correction_layout.addWidget(nav_correction)
    response_correction_layout.addWidget(nav_active_response)
    response_correction_layout.addWidget(nav_active_correction)

    nav_preview = QPushButton("预览/导出PDF")
    nav_preview.setObjectName("SidebarItem")
    nav_preview.setCheckable(True)
    try:
        nav_preview.setIcon(style.standardIcon(QStyle.SP_DialogOpenButton))
    except Exception:
        pass

    nav_data_management = QPushButton("数据管理")
    nav_data_management.setObjectName("SidebarItem")
    nav_data_management.setCheckable(True)
    try:
        nav_data_management.setIcon(style.standardIcon(QStyle.SP_DirHomeIcon))
    except Exception:
        pass

    nav_official_docs = QPushButton("官文处理")
    nav_official_docs.setObjectName("SidebarItem")
    nav_official_docs.setCheckable(True)
    try:
        nav_official_docs.setIcon(style.standardIcon(QStyle.SP_FileDialogContentsView))
    except Exception:
        pass

    nav_formal_review = QPushButton("形式审查")
    nav_formal_review.setObjectName("SidebarItem")
    nav_formal_review.setCheckable(True)
    try:
        nav_formal_review.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
    except Exception:
        pass

    nav_settings = QPushButton("其他设置")
    nav_settings.setObjectName("SidebarItem")
    nav_settings.setCheckable(True)
    try:
        nav_settings.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
    except Exception:
        pass

    for btn in (
        nav_home,
        nav_batch,
        nav_response,
        nav_correction,
        nav_active_response,
        nav_active_correction,
        nav_preview,
    ):
        try:
            btn._full_text = btn.text()
            btn.setToolTip(btn.text())
            btn.setProperty("collapsed", False)
        except Exception:
            pass
        btn_group.addButton(btn)

    try:
        domestic_conversion_header.setToolTip(domestic_conversion_header.text())
        domestic_conversion_header.setProperty("collapsed", False)
    except Exception:
        pass
    try:
        response_correction_header.setToolTip(response_correction_header.text())
        response_correction_header.setProperty("collapsed", False)
    except Exception:
        pass
    layout.addWidget(domestic_conversion_header)
    layout.addWidget(domestic_conversion_container)
    layout.addWidget(response_correction_header)
    layout.addWidget(response_correction_container)
    layout.addWidget(nav_preview)

    for btn in (nav_data_management, nav_official_docs, nav_formal_review, nav_settings):
        try:
            btn._full_text = btn.text()
            btn.setToolTip(btn.text())
            btn.setProperty("collapsed", False)
        except Exception:
            pass
        btn_group.addButton(btn)
    layout.addWidget(nav_data_management)
    layout.addWidget(nav_official_docs)
    layout.addWidget(nav_formal_review)
    layout.addWidget(nav_settings)

    env_status = QPushButton("环境：未检测")
    env_status.setObjectName("SidebarItem")
    try:
        env_status.setIcon(style.standardIcon(QStyle.SP_MessageBoxInformation))
    except Exception:
        pass
    try:
        env_status._full_text = env_status.text()
        env_status.setToolTip(env_status.text())
        env_status.setProperty("collapsed", False)
    except Exception:
        pass
    layout.addWidget(env_status)

    nav_about = QPushButton("关于")
    nav_about.setObjectName("SidebarItem")
    nav_about.setCheckable(True)
    try:
        nav_about.setIcon(style.standardIcon(QStyle.SP_MessageBoxInformation))
    except Exception:
        pass
    try:
        nav_about._full_text = nav_about.text()
        nav_about.setToolTip(nav_about.text())
        nav_about.setProperty("collapsed", False)
    except Exception:
        pass
    btn_group.addButton(nav_about)
    layout.addWidget(nav_about)

    sidebar.nav_home = nav_home
    sidebar.nav_batch = nav_batch
    sidebar.nav_response = nav_response
    sidebar.nav_correction = nav_correction
    sidebar.nav_active_response = nav_active_response
    sidebar.nav_active_correction = nav_active_correction
    sidebar.nav_preview = nav_preview
    sidebar.domestic_conversion_header = domestic_conversion_header
    sidebar.domestic_conversion_container = domestic_conversion_container
    sidebar._domestic_conversion_expanded = False
    sidebar.response_correction_header = response_correction_header
    sidebar.response_correction_container = response_correction_container
    sidebar._response_correction_expanded = False
    sidebar.nav_data_management = nav_data_management
    sidebar.nav_settings = nav_settings
    sidebar.nav_official_docs = nav_official_docs
    sidebar.nav_formal_review = nav_formal_review
    sidebar.nav_about = nav_about
    sidebar.env_status = env_status
    sidebar.nav_group = btn_group
    sidebar.toggle_btn = toggle_btn
    _sync_all_sidebar_groups(sidebar)
    return sidebar


def _build_header(title_text: str, subtitle_text: str) -> QFrame:
    header = QFrame()
    hl = QVBoxLayout(header)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(4)

    title = QLabel(title_text)
    title.setProperty("role", "h1")
    hl.addWidget(title)

    if subtitle_text:
        subtitle = QLabel(subtitle_text)
        subtitle.setProperty("role", "caption")
        hl.addWidget(subtitle)
    return header


def _build_drop_zone() -> QFrame:
    drop = QFrame()
    drop.setObjectName("DropZone")
    drop.setMinimumHeight(140)
    drop.setStyleSheet(
        """
        QFrame#DropZone {
            background: #FFFFFF;
            border: 1px dashed #CBD5E1;
            border-radius: 12px;
        }
        """
    )
    v = QVBoxLayout(drop)
    v.setContentsMargins(24, 24, 24, 24)
    v.setSpacing(8)
    hint = QLabel("拖拽 DOCX / XML 到此处，或点击选择")
    hint.setAlignment(Qt.AlignCenter)
    hint.setProperty("role", "label")
    sub = QLabel("批量处理将自动队列执行，勿扰模式可全程遮罩")
    sub.setAlignment(Qt.AlignCenter)
    sub.setProperty("role", "caption")
    v.addStretch(1)
    v.addWidget(hint, 0, Qt.AlignCenter)
    v.addWidget(sub, 0, Qt.AlignCenter)
    v.addStretch(1)
    return drop


def _build_file_list_card() -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)

    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(8)
    title = QLabel("待处理文件")
    title.setProperty("role", "label")
    count = QLabel("0 项")
    count.setProperty("role", "caption")
    title_row.addWidget(title)
    title_row.addWidget(count)
    title_row.addStretch(1)
    layout.addLayout(title_row)

    lst = QListWidget()
    lst.setObjectName("CardList")
    lst.setStyleSheet(
        """
        QListWidget#CardList {
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 8px;
            background: #FFFFFF;
        }
        QListWidget#CardList::item {
            padding: 8px;
        }
        QListWidget#CardList::item:selected {
            background: #EFF6FF;
            color: #0F172A;
        }
        """
    )
    # 占位项
    placeholder = QListWidgetItem("CN1029384_说明书.docx · 待处理")
    lst.addItem(placeholder)

    layout.addWidget(lst)
    return card


def _build_footer_actions() -> QFrame:
    footer = QFrame()
    hl = QHBoxLayout(footer)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(12)

    btn_back = QPushButton("清空列表")
    btn_back.setObjectName("Ghost")

    btn_run = QPushButton("开始转换")
    btn_run.setObjectName("Primary")

    hl.addStretch(1)
    hl.addWidget(btn_back)
    hl.addWidget(btn_run)
    return footer


def build_modern_shell(
    parent: QWidget | None = None,
    central: QWidget | None = None,
    header_title: str = "专利 XML 转档",
    header_subtitle: str = "支持单文档与批处理，保持格式一致性",
) -> QFrame:
    """构建现代化主界面骨架（侧栏 + 主内容）。

    central: 若提供，则作为主内容替换默认的拖拽区/列表/按钮占位。
    """
    container = QFrame(parent)
    container.setObjectName("ModernShell")

    root = QHBoxLayout(container)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    sidebar = _build_sidebar()
    root.addWidget(sidebar, 0)

    main = QFrame()
    main_layout = QVBoxLayout(main)
    main_layout.setContentsMargins(18, 12, 18, 12)
    main_layout.setSpacing(10)

    try:
        if str(header_title or "").strip() or str(header_subtitle or "").strip():
            header = _build_header(header_title, header_subtitle)
            main_layout.addWidget(header)
    except Exception:
        pass

    if central is None:
        drop = _build_drop_zone()
        files = _build_file_list_card()
        footer = _build_footer_actions()
        main_layout.addWidget(drop)
        main_layout.addWidget(files)
        main_layout.addStretch(1)
        main_layout.addWidget(footer)
    else:
        main_layout.addWidget(central, 1)

    root.addWidget(main, 1)
    container.sidebar = sidebar
    container.nav_home = sidebar.nav_home
    container.nav_batch = sidebar.nav_batch
    container.nav_response = getattr(sidebar, "nav_response", None)
    container.nav_correction = getattr(sidebar, "nav_correction", None)
    container.nav_active_response = getattr(sidebar, "nav_active_response", None)
    container.nav_active_correction = getattr(sidebar, "nav_active_correction", None)
    container.nav_preview = getattr(sidebar, "nav_preview", None)
    container.nav_data_management = getattr(sidebar, "nav_data_management", None)
    container.nav_official_docs = getattr(sidebar, "nav_official_docs", None)
    container.nav_formal_review = getattr(sidebar, "nav_formal_review", None)
    container.nav_settings = sidebar.nav_settings
    container.nav_about = sidebar.nav_about
    container.env_status = getattr(sidebar, "env_status", None)
    container.nav_group = sidebar.nav_group
    container.main_area = main
    container.sidebar_toggle = getattr(sidebar, "toggle_btn", None)
    return container
