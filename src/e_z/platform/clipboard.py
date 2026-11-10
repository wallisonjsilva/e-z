"""Acesso ao clipboard Qt restrito à thread gráfica."""

from PySide6.QtCore import QThread
from PySide6.QtGui import QClipboard, QImage
from PySide6.QtWidgets import QApplication

from e_z.domain.document import SourceImage
from e_z.domain.geometry import validate_surface
from e_z.imaging.images import ImageError, source_from_image
from e_z.imaging.budget import check_conversion, check_peak

_published_highwater = 0


def reserved_bytes() -> int:
    """Cota conservadora, sem ler o conteúdo de outro aplicativo."""
    return _published_highwater


def snapshot_image(*, resident_bytes: int = 0) -> QImage:
    app = QApplication.instance()
    if not isinstance(app, QApplication) or QThread.currentThread() != app.thread():
        raise ImageError("Não foi possível acessar a área de transferência.")
    image = app.clipboard().image()
    if image.isNull():
        raise ImageError("Não há uma imagem válida para carregar.")
    check_conversion(image.sizeInBytes(), image.width(), image.height(), resident_bytes)
    return QImage(image)


def read_image(*, resident_bytes: int = 0) -> SourceImage:
    return source_from_image(QApplication.clipboard().image(), resident_bytes=resident_bytes)


def write_image(image: QImage, *, resident_bytes: int = 0) -> None:
    """Publica só a imagem no Clipboard; setImage não confirma recepção externa."""
    app = QApplication.instance()
    if not isinstance(app, QApplication) or QThread.currentThread() != app.thread():
        raise ImageError("Não foi possível acessar a área de transferência.")
    if image.isNull():
        raise ImageError("Não há composição válida para copiar.")
    validate_surface(image.width(), image.height())
    global _published_highwater
    check_peak(resident_bytes, reserved_bytes(), image.sizeInBytes() * 3)
    normalized = QImage(image)
    normalized.setDevicePixelRatio(1)
    try:
        app.clipboard().setImage(normalized, QClipboard.Mode.Clipboard)
        _published_highwater = max(_published_highwater, image.sizeInBytes())
    except RuntimeError:
        raise ImageError("Não foi possível publicar a imagem na área de transferência.") from None
