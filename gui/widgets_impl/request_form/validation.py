from PySide6.QtWidgets import QComboBox, QDialog

from core.id_validation import validate_cn_id, validate_uscc
from gui.dialog_utils import ask_continue_cancel
from gui.dialog_utils import show_blocking_alert_modal


def accept(self):  # type: ignore[override]
    missing = []
    if self.app_tabs.count() > 0:
        first_tab = self.app_tabs.widget(0)
        name_edit = getattr(first_tab, "name_edit", None)
        type_combo = getattr(first_tab, "type_combo", None)
        id_edit = getattr(first_tab, "id_edit", None)
        prov_combo = getattr(first_tab, "province_combo", None)
        city_combo = getattr(first_tab, "city_combo", None)
        addr_edit = getattr(first_tab, "address_edit", None)
        zip_edit = getattr(first_tab, "zip_edit", None)
        phone_edit = getattr(first_tab, "phone_edit", None)

        field_defs = [
            (name_edit, "第一申请人名称"),
            (type_combo, "申请人类型"),
            (id_edit, "申请人证件号码"),
            (prov_combo, "申请人省"),
            (city_combo, "申请人市/区"),
            (addr_edit, "申请人详细地址"),
            (zip_edit, "申请人邮编"),
            (phone_edit, "申请人电话"),
        ]
        for widget, label in field_defs:
            if widget is None:
                continue
            text = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
            if text.strip() == "":
                missing.append(label)

    if missing:
        show_blocking_alert_modal(
            self,
            "提示",
            "以下申请人字段不能为空：\n" + "\n".join("- " + m for m in missing),
            primary_text="关闭",
            secondary_text="关闭",
        )
        return

    agency_enabled = False
    try:
        cb = getattr(self, "agency_enabled_checkbox", None)
        if cb is not None:
            agency_enabled = bool(cb.isChecked())
    except Exception:
        agency_enabled = False

    if agency_enabled:
        seen_poa = set()
        dup_poa = set()
        for i in range(self.app_tabs.count()):
            tab = self.app_tabs.widget(i)
            poa_edit = getattr(tab, "poa_edit", None)
            if poa_edit is None:
                continue
            try:
                poa = (poa_edit.currentText() if isinstance(poa_edit, QComboBox) else poa_edit.text()).strip()
            except Exception:
                poa = ""
            if not poa:
                continue
            if poa in seen_poa:
                dup_poa.add(poa)
            else:
                seen_poa.add(poa)
        if dup_poa:
            msg = "发现重复的总委托书编号(POA)，同一申请内不可重复，请修改后再提交：\n" + "\n".join(
                f"- {d}" for d in sorted(dup_poa)
            )
            show_blocking_alert_modal(self, "提示", msg, primary_text="关闭", secondary_text="关闭")
            return

    issues = []
    validate_cn_enabled = True
    validate_uscc_enabled = True
    try:
        validate_cn_enabled = bool(getattr(self, "_id_validation_cn_enabled", True))
    except Exception:
        validate_cn_enabled = True
    try:
        validate_uscc_enabled = bool(getattr(self, "_id_validation_uscc_enabled", True))
    except Exception:
        validate_uscc_enabled = True
    for i in range(self.app_tabs.count()):
        tab = self.app_tabs.widget(i)
        id_type_combo = getattr(tab, "id_type_combo", None)
        id_edit = getattr(tab, "id_edit", None)
        if id_type_combo is None or id_edit is None:
            continue
        id_no = (id_edit.currentText() if isinstance(id_edit, QComboBox) else id_edit.text()).strip()
        if not id_no:
            continue
        id_type_text = id_type_combo.currentText().strip()
        label = f"申请人{i + 1}"
        lowered = id_type_text.lower()
        need_uscc = ("统一社会信用代码" in id_type_text) or lowered.startswith("f")
        need_id = "身份证" in id_type_text
        if need_uscc and validate_uscc_enabled:
            if not validate_uscc(id_no):
                issues.append(f"{label}：统一社会信用代码疑似不合法")
        elif need_id and validate_cn_enabled:
            if not validate_cn_id(id_no):
                issues.append(f"{label}：身份证号码疑似不合法")

    for i in range(self.inv_tabs.count()):
        tab = self.inv_tabs.widget(i)
        id_type_combo = getattr(tab, "id_type_combo", None)
        id_edit = getattr(tab, "id_edit", None)
        if id_type_combo is None or id_edit is None:
            continue
        id_no = (id_edit.currentText() if isinstance(id_edit, QComboBox) else id_edit.text()).strip()
        if not id_no:
            continue
        id_type_text = id_type_combo.currentText().strip()
        if "身份证" in id_type_text and validate_cn_enabled and not validate_cn_id(id_no):
            issues.append(f"发明人{i + 1}：身份证号码疑似不合法")

    if issues:
        ok = ask_continue_cancel(
            self,
            "证件号码校验提示",
            "发现以下证件号码可能不符合规范：\n" + "\n".join("- " + item for item in issues) + "\n\n是否仍然继续？",
            cancel_text="返回修改",
        )
        if not ok:
            return

    inv_names = []
    inv_ids = []
    for i in range(self.inv_tabs.count()):
        tab = self.inv_tabs.widget(i)
        name_edit = getattr(tab, "name_edit", None)
        id_edit = getattr(tab, "id_edit", None)
        name_text = ""
        if name_edit is not None:
            name_text = (name_edit.currentText() if isinstance(name_edit, QComboBox) else name_edit.text()).strip()
        id_text = ""
        if id_edit is not None:
            id_text = (id_edit.currentText() if isinstance(id_edit, QComboBox) else id_edit.text()).strip()
        if name_text:
            inv_names.append(name_text)
        if id_text:
            inv_ids.append(id_text)
    if len(inv_ids) > len(inv_names):
        show_blocking_alert_modal(
            self,
            "提示",
            "发明人身份证号码数量多于姓名，请修改后再提交。",
            primary_text="关闭",
            secondary_text="关闭",
        )
        return

    seen_ids = set()
    dup_ids = set()
    for _id in inv_ids:
        if _id in seen_ids:
            dup_ids.add(_id)
        else:
            seen_ids.add(_id)
    if dup_ids:
        msg = "发现重复的发明人身份证号码，请修改后再提交：\n" + "\n".join(f"- {d}" for d in sorted(dup_ids))
        show_blocking_alert_modal(self, "提示", msg, primary_text="关闭", secondary_text="关闭")
        return

    try:
        fin = getattr(self, "_finish_dialog", None)
        if callable(fin):
            fin(True)
            return
    except Exception:
        pass

    QDialog.accept(self)


__all__ = ["accept"]
