from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QProgressBar

from gui.app_impl import progress_callback_safe, resize_event_safe, set_current_file_label, update_progress_safe
from gui.dialog_utils import resolve_modal_owner
from gui.patent_type_dialogs import format_processing_patent_type_text
from gui.section_resolution import needs_patent_type
from gui.ui_modals import build_processing_modal, build_result_sheet_modal
from gui.windowing import overlay_controller as overlay_controller_api

_PROCESSING_OVERLAY_NAME = "main_processing_overlay"
_RESULT_OVERLAY_NAME = "main_result_overlay"


class ProgressMixin:
    def _resolve_processing_enabled_sections(self) -> dict | None:
        try:
            scope = getattr(self, "_progress_scope", None)
        except Exception:
            scope = None

        if scope == "single":
            try:
                enabled_sections = getattr(self, "_last_single_effective_enabled_sections", None)
            except Exception:
                enabled_sections = None
            if isinstance(enabled_sections, dict):
                return enabled_sections
            try:
                return getattr(self, "_last_single_enabled_sections", None)
            except Exception:
                return None

        if scope == "batch":
            try:
                current_file = str(getattr(self, "_current_file_path", "") or "")
            except Exception:
                current_file = ""
            try:
                effective_map = getattr(self, "_batch_effective_enabled_sections_map", None)
            except Exception:
                effective_map = None
            if isinstance(effective_map, dict) and current_file:
                enabled_sections = effective_map.get(current_file)
                if isinstance(enabled_sections, dict):
                    return enabled_sections
            try:
                return getattr(self, "_last_batch_enabled_sections", None)
            except Exception:
                return None

        return None

    def _should_show_processing_patent_type(self) -> bool:
        enabled_sections = self._resolve_processing_enabled_sections()
        if not isinstance(enabled_sections, dict):
            return True
        return needs_patent_type(enabled_sections)

    def _resolve_current_processing_patent_type(self) -> str | None:
        try:
            scope = getattr(self, "_progress_scope", None)
        except Exception:
            scope = None

        if scope == "single":
            try:
                return getattr(self, "_last_single_patent_type", None)
            except Exception:
                return None

        if scope == "batch":
            try:
                current_file = str(getattr(self, "_current_file_path", "") or "")
            except Exception:
                current_file = ""
            try:
                batch_types = getattr(self, "_batch_file_types", None)
            except Exception:
                batch_types = None
            if isinstance(batch_types, dict) and current_file:
                return batch_types.get(current_file)
        return None

    def _refresh_processing_config_box(self, overlay) -> None:
        if overlay is None:
            return

        lb_opt = overlay.findChild(QLabel, "processingCfgOptCenter")
        lb_tbl = overlay.findChild(QLabel, "processingCfgTableCenter")
        lb_ratio = overlay.findChild(QLabel, "processingCfgScaleRatio")
        lb_desc = overlay.findChild(QLabel, "processingCfgDescMode")
        lb_patent_type = overlay.findChild(QLabel, "processingCfgPatentType")

        try:
            opt_center = bool(self.get_optimize_equation_centering_enabled()) if hasattr(self, "get_optimize_equation_centering_enabled") else False
        except Exception:
            opt_center = False
        try:
            opt_table = bool(getattr(self, "_opt_table_img_center_enabled", True))
        except Exception:
            opt_table = True
        try:
            ratio_val = float(getattr(self, "_img_scale_ratio_override", 1.0))
        except Exception:
            ratio_val = 1.0
        try:
            ratio_val = max(0.4, min(1.0, float(ratio_val)))
        except Exception:
            ratio_val = 1.0
        try:
            desc_mode = str(self.get_description_paragraph_split_mode() or "word") if hasattr(self, "get_description_paragraph_split_mode") else "word"
        except Exception:
            desc_mode = "word"
        desc_mode = desc_mode.strip().lower()
        if desc_mode == "period":
            desc_text = "按句号"
        elif desc_mode == "word_period_end":
            desc_text = "匹配官方"
        else:
            desc_text = "按 Word 段落"

        def _onoff(value: bool) -> str:
            return "开启" if bool(value) else "关闭"

        if lb_opt:
            lb_opt.setText(f"公式居中：{_onoff(opt_center)}")
        if lb_tbl:
            lb_tbl.setText(f"表格居中：{_onoff(opt_table)}")
        if lb_ratio:
            lb_ratio.setText(f"缩放：{ratio_val:.2f}")
        if lb_desc:
            lb_desc.setText(f"段号分配：{desc_text}")
        if lb_patent_type:
            if self._should_show_processing_patent_type():
                lb_patent_type.setText(format_processing_patent_type_text(self._resolve_current_processing_patent_type()))
                lb_patent_type.setVisible(True)
            else:
                lb_patent_type.clear()
                lb_patent_type.setVisible(False)

    def _reset_cancel_state(self) -> None:
        try:
            self._cancel_requested = False
        except Exception:
            pass

    def update_progress(
        self,
        percent: int,
        primary_text: str | None = None,
        detail_text: str | None = None,
        batch_info: str | None = None,
    ):
        update_progress_safe(self, percent, primary_text, detail_text, batch_info)

    def _show_processing_overlay(self, status_text: str = "", file_text: str = "") -> None:
        try:
            if self._processing_overlay:
                try:
                    overlay_controller_api.set_modal_active(False)
                except Exception:
                    pass
                try:
                    overlay_controller_api.detach(_PROCESSING_OVERLAY_NAME)
                except Exception:
                    pass
                self._processing_overlay.setParent(None)
                self._processing_overlay.deleteLater()
        except Exception:
            pass

        try:
            owner = resolve_modal_owner(self)
            overlay = build_processing_modal(owner, status_text=status_text or "正在处理...", filename_text=file_text or "")
            overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)

            try:
                is_conversion = bool(getattr(self, "_progress_scope", None) in ("single", "batch"))
            except Exception:
                is_conversion = False
            try:
                is_preview = bool(getattr(self, "_progress_scope", None) == "preview")
            except Exception:
                is_preview = False

            if is_conversion:
                try:
                    warn_label = overlay.findChild(QLabel, "processingWarnLabel")
                    if warn_label:
                        warn_label.setText("正在转换文档，请暂时停止其他鼠标、键盘操作；转换期间会使用 Word 和剪贴板。")
                except Exception:
                    pass
                try:
                    cfg_frame = overlay.findChild(QFrame, "processingConfigBox")
                    if cfg_frame is not None:
                        cfg_frame.setVisible(True)
                    self._refresh_processing_config_box(overlay)
                except Exception:
                    pass
            else:
                try:
                    cfg_frame = overlay.findChild(QFrame, "processingConfigBox")
                    if cfg_frame is not None:
                        cfg_frame.setVisible(False)
                except Exception:
                    pass

            if is_preview:
                try:
                    warn_label = overlay.findChild(QLabel, "processingWarnLabel")
                    if warn_label:
                        warning_box = warn_label.parentWidget()
                        is_full_preview_render = getattr(self, "_preview_overlay_kind", "") == "full"
                        if is_full_preview_render:
                            warn_label.setText("正在生成文书 PDF，具体进度见上方；可取消本次任务。")
                        else:
                            warn_label.clear()
                        if warning_box is not None:
                            warning_box.setVisible(is_full_preview_render)
                except Exception:
                    pass
                try:
                    header_box = overlay.findChild(QFrame, "processingHeaderBox")
                    if header_box is not None:
                        header_box.setVisible(False)
                except Exception:
                    pass

            try:
                btn_cancel = overlay.findChild(QPushButton, "processingCancelButton")
                if btn_cancel:
                    if getattr(self, "_progress_scope", None) == "response_correction":
                        btn_cancel.setVisible(False)
                    else:
                        btn_cancel.clicked.connect(self._on_processing_cancel)
            except Exception:
                pass

            overlay.show()
            overlay.raise_()
            self._processing_overlay = overlay
            try:
                overlay_controller_api.attach(_PROCESSING_OVERLAY_NAME, overlay, owner)
                overlay_controller_api.set_modal_active(True)
            except Exception:
                pass
        except Exception:
            self._processing_overlay = None

    def _on_processing_cancel(self) -> None:
        try:
            self._cancel_requested = True
        except Exception:
            pass
        try:
            preview_worker = getattr(self, "_preview_render_worker", None)
            if preview_worker is not None:
                preview_worker.request_cancel()
        except Exception:
            pass
        try:
            self._update_processing_overlay(0, "正在取消...", "请稍候，正在尝试停止当前任务...", None)
        except Exception:
            pass

    def _update_processing_overlay(
        self,
        percent: int,
        primary_text: str | None = None,
        detail_text: str | None = None,
        batch_info: str | None = None,
    ) -> None:
        overlay = getattr(self, "_processing_overlay", None)
        if not overlay:
            return

        try:
            status_label = overlay.findChild(QLabel, "processingStatus")
            file_label = overlay.findChild(QLabel, "processingFile")
            bar = overlay.findChild(QProgressBar, "processingBar")
            header_box = overlay.findChild(QFrame, "processingHeaderBox")
            header_stage = overlay.findChild(QLabel, "processingHeaderStage")
            header_summary = overlay.findChild(QLabel, "processingHeaderSummary")

            if status_label:
                text = primary_text or status_label.text() or "正在处理..."
                if batch_info:
                    text = batch_info
                status_label.setText(text)
            if file_label:
                file_text = detail_text or file_label.text() or ""
                try:
                    if not detail_text and hasattr(self, "current_file_label"):
                        file_text = self.current_file_label.text()
                except Exception:
                    pass
                file_label.setText(file_text)
            if bar:
                try:
                    bar.setValue(int(percent))
                except Exception:
                    pass

            try:
                is_conversion = bool(getattr(self, "_progress_scope", None) in ("single", "batch"))
            except Exception:
                is_conversion = False

            try:
                stage_text = str(getattr(self, "_header_precheck_stage", "") or "").strip()
            except Exception:
                stage_text = ""
            try:
                summary_text = str(getattr(self, "_header_precheck_summary", "") or "").strip()
            except Exception:
                summary_text = ""
            if not is_conversion:
                stage_text = ""
                summary_text = ""

            if header_box is not None:
                try:
                    header_box.setVisible(bool(stage_text or summary_text))
                except Exception:
                    pass
            if header_stage is not None:
                try:
                    header_stage.setText(stage_text)
                except Exception:
                    pass
            if header_summary is not None:
                try:
                    header_summary.setText(summary_text)
                except Exception:
                    pass

            self._refresh_processing_config_box(overlay)
        except Exception:
            pass

    def _hide_processing_overlay(self) -> None:
        had_overlay = bool(getattr(self, "_processing_overlay", None))
        try:
            if self._processing_overlay:
                self._processing_overlay.setParent(None)
                self._processing_overlay.deleteLater()
        except Exception:
            pass
        self._processing_overlay = None
        if had_overlay:
            try:
                overlay_controller_api.set_modal_active(False)
            except Exception:
                pass
            try:
                overlay_controller_api.detach(_PROCESSING_OVERLAY_NAME)
            except Exception:
                pass

    def _show_result_overlay(
        self,
        items: list[tuple[str, str]],
        total: int,
        success: int,
        failed: int,
        notice_text: str | None = None,
    ) -> None:
        try:
            self._hide_processing_overlay()
        except Exception:
            pass
        try:
            if self._result_overlay:
                try:
                    overlay_controller_api.set_modal_active(False)
                except Exception:
                    pass
                try:
                    overlay_controller_api.detach(_RESULT_OVERLAY_NAME)
                except Exception:
                    pass
                self._result_overlay.setParent(None)
                self._result_overlay.deleteLater()
        except Exception:
            pass

        try:
            owner = resolve_modal_owner(self)
            overlay = build_result_sheet_modal(
                owner,
                total=total,
                success=success,
                failed=failed,
                items=items,
                notice_text=notice_text,
            )
            overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            btn_back = overlay.findChild(QPushButton, "resultBackButton")
            btn_open = overlay.findChild(QPushButton, "resultOpenButton")
            btn_x = overlay.findChild(QPushButton, "ModalCloseButton")
            if btn_back:
                btn_back.clicked.connect(self._on_result_back)
            if btn_open:
                btn_open.clicked.connect(self._on_result_open_output)
            if btn_x:
                btn_x.clicked.connect(self._hide_result_overlay)
            overlay.show()
            overlay.raise_()
            self._result_overlay = overlay
            try:
                overlay_controller_api.attach(_RESULT_OVERLAY_NAME, overlay, owner)
                overlay_controller_api.set_modal_active(True)
            except Exception:
                pass
        except Exception:
            self._result_overlay = None

    def _hide_result_overlay(self) -> None:
        had_overlay = bool(getattr(self, "_result_overlay", None))
        try:
            if self._result_overlay:
                self._result_overlay.setParent(None)
                self._result_overlay.deleteLater()
        except Exception:
            pass
        self._result_overlay = None
        if had_overlay:
            try:
                overlay_controller_api.set_modal_active(False)
            except Exception:
                pass
            try:
                overlay_controller_api.detach(_RESULT_OVERLAY_NAME)
            except Exception:
                pass

    def _on_result_back(self) -> None:
        self._hide_result_overlay()

    def _on_result_open_output(self) -> None:
        try:
            target_dir = ""
            try:
                last_batch = getattr(self, "_last_batch_saved_path", "") or ""
                if last_batch:
                    target_dir = os.path.dirname(os.path.abspath(last_batch))
            except Exception:
                target_dir = ""
            if not target_dir:
                try:
                    last_single = getattr(self, "_last_single_saved_zip_path", "") or ""
                    if last_single:
                        target_dir = os.path.dirname(os.path.abspath(last_single))
                except Exception:
                    target_dir = ""
            if not target_dir:
                try:
                    output_dir = self.output_dir_edit.text().strip()
                except Exception:
                    output_dir = ""
                if output_dir:
                    target_dir = os.path.abspath(output_dir)

            if target_dir and os.path.isdir(target_dir):
                os.startfile(target_dir)
            else:
                self.on_open_output()
        except Exception:
            try:
                self.on_open_output()
            except Exception:
                pass
        self._hide_result_overlay()

    def _set_current_file_label(self, file_path: str | None):
        set_current_file_label(self, file_path)

    def _progress_callback(self, stage: str, payload: dict):
        progress_callback_safe(self, stage, payload)

    def resizeEvent(self, event):
        resize_event_safe(self, event)
        try:
            if self._processing_overlay:
                overlay_controller_api.relayout(_PROCESSING_OVERLAY_NAME, reason="main_resize")
                if hasattr(self, "_fit_formal_review_overlay_card_width"):
                    self._fit_formal_review_overlay_card_width()
            if self._result_overlay:
                overlay_controller_api.relayout(_RESULT_OVERLAY_NAME, reason="main_resize")
        except Exception:
            pass
        try:
            formal_page = getattr(self, "_formal_review_page", None)
            if formal_page is None:
                formal_page = getattr(self, "formal_review_page", None)
            if formal_page is not None and bool(formal_page.isVisible()):
                if hasattr(self, "_refresh_results_tree_layout"):
                    self._refresh_results_tree_layout()
                if hasattr(self, "_schedule_results_tree_layout_refresh"):
                    self._schedule_results_tree_layout_refresh()
        except Exception:
            pass
