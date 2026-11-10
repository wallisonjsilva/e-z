"""Portal Screenshot por QtDBus, com consentimento e ciclo de Request."""

from uuid import uuid4

from PySide6.QtCore import QObject, QTimer, QUrl, SLOT, Slot
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher, QDBusVariant

from true_screen.application.capture import CaptureCapabilities, CaptureResult, CaptureStatus
from true_screen.imaging.images import load_image
from true_screen.imaging.tasks import TaskRunner

SERVICE = "org.freedesktop.portal.Desktop"
DESKTOP_PATH = "/org/freedesktop/portal/desktop"
SCREENSHOT = "org.freedesktop.portal.Screenshot"
REQUEST = "org.freedesktop.portal.Request"


def dbus_error_status(name: str) -> CaptureStatus:
    if name in ("org.freedesktop.portal.Error.NotAllowed", "org.freedesktop.DBus.Error.AccessDenied"):
        return CaptureStatus.DENIED
    if name in ("org.freedesktop.DBus.Error.ServiceUnknown", "org.freedesktop.DBus.Error.NameHasNoOwner",
                "org.freedesktop.DBus.Error.UnknownInterface", "org.freedesktop.DBus.Error.UnknownMethod",
                "org.freedesktop.DBus.Error.Disconnected", "org.freedesktop.portal.Error.NotFound"):
        return CaptureStatus.UNAVAILABLE
    return CaptureStatus.FAILED


def local_screenshot_path(uri: str) -> str:
    if not isinstance(uri, str) or not uri or len(uri) > 16_384:
        raise ValueError("O portal não forneceu uma imagem local válida.")
    url = QUrl(uri)
    if (not url.isValid() or url.scheme() != "file" or not url.isLocalFile() or url.host()
            or url.hasQuery() or url.hasFragment() or not url.path().startswith("/")):
        raise ValueError("O portal não forneceu uma imagem local válida.")
    path = url.toLocalFile()
    if "\x00" in path:
        raise ValueError("O portal não forneceu uma imagem local válida.")
    return path


class QtPortalTransport(QObject):
    def __init__(self, parent=None, *, bus=None, timeout_ms=120_000) -> None:
        super().__init__(parent)
        self.bus = bus if bus is not None else QDBusConnection.sessionBus()
        self._callback = None
        self._path = ""
        self._watcher = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(timeout_ms)
        self._timer.timeout.connect(self._timed_out)

    def available(self) -> bool:
        return self.bus.isConnected()

    def start(self, callback) -> None:
        if self._callback is not None:
            callback(CaptureStatus.FAILED, "")
            return
        if not self.available():
            callback(CaptureStatus.UNAVAILABLE, "")
            return
        self._callback = callback
        token = "true_screen_" + uuid4().hex
        sender = self.bus.baseService().lstrip(":").replace(".", "_")
        self._path = f"{DESKTOP_PATH}/request/{sender}/{token}"
        if not self._subscribe(self._path):
            self._finish(CaptureStatus.UNAVAILABLE)
            return
        message = QDBusMessage.createMethodCall(SERVICE, DESKTOP_PATH, SCREENSHOT, "Screenshot")
        message.setArguments(["", {"handle_token": QDBusVariant(token), "interactive": QDBusVariant(True),
                                   "modal": QDBusVariant(False)}])
        self._watcher = QDBusPendingCallWatcher(self.bus.asyncCall(message, 10_000), self)
        self._watcher.finished.connect(self._method_finished)
        self._timer.start()

    def _subscribe(self, path: str) -> bool:
        return self.bus.connect(SERVICE, path, REQUEST, "Response", self, SLOT("_response(uint,QVariantMap,QDBusMessage)"))

    def _unsubscribe(self, path: str) -> None:
        self.bus.disconnect(SERVICE, path, REQUEST, "Response", self, SLOT("_response(uint,QVariantMap,QDBusMessage)"))

    def _valid_handle(self, path) -> bool:
        sender = self.bus.baseService().lstrip(":").replace(".", "_")
        prefix = f"{DESKTOP_PATH}/request/{sender}/"
        return isinstance(path, str) and len(path) <= 512 and path.startswith(prefix) and bool(path[len(prefix):]) and "/" not in path[len(prefix):]

    def _method_finished(self, watcher) -> None:
        reply = watcher.reply()
        arguments = reply.arguments()
        handle = arguments[0].path() if arguments and hasattr(arguments[0], "path") else None
        active = watcher is self._watcher and self._callback is not None
        watcher.deleteLater()
        if not active:
            if self._valid_handle(handle):
                self._close(handle)
            return
        self._watcher = None
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            self._finish(dbus_error_status(reply.errorName()))
        elif not self._valid_handle(handle):
            self._close(self._path)
            self._finish(CaptureStatus.FAILED)
        elif handle != self._path:
            previous = self._path
            self._path = handle
            if not self._subscribe(handle):
                self._close(handle)
                self._unsubscribe(previous)
                self._finish(CaptureStatus.FAILED)
                return
            self._unsubscribe(previous)

    @Slot("uint", "QVariantMap", QDBusMessage)
    def _response(self, code, values, message) -> None:
        if self._callback is None or message.path() != self._path:
            return
        try:
            if type(code) is not int or not isinstance(values, dict):
                raise ValueError("Resposta inválida do portal.")
            if code == 0:
                uri = values.get("uri", "")
                uri = uri.variant() if isinstance(uri, QDBusVariant) else uri
                local_screenshot_path(uri)
                self._finish(CaptureStatus.SUCCESS, uri)
            elif code == 1:
                self._finish(CaptureStatus.CANCELLED)
            else:
                self._finish(CaptureStatus.FAILED)
        except (ValueError, TypeError, RuntimeError):
            self._finish(CaptureStatus.FAILED)

    def _close(self, path: str) -> None:
        if path:
            self.bus.asyncCall(QDBusMessage.createMethodCall(SERVICE, path, REQUEST, "Close"), 1000)

    def cancel(self) -> None:
        if self._callback is not None:
            self._close(self._path)
            self._finish(CaptureStatus.CANCELLED)

    def _timed_out(self) -> None:
        self._close(self._path)
        self._finish(CaptureStatus.FAILED)

    def _finish(self, status, uri="") -> None:
        callback, self._callback = self._callback, None
        self._timer.stop()
        if self._path:
            self._unsubscribe(self._path)
        self._path = ""
        self._watcher = None
        if callback is not None:
            callback(status, uri)


class WaylandCaptureBackend:
    def __init__(self, transport=None, *, runner=None) -> None:
        self.transport = transport if transport is not None else QtPortalTransport()
        self.runner = runner if runner is not None else TaskRunner()
        self._generation = 0
        self._pending_callback = None

    def capabilities(self) -> CaptureCapabilities:
        available = self.transport.available()
        return CaptureCapabilities(available, portal=True, message=(
            "Captura Wayland via portal; seleção e permissão serão solicitadas pelo sistema." if available else
            "Portal Wayland indisponível: sem conexão D-Bus. Use Abrir ou Colar."))

    def capture(self, request, callback) -> None:
        if self._pending_callback is not None:
            callback(CaptureResult(CaptureStatus.FAILED, message="Há outra captura em andamento."))
            return
        self._generation += 1
        generation = self._generation
        self._pending_callback = callback

        def deliver(result):
            if generation == self._generation and self._pending_callback is callback:
                self._pending_callback = None
                callback(result)

        def completed(image):
            if generation == self._generation:
                deliver(CaptureResult(CaptureStatus.SUCCESS, image))

        def failed(error):
            if generation == self._generation:
                deliver(CaptureResult(CaptureStatus.FAILED, message=error.message))

        def received(status, uri):
            if generation != self._generation:
                return
            if status is CaptureStatus.SUCCESS:
                try:
                    path = local_screenshot_path(uri)
                    if not self.runner.submit(lambda: load_image(path, resident_bytes=request.resident_bytes), completed, failed):
                        deliver(CaptureResult(CaptureStatus.FAILED, message="Há outra operação de imagem em andamento."))
                    return
                except (ValueError, MemoryError, RuntimeError):
                    status = CaptureStatus.FAILED
            messages = {
                CaptureStatus.CANCELLED: "Captura cancelada.",
                CaptureStatus.UNAVAILABLE: "Captura via portal indisponível. Use Abrir ou Colar.",
                CaptureStatus.DENIED: "A permissão de captura foi negada pelo sistema.",
                CaptureStatus.FAILED: "Não foi possível concluir a captura via portal.",
            }
            deliver(CaptureResult(status, message=messages.get(status, "Falha na captura.")))

        try:
            self.transport.start(received)
        except Exception:
            deliver(CaptureResult(CaptureStatus.FAILED, message="Não foi possível iniciar a captura via portal."))

    def cancel(self) -> None:
        callback, self._pending_callback = self._pending_callback, None
        self._generation += 1
        try:
            self.transport.cancel()
        except Exception:
            pass
        if callback is not None:
            callback(CaptureResult(CaptureStatus.CANCELLED, message="Captura cancelada."))
