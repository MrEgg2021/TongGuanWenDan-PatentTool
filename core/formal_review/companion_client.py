from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.word_engine_impl.word_com_resolver import get_active_or_dispatch_word_via_com, get_active_word_via_com
from .extractor import extract_formal_review_document_from_doc


def _normalize_path(path: str) -> str:
    try:
        return str(Path(str(path or "")).resolve())
    except Exception:
        return str(path or "")


@dataclass(slots=True)
class CompanionSession:
    app: object
    doc: object
    document_path: str
    document_name: str
    word_hwnd: int | None = None
    app_hwnd: int | None = None
    opened_by_tool: bool = False
    owned_app: bool = False


@dataclass(slots=True)
class WordDocCleanState:
    saved: bool | None
    track_revisions: bool | None
    revisions_count: int | None
    comments_count: int | None
    errors: list[str]

    @property
    def is_clean(self) -> bool:
        if self.errors:
            return False
        if self.saved is not True:
            return False
        if self.track_revisions is not False:
            return False
        if int(self.revisions_count or 0) != 0:
            return False
        if int(self.comments_count or 0) != 0:
            return False
        return True


def inspect_doc_clean_state(doc) -> WordDocCleanState:
    errors: list[str] = []
    if doc is None:
        errors.append("Word 文档对象为空（doc=None）。")
        return WordDocCleanState(
            saved=None,
            track_revisions=None,
            revisions_count=None,
            comments_count=None,
            errors=errors,
        )

    saved: bool | None
    track_revisions: bool | None
    revisions_count: int | None
    comments_count: int | None

    try:
        saved = bool(getattr(doc, "Saved"))
    except Exception as exc:
        saved = None
        errors.append(f"读取 Saved 失败：{exc}")

    try:
        track_revisions = bool(getattr(doc, "TrackRevisions"))
    except Exception as exc:
        track_revisions = None
        errors.append(f"读取 TrackRevisions 失败：{exc}")

    try:
        revisions = getattr(doc, "Revisions")
        revisions_count = int(getattr(revisions, "Count"))
    except Exception as exc:
        revisions_count = None
        errors.append(f"读取 Revisions.Count 失败：{exc}")

    try:
        comments = getattr(doc, "Comments")
        comments_count = int(getattr(comments, "Count"))
    except Exception as exc:
        comments_count = None
        errors.append(f"读取 Comments.Count 失败：{exc}")

    return WordDocCleanState(
        saved=saved,
        track_revisions=track_revisions,
        revisions_count=revisions_count,
        comments_count=comments_count,
        errors=errors,
    )


def _active_app_or_dispatch() -> tuple[object, bool]:
    app, owned_app, _info = get_active_or_dispatch_word_via_com()
    return app, owned_app


def _active_document_or_raise(app):
    doc = getattr(app, "ActiveDocument", None)
    if doc is None:
        raise RuntimeError("未检测到活动 Word 文档，请先在 Word 中打开文档。")
    return doc


def _safe_int_hwnd(value) -> int | None:
    try:
        hwnd = int(value)
    except Exception:
        return None
    return hwnd if hwnd > 0 else None


def _resolve_app_hwnd(app) -> int | None:
    if app is None:
        return None
    try:
        return _safe_int_hwnd(getattr(app, "Hwnd", None))
    except Exception:
        return None


def _resolve_word_hwnd(app, doc) -> int | None:
    # Keep high-version Word behavior: doc.Windows(1).Hwnd remains first priority.
    try:
        if doc is not None:
            windows = getattr(doc, "Windows", None)
            if windows is not None:
                hwnd = _safe_int_hwnd(getattr(windows(1), "Hwnd", None))
                if hwnd:
                    return hwnd
    except Exception:
        pass

    try:
        if app is not None:
            active = getattr(app, "ActiveWindow", None)
            hwnd = _safe_int_hwnd(getattr(active, "Hwnd", None))
            if hwnd:
                return hwnd
    except Exception:
        pass

    return _resolve_app_hwnd(app)


def _session_from_doc(app, doc, *, opened_by_tool: bool, owned_app: bool) -> CompanionSession:
    hwnd = _resolve_word_hwnd(app, doc)
    app_hwnd = _resolve_app_hwnd(app)
    return CompanionSession(
        app=app,
        doc=doc,
        document_path=str(getattr(doc, "FullName", "") or ""),
        document_name=str(getattr(doc, "Name", "") or ""),
        word_hwnd=hwnd,
        app_hwnd=app_hwnd,
        opened_by_tool=bool(opened_by_tool),
        owned_app=bool(owned_app),
    )


def normalize_word_window(session: CompanionSession) -> bool:
    if session is None:
        return False
    app = getattr(session, "app", None)
    doc = getattr(session, "doc", None)
    if app is None or doc is None:
        return False
    ok = False
    try:
        app.Visible = True
        ok = True
    except Exception:
        pass
    try:
        doc.Activate()
        ok = True
    except Exception:
        pass
    try:
        wnd = app.ActiveWindow
        if wnd is not None:
            # wdPrintView = 3
            wnd.View.Type = 3
            ok = True
            zoom_obj = None
            try:
                zoom_obj = getattr(wnd.View, "Zoom", None)
            except Exception:
                zoom_obj = None
            if zoom_obj is not None:
                page_fit_applied = False
                for page_fit in (2, 1):
                    try:
                        zoom_obj.PageFit = int(page_fit)
                        page_fit_applied = True
                        ok = True
                        break
                    except Exception:
                        continue
                if not page_fit_applied:
                    try:
                        current_percent = int(getattr(zoom_obj, "Percentage", 100) or 100)
                    except Exception:
                        current_percent = 100
                    target_percent = max(70, min(95, int(current_percent)))
                    try:
                        zoom_obj.Percentage = int(target_percent)
                        ok = True
                    except Exception:
                        pass
    except Exception:
        pass
    try:
        ribbon = app.CommandBars("Ribbon")
        if ribbon is not None:
            ribbon.Visible = True
            ok = True
    except Exception:
        pass
    try:
        app.DisplayStatusBar = True
    except Exception:
        pass
    return bool(ok)


def connect_active_word() -> CompanionSession:
    app, owned_app = _active_app_or_dispatch()
    doc = _active_document_or_raise(app)
    session = _session_from_doc(app, doc, opened_by_tool=False, owned_app=owned_app)
    normalize_word_window(session)
    return session


def open_or_attach_document(path: str) -> CompanionSession:
    target = _normalize_path(path)
    if not target:
        raise RuntimeError("文档路径为空，无法连接。")

    app, owned_app = _active_app_or_dispatch()
    docs = getattr(app, "Documents", None)
    if docs is None:
        raise RuntimeError("当前 Word 实例不可用（Documents 不可访问）。")

    for i in range(1, int(docs.Count) + 1):
        item = docs(i)
        item_path = _normalize_path(str(getattr(item, "FullName", "") or ""))
        if item_path == target:
            session = _session_from_doc(app, item, opened_by_tool=False, owned_app=owned_app)
            normalize_word_window(session)
            return session

    opened = docs.Open(target, ReadOnly=False, AddToRecentFiles=False)
    session = _session_from_doc(app, opened, opened_by_tool=True, owned_app=owned_app)
    normalize_word_window(session)
    return session


def get_document_snapshot(session: CompanionSession):
    return extract_formal_review_document_from_doc(session.doc)


def get_dirty_state(session: CompanionSession) -> bool:
    # Word: Saved=False 表示文档存在未保存修改。
    return not bool(getattr(session.doc, "Saved", True))


def get_word_hwnd(session: CompanionSession) -> int | None:
    if session is None:
        return None
    cached = getattr(session, "word_hwnd", None)
    if cached:
        return int(cached)

    app = getattr(session, "app", None)
    doc = getattr(session, "doc", None)
    hwnd = _resolve_word_hwnd(app, doc)
    app_hwnd = _resolve_app_hwnd(app)

    try:
        session.word_hwnd = hwnd
    except Exception:
        pass
    try:
        session.app_hwnd = app_hwnd
    except Exception:
        pass
    return hwnd


def detect_unsaved_source(path: str) -> bool:
    target = _normalize_path(path)
    if not target:
        return False
    try:
        app, _info = get_active_word_via_com()
    except Exception:
        return False
    docs = getattr(app, "Documents", None)
    if docs is None:
        return False
    try:
        total = int(getattr(docs, "Count", 0) or 0)
    except Exception:
        total = 0
    for idx in range(1, total + 1):
        try:
            row = docs(idx)
        except Exception:
            continue
        row_path = _normalize_path(str(getattr(row, "FullName", "") or ""))
        if row_path != target:
            continue
        try:
            return not bool(getattr(row, "Saved", True))
        except Exception:
            return False
    return False


def activate_word_window(session: CompanionSession) -> bool:
    hwnd = get_word_hwnd(session)
    if not hwnd:
        return False
    try:
        import win32con
        import win32gui

        try:
            win32gui.ShowWindow(int(hwnd), int(win32con.SW_RESTORE))
        except Exception:
            pass
        win32gui.SetForegroundWindow(int(hwnd))
        return True
    except Exception:
        pass
    try:
        app = getattr(session, "app", None)
        if app is not None:
            app.Activate()
            return True
    except Exception:
        pass
    return False


def close_session(session: CompanionSession) -> None:
    if session is None:
        return
    try:
        if bool(getattr(session, "opened_by_tool", False)) and getattr(session, "doc", None) is not None:
            session.doc.Close(SaveChanges=0)
    except Exception:
        pass
    try:
        if bool(getattr(session, "owned_app", False)) and getattr(session, "app", None) is not None:
            docs = getattr(session.app, "Documents", None)
            remaining = int(getattr(docs, "Count", 0) or 0) if docs is not None else 0
            if remaining <= 0:
                session.app.Quit()
    except Exception:
        pass
