from __future__ import annotations

import os
from typing import Callable, Literal

from PySide6.QtCore import Qt, QSignalBlocker, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.official_docs.models import ParsedNotice, PdfSource
from core.tgd_data_management_impl.pinyin_utils import get_pinyin_full, get_pinyin_initials


ConfirmResult = Literal["continue", "skip", "cancel"]
CollisionResult = tuple[Literal["overwrite", "skip", "rename"], bool]


def _safe_startfile(path: str) -> bool:
    try:
        if path and os.path.exists(path):
            os.startfile(path)
            return True
    except Exception:
        return False
    return False


def show_official_docs_confirm_dialog(
    parent: QWidget,
    *,
    parsed: ParsedNotice,
    summary_path_preview: str,
    archive_path_preview: str,
    on_open_pdf: Callable[[PdfSource], bool],
) -> ConfirmResult:
    dialog = QDialog(parent)
    dialog.setWindowTitle("逐个确认 - 官文处理")
    dialog.setModal(True)
    try:
        dialog.resize(780, 560)
    except Exception:
        pass

    root = QVBoxLayout(dialog)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(10)

    title = QLabel("请核对本条通知书解析信息")
    title.setProperty("role", "h2")
    root.addWidget(title)

    meta = parsed.meta
    lines = [
        f"来源ZIP：{parsed.source_zip_path}",
        f"申请号：{meta.app_no}",
        f"通知书名称：{meta.notice_name}",
        f"通知书代码：{meta.notice_code}",
        f"发文日：{meta.issue_date or meta.issue_date_raw}",
        f"内部编号：{meta.internal_no}",
        f"逾期日：{meta.due_date}",
        f"期限天：{meta.limit_days}",
    ]
    if parsed.errors:
        lines.append(f"错误：{'; '.join(parsed.errors)}")
    text = "\n".join([line for line in lines if str(line or "").strip()])

    meta_box = QFrame()
    meta_box.setObjectName("Card")
    meta_layout = QVBoxLayout(meta_box)
    meta_layout.setContentsMargins(12, 10, 12, 10)
    meta_layout.setSpacing(6)
    meta_label = QLabel(text)
    meta_label.setProperty("role", "caption")
    meta_label.setWordWrap(True)
    meta_layout.addWidget(meta_label)
    root.addWidget(meta_box)

    pdf_box = QFrame()
    pdf_box.setObjectName("Card")
    pdf_layout = QVBoxLayout(pdf_box)
    pdf_layout.setContentsMargins(12, 10, 12, 10)
    pdf_layout.setSpacing(8)
    pdf_title = QLabel("PDF 列表（按需打开）")
    pdf_title.setProperty("role", "label")
    pdf_layout.addWidget(pdf_title)

    pdf_list = QListWidget()
    for source in parsed.pdf_entries or []:
        item = QListWidgetItem(f"{source.kind}: {source.display_name}")
        item.setData(Qt.UserRole, source)
        pdf_list.addItem(item)
    pdf_layout.addWidget(pdf_list, 1)

    open_row = QHBoxLayout()
    open_row.setContentsMargins(0, 0, 0, 0)
    open_row.setSpacing(8)
    btn_open = QPushButton("打开选中PDF")
    btn_open.setObjectName("Secondary")
    open_status = QLabel("")
    open_status.setProperty("role", "caption")
    open_status.setWordWrap(True)
    open_row.addWidget(btn_open, 0)
    open_row.addWidget(open_status, 1)
    pdf_layout.addLayout(open_row)

    def _open_selected() -> None:
        item = pdf_list.currentItem()
        if item is None:
            open_status.setText("请先选择一个 PDF")
            return
        source = item.data(Qt.UserRole)
        if not isinstance(source, PdfSource):
            open_status.setText("PDF 数据无效")
            return
        ok = False
        try:
            ok = bool(on_open_pdf(source))
        except Exception:
            ok = False
        open_status.setText("已打开" if ok else "打开失败，请检查系统默认 PDF 阅读器")

    btn_open.clicked.connect(_open_selected)
    pdf_list.itemDoubleClicked.connect(lambda _=None: _open_selected())
    root.addWidget(pdf_box, 1)

    output_box = QFrame()
    output_box.setObjectName("Card")
    output_layout = QVBoxLayout(output_box)
    output_layout.setContentsMargins(12, 10, 12, 10)
    output_layout.setSpacing(6)
    output_label = QLabel(
        f"拟输出（汇总）：{summary_path_preview or '(未启用)'}\n拟输出（归档）：{archive_path_preview or '(未启用)'}"
    )
    output_label.setProperty("role", "caption")
    output_label.setWordWrap(True)
    output_layout.addWidget(output_label)
    root.addWidget(output_box)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    btn_continue = QPushButton("继续")
    btn_continue.setObjectName("Primary")
    btn_skip = QPushButton("跳过")
    btn_skip.setObjectName("Secondary")
    btn_cancel = QPushButton("取消本次任务")
    btn_cancel.setObjectName("Secondary")
    button_row.addWidget(btn_continue)
    button_row.addWidget(btn_skip)
    button_row.addWidget(btn_cancel)
    root.addLayout(button_row)

    result: list[ConfirmResult] = ["cancel"]

    def _set(value: ConfirmResult) -> None:
        result[0] = value
        dialog.accept()

    btn_continue.clicked.connect(lambda: _set("continue"))
    btn_skip.clicked.connect(lambda: _set("skip"))
    btn_cancel.clicked.connect(lambda: _set("cancel"))

    dialog.exec()
    return result[0]


def show_official_docs_collision_dialog(
    parent: QWidget,
    *,
    summary_path: str,
    archive_path: str,
) -> CollisionResult:
    dialog = QDialog(parent)
    dialog.setWindowTitle("同名冲突 - 官文处理")
    dialog.setModal(True)
    try:
        dialog.resize(720, 320)
    except Exception:
        pass

    root = QVBoxLayout(dialog)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(10)

    title = QLabel("检测到目标文件已存在，请选择处理方式")
    title.setProperty("role", "h2")
    root.addWidget(title)

    text = QLabel(
        f"汇总路径：{summary_path or '(未启用)'}\n归档路径：{archive_path or '(未启用)'}"
    )
    text.setProperty("role", "caption")
    text.setWordWrap(True)
    root.addWidget(text)

    apply_all = QCheckBox("应用到本次全部冲突")
    apply_all.setProperty("class", "OfficialDocsCheck")
    root.addWidget(apply_all)

    row = QHBoxLayout()
    row.addStretch(1)
    btn_overwrite = QPushButton("覆盖")
    btn_overwrite.setObjectName("Primary")
    btn_skip = QPushButton("跳过")
    btn_skip.setObjectName("Secondary")
    btn_rename = QPushButton("自动改名")
    btn_rename.setObjectName("Secondary")
    row.addWidget(btn_overwrite)
    row.addWidget(btn_skip)
    row.addWidget(btn_rename)
    root.addLayout(row)

    result: list[CollisionResult] = [("skip", False)]

    def _set(policy: Literal["overwrite", "skip", "rename"]) -> None:
        result[0] = (policy, bool(apply_all.isChecked()))
        dialog.accept()

    btn_overwrite.clicked.connect(lambda: _set("overwrite"))
    btn_skip.clicked.connect(lambda: _set("skip"))
    btn_rename.clicked.connect(lambda: _set("rename"))

    dialog.exec()
    return result[0]


def show_official_docs_archive_consent_dialog(parent: QWidget, *, doc_version: int) -> bool:
    dialog = QDialog(parent)
    dialog.setWindowTitle("长期归档使用说明")
    dialog.setModal(True)
    try:
        dialog.resize(760, 560)
    except Exception:
        pass

    root = QVBoxLayout(dialog)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(10)

    title = QLabel("启用长期归档前，请完整阅读并同意以下说明")
    title.setProperty("role", "h2")
    root.addWidget(title)

    version_label = QLabel(f"当前协议版本：V{int(doc_version)}")
    version_label.setProperty("role", "caption")
    root.addWidget(version_label)

    content = QFrame()
    content.setObjectName("Card")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(12, 10, 12, 10)
    content_layout.setSpacing(8)

    viewer = QPlainTextEdit()
    viewer.setReadOnly(True)
    viewer.setPlainText(
        "\n".join(
            [
                "1. 长期归档会把本次处理成功的通知书PDF复制到归档目录。",
                "2. 长期归档目录固定为：<归档根目录>/<申请号>/。",
                "3. 申请号目录会长期累积历史文件，请务必确认归档根目录正确。",
                "4. 如目录权限不足、路径异常或冲突处理选择跳过，可能导致部分文件未归档。",
                "5. 本次任务仅归档处理成功的条目；失败/跳过条目不会写入长期归档。",
                "6. 你可以随时取消“输出长期归档”，取消后仅保留单次处理汇总输出。",
            ]
        )
    )
    content_layout.addWidget(viewer, 1)
    root.addWidget(content, 1)

    hint = QLabel("请先滚动到文末后再勾选同意")
    hint.setProperty("role", "caption")
    root.addWidget(hint)

    agree_chk = QCheckBox("我已完整阅读并同意启用“长期归档”")
    agree_chk.setProperty("class", "OfficialDocsCheck")
    agree_chk.setEnabled(False)
    root.addWidget(agree_chk)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    btn_cancel = QPushButton("取消")
    btn_cancel.setObjectName("Secondary")
    btn_ok = QPushButton("同意并启用")
    btn_ok.setObjectName("Primary")
    btn_ok.setEnabled(False)
    button_row.addWidget(btn_cancel)
    button_row.addWidget(btn_ok)
    root.addLayout(button_row)

    bar = viewer.verticalScrollBar()

    def _refresh_scroll_gate() -> None:
        if bar is None:
            agree_chk.setEnabled(True)
            hint.setText("")
            return
        maximum = int(bar.maximum())
        if maximum <= 0:
            agree_chk.setEnabled(True)
            hint.setText("")
            return
        if int(bar.value()) >= maximum:
            agree_chk.setEnabled(True)
            hint.setText("")
            return
        agree_chk.setEnabled(False)
        hint.setText("请先滚动到文末后再勾选同意")

    try:
        bar.valueChanged.connect(lambda _=None: _refresh_scroll_gate())
    except Exception:
        pass
    try:
        bar.rangeChanged.connect(lambda _min, _max: _refresh_scroll_gate())
    except Exception:
        pass
    try:
        QTimer.singleShot(0, _refresh_scroll_gate)
    except Exception:
        _refresh_scroll_gate()

    try:
        agree_chk.toggled.connect(lambda checked: btn_ok.setEnabled(bool(checked)))
    except Exception:
        pass

    accepted: list[bool] = [False]

    def _accept() -> None:
        accepted[0] = True
        dialog.accept()

    btn_ok.clicked.connect(_accept)
    btn_cancel.clicked.connect(dialog.reject)
    dialog.exec()
    return bool(accepted[0])


def show_official_docs_pdf_parse_enable_notice_dialog(parent: QWidget) -> tuple[bool, bool]:
    dialog = QDialog(parent)
    dialog.setWindowTitle("PDF解析提醒")
    dialog.setModal(True)
    try:
        dialog.resize(620, 300)
    except Exception:
        pass

    root = QVBoxLayout(dialog)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(10)

    title = QLabel("已启用“解析PDF文件内容”")
    title.setProperty("role", "h2")
    root.addWidget(title)

    card = QFrame()
    card.setObjectName("Card")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(12, 10, 12, 10)
    card_layout.setSpacing(6)
    msg = QLabel("该功能会明显增加处理时间，且提取结果可能存在误差。处理完成后请人工检查核对。")
    msg.setProperty("role", "caption")
    msg.setWordWrap(True)
    card_layout.addWidget(msg)
    root.addWidget(card)

    suppress_chk = QCheckBox("不再提示")
    suppress_chk.setProperty("class", "OfficialDocsCheck")
    root.addWidget(suppress_chk)

    row = QHBoxLayout()
    row.addStretch(1)
    btn_cancel = QPushButton("取消勾选")
    btn_cancel.setObjectName("Secondary")
    btn_ok = QPushButton("继续启用")
    btn_ok.setObjectName("Primary")
    row.addWidget(btn_cancel)
    row.addWidget(btn_ok)
    root.addLayout(row)

    result = {"enabled": False}
    btn_cancel.clicked.connect(dialog.reject)

    def _accept() -> None:
        result["enabled"] = True
        dialog.accept()

    btn_ok.clicked.connect(_accept)
    dialog.exec()
    return bool(result.get("enabled", False)), bool(suppress_chk.isChecked())


def show_official_docs_done_dialog(
    parent: QWidget,
    *,
    total: int,
    success: int,
    skipped: int,
    failed: int,
    items: list[dict[str, str]] | list[tuple[str, str]] | None = None,
    open_dirs: list[str] | None = None,
    excel_path: str = "",
    run_dir: str = "",
) -> None:
    def _normalize_rows(raw_items: list[dict[str, str]] | list[tuple[str, str]] | None) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for raw in list(raw_items or []):
            if isinstance(raw, dict):
                normalized.append(
                    {
                        "display_name": str(raw.get("display_name", "") or "").strip(),
                        "status": str(raw.get("status", "") or "").strip().lower(),
                        "source_zip_path": str(raw.get("source_zip_path", "") or "").strip(),
                        "summary_pdf_path": str(raw.get("summary_pdf_path", "") or "").strip(),
                        "archive_pdf_path": str(raw.get("archive_pdf_path", "") or "").strip(),
                        "output_pdf_name": str(raw.get("output_pdf_name", "") or "").strip(),
                    }
                )
                continue
            if isinstance(raw, tuple) and len(raw) >= 2:
                normalized.append(
                    {
                        "display_name": str(raw[0] or "").strip(),
                        "status": str(raw[1] or "").strip().lower(),
                        "source_zip_path": "",
                        "summary_pdf_path": "",
                        "archive_pdf_path": "",
                        "output_pdf_name": "",
                    }
                )
        return normalized

    def _status_label(status_key: str) -> str:
        mapping = {"success": "成功", "skip": "跳过", "fail": "失败"}
        return mapping.get(str(status_key or "").strip().lower(), str(status_key or "").strip() or "未知")

    def _status_color(status_key: str):
        key = str(status_key or "").strip().lower()
        if key == "success":
            return Qt.darkGreen
        if key == "fail":
            return Qt.red
        return Qt.darkYellow

    def _open_selected_file_payload(payload: dict[str, str]) -> bool:
        targets = [
            str(payload.get("summary_pdf_path", "") or "").strip(),
            str(payload.get("archive_pdf_path", "") or "").strip(),
            str(payload.get("source_zip_path", "") or "").strip(),
        ]
        for target in targets:
            if target and _safe_startfile(target):
                return True
        return False

    result_items = _normalize_rows(items)
    dirs = [str(path or "").strip() for path in (open_dirs or []) if str(path or "").strip()]
    primary_run_dir = str(run_dir or "").strip() or (dirs[0] if dirs else "")

    dialog = QDialog(parent)
    dialog.setWindowTitle("官文处理完成")
    dialog.setModal(True)
    dialog.setSizeGripEnabled(True)
    try:
        dialog.resize(900, 640)
        dialog.setMinimumSize(760, 520)
    except Exception:
        pass

    root = QVBoxLayout(dialog)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(8)

    title = QLabel("处理完成")
    title.setProperty("role", "h2")
    root.addWidget(title)

    stats_row = QHBoxLayout()
    stats_row.setContentsMargins(0, 0, 0, 0)
    stats_row.setSpacing(6)
    status_group = QButtonGroup(dialog)
    status_group.setExclusive(True)
    status_buttons: dict[str, QPushButton] = {}
    for key, label, count in (
        ("all", "总数", total),
        ("success", "成功", success),
        ("skip", "跳过", skipped),
        ("fail", "失败", failed),
    ):
        button = QPushButton(f"{label}: {count}")
        button.setObjectName("Secondary")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        status_group.addButton(button)
        status_buttons[key] = button
        stats_row.addWidget(button, 0)
    stats_row.addStretch(1)
    root.addLayout(stats_row)

    list_box = QFrame()
    list_box.setObjectName("Card")
    list_layout = QVBoxLayout(list_box)
    list_layout.setContentsMargins(12, 10, 12, 10)
    list_layout.setSpacing(6)
    list_header = QHBoxLayout()
    list_header.setContentsMargins(0, 0, 0, 0)
    list_header.setSpacing(6)
    list_title = QLabel("任务结果")
    list_title.setProperty("role", "label")
    list_header.addWidget(list_title, 0)
    list_header.addStretch(1)
    btn_open_run_dir = QPushButton("打开处理目录")
    btn_open_run_dir.setObjectName("Secondary")
    btn_open_selected = QPushButton("打开选中文件")
    btn_open_selected.setObjectName("Secondary")
    list_header.addWidget(btn_open_run_dir, 0)
    list_header.addWidget(btn_open_selected, 0)
    list_layout.addLayout(list_header)

    search_edit = QLineEdit()
    search_edit.setPlaceholderText("搜索（名称/路径/状态/拼音）")
    list_layout.addWidget(search_edit)

    result_table = QTableWidget(0, 2)
    result_table.setObjectName("officialDocsResultTable")
    result_table.setHorizontalHeaderLabels(["源ZIP路径", "处理后PDF文件名"])
    result_table.setSelectionMode(QAbstractItemView.SingleSelection)
    result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
    result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    result_table.setWordWrap(True)
    result_table.setTextElideMode(Qt.ElideNone)
    result_table.verticalHeader().setVisible(False)
    result_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    result_table.horizontalHeader().setStretchLastSection(True)
    result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    list_layout.addWidget(result_table, 1)
    root.addWidget(list_box, 1)

    if excel_path:
        excel_label = QLabel(f"Excel：{excel_path}")
        excel_label.setProperty("role", "caption")
        excel_label.setWordWrap(True)
        root.addWidget(excel_label)

    buttons = QHBoxLayout()
    buttons.addStretch(1)
    if excel_path:
        btn_open_excel = QPushButton("打开Excel")
        btn_open_excel.setObjectName("Secondary")
        btn_open_excel.clicked.connect(lambda: _safe_startfile(excel_path))
        buttons.addWidget(btn_open_excel)
    btn_close = QPushButton("关闭")
    btn_close.setObjectName("Primary")
    btn_close.clicked.connect(dialog.accept)
    buttons.addWidget(btn_close)
    root.addLayout(buttons)

    filter_state = {"status": "all", "query": ""}

    def _row_matches(payload: dict[str, str]) -> bool:
        status_filter = str(filter_state.get("status", "all") or "all")
        if status_filter != "all" and str(payload.get("status", "") or "").strip().lower() != status_filter:
            return False
        query = str(filter_state.get("query", "") or "").strip().lower()
        if not query:
            return True
        source_zip = str(payload.get("source_zip_path", "") or "").strip()
        output_name = str(payload.get("output_pdf_name", "") or "").strip()
        status_text = _status_label(str(payload.get("status", "") or ""))
        targets = [
            source_zip,
            output_name,
            status_text,
            get_pinyin_full(source_zip),
            get_pinyin_initials(source_zip),
            get_pinyin_full(output_name),
            get_pinyin_initials(output_name),
        ]
        lowered = [str(item or "").strip().lower() for item in targets if str(item or "").strip()]
        return any(query in item for item in lowered)

    def _refresh_result_list() -> None:
        current_payload = None
        current_row = int(result_table.currentRow())
        if current_row >= 0:
            item = result_table.item(current_row, 0)
            if item is not None:
                current_payload = item.data(Qt.UserRole)
        with QSignalBlocker(result_table):
            result_table.setRowCount(0)
            selected_row = 0
            row = 0
            for payload in result_items:
                if not _row_matches(payload):
                    continue
                status_key = str(payload.get("status", "") or "").strip().lower()
                source_zip = str(payload.get("source_zip_path", "") or "").strip()
                output_pdf_name = str(payload.get("output_pdf_name", "") or "").strip()

                result_table.insertRow(row)

                source_item = QTableWidgetItem(source_zip)
                source_item.setData(Qt.UserRole, payload)
                source_item.setToolTip(source_zip)
                source_item.setForeground(_status_color(status_key))

                output_item = QTableWidgetItem(output_pdf_name)
                output_item.setData(Qt.UserRole, payload)
                output_item.setToolTip(output_pdf_name)
                output_item.setForeground(_status_color(status_key))

                result_table.setItem(row, 0, source_item)
                result_table.setItem(row, 1, output_item)

                if current_payload and isinstance(current_payload, dict) and current_payload == payload:
                    selected_row = row
                row += 1

            if result_table.rowCount() > 0:
                result_table.selectRow(min(selected_row, result_table.rowCount() - 1))
            result_table.resizeRowsToContents()

    def _set_filter(status_key: str) -> None:
        filter_state["status"] = status_key
        _refresh_result_list()

    for key, button in status_buttons.items():
        button.clicked.connect(lambda _=None, status_key=key: _set_filter(status_key))
    status_buttons["all"].setChecked(True)

    def _on_search_changed(text: str) -> None:
        filter_state["query"] = str(text or "")
        _refresh_result_list()

    search_edit.textChanged.connect(_on_search_changed)

    def _open_run_dir() -> None:
        target = str(primary_run_dir or "").strip()
        if target and _safe_startfile(target):
            return
        for directory in dirs:
            if _safe_startfile(directory):
                return

    def _open_selected_file() -> None:
        selected_row = int(result_table.currentRow())
        if selected_row < 0:
            try:
                search_edit.setFocus()
            except Exception:
                pass
            return
        selected = result_table.item(selected_row, 0)
        if selected is None:
            return
        payload = selected.data(Qt.UserRole)
        if not isinstance(payload, dict):
            return
        _open_selected_file_payload(payload)

    btn_open_run_dir.clicked.connect(_open_run_dir)
    btn_open_selected.clicked.connect(_open_selected_file)
    result_table.itemDoubleClicked.connect(lambda _=None: _open_selected_file())

    _refresh_result_list()
    dialog.exec()


__all__ = [
    "CollisionResult",
    "ConfirmResult",
    "show_official_docs_archive_consent_dialog",
    "show_official_docs_collision_dialog",
    "show_official_docs_confirm_dialog",
    "show_official_docs_done_dialog",
    "show_official_docs_pdf_parse_enable_notice_dialog",
]
