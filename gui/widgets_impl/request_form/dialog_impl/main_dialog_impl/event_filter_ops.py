from __future__ import annotations

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QComboBox, QStyle, QStyleOptionComboBox



def _register_combo_wheel_block(self, combo: QComboBox | None) -> None:
    """禁用下拉框滚轮（含展开列表），防止误选。"""
    if combo is None:
        return
    try:
        combo.installEventFilter(self)
        self._wheel_block_targets.add(combo)
    except Exception:
        pass
    try:
        view = combo.view()
        if view is not None and view.viewport() is not None:
            vp = view.viewport()
            try:
                view.installEventFilter(self)
            except Exception:
                pass

            vp.installEventFilter(self)
            self._wheel_block_targets.add(vp)
            self._wheel_block_targets.add(view)
            try:
                if isinstance(getattr(self, "_combo_popup_owner_map", None), dict):
                    self._combo_popup_owner_map[view] = combo
                    self._combo_popup_owner_map[vp] = combo
            except Exception:
                pass
    except Exception:
        pass


def event_filter(self, obj, event) -> bool:
    try:
        size_target = getattr(self, "_size_target", None)
        if size_target is not None and obj is size_target:
            watch_types = {
                int(QEvent.Resize),
                int(QEvent.Move),
                int(QEvent.Show),
                int(QEvent.LayoutRequest),
            }
            if hasattr(QEvent, "ScreenChangeInternal"):
                try:
                    watch_types.add(int(QEvent.ScreenChangeInternal))
                except Exception:
                    pass
            if int(event.type()) in watch_types:
                self._schedule_sync_from_target()
    except Exception:
        pass

    try:
        et = event.type()
        if et in (QEvent.KeyPress, QEvent.ShortcutOverride):

            try:
                line_edit_map = getattr(self, "_fact_combo_line_edit_map", None)
                if isinstance(line_edit_map, dict) and obj in line_edit_map:
                    combo = line_edit_map.get(obj)
                    try:
                        key = int(event.key())
                    except Exception:
                        key = 0
                    if key in (Qt.Key_Return, Qt.Key_Enter) and et in (QEvent.KeyPress, QEvent.ShortcutOverride):
                        try:
                            view = combo.view() if combo is not None else None
                            if view is None or not bool(view.isVisible()):
                                return True
                        except Exception:
                            return True
            except Exception:
                pass

            owner_map = getattr(self, "_combo_popup_owner_map", None)
            if isinstance(owner_map, dict) and obj in owner_map:
                combo = owner_map.get(obj)
                le = None
                try:
                    le = combo.lineEdit() if combo is not None else None
                except Exception:
                    le = None
                if le is not None:
                    try:
                        key = int(event.key())
                    except Exception:
                        key = 0
                    if key in (Qt.Key_Return, Qt.Key_Enter) and et in (QEvent.KeyPress, QEvent.ShortcutOverride):
                        return False
                    try:
                        mods = event.modifiers()
                    except Exception:
                        mods = Qt.NoModifier
                    try:
                        txt = str(event.text() or "")
                    except Exception:
                        txt = ""

                    forward = False
                    if et == QEvent.KeyPress:
                        if key in (Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End):
                            forward = True
                        elif txt:
                            forward = True
                        elif (mods & Qt.ControlModifier) and key in (
                            Qt.Key_A,
                            Qt.Key_C,
                            Qt.Key_V,
                            Qt.Key_X,
                            Qt.Key_Z,
                            Qt.Key_Y,
                        ):
                            forward = True

                    if forward:
                        try:
                            le.setFocus(Qt.OtherFocusReason)
                        except Exception:
                            pass
                        try:
                            ke = QKeyEvent(QEvent.KeyPress, key, mods, txt, bool(getattr(event, "isAutoRepeat", lambda: False)()), int(getattr(event, "count", lambda: 1)()))
                        except Exception:
                            try:
                                ke = QKeyEvent(QEvent.KeyPress, key, mods, txt)
                            except Exception:
                                ke = None
                        if ke is not None:
                            try:
                                # Use queued delivery to avoid deep re-entrancy in combo event filtering.
                                QApplication.postEvent(le, ke)
                            except Exception:
                                pass
                        return True
    except Exception:
        pass

    try:
        et_mouse = event.type()
        if et_mouse in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease) and obj in getattr(self, "_fact_combo_managed_targets", set()):
            combo = obj
            try:
                opt = QStyleOptionComboBox()
                combo.initStyleOption(opt)
                arrow_rect = combo.style().subControlRect(QStyle.CC_ComboBox, opt, QStyle.SC_ComboBoxArrow, combo)
                pos = event.pos()
                if arrow_rect.contains(pos):
                    try:
                        if hasattr(combo, "isEnabled") and (not bool(combo.isEnabled())):
                            return True
                    except Exception:
                        pass

                    # Consume press to avoid native toggle; open explicitly on release.
                    if et_mouse == QEvent.MouseButtonPress:
                        return True
                    try:
                        fn = getattr(self, "_refresh_inline_fact_dropdown", None)
                        if callable(fn):
                            fn(combo, show_popup=True)
                            return True
                    except Exception:
                        return True
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # 需求：下拉框及其展开列表不响应滚轮（既不切换选项，也不滚主区域）
    if event.type() == QEvent.Wheel and obj in self._wheel_block_targets:
        return True
    return False


def _is_descendant_of(widget, root) -> bool:
    if widget is None or root is None:
        return False
    node = widget
    for _ in range(30):
        if node is None:
            return False
        if node is root:
            return True
        try:
            node = node.parent()
        except Exception:
            return False
    return False
