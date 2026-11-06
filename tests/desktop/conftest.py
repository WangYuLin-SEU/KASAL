"""Shared native-window lifecycle; tests use only temporary data and preferences."""
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from kasal.studio.theme import STYLE
from kasal.studio.window import StudioWindow


@pytest.fixture(scope='session')
def qt_app():
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    yield app


class Desktop:
    def __init__(self, app, work):
        self.app, self.work, self.window = app, work, None
        self.settings = QSettings(str(work / 'preferences.ini'), QSettings.Format.IniFormat)

    def events(self):
        self.app.processEvents()
        QTest.qWait(30)

    def wait(self, predicate, timeout=120):
        deadline = time.monotonic() + timeout
        while not predicate():
            self.events()
            assert time.monotonic() < deadline, 'Desktop operation timed out'
        self.events()

    def open(self, path):
        if self.window is None:
            self.window = StudioWindow(path, settings=self.settings)
            self.window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            self.window.show()
        else:
            self.window.open_path(path)
        self.events()
        return self.window

    def camera(self):
        c = self.window.view.renderer.GetActiveCamera()
        return (*c.GetPosition(), *c.GetFocalPoint(), *c.GetViewUp(),
                c.GetParallelScale(), c.GetParallelProjection())

    def export(self, destination):
        destination.mkdir()

        def choose(dialog):
            dialog.setDirectory(str(destination))
            dialog.accept()

        self.modal(self.window.export_result, choose)

    def modal(self, action, respond):
        """Drive a real dialog; callback assertions propagate instead of hanging Qt."""
        errors, visited = [], []

        def answer():
            dialog = self.app.activeModalWidget()
            try:
                assert dialog is not None, 'Expected a modal dialog'
                visited.append(dialog)
                respond(dialog)
            except BaseException as exc:
                errors.append(exc)
            finally:
                if dialog is not None and dialog.isVisible():
                    dialog.reject()

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(answer)
        timer.start(80)
        try:
            action()
        finally:
            timer.stop()
        assert visited, 'The action did not open a dialog'
        if errors:
            raise errors[0]
        self.events()

    def close(self):
        w = self.window
        if w is None:
            return
        if w.runner.busy:
            w.cancel_jobs()
            self.wait(lambda: not w.runner.busy, timeout=15)
        # Let queued layout/scroll callbacks finish before destroying their widgets.
        self.events()
        for record in w.records:
            record.edited = False
        w.close()
        self.app.removeTranslator(w.localizer.translator)
        self.window = None
        w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.events()


@pytest.fixture
def desktop(qt_app, tmp_path):
    ui = Desktop(qt_app, tmp_path)
    try:
        yield ui
    finally:
        ui.close()
