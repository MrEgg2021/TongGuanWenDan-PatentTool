import os
from typing import Any

from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from gui.dialog_utils import show_blocking_alert_modal
from gui.widgets_impl.combo_wheel_blocker import ComboWheelBlocker

from .text_utils import _norm_text


def _dedup_keep_order(items: list[str]) -> tuple[list[str], list[str]]:
    seen: set[str] = set()
    out: list[str] = []
    dups: list[str] = []
    for it in items or []:
        v = _norm_text(it)
        if not v:
            continue
        if v in seen:
            if v not in dups:
                dups.append(v)
            continue
        seen.add(v)
        out.append(v)
    return out, dups


def _is_effective_applicant(app: Any) -> bool:
    if not isinstance(app, dict):
        return False
    for k in ("name", "id_no", "address", "phone", "email"):
        if _norm_text(app.get(k)):
            return True
    return False


class _PoaMappingDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        *,
        applicants: list[dict],
        poa_nos: list[str],
        source_path: str,
    ):
        super().__init__(parent)
        self._poa_nos = poa_nos
        self._mapping: list[str] = []
        self._poa_combos: list[QComboBox] = []
        self._combo_wheel_blocker = ComboWheelBlocker(self)

        self.setWindowTitle("POA 映射")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        file_name = os.path.basename(str(source_path or ""))
        hint = QLabel(
            "检测到‘总委托书编号(POA)’与申请人存在歧义，请为每个有效申请人选择一个 POA（可留空）。\n"
            "同一申请内 POA 不可重复，且解析出的每个 POA 必须分配给某个申请人。\n\n"
            f"文件：{file_name}"
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        table = QTableWidget(self)
        table.setRowCount(max(0, len(applicants)))
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["申请人名称", "证件号码", "总委托书编号(POA)"])

        try:
            self._combo_wheel_blocker.register_strict_scroll_area(table)
        except Exception:
            pass

        for i, app in enumerate(applicants or []):
            if not isinstance(app, dict):
                app = {}
            name = _norm_text(app.get("name"))
            id_no = _norm_text(app.get("id_no"))
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(id_no))

            cb = QComboBox(table)
            cb.addItem("")
            for p in poa_nos or []:
                cb.addItem(_norm_text(p))

            try:
                self._combo_wheel_blocker.register_combo(cb)
            except Exception:
                pass

            existing = ""
            try:
                existing = _norm_text(app.get("power_of_attorney_no"))
            except Exception:
                existing = ""
            if existing and existing in (poa_nos or []):
                try:
                    cb.setCurrentText(existing)
                except Exception:
                    pass

            table.setCellWidget(i, 2, cb)
            self._poa_combos.append(cb)

        try:
            table.resizeColumnsToContents()
        except Exception:
            pass
        root.addWidget(table)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        btn_cancel = QPushButton("取消")
        btn_ok = QPushButton("确定")

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

        try:
            btn_cancel.clicked.connect(lambda: self.reject())
        except Exception:
            pass
        try:
            btn_ok.clicked.connect(lambda: self._on_ok_clicked())
        except Exception:
            pass

    def get_mapping(self) -> list[str]:
        return list(self._mapping or [])

    def _on_ok_clicked(self) -> None:
        mapping: list[str] = []
        for cb in self._poa_combos:
            try:
                mapping.append(_norm_text(cb.currentText()))
            except Exception:
                mapping.append("")

        seen = set()
        dup = set()
        for v in mapping:
            if not v:
                continue
            if v in seen:
                dup.add(v)
            else:
                seen.add(v)

        if dup:
            msg = "发现重复的总委托书编号(POA)，同一申请内不可重复，请修改后再确定：\n" + "\n".join(
                f"- {d}" for d in sorted(dup)
            )
            show_blocking_alert_modal(self, "提示", msg, primary_text="关闭", secondary_text="关闭")
            return

        used = set([v for v in mapping if v])
        missing = [p for p in (self._poa_nos or []) if p not in used]
        if missing:
            msg = "以下总委托书编号(POA)尚未分配给任何申请人，请修改后再确定：\n" + "\n".join(
                f"- {m}" for m in missing
            )
            show_blocking_alert_modal(self, "提示", msg, primary_text="关闭", secondary_text="关闭")
            return

        self._mapping = mapping
        self.accept()


def _normalize_parsed_applicants(parsed_info: dict) -> list[dict]:
    applicants = []
    try:
        applicants = parsed_info.get("applicants") or []
    except Exception:
        applicants = []
    if not isinstance(applicants, list) or not applicants:
        applicants = [{}]
        try:
            parsed_info["applicants"] = applicants
        except Exception:
            pass

    norm_apps: list[dict] = []
    for a in applicants:
        if isinstance(a, dict):
            norm_apps.append(a)
        else:
            norm_apps.append({})
    applicants = norm_apps
    try:
        parsed_info["applicants"] = applicants
    except Exception:
        pass
    return applicants


def _collect_effective_applicants(applicants: list[dict]) -> tuple[list[int], list[dict]]:
    effective_indices: list[int] = []
    effective_apps: list[dict] = []
    for i, a in enumerate(applicants or []):
        if _is_effective_applicant(a):
            effective_indices.append(int(i))
            effective_apps.append(a)
    return effective_indices, effective_apps


def _collect_poa_nos_from_parsed_info(parsed_info: dict) -> tuple[list[str], list[str]]:
    raw_poa = []
    try:
        raw_poa = parsed_info.get("_poa_nos_from_xml") or []
    except Exception:
        raw_poa = []
    poa_items: list[str] = []
    if isinstance(raw_poa, list):
        for it in raw_poa:
            v = _norm_text(it)
            if v:
                poa_items.append(v)
    poa_nos, dup_poa = _dedup_keep_order(poa_items)
    return poa_nos, dup_poa


def _apply_poa_mapping_to_applicants(applicants: list[dict], effective_indices: list[int], mapping: list[str]) -> None:
    for i, poa in enumerate(mapping or []):
        idx = int(effective_indices[i])
        try:
            applicants[idx]["power_of_attorney_no"] = _norm_text(poa)
        except Exception:
            pass


def _apply_zip_poa_mapping(window, parsed_info: dict, *, source_path: str) -> tuple[bool, list[str]]:
    msgs: list[str] = []
    applicants = _normalize_parsed_applicants(parsed_info)

    effective_indices, effective_apps = _collect_effective_applicants(applicants)

    poa_nos, dup_poa = _collect_poa_nos_from_parsed_info(parsed_info)
    if dup_poa:
        msgs.append(
            "ZIP 内发现重复的总委托书编号(POA)，已自动去重：\n" + "\n".join([f"- {d}" for d in dup_poa])
        )

    if not poa_nos:
        return True, msgs

    try:
        parsed_info["agency_enabled"] = True
    except Exception:
        pass

    effective_count = len(effective_apps)
    poa_count = len(poa_nos)

    if effective_count <= 0:
        return False, ["解析到总委托书编号(POA)，但未找到有效申请人信息，无法映射，已跳过该 ZIP。"]

    if effective_count == 1:
        if poa_count == 1:
            idx0 = int(effective_indices[0])
            try:
                applicants[idx0]["power_of_attorney_no"] = poa_nos[0]
            except Exception:
                pass
            try:
                parsed_info["applicants"] = applicants
            except Exception:
                pass
            return True, msgs
        return False, [
            "解析到多个总委托书编号(POA)，但只有 1 个有效申请人。根据规则：单申请人 + 多 POA 需要报错并跳过该 ZIP。"
        ]

    if poa_count > effective_count:
        return False, [
            f"总委托书编号(POA)数量({poa_count})大于有效申请人数量({effective_count})，无法按“每个申请人最多一个 POA”进行映射。"
        ]

    dlg = _PoaMappingDialog(
        window,
        applicants=effective_apps,
        poa_nos=poa_nos,
        source_path=source_path,
    )
    ok = False
    try:
        ok = dlg.exec() == QDialog.Accepted
    except Exception:
        ok = False
    if not ok:
        return False, ["已取消 POA 映射，本 ZIP 已跳过导入。"]

    mapping = dlg.get_mapping()
    if not mapping or len(mapping) != len(effective_apps):
        return False, ["POA 映射结果无效，本 ZIP 已跳过导入。"]

    _apply_poa_mapping_to_applicants(applicants, effective_indices, mapping)

    try:
        parsed_info["applicants"] = applicants
    except Exception:
        pass
    return True, msgs
