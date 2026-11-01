from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction, QColor, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gui.widgets_impl import GraphicCheckBox


class _RowMenuOpsMixin:
    def _show_row_menu(self, pos: QPoint, tbl: QTableWidget) -> None:
        row = tbl.rowAt(pos.y())
        if row < 1:  # Row 0 is filter row
            return

        menu = QMenu(self)

        act_up = QAction("在上方插入行", menu)
        act_up.triggered.connect(lambda *_: self._insert_rows_action(tbl, row, "above"))

        act_down = QAction("在下方插入行", menu)
        act_down.triggered.connect(lambda *_: self._insert_rows_action(tbl, row, "below"))

        menu.addSeparator()

        act_copy_up = QAction("复制上方行内容", menu)
        if row <= 1:
            act_copy_up.setEnabled(False)
        act_copy_up.triggered.connect(lambda *_: self._fill_row_action(tbl, row, row - 1))

        act_copy_down = QAction("复制下方行内容", menu)
        if row >= tbl.rowCount() - 1:
            act_copy_down.setEnabled(False)
        act_copy_down.triggered.connect(lambda *_: self._fill_row_action(tbl, row, row + 1))

        menu.addActions([act_up, act_down])
        menu.addSeparator()
        menu.addActions([act_copy_up, act_copy_down])

        menu.exec_(tbl.viewport().mapToGlobal(pos))

    def _ask_insert_rows_count(self) -> int | None:
        dlg = QDialog(self)
        dlg.setObjectName("ModalOverlay")
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        try:
            dlg.setWindowFlag(Qt.FramelessWindowHint, True)
        except Exception:
            pass
        try:
            dlg.setAttribute(Qt.WA_TranslucentBackground, True)
        except Exception:
            pass

        overlay_layout = QVBoxLayout(dlg)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)
        overlay_layout.setAlignment(Qt.AlignCenter)

        card = QFrame(dlg)
        card.setObjectName("ModalCard")
        try:
            card.setFixedWidth(420)
        except Exception:
            pass

        try:
            eff = QGraphicsDropShadowEffect(card)
            eff.setBlurRadius(28)
            eff.setOffset(0, 10)
            eff.setColor(QColor(15, 23, 42, 70))
            card.setGraphicsEffect(eff)
        except Exception:
            pass

        v = QVBoxLayout(card)
        v.setContentsMargins(24, 20, 24, 16)
        v.setSpacing(12)

        titlebar = QFrame(card)
        titlebar.setObjectName("ModalTitleBar")
        tl = QHBoxLayout(titlebar)
        tl.setContentsMargins(0, 0, 0, 8)
        tl.setSpacing(8)

        title = QLabel("插入行")
        title.setObjectName("ModalTitleText")
        title.setProperty("role", "h2")
        tl.addWidget(title, 1)

        btn_close = QPushButton("×")
        btn_close.setObjectName("ModalCloseButton")
        btn_close.setFixedSize(28, 28)
        btn_close.setFocusPolicy(Qt.NoFocus)
        tl.addWidget(btn_close, 0, Qt.AlignTop)
        v.addWidget(titlebar)

        body = QFrame(card)
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)
        lbl = QLabel("请输入插入行数：")
        bl.addWidget(lbl)
        spin = QSpinBox(body)
        spin.setRange(1, 100)
        spin.setValue(1)
        try:
            spin.setFixedHeight(36)
        except Exception:
            pass
        bl.addWidget(spin)
        v.addWidget(body)

        footer = QFrame(card)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(0, 8, 0, 0)
        fl.setSpacing(10)
        fl.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("secondaryButton")
        btn_ok = QPushButton("确定")
        btn_ok.setObjectName("primaryButton")
        fl.addWidget(btn_cancel)
        fl.addWidget(btn_ok)
        v.addWidget(footer)

        overlay_layout.addWidget(card)

        btn_close.clicked.connect(dlg.reject)
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok.clicked.connect(dlg.accept)

        ok = dlg.exec() == QDialog.Accepted
        if not ok:
            return None
        try:
            return int(spin.value())
        except Exception:
            return None

    def _insert_rows_action(self, tbl: QTableWidget, ref_row: int, direction: str) -> None:
        count = self._ask_insert_rows_count()
        if count is None:
            return

        insert_idx = ref_row if direction == "above" else ref_row + 1

        if tbl in [self.fact_table_left, self.fact_table_right]:
            # Both fact tables must stay in sync
            self.fact_table_left.blockSignals(True)
            self.fact_table_right.blockSignals(True)
            for _ in range(count):
                self.fact_table_left.insertRow(insert_idx)
                self.fact_table_right.insertRow(insert_idx)

                for t in [self.fact_table_left, self.fact_table_right]:
                    # Column 0: CheckBox
                    cb = GraphicCheckBox(str(insert_idx))
                    try:
                        cb.setProperty("class", "TableRowCheck")
                    except Exception:
                        pass
                    cb.toggled.connect(self._on_fact_row_checkbox_toggled)
                    t.setCellWidget(insert_idx, 0, cb)

                    # Others: Empty items
                    for c in range(1, t.columnCount()):
                        it = QTableWidgetItem("")
                        it.setData(Qt.UserRole, None)
                        t.setItem(insert_idx, c, it)

            self.fact_table_left.blockSignals(False)
            self.fact_table_right.blockSignals(False)
            self._update_fact_row_numbers()
        else:
            # Agency table
            tbl.blockSignals(True)
            for _ in range(count):
                tbl.insertRow(insert_idx)
                cb = GraphicCheckBox(str(insert_idx))
                try:
                    cb.setProperty("class", "TableRowCheck")
                except Exception:
                    pass
                cb.toggled.connect(self._on_agency_row_checkbox_toggled)
                tbl.setCellWidget(insert_idx, 0, cb)
                for c in range(1, tbl.columnCount()):
                    it = QTableWidgetItem("")
                    it.setData(Qt.UserRole, None)
                    tbl.setItem(insert_idx, c, it)
            tbl.blockSignals(False)
            self._update_agency_row_numbers()

        self._dirty = True

    def _fill_row_action(self, tbl: QTableWidget, target_row: int, src_row: int) -> None:
        if src_row < 1 or src_row >= tbl.rowCount():
            return

        # Determine tables to sync (both fact tables should stay aligned)
        sync_tables = []
        if tbl in [self.fact_table_left, self.fact_table_right]:
            sync_tables = [self.fact_table_left, self.fact_table_right]
        else:
            sync_tables = [self.agency_table]

        for t in sync_tables:
            if not t:
                continue
            t.blockSignals(True)
            # We only copy the data columns, NOT the checkbox/ID
            for c in range(1, t.columnCount()):
                src_it = t.item(src_row, c)
                if not src_it:
                    continue

                tgt_it = t.item(target_row, c)
                if not tgt_it:
                    tgt_it = QTableWidgetItem("")
                    t.setItem(target_row, c, tgt_it)

                tgt_it.setText(src_it.text())
                # Mark dirty visually
                tgt_it.setBackground(QBrush(QColor("#fef9c3")))  # light yellow
                tgt_it.setData(Qt.UserRole + 1, True)

            t.blockSignals(False)

        self._dirty = True

    def _show_header_menu(self, pos: QPoint, tbl: QTableWidget) -> None:
        h = tbl.horizontalHeader()
        menu = QMenu(self)
        menu.setTitle("显示/隐藏列")

        for i in range(h.count()):
            label = tbl.horizontalHeaderItem(i).text() or f"列 {i}"
            if not label and i == 0:
                label = "编号/勾选"

            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(not h.isSectionHidden(i))

            def _toggle(checked, idx=i):
                if idx == 0 and not checked:
                    return
                h.setSectionHidden(idx, not checked)
                if tbl in [self.fact_table_left, self.fact_table_right]:
                    self._ensure_fact_tables_last_visible_stretch()
                self._save_layout_state()

            action.toggled.connect(_toggle)
            menu.addAction(action)

        menu.exec_(h.mapToGlobal(pos))
