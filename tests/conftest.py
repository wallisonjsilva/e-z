"""Fixtures Qt locais; não homologam clipboard ou DPI nativos."""

import os

import pytest
from PySide6.QtCore import QObject, Signal

from true_screen.imaging.tasks import public_error


class ImmediateRunner(QObject):
    """Somente para regressão funcional; afinidade é testada com TaskRunner real."""
    busy_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.busy = False

    def submit(self, operation, success, failure):
        if self.busy:
            return False
        self.busy = True
        self.busy_changed.emit(True)
        try:
            result = operation()
        except Exception as error:
            self.busy = False
            self.busy_changed.emit(False)
            failure(public_error(error))
            return False
        self.busy = False
        self.busy_changed.emit(False)
        return success(result) is not False


@pytest.fixture(scope="session")
def qt_app():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def immediate_runner(qt_app):
    return ImmediateRunner()


@pytest.fixture
def window(qt_app, immediate_runner):
    from true_screen.ui.main_window import MainWindow

    widget = MainWindow(runner=immediate_runner)
    yield widget
    widget.session.dirty = False
    widget.close()
    widget.deleteLater()
    qt_app.processEvents()
