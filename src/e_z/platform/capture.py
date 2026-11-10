"""Seleção conservadora do backend, sem contornar permissões Wayland."""

import os
import sys

from PySide6.QtGui import QGuiApplication

from e_z.application.capture import CaptureCapabilities, CaptureResult, CaptureStatus


def detect_session(environment, qt_platform: str, system: str) -> str:
    if system != "linux" or qt_platform in ("offscreen", "minimal"):
        return "unavailable"
    session = environment.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland" or environment.get("WAYLAND_DISPLAY") or qt_platform.startswith("wayland"):
        return "wayland"
    if session == "x11" and qt_platform == "xcb":
        return "x11"
    return "unavailable"


class UnavailableCaptureBackend:
    def capabilities(self) -> CaptureCapabilities:
        return CaptureCapabilities(False, message="Captura indisponível nesta sessão. Use Abrir ou Colar.")

    def capture(self, request, callback) -> None:
        callback(CaptureResult(CaptureStatus.UNAVAILABLE, message=self.capabilities().message))

    def cancel(self) -> None:
        pass


def create_capture_backend(*, runner=None):
    session = detect_session(os.environ, QGuiApplication.platformName(), sys.platform)
    if session == "wayland":
        from e_z.platform.linux_wayland import WaylandCaptureBackend
        return WaylandCaptureBackend(runner=runner)
    if session == "x11":
        from e_z.platform.linux_x11 import X11CaptureBackend
        return X11CaptureBackend(runner=runner)
    return UnavailableCaptureBackend()
