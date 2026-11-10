"""Imagens Qt na fronteira com os bytes imutáveis do domínio."""

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtGui import QImage, QImageReader

from e_z.domain.document import SourceImage
from e_z.domain.errors import ValidationError
from e_z.imaging.budget import check_conversion, check_decode


class ImageError(ValidationError):
    """Erro recuperável de entrada/saída com mensagem pública sem dados privados."""


def source_from_image(image: QImage, *, resident_bytes: int = 0) -> SourceImage:
    if image.isNull():
        raise ImageError("Não há uma imagem válida para carregar.")
    # Imagem recebida, conversão, bytes imutáveis e futuro preview.
    check_conversion(image.sizeInBytes(), image.width(), image.height(), resident_bytes)
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    if converted.isNull():
        raise ImageError("Não foi possível converter a imagem em RGBA.")
    return SourceImage(converted.width(), converted.height(), bytes(converted.constBits()))


def image_from_source(source: SourceImage) -> QImage:
    # A cópia impede que um consumidor Qt possa escrever nos bytes da base.
    image = QImage(source.rgba, source.width, source.height, source.width * 4,
                   QImage.Format.Format_RGBA8888).copy()
    if image.isNull():
        raise ImageError("Não foi possível preparar a imagem para exibição.")
    image.setDevicePixelRatio(1)
    return image


def load_image(path: str, *, resident_bytes: int = 0) -> SourceImage:
    file = QFile(path)
    if not file.open(QIODevice.OpenModeFlag.ReadOnly):
        raise ImageError("Não foi possível abrir a imagem. Verifique acesso ao arquivo.")
    try:
        reader = QImageReader(file)
        reader.setDecideFormatFromContent(True)
        reader.setAutoTransform(False)
        if bytes(reader.format()).lower() not in (b"png", b"jpeg", b"jpg"):
            raise ImageError("Formato inválido. Abra uma imagem PNG ou JPEG.")
        dimensions = reader.size()
        # Decoder até RGBA64 + conversão + bytes + preview; sem ler o arquivo inteiro.
        check_decode(dimensions.width(), dimensions.height(), resident_bytes)
        image = reader.read()
        if image.isNull() or image.size() != dimensions:
            raise ImageError("A imagem está incompleta, corrompida ou não pode ser decodificada.")
        return source_from_image(image, resident_bytes=resident_bytes)
    finally:
        file.close()
