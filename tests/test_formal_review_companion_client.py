import unittest
from unittest.mock import patch

from core.formal_review import companion_client
from core.formal_review.companion_client import (
    CompanionSession,
    close_session,
    connect_active_word,
    get_word_hwnd,
    open_or_attach_document,
)


class _FakeDoc:
    def __init__(self, full_name: str, name: str) -> None:
        self.FullName = full_name
        self.Name = name


class _FakeDocs:
    def __init__(self, rows):
        self._rows = list(rows)
        self.Count = len(self._rows)
        self.open_called = False
        self.opened_doc = None

    def __call__(self, index: int):
        return self._rows[int(index) - 1]

    def Open(self, target, ReadOnly=False, AddToRecentFiles=False):  # noqa: N802 - COM style
        self.open_called = True
        self.opened_doc = _FakeDoc(target, target.split("\\")[-1])
        return self.opened_doc


class _FakeApp:
    def __init__(self, docs):
        self.Documents = docs
        self.quit_called = False

    def Quit(self):  # noqa: N802 - COM style
        self.quit_called = True


class _FakeCloseableDoc:
    def __init__(self) -> None:
        self.close_called = False

    def Close(self, SaveChanges=0):  # noqa: N802 - COM style
        self.close_called = True


class _FakeWindow:
    def __init__(self, hwnd):
        self.Hwnd = hwnd


class _FakeWindowsCollection:
    def __init__(self, hwnd=None, should_raise: bool = False) -> None:
        self._hwnd = hwnd
        self._should_raise = bool(should_raise)

    def __call__(self, index: int):
        if self._should_raise:
            raise RuntimeError("windows unavailable")
        return _FakeWindow(self._hwnd)


class _FakeDocWithWindows:
    def __init__(self, hwnd=None, should_raise: bool = False) -> None:
        self.FullName = r"C:\tmp\a.docx"
        self.Name = "a.docx"
        self.Windows = _FakeWindowsCollection(hwnd=hwnd, should_raise=should_raise)


class _BrokenActiveWindow:
    @property
    def Hwnd(self):  # noqa: N802 - COM style
        raise RuntimeError("active hwnd unavailable")


class _FakeAppForHwnd:
    def __init__(self, *, active_hwnd=None, app_hwnd=None, broken_active: bool = False) -> None:
        if broken_active:
            self.ActiveWindow = _BrokenActiveWindow()
        else:
            self.ActiveWindow = _FakeWindow(active_hwnd)
        self.Hwnd = app_hwnd


class FormalReviewCompanionClientTests(unittest.TestCase):
    def test_active_app_or_dispatch_uses_shared_word_binding_helper(self) -> None:
        app = object()
        with patch.object(
            companion_client,
            "get_active_or_dispatch_word_via_com",
            return_value=(app, True, {"binding_source": "dispatch"}),
        ) as mock_resolver:
            resolved, owned = companion_client._active_app_or_dispatch()

        self.assertIs(app, resolved)
        self.assertTrue(owned)
        mock_resolver.assert_called_once_with()

    def test_connect_active_word_returns_session(self) -> None:
        app = object()
        doc = _FakeDoc(r"C:\tmp\a.docx", "a.docx")
        with patch("core.formal_review.companion_client._active_app_or_dispatch", return_value=(app, False)), patch(
            "core.formal_review.companion_client._active_document_or_raise",
            return_value=doc,
        ):
            session = connect_active_word()
        self.assertEqual(session.document_path, r"C:\tmp\a.docx")
        self.assertEqual(session.document_name, "a.docx")
        self.assertFalse(session.opened_by_tool)
        self.assertFalse(session.owned_app)

    def test_open_or_attach_reuses_existing_document(self) -> None:
        doc = _FakeDoc(r"C:\tmp\a.docx", "a.docx")
        docs = _FakeDocs([doc])
        app = _FakeApp(docs)
        with patch("core.formal_review.companion_client._active_app_or_dispatch", return_value=(app, False)), patch(
            "core.formal_review.companion_client._normalize_path",
            side_effect=lambda x: str(x),
        ):
            session = open_or_attach_document(r"C:\tmp\a.docx")
        self.assertEqual(session.document_name, "a.docx")
        self.assertFalse(docs.open_called)

    def test_open_or_attach_opens_when_not_found(self) -> None:
        doc = _FakeDoc(r"C:\tmp\other.docx", "other.docx")
        docs = _FakeDocs([doc])
        app = _FakeApp(docs)
        with patch("core.formal_review.companion_client._active_app_or_dispatch", return_value=(app, False)), patch(
            "core.formal_review.companion_client._normalize_path",
            side_effect=lambda x: str(x),
        ):
            session = open_or_attach_document(r"C:\tmp\target.docx")
        self.assertTrue(docs.open_called)
        self.assertEqual(session.document_name, "target.docx")
        self.assertTrue(session.opened_by_tool)

    def test_close_session_does_not_quit_owned_app_when_docs_remain(self) -> None:
        docs = _FakeDocs([])
        docs.Count = 1
        app = _FakeApp(docs)
        doc = _FakeCloseableDoc()
        session = CompanionSession(
            app=app,
            doc=doc,
            document_path=r"C:\tmp\src.docx",
            document_name="src.docx",
            opened_by_tool=True,
            owned_app=True,
        )
        close_session(session)
        self.assertTrue(doc.close_called)
        self.assertFalse(app.quit_called)

    def test_close_session_quits_owned_app_when_no_docs_remain(self) -> None:
        docs = _FakeDocs([])
        docs.Count = 0
        app = _FakeApp(docs)
        doc = _FakeCloseableDoc()
        session = CompanionSession(
            app=app,
            doc=doc,
            document_path=r"C:\tmp\src.docx",
            document_name="src.docx",
            opened_by_tool=True,
            owned_app=True,
        )
        close_session(session)
        self.assertTrue(doc.close_called)
        self.assertTrue(app.quit_called)

    def test_get_word_hwnd_prefers_doc_windows_hwnd_when_available(self) -> None:
        app = _FakeAppForHwnd(active_hwnd=222, app_hwnd=333)
        doc = _FakeDocWithWindows(hwnd=111, should_raise=False)
        session = CompanionSession(
            app=app,
            doc=doc,
            document_path=r"C:\tmp\a.docx",
            document_name="a.docx",
            word_hwnd=None,
            app_hwnd=None,
        )

        hwnd = get_word_hwnd(session)

        self.assertEqual(hwnd, 111)
        self.assertEqual(session.word_hwnd, 111)
        self.assertEqual(session.app_hwnd, 333)

    def test_get_word_hwnd_falls_back_to_active_window_when_doc_windows_unavailable(self) -> None:
        app = _FakeAppForHwnd(active_hwnd=222, app_hwnd=333)
        doc = _FakeDocWithWindows(hwnd=None, should_raise=True)
        session = CompanionSession(
            app=app,
            doc=doc,
            document_path=r"C:\tmp\a.docx",
            document_name="a.docx",
        )

        hwnd = get_word_hwnd(session)

        self.assertEqual(hwnd, 222)
        self.assertEqual(session.word_hwnd, 222)

    def test_get_word_hwnd_falls_back_to_app_hwnd_when_active_window_unavailable(self) -> None:
        app = _FakeAppForHwnd(active_hwnd=None, app_hwnd=333, broken_active=True)
        doc = _FakeDocWithWindows(hwnd=None, should_raise=True)
        session = CompanionSession(
            app=app,
            doc=doc,
            document_path=r"C:\tmp\a.docx",
            document_name="a.docx",
        )

        hwnd = get_word_hwnd(session)

        self.assertEqual(hwnd, 333)
        self.assertEqual(session.word_hwnd, 333)
        self.assertEqual(session.app_hwnd, 333)

    def test_get_word_hwnd_returns_none_when_all_sources_fail(self) -> None:
        app = _FakeAppForHwnd(active_hwnd=None, app_hwnd="invalid", broken_active=True)
        doc = _FakeDocWithWindows(hwnd=None, should_raise=True)
        session = CompanionSession(
            app=app,
            doc=doc,
            document_path=r"C:\tmp\a.docx",
            document_name="a.docx",
        )

        hwnd = get_word_hwnd(session)

        self.assertIsNone(hwnd)
        self.assertIsNone(session.word_hwnd)


if __name__ == "__main__":
    unittest.main()
