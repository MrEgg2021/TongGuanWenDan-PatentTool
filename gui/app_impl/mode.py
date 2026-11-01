import html
import os

from PySide6.QtWidgets import QWidget
from gui.dialog_utils import show_blocking_alert_modal
from .layout_splitter_prefs import (
    restore_workflow_home_splitter_for_mode,
    restore_workflow_footer_splitter_for_mode,
)


def set_current_file_label(window, file_path: str | None) -> None:
    if not file_path:
        try:
            window._current_file_path = ""
        except Exception:
            pass
        try:
            window._current_file_display_text = ""
        except Exception:
            pass
        try:
            if hasattr(window, "current_file_label"):
                window.current_file_label.setText("")
        except Exception:
            pass
        return

    try:
        window._current_file_path = file_path
    except Exception:
        pass

    name = os.path.basename(file_path)

    patent_type_label = ""
    try:
        mode = getattr(window, "_processing_mode", "single")
        if mode == "single":
            last_patent_type = getattr(window, "_last_single_patent_type", None)
            if last_patent_type in ("invention", "utility_model"):
                if last_patent_type == "utility_model":
                    patent_type_label = "实用新型"
                else:
                    patent_type_label = "发明"
        else:
            ptype = None
            if hasattr(window, "_batch_file_types"):
                ptype = window._batch_file_types.get(file_path)
            if ptype == "utility_model":
                patent_type_label = "实用新型"
            elif ptype == "invention":
                patent_type_label = "发明"
    except Exception:
        patent_type_label = ""

    text = f"当前文件：{name}"
    if patent_type_label:
        text = f"{text}｜专利类型：{patent_type_label}"
    try:
        window._current_file_display_text = text
    except Exception:
        pass

    try:
        if hasattr(window, "current_file_label"):
            window.current_file_label.setText(text)
            try:
                window.current_file_label.setToolTip(name)
            except Exception:
                pass
    except Exception:
        pass


def on_mode_changed(window, mode: str | None = None):
    if mode in ("single", "batch"):
        try:
            window._processing_mode = str(mode)
        except Exception:
            window._processing_mode = "single"
    else:
        try:
            mode = str(getattr(window, "_processing_mode", "single") or "single")
        except Exception:
            mode = "single"
        if mode not in ("single", "batch"):
            mode = "single"
        try:
            window._processing_mode = str(mode)
        except Exception:
            window._processing_mode = "single"

    if window._processing_mode == "single":
        window.single_path_widget.setVisible(True)
        window.single_type_widget.setVisible(True)
        window.batch_widget.setVisible(False)
        window.btn_run.setText("开始转换")
    else:
        window.single_path_widget.setVisible(False)
        window.single_type_widget.setVisible(True)
        window.batch_widget.setVisible(True)
        window.btn_run.setText("开始批量转换")
    try:
        if hasattr(window, "single_auto_preview_frame"):
            window.single_auto_preview_frame.setVisible(window._processing_mode == "single")
    except Exception:
        pass
    try:
        if hasattr(window, "batch_options_frame"):
            window.batch_options_frame.setVisible(window._processing_mode == "batch")
    except Exception:
        pass

    try:
        if hasattr(window, "batch_confirm_frame"):
            window.batch_confirm_frame.setVisible(window._processing_mode == "batch")
    except Exception:
        pass

    try:
        if (
            hasattr(window, "output_dir_frame")
            and hasattr(window, "_single_path_layout")
            and hasattr(window, "_batch_case_output_layout")
            and hasattr(window, "_batch_output_anchor")
            and hasattr(window, "output_dir_layout")
        ):
            try:
                window._single_path_layout.removeWidget(window.output_dir_frame)
            except Exception:
                pass
            try:
                window._batch_case_output_layout.removeWidget(window.output_dir_frame)
            except Exception:
                pass

            if window._processing_mode == "batch":
                try:
                    # 先调整目录行内部顺序：按钮在前，输入框在后（更靠中线）
                    window.output_dir_layout.removeWidget(window.btn_browse_output_dir)
                    window.output_dir_layout.removeWidget(window.output_dir_edit)
                    window.output_dir_layout.addWidget(window.btn_browse_output_dir, 0)
                    window.output_dir_layout.addWidget(window.output_dir_edit, 1)
                    window.output_dir_layout.setStretch(0, 0)
                    window.output_dir_layout.setStretch(1, 1)
                except Exception:
                    pass

                idx = -1
                try:
                    idx = window._batch_case_output_layout.indexOf(window._batch_output_anchor)
                except Exception:
                    idx = -1
                if idx is None or idx < 0:
                    window._batch_case_output_layout.addWidget(window.output_dir_frame, 1)
                else:
                    window._batch_case_output_layout.insertWidget(idx, window.output_dir_frame, 1)

                try:
                    idx_zip = window._batch_case_output_layout.indexOf(window.batch_name_frame)
                    idx_dir = window._batch_case_output_layout.indexOf(window.output_dir_frame)
                    if idx_zip is not None and idx_zip >= 0:
                        window._batch_case_output_layout.setStretch(idx_zip, 1)
                    if idx_dir is not None and idx_dir >= 0:
                        window._batch_case_output_layout.setStretch(idx_dir, 1)
                except Exception:
                    pass
            else:
                try:
                    # 恢复单文档顺序：输入框在前，按钮在后
                    window.output_dir_layout.removeWidget(window.btn_browse_output_dir)
                    window.output_dir_layout.removeWidget(window.output_dir_edit)
                    window.output_dir_layout.addWidget(window.output_dir_edit, 1)
                    window.output_dir_layout.addWidget(window.btn_browse_output_dir, 0)
                    window.output_dir_layout.setStretch(0, 1)
                    window.output_dir_layout.setStretch(1, 0)
                except Exception:
                    pass

                window._single_path_layout.addWidget(window.output_dir_frame, 1)
    except Exception:
        pass

    try:
        if hasattr(window, "_card_layout") and hasattr(window, "single_type_widget"):
            layout = window._card_layout
            try:
                layout.removeWidget(window.single_type_widget)
            except Exception:
                pass

            if window._processing_mode == "batch":
                try:
                    layout.insertWidget(max(0, layout.count() - 1), window.single_type_widget)
                except Exception:
                    layout.addWidget(window.single_type_widget)
            else:
                idx = -1
                try:
                    idx = layout.indexOf(window.single_path_widget)
                except Exception:
                    idx = -1
                if idx is None or idx < 0:
                    layout.addWidget(window.single_type_widget)
                else:
                    layout.insertWidget(idx + 1, window.single_type_widget)
    except Exception:
        pass

    try:
        enabled_sections = get_enabled_sections_safe(window)
        request_form_enabled = enabled_sections.get("request_form", True)
        if hasattr(window, "batch_chk_confirm_req"):
            if window._processing_mode == "batch" and not request_form_enabled:
                window.batch_chk_confirm_req.setChecked(False)
                window.batch_chk_confirm_req.setEnabled(False)
            else:
                window.batch_chk_confirm_req.setEnabled(True)
    except Exception:
        pass

    try:
        mode = getattr(window, "_processing_mode", "single")
    except Exception:
        mode = "single"
    try:
        if hasattr(window, "chk_request_form") and window.chk_request_form is not None:
            window.chk_request_form.setToolTip(_format_tooltip_html(_request_form_skip_tip_text(mode), 420))
    except Exception:
        pass

    try:
        update_batch_file_list_height(window)
    except Exception:
        pass
    try:
        restore_workflow_home_splitter_for_mode(window)
    except Exception:
        pass
    try:
        restore_workflow_footer_splitter_for_mode(window)
    except Exception:
        pass


def update_batch_file_list_height(window) -> None:
    if getattr(window, "_processing_mode", "single") != "batch":
        try:
            if hasattr(window, "file_list_widget") and window.file_list_widget is not None:
                window.file_list_widget.setMaximumHeight(16777215)
                try:
                    window.file_list_widget.setMinimumHeight(120)
                except Exception:
                    pass
        except Exception:
            pass
        return

    if not hasattr(window, "file_list_widget") or window.file_list_widget is None:
        return

    # 当页面使用可拖拽 splitter 时，不要用固定 max-height 抵消用户拖拽结果。
    if getattr(window, "batch_main_splitter", None) is not None:
        try:
            window.file_list_widget.setMaximumHeight(16777215)
            window.file_list_widget.setMinimumHeight(70)
        except Exception:
            pass
        return

    try:
        h = int(window.height())
    except Exception:
        h = 0
    if h <= 0:
        return

    desired = int(h * 0.22)
    if desired < 100:
        desired = 100
    if desired > 240:
        desired = 240

    min_h = int(h * 0.10)
    if min_h < 70:
        min_h = 70
    if min_h > 110:
        min_h = 110
    if min_h > desired:
        min_h = desired

    window.file_list_widget.setMinimumHeight(min_h)
    window.file_list_widget.setMaximumHeight(desired)


def resize_event_safe(window, event):
    try:
        QWidget.resizeEvent(window, event)
    except Exception:
        try:
            super(window.__class__, window).resizeEvent(event)
        except Exception:
            pass
    try:
        update_batch_file_list_height(window)
    except Exception:
        pass


def get_enabled_sections_safe(window) -> dict:
    try:
        return {
            "claims": bool(window.chk_claims.isChecked()),
            "description": bool(window.chk_description.isChecked()),
            "drawings": bool(window.chk_drawings.isChecked()),
            "abstract": bool(window.chk_abstract.isChecked()),
            "request_form": bool(window.chk_request_form.isChecked()),
        }
    except Exception:
        return {
            "claims": True,
            "description": True,
            "drawings": True,
            "abstract": True,
            "request_form": True,
        }


def _request_form_skip_tip_text(mode: str = "single") -> str:
    if mode == "batch":
        return (
            "由于您未勾选请求书，因此生成的文件不能直接以“导入案卷”的方式导入客户端，"
            "需要解压后，将每个压缩包，在申请文件的编辑界面，通过“上传”的方式导入使用"
        )
    return (
        "由于您未勾选请求书，因此生成的文件不能直接以“导入案卷”的方式导入客户端，"
        "需要在申请文件的编辑界面，通过“上传”的方式导入使用"
    )


def _format_tooltip_html(text: str, max_width_px: int = 420) -> str:
    safe = html.escape(str(text or "")).replace("\n", "<br/>")
    try:
        w = int(max_width_px)
    except Exception:
        w = 420
    if w <= 0:
        w = 420
    return f'<div style="max-width: {w}px; white-space: normal;">{safe}</div>'


def show_request_form_skip_tip(window, mode: str = "single") -> None:
    enabled = True
    try:
        enabled = bool(getattr(window, "_req_form_skip_tip_enabled", True))
    except Exception:
        enabled = True
    if not enabled:
        return

    msg = _request_form_skip_tip_text(mode)
    show_blocking_alert_modal(window, "提示", msg, primary_text="关闭", secondary_text="关闭")


def on_request_form_toggled_safe(window, checked: bool) -> None:
    if checked:
        if getattr(window, "_processing_mode", "single") == "batch":
            try:
                if hasattr(window, "batch_chk_confirm_req"):
                    window.batch_chk_confirm_req.setEnabled(True)
            except Exception:
                pass
        return
    mode = getattr(window, "_processing_mode", "single")
    show_request_form_skip_tip(window, mode)
    if mode == "batch":
        try:
            if hasattr(window, "batch_chk_confirm_req"):
                window.batch_chk_confirm_req.setChecked(False)
                window.batch_chk_confirm_req.setEnabled(False)
        except Exception:
            pass
