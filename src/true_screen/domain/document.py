"""Estados imutáveis do documento; cada região referencia a mesma base."""

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from true_screen.domain.errors import ValidationError
from true_screen.domain.geometry import Rect, validate_buffer_budget, validate_surface


class ZoomMode(Enum):
    OVERLAY = "Overlay"
    EXTERNAL = "External"


@dataclass(frozen=True)
class SourceImage:
    width: int
    height: int
    rgba: bytes = field(repr=False)

    def __post_init__(self) -> None:
        expected = validate_surface(self.width, self.height)
        if type(self.rgba) is not bytes or len(self.rgba) != expected:
            raise ValidationError("A fonte deve conter bytes RGBA imutáveis com o tamanho esperado.")

    @property
    def bounds(self) -> Rect:
        return Rect(0, 0, self.width, self.height)


@dataclass(frozen=True)
class ZoomRegion:
    source: Rect
    destination: Rect
    mode: ZoomMode = ZoomMode.OVERLAY
    id: UUID = field(default_factory=uuid4)
    z_index: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.source, Rect) or not isinstance(self.destination, Rect):
            raise ValidationError("Origem e destino devem ser retângulos válidos.")
        if not isinstance(self.id, UUID) or not isinstance(self.mode, ZoomMode):
            raise ValidationError("Identidade ou modo da ampliação inválido.")
        if type(self.z_index) is not int:
            raise ValidationError("A ordem da camada deve ser um inteiro.")
        # Há um único fator compatível com os dois eixos e arredondamento de meio pixel.
        low = max(1, (self.destination.width - 0.5) / self.source.width,
                  (self.destination.height - 0.5) / self.source.height)
        high = min(8, (self.destination.width + 0.5) / self.source.width,
                   (self.destination.height + 0.5) / self.source.height)
        if low > high or (low == high and low != 8):
            raise ValidationError("O destino deve preservar a proporção e o fator entre 1 e 8.")


@dataclass(frozen=True)
class EvidenceProject:
    base: SourceImage
    regions: tuple[ZoomRegion, ...] = ()
    id: UUID = field(default_factory=uuid4)
    schema_version: int = field(default=1, init=False)
    background: tuple[int, int, int, int] = (255, 255, 255, 255)

    def __post_init__(self) -> None:
        if not isinstance(self.base, SourceImage) or not isinstance(self.id, UUID):
            raise ValidationError("Fonte ou identidade do documento inválida.")
        if type(self.regions) is not tuple or any(not isinstance(r, ZoomRegion) for r in self.regions):
            raise ValidationError("As ampliações devem formar uma sequência imutável de regiões.")
        if (type(self.background) is not tuple or len(self.background) != 4
                or any(type(v) is not int or not 0 <= v <= 255 for v in self.background)):
            raise ValidationError("O fundo deve conter quatro canais RGBA entre 0 e 255.")
        if len({region.id for region in self.regions}) != len(self.regions):
            raise ValidationError("As identidades das ampliações devem ser únicas.")
        for region in self.regions:
            if not self.base.bounds.contains(region.source):
                raise ValidationError("A origem da ampliação deve estar dentro da imagem-base.")
            if region.mode is ZoomMode.EXTERNAL and self.base.bounds.intersects(region.destination):
                raise ValidationError("A ampliação externa deve ficar inteiramente fora da base.")
        output = self.canvas_bounds
        largest_work = max((r.source.width * r.source.height * 4
                            + r.destination.width * r.destination.height * 4 for r in self.regions), default=0)
        validate_buffer_budget(len(self.base.rgba), output.width * output.height * 4, largest_work)

    @property
    def canvas_bounds(self) -> Rect:
        bounds = self.base.bounds
        for region in self.regions:
            bounds = bounds.union(region.destination)
        return bounds
