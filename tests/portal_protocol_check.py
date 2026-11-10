"""Protocolo QtDBus real em barramento privado, sem compositor ou tela real.

Executar: dbus-run-session -- .venv/bin/python tests/portal_protocol_check.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import ClassInfo, QCoreApplication, QEventLoop, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtDBus import QDBusConnection, QDBusObjectPath, QDBusVariant

from true_screen.application.capture import CaptureRequest, CaptureStatus
from true_screen.domain.document import SourceImage
from true_screen.imaging.images import image_from_source
from true_screen.platform.linux_wayland import DESKTOP_PATH, REQUEST, SCREENSHOT, SERVICE, QtPortalTransport, WaylandCaptureBackend


@ClassInfo(**{"D-Bus Interface": REQUEST})
class FakeRequest(QObject):
    Response = Signal("uint", "QVariantMap")
    def __init__(self, parent):
        super().__init__(parent)
        self.closed = 0

    @Slot()
    def Close(self):
        self.closed += 1


@ClassInfo(**{"D-Bus Interface": SCREENSHOT})
class FakePortal(QObject):
    def __init__(self, bus, uri):
        super().__init__()
        self.bus = bus
        self.uri = uri
        self.mode = "success"
        self.requests = []
        self.options = []

    @Slot(str, "QVariantMap", result="QDBusObjectPath")
    def Screenshot(self, parent, options):
        options = {key: value.variant() if isinstance(value, QDBusVariant) else value for key, value in options.items()}
        assert parent == ""
        assert options["interactive"] is True
        self.options.append(options)
        sender = self.bus.baseService().lstrip(":").replace(".", "_")
        path = f"{DESKTOP_PATH}/request/{sender}/{options['handle_token']}"
        if self.mode == "legacy":
            path += "_legacy"
        request = FakeRequest(self)
        assert self.bus.registerObject(path, request, QDBusConnection.RegisterOption.ExportAllSlots | QDBusConnection.RegisterOption.ExportAllSignals)
        self.requests.append(request)
        mode = self.mode

        def respond():
            code = {"cancel": 1, "failure": 2}.get(mode, 0)
            uri = "https://example.com/ficticio.png" if mode == "bad_uri" else self.uri
            request.Response.emit(code, {"uri": uri})

        if mode == "early":
            respond()
        elif mode != "timeout":
            QTimer.singleShot(10, respond)
        return QDBusObjectPath(path)


class NoActivationBus:
    """Evita que o teste acione serviços instalados quando o fictício sai."""

    def __init__(self, bus):
        self.bus = bus

    def __getattr__(self, name):
        return getattr(self.bus, name)

    def asyncCall(self, message, timeout):
        message.setAutoStartService(False)
        return self.bus.asyncCall(message, timeout)


def check():
    app = QCoreApplication([])
    bus = QDBusConnection.sessionBus()
    assert bus.isConnected(), "Execute este script dentro de dbus-run-session"
    assert bus.registerService(SERVICE)
    with TemporaryDirectory(prefix="true-screen-portal-") as directory:
        path = Path(directory) / "imagem ficticia.png"
        source = SourceImage(3, 2, bytes([12, 34, 56, 255]) * 6)
        assert image_from_source(source).save(str(path), "PNG")
        portal = FakePortal(bus, QUrl.fromLocalFile(str(path)).toString())
        assert bus.registerObject(DESKTOP_PATH, portal, QDBusConnection.RegisterOption.ExportAllSlots)
        for mode, expected in (("success", CaptureStatus.SUCCESS), ("early", CaptureStatus.SUCCESS),
                               ("legacy", CaptureStatus.SUCCESS), ("cancel", CaptureStatus.CANCELLED),
                               ("failure", CaptureStatus.FAILED), ("bad_uri", CaptureStatus.FAILED),
                               ("timeout", CaptureStatus.FAILED), ("abort", CaptureStatus.CANCELLED)):
            portal.mode = "timeout" if mode == "abort" else mode
            transport = QtPortalTransport(bus=NoActivationBus(bus), timeout_ms=50 if mode == "timeout" else 1000)
            backend = WaylandCaptureBackend(transport)
            results = []
            loop = QEventLoop()

            def received(result):
                results.append(result)
                loop.quit()

            backend.capture(CaptureRequest(), received)
            if mode == "abort":
                QTimer.singleShot(15, backend.cancel)
            QTimer.singleShot(2000, loop.quit)
            loop.exec()
            assert len(results) == 1 and results[0].status is expected, (mode, results)
            if expected is CaptureStatus.SUCCESS:
                assert results[0].image == source
            if mode in ("timeout", "abort"):
                # Esperar entrega da chamada Close sem tocar no barramento da sessão real.
                wait = QEventLoop()
                QTimer.singleShot(20, wait.quit)
                wait.exec()
                assert portal.requests[-1].closed >= 1
            assert path.exists(), "O arquivo fornecido pelo portal não pertence ao aplicativo"
            transport.deleteLater()
            app.processEvents()
        assert len({options["handle_token"] for options in portal.options}) == len(portal.options)
        bus.unregisterService(SERVICE)
        transport = QtPortalTransport(bus=NoActivationBus(bus))
        backend = WaylandCaptureBackend(transport)
        loop = QEventLoop()
        results = []
        backend.capture(CaptureRequest(), lambda result: (results.append(result), loop.quit()))
        QTimer.singleShot(2000, loop.quit)
        loop.exec()
        assert len(results) == 1 and results[0].status is CaptureStatus.UNAVAILABLE
    print("9 cenários de protocolo passaram: sucesso, resposta antecipada, handle alternativo, cancelamento, falha, URI inválida, timeout, Close e serviço ausente.")


if __name__ == "__main__":
    check()
