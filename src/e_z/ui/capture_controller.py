"""Ocultação e restauração de janelas no event loop gráfico Qt."""

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from e_z.application.capture import CaptureResult, CaptureStatus


class CaptureController(QObject):
    finished = Signal(object)
    busy_changed = Signal(bool)

    def __init__(self, backend, parent=None, *, delay_ms=250, timeout_ms=125_000) -> None:
        super().__init__(parent)
        self.backend = backend
        self.busy = False
        self._generation = 0
        self._windows = []
        self._request = None
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(delay_ms)
        self._delay.timeout.connect(self._capture)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.setInterval(timeout_ms)
        self._deadline.timeout.connect(self._timeout)

    def start(self, request) -> bool:
        if self.busy:
            return False
        self._generation += 1
        self.busy = True
        self._request = request
        self._windows = []
        app = QApplication.instance()
        self._quit_on_close = app.quitOnLastWindowClosed()
        app.setQuitOnLastWindowClosed(False)
        try:
            self.busy_changed.emit(True)
            for window in app.topLevelWidgets():
                if window.isVisible():
                    self._windows.append((window, window.windowState()))
                    window.hide()
            self._deadline.start()
            self._delay.start()
        except Exception:
            self._finish(CaptureResult(CaptureStatus.FAILED, message="Não foi possível preparar as janelas para captura."))
        return True

    def _capture(self) -> None:
        generation = self._generation
        if not self.busy:
            return
        try:
            self.backend.capture(self._request, lambda result: self._receive(generation, result))
        except Exception:
            self._finish(CaptureResult(CaptureStatus.FAILED, message="Não foi possível concluir a captura."))

    def _receive(self, generation, result) -> None:
        if generation == self._generation:
            self._finish(result)

    def cancel(self) -> None:
        if self.busy:
            self._generation += 1
            try:
                self.backend.cancel()
            except Exception:
                pass
            finally:
                self._finish(CaptureResult(CaptureStatus.CANCELLED, message="Captura cancelada."))

    def _timeout(self) -> None:
        if self.busy:
            # Invalidar callback antes de pedir Close ao adaptador.
            self._generation += 1
            try:
                self.backend.cancel()
            except Exception:
                pass
            finally:
                self._finish(CaptureResult(CaptureStatus.FAILED, message="A captura não respondeu no tempo esperado."))

    def _finish(self, result) -> None:
        if not self.busy:
            return
        self._delay.stop()
        self._deadline.stop()
        self._request = None
        try:
            for window, state in self._windows:
                try:
                    window.setWindowState(state)
                    window.show()
                except RuntimeError:
                    # Uma janela pode ter sido destruída enquanto o portal estava aberto.
                    continue
        finally:
            self._windows = []
            QApplication.instance().setQuitOnLastWindowClosed(self._quit_on_close)
            self.busy = False
            self.busy_changed.emit(False)
            self.finished.emit(result)
