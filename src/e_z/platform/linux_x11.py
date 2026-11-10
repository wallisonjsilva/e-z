"""Captura Qt de monitor em sessão X11; não usar como fallback Wayland."""

from math import ceil, floor, isfinite

from PySide6.QtGui import QGuiApplication

from e_z.application.capture import CaptureCapabilities, CaptureRequest, CaptureResult, CaptureStatus, Monitor
from e_z.domain.geometry import validate_buffer_budget, validate_surface
from e_z.imaging.images import source_from_image
from e_z.imaging.budget import check_peak
from e_z.imaging.tasks import TaskRunner


class X11CaptureBackend:
    def __init__(self, screens=None, *, runner=None) -> None:
        self._provider = screens or QGuiApplication.screens
        self._screens = {}
        self.runner = runner if runner is not None else TaskRunner()
        self._generation = 0
        self._pending_callback = None

    def capabilities(self) -> CaptureCapabilities:
        monitors = []
        try:
            self._screens = {f"screen-{index}": screen for index, screen in enumerate(self._provider())}
            for key, screen in self._screens.items():
                scale = screen.devicePixelRatio()
                if not isfinite(scale) or scale <= 0:
                    raise ValueError("Escala de monitor inválida.")
                size = screen.size()
                width, height = ceil(size.width() * scale), ceil(size.height() * scale)
                monitors.append(Monitor(key, width, height, scale))
        except (RuntimeError, ValueError):
            return CaptureCapabilities(False, message="Não foi possível consultar os monitores X11.")
        return CaptureCapabilities(bool(monitors), tuple(monitors), message="Capturar monitor X11" if monitors else "Nenhum monitor X11 disponível.")

    def capture(self, request: CaptureRequest, callback) -> None:
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
        try:
            screen = self._screens.get(request.monitor_id)
            if screen is None or screen not in self._provider():
                deliver(CaptureResult(CaptureStatus.UNAVAILABLE, message="O monitor não está mais disponível."))
                return
            scale = screen.devicePixelRatio()
            if not isfinite(scale) or scale <= 0:
                raise ValueError("Escala de monitor inválida.")
            size = screen.size()
            # A geometria lógica inteira pode arredondar o tamanho físico fracionário.
            width, height = ceil((size.width() + 1) * scale), ceil((size.height() + 1) * scale)
            image_bytes = validate_surface(width, height)
            check_peak(request.resident_bytes, image_bytes * 5)
            pixmap = screen.grabWindow(0)
            minimum_width = max(1, floor((size.width() - 1) * scale))
            minimum_height = max(1, floor((size.height() - 1) * scale))
            if (pixmap.isNull() or not minimum_width <= pixmap.width() <= width
                    or not minimum_height <= pixmap.height() <= height):
                raise ValueError("A captura não corresponde às dimensões físicas esperadas do monitor.")
            image = pixmap.toImage()
            del pixmap
        except Exception:
            deliver(CaptureResult(CaptureStatus.FAILED, message="Não foi possível capturar o monitor dentro dos limites de imagem e memória."))
            return

        def completed(source):
            if generation == self._generation:
                deliver(CaptureResult(CaptureStatus.SUCCESS, source, scale))

        def failed(error):
            if generation == self._generation:
                deliver(CaptureResult(CaptureStatus.FAILED, message=error.message))

        if not self.runner.submit(lambda: source_from_image(image, resident_bytes=request.resident_bytes), completed, failed):
            deliver(CaptureResult(CaptureStatus.FAILED, message="Há outra operação de imagem em andamento."))

    def cancel(self) -> None:
        # Conversão em andamento pode terminar; seu resultado será ignorado.
        self._generation += 1
        callback, self._pending_callback = self._pending_callback, None
        if callback is not None:
            callback(CaptureResult(CaptureStatus.CANCELLED, message="Captura cancelada."))
