"""Executor Qt de imagens; sem widgets ou dependências da UI."""

from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot

from e_z.domain.errors import ValidationError


@dataclass(frozen=True)
class TaskError:
    message: str


def public_error(error: Exception) -> TaskError:
    if isinstance(error, MemoryError):
        return TaskError("Memória insuficiente para concluir a operação.")
    if isinstance(error, ValidationError):
        # Validadores do aplicativo fornecem mensagens públicas sem dados de entrada.
        return TaskError(str(error))
    return TaskError("Não foi possível concluir a operação. Tente novamente.")


class _Signals(QObject):
    finished = Signal(object, object)


class _Job(QRunnable):
    def __init__(self, operation) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _Signals()

    def run(self) -> None:
        value, error = None, None
        try:
            value = self.operation()
        except Exception as failure:
            error = public_error(failure)
        finally:
            # Não reter entradas QImage/bytes grandes na closure do worker.
            self.operation = None
        self.signals.finished.emit(value, error)


class TaskRunner(QObject):
    busy_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.busy = False
        self._job = None
        self._success = self._failure = None

    def submit(self, operation, success, failure) -> bool:
        if self.busy:
            return False
        try:
            job = _Job(operation)
        except Exception as error:
            failure(public_error(error))
            return False
        self.busy = True
        self._success, self._failure = success, failure
        self._job = job
        self._job.signals.finished.connect(self._completed, Qt.ConnectionType.QueuedConnection)
        self.busy_changed.emit(True)
        try:
            self.pool.start(self._job)
        except Exception as error:
            self._completed(None, public_error(error))
            return False
        return True

    @Slot(object, object)
    def _completed(self, value, error) -> None:
        success, failure = self._success, self._failure
        self._success = self._failure = self._job = None
        self.busy = False
        self.busy_changed.emit(False)
        if error is None:
            success(value)
        else:
            failure(error)
