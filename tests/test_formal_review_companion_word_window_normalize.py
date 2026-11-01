import unittest

from core.formal_review.companion_client import normalize_word_window


class _FakeView:
    def __init__(self) -> None:
        self.Type = None
        self.Zoom = _FakeZoom()


class _FakeZoom:
    def __init__(self) -> None:
        self.PageFit = None
        self.Percentage = 100


class _FakeWindow:
    def __init__(self) -> None:
        self.View = _FakeView()


class _FakeRibbon:
    def __init__(self) -> None:
        self.Visible = False


class _FakeApp:
    def __init__(self) -> None:
        self.Visible = False
        self.ActiveWindow = _FakeWindow()
        self.DisplayStatusBar = False
        self._ribbon = _FakeRibbon()

    def CommandBars(self, name):  # noqa: N802
        if name == "Ribbon":
            return self._ribbon
        raise KeyError(name)


class _FakeDoc:
    def __init__(self) -> None:
        self.activated = False

    def Activate(self):  # noqa: N802
        self.activated = True


class _FakeSession:
    def __init__(self) -> None:
        self.app = _FakeApp()
        self.doc = _FakeDoc()


class FormalReviewCompanionWordWindowNormalizeTests(unittest.TestCase):
    def test_normalize_word_window_sets_visible_print_view_and_ribbon(self) -> None:
        session = _FakeSession()
        ok = normalize_word_window(session)
        self.assertTrue(ok)
        self.assertTrue(session.app.Visible)
        self.assertTrue(session.doc.activated)
        self.assertEqual(session.app.ActiveWindow.View.Type, 3)
        self.assertIn(session.app.ActiveWindow.View.Zoom.PageFit, {1, 2})
        self.assertTrue(session.app.CommandBars("Ribbon").Visible)
        self.assertTrue(session.app.DisplayStatusBar)


if __name__ == "__main__":
    unittest.main()
