from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QTabWidget, QWidget, QTextEdit, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class ImportResultDialog(QDialog):
    def __init__(self, parent, result_data: dict):
        super().__init__(parent)
        self.setWindowTitle("批量导入结果")
        self.resize(900, 650)
        self.result_data = result_data
        # Data structure expected:
        # {
        #   "processed_count": int,
        #   "new_records": list[dict], # {applicant, inventor, source}
        #   "dup_records": list[dict],
        #   "skipped_count": int,
        #   "errors": list[str]
        # }
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. Summary Cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)
        
        processed = self.result_data.get("processed_count", 0)
        new_list = self.result_data.get("new_records", [])
        dup_list = self.result_data.get("dup_records", [])
        skipped = self.result_data.get("skipped_count", 0)
        errors = self.result_data.get("errors", [])
        
        
        self.add_card(cards_layout, "处理文件", str(processed), "#F0F4F8", "#333")
        self.add_card(cards_layout, "新增记录", str(len(new_list)), "#E3FCEF", "#2E7D32") # Green
        self.add_card(cards_layout, "重复/更新", str(len(dup_list)), "#FFF7E6", "#FF8B00") # Orange
        self.add_card(cards_layout, "跳过/失败", str(skipped), "#FFEBE6", "#BF2600") # Red

        layout.addLayout(cards_layout)

        # 2. Details Tabs
        tabs = QTabWidget()
        
        # Tab 1: New Records
        tab_new = QWidget()
        layout_new = QVBoxLayout(tab_new)
        layout_new.setContentsMargins(0, 10, 0, 0)
        table_new = self.create_table(new_list)
        layout_new.addWidget(table_new)
        tabs.addTab(tab_new, f"新增数据 ({len(new_list)})")
        
        # Tab 2: Duplicate Records
        tab_dup = QWidget()
        layout_dup = QVBoxLayout(tab_dup)
        layout_dup.setContentsMargins(0, 10, 0, 0)
        table_dup = self.create_table(dup_list)
        layout_dup.addWidget(table_dup)
        tabs.addTab(tab_dup, f"重复/更新数据 ({len(dup_list)})")
        
        # Tab 3: Errors
        tab_err = QWidget()
        layout_err = QVBoxLayout(tab_err)
        layout_err.setContentsMargins(0, 10, 0, 0)
        text_err = QTextEdit()
        text_err.setReadOnly(True)
        if errors:
            text_err.setText("\n".join(errors))
        else:
            text_err.setText("无错误信息。")
        layout_err.addWidget(text_err)
        tabs.addTab(tab_err, f"错误日志 ({len(errors)})")
        
        layout.addWidget(tabs)

        # 3. Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_dm = QPushButton("前往常用信息")
        btn_dm.setMinimumWidth(100)
        btn_dm.setProperty("class", "Secondary")
        btn_dm.clicked.connect(self._open_data_management_page)
        btn_layout.addWidget(btn_dm)

        btn_close = QPushButton("关闭")
        btn_close.setMinimumWidth(100)
        btn_close.setProperty("class", "Ghost")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def add_card(self, layout, title, value, bg_color, text_color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 8px;
                border: 1px solid {bg_color};
            }}
        """)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(15, 15, 15, 15)
        
        lbl_val = QLabel(value)
        lbl_val.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        lbl_val.setFont(f)
        lbl_val.setStyleSheet(f"color: {text_color}; border: none;")
        
        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color: #555; border: none; font-size: 13px;")
        
        fl.addWidget(lbl_val)
        fl.addWidget(lbl_title)
        layout.addWidget(frame)

    def _open_data_management_page(self) -> None:
        owner = self.parent()
        fn = None
        try:
            if owner is not None:
                fn = getattr(owner, "_show_data_management_page", None)
                if not callable(fn):
                    fn = getattr(owner, "_nav_to_data_management", None)
        except Exception:
            fn = None
        try:
            if callable(fn):
                fn()
        except Exception:
            pass
        self.accept()

    def create_table(self, data: list[dict]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["申请人", "发明人", "来源案卷"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        
        table.setRowCount(len(data))
        for i, row in enumerate(data):
            t_app = row.get("applicant", "")
            t_inv = row.get("inventor", "")
            t_src = row.get("source", "")
            
            table.setItem(i, 0, QTableWidgetItem(str(t_app)))
            table.setItem(i, 1, QTableWidgetItem(str(t_inv)))
            table.setItem(i, 2, QTableWidgetItem(str(t_src)))
            
        return table
