"""W08: contratos, sessão, adaptadores e restauração, sem tela real."""

import pytest
from PySide6.QtCore import QEventLoop, QSize, QTimer, QUrl, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from true_screen.application.capture import CaptureCapabilities, CaptureRequest, CaptureResult, CaptureStatus
from true_screen.domain.document import SourceImage
from true_screen.domain.geometry import MAX_BUFFER_BYTES
from true_screen.imaging.images import image_from_source
from true_screen.platform.capture import UnavailableCaptureBackend, detect_session
from true_screen.platform.linux_wayland import WaylandCaptureBackend, dbus_error_status, local_screenshot_path
from true_screen.platform.linux_x11 import X11CaptureBackend
from true_screen.platform import dialogs
from true_screen.ui.capture_controller import CaptureController


@pytest.fixture(autouse=True)
def immediate_capture_workers(monkeypatch, immediate_runner):
    from true_screen.platform import linux_wayland, linux_x11
    monkeypatch.setattr(linux_wayland, "TaskRunner", lambda: immediate_runner)
    monkeypatch.setattr(linux_x11, "TaskRunner", lambda: immediate_runner)


def source(width=3, height=2):
    return SourceImage(width, height, bytes([12, 34, 56, 255]) * width * height)


def wait_for(test, *, timeout=500):
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(1)
    timer.timeout.connect(lambda: loop.quit() if test() else None)
    timer.start()
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    deadline.start(timeout)
    loop.exec()
    assert test(), "Condição não alcançada dentro do prazo do teste"


@pytest.mark.parametrize("environment,plugin,system,expected", [
    ({"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}, "xcb", "linux", "wayland"),
    ({"WAYLAND_DISPLAY": "wayland-ficticio", "DISPLAY": ":0"}, "xcb", "linux", "wayland"),
    ({}, "wayland", "linux", "wayland"),
    ({"XDG_SESSION_TYPE": "x11"}, "xcb", "linux", "x11"),
    ({"DISPLAY": ":0"}, "xcb", "linux", "unavailable"),
    ({"XDG_SESSION_TYPE": "wayland"}, "offscreen", "linux", "unavailable"),
    ({"XDG_SESSION_TYPE": "x11"}, "minimal", "linux", "unavailable"),
    ({"XDG_SESSION_TYPE": "x11"}, "windows", "win32", "unavailable"),
])
def test_detect_session_does_not_bypass_wayland(environment, plugin, system, expected):
    assert detect_session(environment, plugin, system) == expected


@pytest.mark.parametrize("uri", ["https://example.com/imagem.png", "file://servidor/imagem.png",
                                 "file:///tmp/imagem.png?x=1", "file:///tmp/imagem.png#fragmento",
                                 "file:relativo.png", "", None, "file:///tmp/%00.png", "x" * 16385])
def test_portal_rejects_nonlocal_or_invalid_uri(uri):
    with pytest.raises(ValueError):
        local_screenshot_path(uri)


def test_portal_accepts_encoded_local_path(tmp_path):
    path = tmp_path / "imagem fictícia.png"
    assert local_screenshot_path(QUrl.fromLocalFile(str(path)).toString()) == str(path)


@pytest.mark.parametrize("name,expected", [
    ("org.freedesktop.portal.Error.NotAllowed", CaptureStatus.DENIED),
    ("org.freedesktop.DBus.Error.AccessDenied", CaptureStatus.DENIED),
    ("org.freedesktop.DBus.Error.ServiceUnknown", CaptureStatus.UNAVAILABLE),
    ("org.freedesktop.DBus.Error.UnknownMethod", CaptureStatus.UNAVAILABLE),
    ("org.freedesktop.portal.Error.Failed", CaptureStatus.FAILED),
])
def test_typed_dbus_errors(name, expected):
    assert dbus_error_status(name) is expected


class FakeTransport:
    def __init__(self, status, uri="", available=True):
        self.status, self.uri, self.ready = status, uri, available

    def available(self):
        return self.ready

    def start(self, callback):
        callback(self.status, self.uri)

    def cancel(self):
        pass


def test_wayland_reads_authorized_file_preserves_file_and_uses_limits(tmp_path):
    path = tmp_path / "portal.png"
    assert image_from_source(source()).save(str(path), "PNG")
    backend = WaylandCaptureBackend(FakeTransport(CaptureStatus.SUCCESS, QUrl.fromLocalFile(str(path)).toString()))
    results = []
    backend.capture(CaptureRequest(), results.append)
    assert results[0].image == source()
    assert results[0].scale is None
    assert path.exists()
    backend.capture(CaptureRequest(resident_bytes=MAX_BUFFER_BYTES), results.append)
    assert results[1].status is CaptureStatus.FAILED and results[1].image is None
    assert str(path) not in results[1].message


@pytest.mark.parametrize("status", [CaptureStatus.CANCELLED, CaptureStatus.UNAVAILABLE, CaptureStatus.DENIED, CaptureStatus.FAILED])
def test_wayland_non_success_statuses_are_preserved(status):
    backend = WaylandCaptureBackend(FakeTransport(status))
    result = []
    backend.capture(CaptureRequest(), result.append)
    assert result[0].status is status and result[0].image is None
    assert result[0].message


class FakeScreen:
    def __init__(self, scale=2, *, empty=False, logical_width=10):
        self.scale, self.empty, self.logical_width = scale, empty, logical_width
        self.calls = 0

    def size(self):
        return QSize(self.logical_width, 10)

    def devicePixelRatio(self):
        return self.scale

    def grabWindow(self, window):
        assert window == 0
        self.calls += 1
        if self.empty:
            return QPixmap()
        result = QPixmap.fromImage(image_from_source(source(int(self.logical_width * self.scale), int(10 * self.scale))))
        result.setDevicePixelRatio(self.scale)
        return result


def test_x11_keeps_physical_pixels_without_applying_dpr_twice(qt_app):
    screen = FakeScreen()
    backend = X11CaptureBackend(lambda: [screen])
    caps = backend.capabilities()
    assert caps.available and caps.monitors[0].width == 20
    results = []
    backend.capture(CaptureRequest(caps.monitors[0].id), results.append)
    assert results[0].status is CaptureStatus.SUCCESS
    assert (results[0].image.width, results[0].image.height) == (20, 20)
    assert results[0].scale == 2 and screen.calls == 1


@pytest.mark.parametrize("scale", [1.25, 1.5])
def test_x11_fractional_dpi_preserves_actual_bitmap_dimensions(qt_app, scale):
    screen = FakeScreen(scale)
    backend = X11CaptureBackend(lambda: [screen])
    monitor = backend.capabilities().monitors[0]
    results = []
    backend.capture(CaptureRequest(monitor.id), results.append)
    assert results[0].status is CaptureStatus.SUCCESS
    assert (results[0].image.width, results[0].image.height) == (int(10 * scale), int(10 * scale))


def test_x11_impossible_metadata_is_refused_before_grab(qt_app):
    screen = FakeScreen(logical_width=40000)
    backend = X11CaptureBackend(lambda: [screen])
    monitor = backend.capabilities().monitors[0]
    results = []
    backend.capture(CaptureRequest(monitor.id), results.append)
    assert results[0].status is CaptureStatus.FAILED
    assert screen.calls == 0


def test_x11_refuses_budget_and_disconnected_monitor_before_grab(qt_app):
    screen = FakeScreen()
    screens = [screen]
    backend = X11CaptureBackend(lambda: screens)
    monitor = backend.capabilities().monitors[0]
    results = []
    backend.capture(CaptureRequest(monitor.id, MAX_BUFFER_BYTES), results.append)
    assert results[-1].status is CaptureStatus.FAILED and screen.calls == 0
    screens.clear()
    backend.capture(CaptureRequest(monitor.id), results.append)
    assert results[-1].status is CaptureStatus.UNAVAILABLE and screen.calls == 0


def test_x11_empty_capture_is_failure_and_no_monitors_is_unavailable(qt_app):
    screen = FakeScreen(empty=True)
    backend = X11CaptureBackend(lambda: [screen])
    key = backend.capabilities().monitors[0].id
    results = []
    backend.capture(CaptureRequest(key), results.append)
    assert results[0].status is CaptureStatus.FAILED
    assert not X11CaptureBackend(lambda: []).capabilities().available


class FakeBackend:
    def __init__(self, result=None, *, raises=False, pending=False, cancel_raises=False):
        self.result = result or CaptureResult(CaptureStatus.SUCCESS, source())
        self.raises, self.pending, self.cancel_raises = raises, pending, cancel_raises
        self.calls = 0
        self.callback = None

    def capabilities(self):
        return CaptureCapabilities(True, portal=True, message="Portal fictício")

    def capture(self, request, callback):
        self.calls += 1
        self.callback = callback
        if self.raises:
            raise RuntimeError("Falha fictícia")
        if not self.pending:
            callback(self.result)

    def cancel(self):
        if self.cancel_raises:
            raise RuntimeError("Falha fictícia ao cancelar")


@pytest.mark.parametrize("status", list(CaptureStatus))
def test_controller_restores_only_previously_visible_windows_and_states(qt_app, status):
    visible, hidden = QWidget(), QWidget()
    visible.showMaximized()
    original_state = visible.windowState()
    previous_quit = qt_app.quitOnLastWindowClosed()
    backend = FakeBackend(CaptureResult(status, source() if status is CaptureStatus.SUCCESS else None), pending=True)
    controller = CaptureController(backend, delay_ms=0)
    results = []
    controller.finished.connect(results.append)
    assert controller.start(CaptureRequest())
    assert not visible.isVisible() and not hidden.isVisible()
    assert not qt_app.quitOnLastWindowClosed()
    assert not controller.start(CaptureRequest())
    wait_for(lambda: backend.callback is not None)
    backend.callback(backend.result)
    assert not controller.busy and visible.isVisible() and not hidden.isVisible()
    assert visible.windowState() == original_state
    assert qt_app.quitOnLastWindowClosed() == previous_quit
    assert len(results) == 1
    visible.close()
    hidden.close()


def test_controller_restores_windows_on_backend_exception(qt_app):
    window = QWidget()
    window.show()
    backend = FakeBackend(raises=True)
    controller = CaptureController(backend, delay_ms=0)
    results = []
    controller.finished.connect(results.append)
    controller.start(CaptureRequest())
    wait_for(lambda: bool(results))
    assert results[0].status is CaptureStatus.FAILED and window.isVisible()
    window.close()


@pytest.mark.parametrize("cancel_raises", [False, True])
def test_cancel_before_delay_restores_and_does_not_capture(qt_app, cancel_raises):
    window = QWidget()
    window.show()
    backend = FakeBackend(cancel_raises=cancel_raises)
    controller = CaptureController(backend, delay_ms=100)
    results = []
    controller.finished.connect(results.append)
    controller.start(CaptureRequest())
    controller.cancel()
    assert results[0].status is CaptureStatus.CANCELLED
    assert window.isVisible() and backend.calls == 0
    window.close()


def test_timeout_and_late_callback_cannot_replace_finished_capture(qt_app):
    backend = FakeBackend(pending=True)
    controller = CaptureController(backend, delay_ms=0, timeout_ms=15)
    results = []
    controller.finished.connect(results.append)
    controller.start(CaptureRequest())
    wait_for(lambda: bool(results))
    assert results[0].status is CaptureStatus.FAILED
    callback = backend.callback
    controller.start(CaptureRequest())
    callback(CaptureResult(CaptureStatus.SUCCESS, source()))
    assert len(results) == 1 and controller.busy
    controller.cancel()


def attach_backend(window, backend):
    window.capture_controller.backend = backend
    window.capture_controller._delay.setInterval(0)
    window._update_capture_action()


@pytest.mark.parametrize("status", [CaptureStatus.CANCELLED, CaptureStatus.DENIED, CaptureStatus.UNAVAILABLE, CaptureStatus.FAILED])
def test_ui_non_success_preserves_document_scene_and_selection(window, qt_app, monkeypatch, status):
    window.show()
    assert window._load_candidate(source)
    snapshot, scene = window.session.project, window.scene
    errors = []
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: errors.append(message))
    attach_backend(window, FakeBackend(CaptureResult(status, message="Resultado fictício")))
    window.actions_by_name["Capturar"].trigger()
    assert not window.isVisible()
    wait_for(lambda: not window.capture_controller.busy)
    assert window.isVisible() and window.session.project is snapshot and window.scene is scene
    assert window.session.dirty
    assert bool(errors) is (status is not CaptureStatus.CANCELLED)
    assert window.actions_by_name["Abrir"].isEnabled() and window.actions_by_name["Colar"].isEnabled()


@pytest.mark.parametrize("discard", [False, True])
def test_ui_success_restores_before_discard_and_commits_only_if_accepted(window, qt_app, monkeypatch, discard):
    window.show()
    assert window._load_candidate(source)
    snapshot, scene = window.session.project, window.scene

    def confirm(parent):
        assert window.isVisible() and not window.capture_controller.busy
        return discard

    monkeypatch.setattr(dialogs, "confirm_discard", confirm)
    attach_backend(window, FakeBackend(CaptureResult(CaptureStatus.SUCCESS, source(4, 3))))
    window.capture_image()
    wait_for(lambda: not window.capture_controller.busy)
    if discard:
        assert window.session.project.base == source(4, 3) and window.scene is not scene
    else:
        assert window.session.project is snapshot and window.scene is scene


def test_monitor_dialog_cancel_does_not_hide_or_capture(window, qt_app, monkeypatch):
    backend = X11CaptureBackend(lambda: [FakeScreen()])
    attach_backend(window, backend)
    monkeypatch.setattr(dialogs, "choose_monitor", lambda parent, monitors: None)
    window.show()
    window.capture_image()
    assert window.isVisible() and not window.capture_controller.busy


def test_unavailable_backend_keeps_import_enabled(window):
    attach_backend(window, UnavailableCaptureBackend())
    assert not window.actions_by_name["Capturar"].isEnabled()
    assert window.actions_by_name["Abrir"].isEnabled() and window.actions_by_name["Colar"].isEnabled()


def test_close_during_capture_cancels_and_can_preserve_dirty_document(window, monkeypatch):
    window.show()
    assert window._load_candidate(source)
    attach_backend(window, FakeBackend(pending=True))
    window.capture_image()
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: False)
    assert not window.close()
    assert window.isVisible() and not window.capture_controller.busy
