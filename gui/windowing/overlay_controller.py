from __future__ import annotations

from dataclasses import dataclass
import weakref

from PySide6.QtCore import QEvent, QObject


@dataclass
class _OverlayRecord:
    name: str
    overlay: object
    owner: object


class _OverlayController(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._records: dict[str, _OverlayRecord] = {}
        self._owner_to_names: dict[object, set[str]] = {}
        self._name_to_attach_seq: dict[str, int] = {}
        self._attach_seq_counter: int = 0
        self._known_windows: weakref.WeakSet = weakref.WeakSet()
        self._modal_depth = 0

    def attach(self, name: str, overlay, owner) -> None:
        key = str(name or "").strip()
        if (not key) or overlay is None or owner is None:
            return
        self.detach(key)
        try:
            overlay.setParent(owner)
        except Exception:
            pass
        record = _OverlayRecord(name=key, overlay=overlay, owner=owner)
        self._records[key] = record
        self._attach_seq_counter += 1
        self._name_to_attach_seq[key] = int(self._attach_seq_counter)

        names = self._owner_to_names.setdefault(owner, set())
        names.add(key)
        if len(names) == 1:
            try:
                owner.installEventFilter(self)
            except Exception:
                pass

        self._remember_window(owner)
        self._relayout_record(record, reason="attach")

    def detach(self, name: str) -> None:
        key = str(name or "").strip()
        if not key:
            return
        record = self._records.pop(key, None)
        if record is None:
            return
        self._name_to_attach_seq.pop(key, None)
        owner = record.owner
        names = self._owner_to_names.get(owner)
        if names is not None:
            names.discard(key)
            if not names:
                self._owner_to_names.pop(owner, None)
                try:
                    owner.removeEventFilter(self)
                except Exception:
                    pass

    def relayout(self, name_or_all: str = "all", reason: str = "") -> None:
        key = str(name_or_all or "all").strip().lower()
        if key in ("", "all", "*"):
            items = sorted(
                list(self._records.values()),
                key=lambda rec: int(self._name_to_attach_seq.get(rec.name, -1)),
            )
        else:
            record = self._records.get(str(name_or_all))
            items = [record] if record is not None else []
        for record in items:
            self._relayout_record(record, reason=str(reason or ""))

    def set_modal_active(self, flag: bool) -> None:
        if bool(flag):
            self._modal_depth += 1
        else:
            self._modal_depth = max(0, self._modal_depth - 1)
        active = self._modal_depth > 0
        self._sync_sidebar_toggle_enabled(enabled=(not active))

    def is_modal_active(self) -> bool:
        return self._modal_depth > 0

    def reconcile_sidebar_toggle(self, window=None) -> None:
        if window is not None:
            self._remember_window(window)
        self._sync_sidebar_toggle_enabled(enabled=(not self.is_modal_active()))

    def eventFilter(self, obj, event) -> bool:
        if obj is None or event is None:
            return False
        names = self._owner_to_names.get(obj)
        if not names:
            return False

        event_type = int(event.type())
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

        if event_type in watch_types:
            ordered_names = sorted(
                list(names),
                key=lambda name: int(self._name_to_attach_seq.get(name, -1)),
            )
            for name in ordered_names:
                record = self._records.get(name)
                if record is not None:
                    self._relayout_record(record, reason="owner_event")
        elif event_type == int(QEvent.Destroy):
            for name in list(names):
                self._records.pop(name, None)
                self._name_to_attach_seq.pop(name, None)
            self._owner_to_names.pop(obj, None)
        return False

    def _relayout_record(self, record: _OverlayRecord, reason: str = "") -> None:
        _ = reason
        owner = record.owner
        overlay = record.overlay
        if owner is None or overlay is None:
            return
        try:
            overlay.setGeometry(owner.rect())
        except Exception:
            return
        try:
            overlay.raise_()
        except Exception:
            pass

    def _sync_sidebar_toggle_enabled(self, *, enabled: bool) -> None:
        windows: set[object] = set()
        for record in list(self._records.values()):
            owner = record.owner
            if owner is None:
                continue
            try:
                win = owner.window()
                if win is not None:
                    windows.add(win)
                    self._remember_window(win)
            except Exception:
                pass
        for win in list(self._known_windows):
            try:
                windows.add(win)
            except Exception:
                pass
        for win in windows:
            try:
                shell = getattr(win, "_modern_shell", None)
                toggle = getattr(shell, "sidebar_toggle", None) if shell is not None else None
                if toggle is not None:
                    toggle.setEnabled(bool(enabled))
            except Exception:
                pass

    def _remember_window(self, owner) -> None:
        if owner is None:
            return
        win = owner
        try:
            if hasattr(owner, "window"):
                _w = owner.window()
                if _w is not None:
                    win = _w
        except Exception:
            win = owner
        try:
            self._known_windows.add(win)
        except Exception:
            pass


_INSTANCE: _OverlayController | None = None


def _controller() -> _OverlayController:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _OverlayController()
    return _INSTANCE


def attach(name: str, overlay, owner) -> None:
    _controller().attach(name, overlay, owner)


def detach(name: str) -> None:
    _controller().detach(name)


def relayout(name_or_all: str = "all", reason: str = "") -> None:
    _controller().relayout(name_or_all, reason=reason)


def set_modal_active(flag: bool) -> None:
    _controller().set_modal_active(flag)


def is_modal_active() -> bool:
    return _controller().is_modal_active()


def reconcile_sidebar_toggle(window=None) -> None:
    _controller().reconcile_sidebar_toggle(window)
