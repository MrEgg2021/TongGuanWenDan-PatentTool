from __future__ import annotations

from PySide6.QtCore import QRect, QTimer
from PySide6.QtWidgets import QWidget


def _apply_target_geometry(self, target: QWidget | None) -> None:
    if target is None:
        return

    try:
        self.setGeometry(QRect(target.rect()))
    except Exception:
        try:
            self.setGeometry(target.rect())
        except Exception:
            pass

    try:
        card = getattr(self, "_card", None)
        if card is None:
            return
        try:
            tw = int(target.size().width())
            th = int(target.size().height())
        except Exception:
            tw = 0
            th = 0

        w = 760
        h = 680
        if tw > 0:
            desired_w = int(tw * 0.97)
            max_w = max(420, tw - 40)
            w = min(desired_w, max_w)
            w = max(420, w)

        if th > 0:
            desired_h = max(520, int(th * 0.97))
            max_h = max(420, th - 40)
            h = min(desired_h, max_h)
            h = max(420, h)

        card.setFixedSize(int(w), int(h))
    except Exception:
        pass


def _sync_from_target(self) -> None:
    try:
        self._pending_resize_sync = False
    except Exception:
        pass
    target = getattr(self, "_size_target", None)
    if target is None:
        return
    self._apply_target_geometry(target)


def _schedule_sync_from_target(self) -> None:
    try:
        if bool(getattr(self, "_pending_resize_sync", False)):
            return
        self._pending_resize_sync = True
    except Exception:
        return
    try:
        QTimer.singleShot(0, self._sync_from_target)
    except Exception:
        pass
