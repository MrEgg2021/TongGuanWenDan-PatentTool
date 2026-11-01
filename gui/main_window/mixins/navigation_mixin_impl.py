from core.user_messages import user_error_text
from PySide6.QtWidgets import QMessageBox
from core.official_docs.field_registry import get_supported_type_catalog_health
from gui.windowing import overlay_controller as overlay_controller_api


class NavigationMixin:
    def _scroll_main_to_top(self) -> None:
        try:
            scroll_area = getattr(self, "_main_scroll_area", None)
            if scroll_area is None:
                return
            bar = getattr(scroll_area, "verticalScrollBar", None)
            if callable(bar):
                bar_obj = bar()
                if bar_obj is not None:
                    bar_obj.setValue(0)
        except Exception:
            pass

    def _hide_response_correction_page(self) -> None:
        try:
            for attr in (
                "_response_page",
                "_correction_page",
                "_active_response_page",
                "_active_correction_page",
                "_response_correction_page",
            ):
                page = getattr(self, attr, None)
                if page:
                    page.setVisible(False)
        except Exception:
            pass

    def _confirm_leave_settings_before_navigation(self) -> bool:
        if not self._confirm_leave_official_docs_if_dirty():
            self._set_nav_checked("official_docs")
            return False
        if not self._confirm_leave_settings_if_dirty():
            self._set_nav_checked("settings")
            return False
        return True

    def _show_workflow_page(self) -> None:
        self._hide_response_correction_page()
        try:
            if hasattr(self, "_official_docs_page") and self._official_docs_page:
                self._official_docs_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_formal_review_page") and self._formal_review_page:
                self._formal_review_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "about_page") and self.about_page:
                self.about_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_data_management_page") and self._data_management_page:
                self._data_management_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_settings_page") and self._settings_page:
                self._settings_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_preview_page") and self._preview_page:
                self._preview_page.setVisible(False)
        except Exception:
            pass
        try:
            for w in getattr(self, "_workflow_widgets", []) or []:
                try:
                    w.setVisible(True)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self._scroll_main_to_top()
        except Exception:
            pass

    def _show_preview_page(self) -> None:
        self._hide_response_correction_page()
        try:
            if hasattr(self, "_official_docs_page") and self._official_docs_page:
                self._official_docs_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_formal_review_page") and self._formal_review_page:
                self._formal_review_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "about_page") and self.about_page:
                self.about_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_data_management_page") and self._data_management_page:
                self._data_management_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_settings_page") and self._settings_page:
                self._settings_page.setVisible(False)
        except Exception:
            pass

        try:
            for w in getattr(self, "_conversion_widgets", []) or []:
                try:
                    w.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if hasattr(self, "_status_frame") and self._status_frame:
                self._status_frame.setVisible(True)
        except Exception:
            pass

        try:
            if hasattr(self, "_preview_page") and self._preview_page:
                self._preview_page.setVisible(True)
        except Exception:
            pass

        try:
            self._refresh_preview_case_list_ui(selected_path=None)
        except Exception:
            pass

        try:
            self._ensure_full_preview_prewarm()
        except Exception:
            pass

        try:
            self._scroll_main_to_top()
        except Exception:
            pass

    def _show_settings_page(self) -> None:
        self._hide_response_correction_page()
        try:
            if hasattr(self, "_official_docs_page") and self._official_docs_page:
                self._official_docs_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_formal_review_page") and self._formal_review_page:
                self._formal_review_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "about_page") and self.about_page:
                self.about_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_data_management_page") and self._data_management_page:
                self._data_management_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_preview_page") and self._preview_page:
                self._preview_page.setVisible(False)
        except Exception:
            pass

        try:
            for w in getattr(self, "_workflow_widgets", []) or []:
                try:
                    w.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if hasattr(self, "_status_frame") and self._status_frame:
                self._status_frame.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_settings_page") and self._settings_page:
                self._refresh_settings_page_from_state()
                self._settings_page.setVisible(True)
        except Exception:
            pass

        try:
            self._scroll_main_to_top()
        except Exception:
            pass

    def show_about_page(self) -> None:
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass
        self._hide_response_correction_page()
        try:
            if hasattr(self, "_official_docs_page") and self._official_docs_page:
                self._official_docs_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_formal_review_page") and self._formal_review_page:
                self._formal_review_page.setVisible(False)
        except Exception:
            pass
        self._set_nav_checked("about")
        try:
            for w in getattr(self, "_workflow_widgets", []) or []:
                try:
                    w.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, "_preview_page") and self._preview_page:
                self._preview_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_data_management_page") and self._data_management_page:
                self._data_management_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_settings_page") and self._settings_page:
                self._settings_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "about_page") and self.about_page:
                self.about_page.setVisible(True)
        except Exception:
            pass

        try:
            self._scroll_main_to_top()
        except Exception:
            pass

    def _set_nav_checked(self, target: str) -> None:
        shell = getattr(self, "_modern_shell", None)
        if not shell:
            return
        try:
            self._current_nav_target = str(target or "").strip() or "home"
        except Exception:
            pass
        try:
            mapping = {
                "home": getattr(shell, "nav_home", None),
                "batch": getattr(shell, "nav_batch", None),
                "preview": getattr(shell, "nav_preview", None),
                "response": getattr(shell, "nav_response", None),
                "correction": getattr(shell, "nav_correction", None),
                "active_response": getattr(shell, "nav_active_response", None),
                "active_correction": getattr(shell, "nav_active_correction", None),
                "data_management": getattr(shell, "nav_data_management", None),
                "official_docs": getattr(shell, "nav_official_docs", None),
                "formal_review": getattr(shell, "nav_formal_review", None),
                "settings": getattr(shell, "nav_settings", None),
                "about": getattr(shell, "nav_about", None),
            }
            for key, btn in mapping.items():
                if not btn:
                    continue
                btn.setChecked(key == target)
        except Exception:
            pass
        try:
            overlay_controller_api.reconcile_sidebar_toggle(self)
        except Exception:
            pass

    def _nav_to_home(self):
        """Side Nav: Single Conversion."""
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass
        self._set_nav_checked("home")
        try:
            self._show_workflow_page()
            try:
                self._processing_mode = "single"
            except Exception:
                pass
            self.on_mode_changed("single")
        except Exception:
            pass

    def _nav_to_batch(self):
        """Side Nav: Batch Conversion."""
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass
        self._set_nav_checked("batch")
        try:
            self._show_workflow_page()
            try:
                self._processing_mode = "batch"
            except Exception:
                pass
            self.on_mode_changed("batch")
            # 杩涘叆鎵归噺妯″紡鍚庡皢鐒︾偣鏀惧埌鍒楄〃锛屼究浜庨敭鐩樻搷浣溿€?
            if hasattr(self, "batch_list"):
                self.batch_list.setFocus()
        except Exception:
            pass

    def _nav_to_settings(self):
        """Side Nav: Settings."""
        self._set_nav_checked("settings")
        try:
            self._show_settings_page()
        except Exception:
            pass

    def _show_data_management_page(self) -> None:
        self._hide_response_correction_page()
        try:
            if hasattr(self, "_official_docs_page") and self._official_docs_page:
                self._official_docs_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_formal_review_page") and self._formal_review_page:
                self._formal_review_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "about_page") and self.about_page:
                self.about_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_preview_page") and self._preview_page:
                self._preview_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_settings_page") and self._settings_page:
                self._settings_page.setVisible(False)
        except Exception:
            pass

        try:
            for w in getattr(self, "_workflow_widgets", []) or []:
                try:
                    w.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if hasattr(self, "_status_frame") and self._status_frame:
                self._status_frame.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_data_management_page") and self._data_management_page:
                self._data_management_page.setVisible(True)
        except Exception:
            pass

        try:
            self._scroll_main_to_top()
        except Exception:
            pass

        try:
            fn = getattr(self, "_tgd_dm_maybe_auto_expand_guide", None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _nav_to_data_management(self):
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass


        self._set_nav_checked("data_management")
        try:
            self._show_data_management_page()
        except Exception:
            pass

    def _show_official_docs_page(self) -> None:
        self._hide_response_correction_page()
        try:
            if hasattr(self, "about_page") and self.about_page:
                self.about_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_data_management_page") and self._data_management_page:
                self._data_management_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_preview_page") and self._preview_page:
                self._preview_page.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, "_settings_page") and self._settings_page:
                self._settings_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_formal_review_page") and self._formal_review_page:
                self._formal_review_page.setVisible(False)
        except Exception:
            pass

        try:
            for w in getattr(self, "_workflow_widgets", []) or []:
                try:
                    w.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if hasattr(self, "_status_frame") and self._status_frame:
                self._status_frame.setVisible(False)
        except Exception:
            pass

        try:
            fn = getattr(self, "_refresh_official_docs_page_from_state", None)
            if callable(fn):
                fn()
        except Exception:
            pass

        try:
            if hasattr(self, "_official_docs_page") and self._official_docs_page:
                self._official_docs_page.setVisible(True)
        except Exception:
            pass

        try:
            self._scroll_main_to_top()
        except Exception:
            pass

    def _nav_to_official_docs(self):
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass

        prev = "home"
        try:
            prev = str(getattr(self, "_current_nav_target", "") or "").strip() or "home"
        except Exception:
            prev = "home"


        try:
            catalog_health = get_supported_type_catalog_health()
        except Exception as exc:
            QMessageBox.critical(self, "官文资源不可用", user_error_text(f"官文类型资源检查失败：{exc}"))
            try:
                self._set_nav_checked(prev)
            except Exception:
                pass
            return

        if not bool(getattr(catalog_health, "healthy", False)):
            warning = str(getattr(catalog_health, "warning", "") or "").strip()
            error = str(getattr(catalog_health, "error", "") or "").strip()
            detail = error or warning or "\u5b98\u6587\u7c7b\u578b\u8d44\u6e90\u7f3a\u5931\u6216\u635f\u574f\uff0c\u8bf7\u91cd\u65b0\u5b89\u88c5\u4e3b\u7a0b\u5e8f\u3002"
            QMessageBox.critical(self, "官文资源不可用", user_error_text(detail))
            try:
                self._set_nav_checked(prev)
            except Exception:
                pass
            return

        self._set_nav_checked("official_docs")
        try:
            self._show_official_docs_page()
        except Exception:
            pass

    def _show_formal_review_page(self) -> None:
        self._hide_response_correction_page()
        try:
            if hasattr(self, "about_page") and self.about_page:
                self.about_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_data_management_page") and self._data_management_page:
                self._data_management_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_preview_page") and self._preview_page:
                self._preview_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_settings_page") and self._settings_page:
                self._settings_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_official_docs_page") and self._official_docs_page:
                self._official_docs_page.setVisible(False)
        except Exception:
            pass
        try:
            for w in getattr(self, "_workflow_widgets", []) or []:
                try:
                    w.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, "_status_frame") and self._status_frame:
                self._status_frame.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_formal_review_page") and self._formal_review_page:
                fn = getattr(self, "_ensure_formal_review_state", None)
                if callable(fn):
                    fn()
                self._formal_review_page.setVisible(True)
        except Exception:
            pass
        try:
            self._scroll_main_to_top()
        except Exception:
            pass
        try:
            fn = getattr(self, "_apply_formal_review_entry_window_state", None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _nav_to_formal_review(self):
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass

        self._set_nav_checked("formal_review")
        try:
            self._show_formal_review_page()
        except Exception:
            pass

    def _show_response_correction_page_for_flow(self, flow: str) -> None:
        try:
            if hasattr(self, "about_page") and self.about_page:
                self.about_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_data_management_page") and self._data_management_page:
                self._data_management_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_preview_page") and self._preview_page:
                self._preview_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_settings_page") and self._settings_page:
                self._settings_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_official_docs_page") and self._official_docs_page:
                self._official_docs_page.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, "_formal_review_page") and self._formal_review_page:
                self._formal_review_page.setVisible(False)
        except Exception:
            pass
        try:
            for w in getattr(self, "_workflow_widgets", []) or []:
                try:
                    w.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, "_status_frame") and self._status_frame:
                self._status_frame.setVisible(False)
        except Exception:
            pass
        try:
            response_page = getattr(self, "_response_page", None)
            correction_page = getattr(self, "_correction_page", None)
            active_response_page = getattr(self, "_active_response_page", None)
            active_correction_page = getattr(self, "_active_correction_page", None)
            if response_page:
                response_page.setVisible(flow == "response")
            if correction_page:
                correction_page.setVisible(flow == "correction")
            if active_response_page:
                active_response_page.setVisible(flow == "active_response")
            if active_correction_page:
                active_correction_page.setVisible(flow == "active_correction")
        except Exception:
            pass
        try:
            self._scroll_main_to_top()
        except Exception:
            pass

    def _show_response_page(self) -> None:
        self._show_response_correction_page_for_flow("response")

    def _show_correction_page(self) -> None:
        self._show_response_correction_page_for_flow("correction")

    def _show_active_response_page(self) -> None:
        self._show_response_correction_page_for_flow("active_response")

    def _show_active_correction_page(self) -> None:
        self._show_response_correction_page_for_flow("active_correction")

    def _nav_to_response(self):
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass

        self._set_nav_checked("response")
        try:
            self._show_response_page()
        except Exception:
            pass

    def _nav_to_correction(self):
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass

        self._set_nav_checked("correction")
        try:
            self._show_correction_page()
        except Exception:
            pass

    def _nav_to_active_response(self):
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass

        self._set_nav_checked("active_response")
        try:
            self._show_active_response_page()
        except Exception:
            pass

    def _nav_to_active_correction(self):
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass

        self._set_nav_checked("active_correction")
        try:
            self._show_active_correction_page()
        except Exception:
            pass

    def _nav_to_preview(self):
        try:
            if not self._confirm_leave_settings_before_navigation():
                return
        except Exception:
            pass
        self._set_nav_checked("preview")
        try:
            self._show_preview_page()
        except Exception:
            pass

    def _nav_to_about(self):
        """Side Nav: About."""
        try:
            self.show_about_page()
        except Exception:
            pass
