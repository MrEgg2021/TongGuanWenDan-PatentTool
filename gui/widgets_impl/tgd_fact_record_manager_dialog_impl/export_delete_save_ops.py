from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QTableWidgetItem

from core.tgd_data_management_impl.db import db_session
from core.tgd_data_management_impl.excel_io import export_tgd_excel_data
from core.tgd_data_management_impl.infra import get_db_path
from core.tgd_data_management_impl.migrations import ensure_db_ready
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal
from gui.widgets_impl import GraphicCheckBox
from gui.widgets_impl.tgd_fact_record_manager_save_ops import save_fact_record
from gui.widgets_impl.tgd_fact_record_manager_utils import _norm_text


class _ExportDeleteSaveOpsMixin:
    def _on_delete_clicked(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._delete_selected_fact_rows()
        else:
            self._delete_selected_agency_rows()

    def _on_select_all_clicked(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._select_all_fact_rows()
        else:
            self._select_all_agency_rows()

    def _on_deselect_all_clicked(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._deselect_all_fact_rows()
        else:
            self._deselect_all_agency_rows()

    def _on_export_clicked(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._export_checked_fact_rows()
        else:
            self._export_checked_agency_rows()

    def _pick_export_xlsx_path(self) -> str:
        path = ""
        try:
            path, _ = QFileDialog.getSaveFileName(self, "导出Excel", "", "Excel 文件 (*.xlsx)")
        except Exception:
            path = ""
        path = _norm_text(path)
        if not path:
            return ""
        if not path.lower().endswith(".xlsx"):
            path = path + ".xlsx"
        return path

    def _export_checked_fact_rows(self) -> None:
        ids = sorted([int(x) for x in (self._checked_fact_ids or set()) if x is not None])
        if not ids:
            show_blocking_alert_modal(self, "提示", "请先勾选需要导出的常用信息。", primary_text="关闭", secondary_text="关闭")
            return
        dest_path = self._pick_export_xlsx_path()
        if not dest_path:
            return
        try:
            export_tgd_excel_data(dest_path, masked=False, fact_record_ids=ids, agency_agent_ids=[])
            show_blocking_alert_modal(self, "完成", f"已导出 {len(ids)} 条常用信息。", primary_text="关闭", secondary_text="关闭")
        except Exception as e:
            show_blocking_alert_modal(self, "错误", f"导出失败：{e}", primary_text="关闭", secondary_text="关闭")

    def _export_checked_agency_rows(self) -> None:
        ids = sorted([int(x) for x in (self._checked_agency_ids or set()) if x is not None])
        if not ids:
            show_blocking_alert_modal(self, "提示", "请先勾选需要导出的代理机构记录。", primary_text="关闭", secondary_text="关闭")
            return
        dest_path = self._pick_export_xlsx_path()
        if not dest_path:
            return
        try:
            export_tgd_excel_data(dest_path, masked=False, fact_record_ids=[], agency_agent_ids=ids)
            show_blocking_alert_modal(self, "完成", f"已导出 {len(ids)} 条代理机构记录。", primary_text="关闭", secondary_text="关闭")
        except Exception as e:
            show_blocking_alert_modal(self, "错误", f"导出失败：{e}", primary_text="关闭", secondary_text="关闭")

    def _delete_selected_fact_rows(self) -> None:
        if self.fact_table_left is None or self.fact_table_right is None:
            return
        rows_checked = set(self._get_checked_fact_row_indices())
        if rows_checked:
            rows = rows_checked
        else:
            rows = set(i.row() for i in self.fact_table_left.selectedItems()) | set(
                i.row() for i in self.fact_table_right.selectedItems()
            )
        rows = {r for r in rows if int(r) >= 1}
        if not rows:
            show_blocking_alert_modal(self, "提示", "请先勾选或选中需要删除的行。", primary_text="关闭", secondary_text="关闭")
            return

        ok = ask_continue_cancel(
            self,
            "确认删除",
            f"确认删除选中的 {len(rows)} 行记录吗？\n\n删除后需要点击“保存修改”才会真正写入数据库。",
            continue_text="确认删除",
            cancel_text="取消",
            default_continue=False,
        )
        if not ok:
            return

        removed_any = False
        for r in sorted(rows, reverse=True):
            item_id = self._get_fact_row_id(r)
            if item_id is not None:
                try:
                    self._deleted_fact_ids.append(int(item_id))
                    self._checked_fact_ids.discard(int(item_id))
                except Exception:
                    pass
            try:
                self.fact_table_left.removeRow(r)
                self.fact_table_right.removeRow(r)
                removed_any = True
            except Exception:
                pass

        if not removed_any:
            return

        self._update_fact_row_numbers()
        self._dirty = True

        save_now = ask_continue_cancel(
            self,
            "已删除",
            "已从列表中移除所选记录。\n\n是否现在保存修改？\n（保存后才会真正写入数据库删除）",
            continue_text="保存修改",
            cancel_text="稍后",
            default_continue=True,
        )
        if save_now:
            self._on_save_clicked()

    def _delete_selected_agency_rows(self) -> None:
        if self.agency_table is None:
            return
        rows_checked = set(self._get_checked_agency_row_indices())
        if rows_checked:
            rows = rows_checked
        else:
            rows = {i.row() for i in self.agency_table.selectedItems()}
        rows = {r for r in rows if int(r) >= 1}
        if not rows:
            show_blocking_alert_modal(self, "提示", "请先勾选或选中需要删除的行。", primary_text="关闭", secondary_text="关闭")
            return

        ok = ask_continue_cancel(
            self,
            "确认删除",
            f"确认删除选中的 {len(rows)} 行记录吗？\n\n删除后需要点击“保存修改”才会真正写入数据库。",
            continue_text="确认删除",
            cancel_text="取消",
            default_continue=False,
        )
        if not ok:
            return

        removed_any = False
        for r in sorted(rows, reverse=True):
            item_id = self._get_agency_row_id(r)
            if item_id is not None:
                try:
                    self._deleted_agency_ids.append(int(item_id))
                    self._checked_agency_ids.discard(int(item_id))
                except Exception:
                    pass
            try:
                self.agency_table.removeRow(r)
                removed_any = True
            except Exception:
                pass

        if not removed_any:
            return

        self._update_agency_row_numbers()
        self._dirty = True

        save_now = ask_continue_cancel(
            self,
            "已删除",
            "已从列表中移除所选记录。\n\n是否现在保存修改？\n（保存后才会真正写入数据库删除）",
            continue_text="保存修改",
            cancel_text="稍后",
            default_continue=True,
        )
        if save_now:
            self._on_save_clicked()

    def _on_add_clicked(self) -> None:
        if self.tabs.currentIndex() == 0:
            # Add to fact tables
            self.fact_table_left.blockSignals(True)
            self.fact_table_right.blockSignals(True)

            rc = self.fact_table_left.rowCount()
            self.fact_table_left.insertRow(rc)
            self.fact_table_right.insertRow(rc)

            cb_left = GraphicCheckBox(str(rc))
            try:
                cb_left.setProperty("_tgd_id", None)
            except Exception:
                pass
            try:
                cb_left.toggled.connect(self._on_fact_row_checkbox_toggled)
            except Exception:
                pass
            try:
                self.fact_table_left.setCellWidget(rc, 0, cb_left)
            except Exception:
                pass

            cb_right = GraphicCheckBox(str(rc))
            try:
                cb_right.setProperty("_tgd_id", None)
            except Exception:
                pass
            try:
                cb_right.toggled.connect(self._on_fact_row_checkbox_toggled)
            except Exception:
                pass
            try:
                self.fact_table_right.setCellWidget(rc, 0, cb_right)
            except Exception:
                pass

            # Init empty items
            for c in range(1, self.fact_table_left.columnCount()):
                it = QTableWidgetItem("")
                it.setData(Qt.UserRole, None)  # New row
                self.fact_table_left.setItem(rc, c, it)

            for c in range(1, self.fact_table_right.columnCount()):
                it = QTableWidgetItem("")
                it.setData(Qt.UserRole, None)
                self.fact_table_right.setItem(rc, c, it)

            # Default values
            # Index 4 is Inventor Nationality Code
            self.fact_table_right.item(rc, 4).setText("CN")  # Nat

            self.fact_table_left.blockSignals(False)
            self.fact_table_right.blockSignals(False)

            self.fact_table_left.scrollToBottom()
            self.fact_table_right.scrollToBottom()

        else:
            # Agency
            self.agency_table.blockSignals(True)
            rc = self.agency_table.rowCount()
            self.agency_table.insertRow(rc)

            cb = GraphicCheckBox(str(rc))
            try:
                cb.setProperty("_tgd_id", None)
            except Exception:
                pass
            try:
                cb.toggled.connect(self._on_agency_row_checkbox_toggled)
            except Exception:
                pass
            try:
                self.agency_table.setCellWidget(rc, 0, cb)
            except Exception:
                pass

            for c in range(1, self.agency_table.columnCount()):
                it = QTableWidgetItem("")
                it.setData(Qt.UserRole, None)
                self.agency_table.setItem(rc, c, it)
            self.agency_table.blockSignals(False)
            self.agency_table.scrollToBottom()

        self._dirty = True

    def _on_save_clicked(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._save_fact_record()
        else:
            self._save_agency_agent()

    def _save_fact_record(self) -> None:
        save_fact_record(self)

    def _save_agency_agent(self) -> None:
        db_path = get_db_path()
        ensure_db_ready(db_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row_count = self.agency_table.rowCount()
        inserted = 0
        updated = 0

        try:
            with db_session(db_path) as conn:
                try:
                    deleted_ids = list(
                        dict.fromkeys(
                            [int(x) for x in (self._deleted_agency_ids or []) if x is not None]
                        )
                    )
                except Exception:
                    deleted_ids = []
                if deleted_ids:
                    placeholders_del = ",".join(["?"] * len(deleted_ids))
                    conn.execute(
                        f"DELETE FROM tgd_agency_agent WHERE id IN ({placeholders_del})",
                        tuple(deleted_ids),
                    )
                    try:
                        self._deleted_agency_ids = []
                    except Exception:
                        pass

                for r in range(1, row_count):
                    item_id = None
                    it0 = self.agency_table.item(r, 1)
                    if it0:
                        item_id = it0.data(Qt.UserRole)

                    is_dirty = False
                    if item_id is None:
                        is_dirty = True
                    else:
                        for c in range(self.agency_table.columnCount()):
                            it = self.agency_table.item(r, c)
                            if it and it.data(Qt.UserRole + 1):
                                is_dirty = True
                                break

                    if not is_dirty:
                        continue

                    # 0:Name, 1:Code, 2:Agent, 3:Cert, 4:Phone
                    def _t(row, col):
                        it = self.agency_table.item(row, col)
                        return _norm_text(it.text()) if it else ""

                    an = _t(r, 1)
                    ac = _t(r, 2)
                    agn = _t(r, 3)
                    agc = _t(r, 4)
                    agp = _t(r, 5)

                    if not an and not agn:
                        continue

                    if item_id:
                        conn.execute(
                            """
                            UPDATE tgd_agency_agent SET
                                agency_name=?, agency_code=?, agent_name=?, agent_cert_no=?, agent_phone=?,
                                updated_at=?, source_type='manual'
                            WHERE id=?
                        """,
                            (an, ac, agn, agc, agp, now, item_id),
                        )
                        updated += 1
                    else:
                        conn.execute(
                            """
                            INSERT INTO tgd_agency_agent (
                                agency_name, agency_code, agent_name, agent_cert_no, agent_phone,
                                created_at, updated_at, source_type, source_ref
                            ) VALUES (?,?,?,?,?,?,?,'manual','data_mgmt_manager')
                        """,
                            (an, ac, agn, agc, agp, now, now),
                        )
                        inserted += 1

        except Exception as e:
            show_blocking_alert_modal(self, "错误", f"保存失败：{e}", primary_text="关闭", secondary_text="关闭")
            return

        msg = f"保存完成：新增 {inserted}，更新 {updated}"
        if deleted_ids:
            msg += f"，删除 {len(deleted_ids)}"
        show_blocking_alert_modal(self, "完成", msg, primary_text="关闭", secondary_text="关闭")
        self._refresh_agency_table()
