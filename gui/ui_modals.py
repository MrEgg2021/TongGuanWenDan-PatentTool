"""自定义模态框组件（占位版），对应设计稿：Processing / Result Sheet / Alert。

仅提供 UI 结构与样式挂点，不接业务逻辑。可在后续流程中接线：
- build_processing_modal: 勿扰模式遮罩 + 全局进度
- build_result_sheet_modal: 结果成绩单（总/成/败 + 列表 + 按钮）
- build_blocking_alert: 阻断式警告（顶部彩线 + 描述 + 动作）
"""

import html

from PySide6.QtCore import Qt
from typing import List, Tuple

from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from gui.widgets_impl.elide_label import ElideLabel


def _overlay(parent: QWidget | None) -> QFrame:
    overlay = QFrame(parent)
    overlay.setObjectName("ModalOverlay")
    overlay.setAttribute(Qt.WA_StyledBackground, True)
    lay = QVBoxLayout(overlay)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lay.setAlignment(Qt.AlignCenter)
    return overlay


def _build_modal_titlebar(title_text: str, *, close_object_name: str = "ModalCloseButton") -> tuple[QFrame, QPushButton]:
    bar = QFrame()
    bar.setObjectName("ModalTitleBar")
    hl = QHBoxLayout(bar)
    hl.setContentsMargins(16, 12, 12, 12)
    hl.setSpacing(8)

    title = QLabel(title_text)
    title.setObjectName("ModalTitleText")
    title.setProperty("role", "h2")
    hl.addWidget(title, 1)

    btn_close = QPushButton("×")
    btn_close.setObjectName(close_object_name)
    btn_close.setFixedSize(28, 28)
    btn_close.setFocusPolicy(Qt.NoFocus)
    hl.addWidget(btn_close, 0, Qt.AlignTop)
    return bar, btn_close


def _resolve_processing_card_width(parent: QWidget | None) -> int:
    return _resolve_modal_card_width(parent, preferred=680, min_width=220, max_width=900, safety_margin=48)


def _owner_width(parent: QWidget | None) -> int:
    width = 0
    try:
        if parent is not None:
            width = int(parent.width() or 0)
    except Exception:
        width = 0
    if width > 0:
        return width
    try:
        owner = QApplication.activeWindow()
        return int(owner.width() or 0) if owner is not None else 0
    except Exception:
        return 0


def _resolve_modal_card_width(
    parent: QWidget | None,
    *,
    preferred: int,
    min_width: int,
    max_width: int,
    safety_margin: int = 24,
) -> int:
    owner_width = max(0, int(_owner_width(parent)))
    upper = max(int(min_width), int(max_width))
    lower = max(180, min(int(min_width), upper))
    if owner_width > 0:
        owner_cap = max(180, int(owner_width) - max(0, int(safety_margin)))
        upper = min(upper, owner_cap)
        lower = min(lower, upper)
    target = int(preferred)
    return max(lower, min(target, upper))


def build_processing_modal(
    parent: QWidget | None = None,
    status_text: str = "正在处理 (0/0)",
    filename_text: str = "等待任务",
    progress_value: int = 0,
) -> QFrame:
    """处理进度遮罩（非可关闭）。"""
    overlay = _overlay(parent)

    card = QFrame()
    card.setObjectName("ModalCard")
    initial_width = _resolve_processing_card_width(parent)
    card.setMinimumWidth(initial_width)
    card.setMaximumWidth(initial_width)
    v = QVBoxLayout(card)
    v.setContentsMargins(24, 24, 24, 16)
    v.setSpacing(12)

    title = QLabel(status_text)
    title.setObjectName("processingStatus")
    title.setAlignment(Qt.AlignCenter)
    title.setProperty("role", "h2")
    try:
        title.setWordWrap(True)
    except Exception:
        pass

    subtitle = ElideLabel(filename_text, elide_mode=Qt.ElideMiddle)
    subtitle.setObjectName("processingFile")
    subtitle.setAlignment(Qt.AlignCenter)
    subtitle.setProperty("role", "caption")
    try:
        subtitle.setWordWrap(False)
    except Exception:
        pass

    bar = QProgressBar()
    bar.setObjectName("processingBar")
    bar.setRange(0, 100)
    bar.setValue(progress_value)

    header_box = QFrame()
    header_box.setObjectName("processingHeaderBox")
    try:
        header_box.setVisible(False)
    except Exception:
        pass
    header_layout = QVBoxLayout(header_box)
    header_layout.setContentsMargins(12, 10, 12, 10)
    header_layout.setSpacing(6)
    header_stage = QLabel("")
    header_stage.setObjectName("processingHeaderStage")
    header_stage.setAlignment(Qt.AlignCenter)
    header_stage.setProperty("role", "caption")
    try:
        header_stage.setWordWrap(True)
    except Exception:
        pass
    header_stage.setProperty("class", "ProcessingStageLabel")
    header_summary = QLabel("")
    header_summary.setObjectName("processingHeaderSummary")
    header_summary.setAlignment(Qt.AlignCenter)
    header_summary.setProperty("role", "caption")
    try:
        header_summary.setWordWrap(True)
    except Exception:
        pass
    header_summary.setProperty("class", "ProcessingSummaryLabel")

    header_layout.addWidget(header_stage)
    header_layout.addWidget(header_summary)

    warn = QFrame()
    warn.setObjectName("ProcessingWarningBar")
    warn_layout = QHBoxLayout(warn)
    warn_layout.setContentsMargins(12, 6, 12, 6)
    warn_layout.setSpacing(8)
    warn_label = QLabel("⚠ 独占模式：转换期间请不要操作鼠标或键盘，也不要切换窗口；否则可能导致失败或结果异常。")
    warn_label.setObjectName("processingWarnLabel")
    warn_label.setProperty("role", "label")
    warn_label.setWordWrap(True)
    warn_label.setAlignment(Qt.AlignCenter)
    warn_layout.addWidget(warn_label, 1, Qt.AlignVCenter)

    cfg = QFrame()
    cfg.setObjectName("processingConfigBox")
    try:
        cfg.setVisible(False)
    except Exception:
        pass
    cfg_layout = QVBoxLayout(cfg)
    cfg_layout.setContentsMargins(12, 8, 12, 8)
    cfg_layout.setSpacing(6)
    cfg_title = QLabel("配置核对（其他设置）")
    cfg_title.setObjectName("processingConfigTitle")
    cfg_title.setAlignment(Qt.AlignCenter)
    cfg_layout.addWidget(cfg_title)

    cfg_opt_center = QLabel("")
    cfg_opt_center.setObjectName("processingCfgOptCenter")
    cfg_opt_center.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    try:
        cfg_opt_center.setWordWrap(True)
    except Exception:
        pass

    cfg_table_center = QLabel("")
    cfg_table_center.setObjectName("processingCfgTableCenter")
    cfg_table_center.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    try:
        cfg_table_center.setWordWrap(True)
    except Exception:
        pass

    cfg_scale_ratio = QLabel("")
    cfg_scale_ratio.setObjectName("processingCfgScaleRatio")
    cfg_scale_ratio.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    try:
        cfg_scale_ratio.setWordWrap(True)
    except Exception:
        pass

    cfg_desc_mode = QLabel("")
    cfg_desc_mode.setObjectName("processingCfgDescMode")
    cfg_desc_mode.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    try:
        cfg_desc_mode.setWordWrap(True)
    except Exception:
        pass

    cfg_patent_type = QLabel("")
    cfg_patent_type.setObjectName("processingCfgPatentType")
    cfg_patent_type.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    try:
        cfg_patent_type.setWordWrap(True)
    except Exception:
        pass

    cfg_layout.addWidget(cfg_opt_center)
    cfg_layout.addWidget(cfg_table_center)
    cfg_layout.addWidget(cfg_scale_ratio)
    cfg_layout.addWidget(cfg_desc_mode)
    cfg_layout.addWidget(cfg_patent_type)

    footer = QFrame()
    footer_layout = QHBoxLayout(footer)
    footer_layout.setContentsMargins(0, 6, 0, 0)
    footer_layout.setSpacing(12)
    footer_layout.addStretch(1)

    btn_cancel = QPushButton("取消")
    btn_cancel.setObjectName("processingCancelButton")
    btn_cancel.setProperty("role", "resultBack")
    footer_layout.addWidget(btn_cancel)

    v.addWidget(title)
    v.addWidget(subtitle)
    v.addWidget(bar)
    v.addWidget(header_box)
    v.addWidget(warn)
    v.addWidget(cfg)
    v.addWidget(footer)

    overlay.layout().addWidget(card, 0, Qt.AlignCenter)
    return overlay


def build_result_sheet_modal(
    parent: QWidget | None = None,
    total: int = 0,
    success: int = 0,
    failed: int = 0,
    items: List[Tuple[str, str]] | None = None,
    notice_text: str | None = None,
) -> QFrame:
    """结果成绩单模态框，占位 UI。items: (filename, status) status in {'success','fail'}"""
    items = items or []
    overlay = _overlay(parent)

    card = QFrame()
    card.setObjectName("ModalCard")
    target_width = _resolve_modal_card_width(parent, preferred=460, min_width=220, max_width=560, safety_margin=24)
    card.setMinimumWidth(target_width)
    card.setMaximumWidth(target_width)
    v = QVBoxLayout(card)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)

    titlebar, _ = _build_modal_titlebar("转换完成", close_object_name="ModalCloseButton")

    v.addWidget(titlebar)

    # 内部包裹容器，用于控制边距
    inner = QWidget()
    il = QVBoxLayout(inner)
    il.setContentsMargins(24, 16, 24, 16)
    il.setSpacing(12)

    stats = QFrame()
    stats_layout = QHBoxLayout(stats)
    stats_layout.setContentsMargins(0, 0, 0, 0)
    stats_layout.setSpacing(12)
    stats_layout.addStretch(1)
    for label, value, color in [
        ("总数", total, "#0F172A"),
        ("成功", success, "#10B981"),
        ("失败", failed, "#EF4444"),
    ]:
        col = QVBoxLayout()
        t1 = QLabel(label)
        t1.setProperty("role", "caption")
        t1.setAlignment(Qt.AlignCenter)
        t2 = QLabel(str(value))
        t2.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 16px;")
        t2.setAlignment(Qt.AlignCenter)
        col.addWidget(t1)
        col.addWidget(t2)
        stats_layout.addLayout(col)
    stats_layout.addStretch(1)
    il.addWidget(stats)

    notice = str(notice_text or "").strip()
    if notice:
        notice_box = QFrame()
        notice_box.setObjectName("ResultNoticeBox")
        notice_layout = QVBoxLayout(notice_box)
        notice_layout.setContentsMargins(10, 8, 10, 8)
        notice_layout.setSpacing(6)

        notice_title = QLabel("提醒")
        notice_title.setObjectName("ResultNoticeTitle")
        notice_title.setProperty("role", "label")
        notice_layout.addWidget(notice_title)

        notice_body = QTextBrowser()
        notice_body.setObjectName("ResultNoticeBody")
        rendered_notice = notice
        try:
            if not bool(Qt.mightBeRichText(notice)):
                rendered_notice = html.escape(notice).replace("\n", "<br/>")
        except Exception:
            rendered_notice = html.escape(notice).replace("\n", "<br/>")
        try:
            notice_body.setHtml(rendered_notice)
        except Exception:
            notice_body.setPlainText(notice)
        try:
            notice_body.setReadOnly(True)
        except Exception:
            pass
        try:
            notice_body.setFrameShape(QFrame.NoFrame)
        except Exception:
            pass
        try:
            notice_body.setMaximumHeight(180)
        except Exception:
            pass
        try:
            notice_body.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        except Exception:
            pass
        notice_layout.addWidget(notice_body)
        il.addWidget(notice_box)

    lst = QListWidget()
    lst.setObjectName("CardList")
    lst.setMinimumHeight(150)
    for name, status in items:
        item = QListWidgetItem(name)
        if status == "success":
            item.setForeground(Qt.darkGreen)
        elif status == "fail":
            item.setForeground(Qt.red)
        lst.addItem(item)

    il.addWidget(lst)
    v.addWidget(inner)

    footer = QFrame()
    footer.setObjectName("ModalFooter")
    fl = QHBoxLayout(footer)
    fl.setContentsMargins(16, 12, 16, 12)
    fl.setSpacing(8)
    fl.addStretch(1)
    btn_back = QPushButton("返回首页")
    btn_back.setObjectName("resultBackButton")
    btn_back.setProperty("role", "resultBack")
    btn_open = QPushButton("打开输出文件夹")
    btn_open.setObjectName("resultOpenButton")
    btn_open.setProperty("role", "resultOpen")
    fl.addWidget(btn_back)
    fl.addWidget(btn_open)

    v.addWidget(footer)

    overlay.layout().addWidget(card, 0, Qt.AlignCenter)
    return overlay


def build_blocking_alert(
    parent: QWidget | None = None,
    title_text: str = "请确认操作",
    body_text: str = "出现异常，是否跳过或重试？",
    primary_text: str = "重试",
    secondary_text: str = "跳过",
    tertiary_text: str | None = None,
    body_variant: str | None = None,
) -> QFrame:
    """阻断式警告模态框，占位 UI。"""
    overlay = _overlay(parent)

    card = QFrame()
    card.setObjectName("ModalCard")
    preferred = 560
    try:
        pw = int(parent.width() or 0) if parent is not None else 0
    except Exception:
        pw = 0
    if pw > 0:
        preferred = int(pw * 0.62)
    target_w = _resolve_modal_card_width(parent, preferred=preferred, min_width=220, max_width=720, safety_margin=24)
    card.setMinimumWidth(target_w)
    card.setMaximumWidth(target_w)
    v = QVBoxLayout(card)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)

    titlebar, _ = _build_modal_titlebar(title_text, close_object_name="ModalCloseButton")

    # 内部内容区域
    inner = QWidget()
    il = QVBoxLayout(inner)
    il.setContentsMargins(24, 16, 24, 16)
    il.setSpacing(12)

    msg_box = QFrame()
    msg_box.setObjectName("AlertMessageBox")
    msg_layout = QVBoxLayout(msg_box)
    msg_layout.setContentsMargins(14, 12, 14, 12)
    msg_layout.setSpacing(0)

    body = QTextBrowser()
    body.setObjectName("alertBody")
    rendered = body_text
    is_rich = False
    try:
        is_rich = bool(Qt.mightBeRichText(body_text))
    except Exception:
        is_rich = False
    if not is_rich:
        rendered = html.escape(str(body_text or "")).replace("\n", "<br/>")
    try:
        body.setOpenExternalLinks(True)
    except Exception:
        pass
    try:
        body.setHtml(rendered)
    except Exception:
        try:
            body.setPlainText(str(body_text or ""))
        except Exception:
            pass
    try:
        body.setReadOnly(True)
    except Exception:
        pass
    try:
        body.setFrameShape(QFrame.NoFrame)
    except Exception:
        pass
    try:
        body.setWordWrapMode(QTextOption.WrapAnywhere)
    except Exception:
        pass
    body.setProperty("role", "body")
    if body_variant:
        try:
            body.setProperty("variant", str(body_variant))
        except Exception:
            pass
    try:
        body.setMaximumHeight(260)
    except Exception:
        pass
    try:
        body.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    except Exception:
        pass
    try:
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    except Exception:
        pass

    msg_layout.addWidget(body)
    il.addWidget(msg_box)
    
    footer = QFrame()
    footer.setObjectName("ModalFooter")
    fl = QHBoxLayout(footer)
    fl.setContentsMargins(16, 12, 16, 12)
    fl.setSpacing(8)
    fl.addStretch(1)
    btn_tertiary = None
    if str(tertiary_text or "").strip():
        btn_tertiary = QPushButton(str(tertiary_text or "").strip())
        btn_tertiary.setObjectName("alertTertiary")
        btn_tertiary.setProperty("role", "alertTertiary")
        btn_tertiary.setProperty("class", "Ghost")
    btn_secondary = QPushButton(secondary_text)
    btn_secondary.setObjectName("alertSecondary")
    btn_secondary.setProperty("role", "alertSecondary")
    btn_primary = QPushButton(primary_text)
    btn_primary.setObjectName("alertPrimary")
    btn_primary.setProperty("role", "alertPrimary")
    btn_primary.setProperty("class", "Primary")
    btn_secondary.setProperty("class", "Ghost")
    if btn_tertiary is not None:
        fl.addWidget(btn_tertiary)
    fl.addWidget(btn_secondary)
    fl.addWidget(btn_primary)

    v.addWidget(titlebar)
    v.addWidget(inner, 1)
    v.addWidget(footer)

    overlay.layout().addWidget(card, 0, Qt.AlignCenter)
    return overlay
