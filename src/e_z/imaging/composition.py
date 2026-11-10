"""Renderer único da composição; sem acesso à UI, viewport ou clipboard."""

from PySide6.QtCore import QIODevice, QSaveFile, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from e_z.domain.document import EvidenceProject
from e_z.imaging.images import ImageError, image_from_source
from e_z.imaging.budget import check_output, check_render


def compose(project: EvidenceProject, *, resident_bytes: int = 0) -> QImage:
    bounds = project.canvas_bounds
    check_render(project, resident_bytes)
    base = image_from_source(project.base)
    output = QImage(bounds.width, bounds.height, QImage.Format.Format_RGBA8888)
    if output.isNull():
        raise ImageError("Não foi possível alocar a composição.")
    output.fill(QColor(*project.background))
    painter = QPainter(output)
    if not painter.isActive():
        raise ImageError("Não foi possível iniciar a composição.")
    try:
        painter.translate(-bounds.x, -bounds.y)
        if project.background[3] == 0:
            # Cópia exata inclusive dos canais RGB de pixels transparentes.
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, base)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        for region in sorted(project.regions, key=lambda region: region.z_index):
            source, destination = region.source, region.destination
            crop = base.copy(source.x, source.y, source.width, source.height)
            if crop.isNull():
                raise ImageError("Não foi possível recortar a região de origem.")
            zoom = crop.scaled(destination.width, destination.height,
                               Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            if zoom.isNull():
                raise ImageError("Não foi possível ampliar a região de origem.")
            painter.drawImage(destination.x, destination.y, zoom)
            # Não manter recorte/destino anteriores vivos durante a próxima alocação.
            del crop, zoom
    finally:
        painter.end()
    return output


def export_png(project: EvidenceProject, path: str, *, resident_bytes: int = 0) -> None:
    check_output(project, resident_bytes)
    image = compose(project, resident_bytes=resident_bytes)
    file = QSaveFile(path)
    file.setDirectWriteFallback(False)
    if not file.open(QIODevice.OpenModeFlag.WriteOnly):
        raise ImageError("Não foi possível criar o PNG. Verifique acesso e espaço no destino.")
    try:
        if not image.save(file, "PNG"):
            raise ImageError("Não foi possível gravar o PNG. Verifique o espaço disponível.")
        if not file.commit():
            raise ImageError("Não foi possível concluir a exportação do PNG.")
    except BaseException:
        file.cancelWriting()
        raise
