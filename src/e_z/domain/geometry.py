"""Coordenadas do documento em pixels físicos; sem zoom de navegação."""

from dataclasses import dataclass
from math import ceil, floor, isfinite
from e_z.domain.errors import ValidationError

MAX_AXIS = 32_768
MAX_PIXELS = 40_000_000
MAX_BUFFER_BYTES = 512 * 1024 * 1024


def validate_surface(width: int, height: int) -> int:
    """Valida dimensões e retorna bytes RGBA, sem alocar a superfície."""
    if any(type(value) is not int or value <= 0 for value in (width, height)):
        raise ValidationError("As dimensões devem ser inteiros positivos.")
    if width > MAX_AXIS or height > MAX_AXIS or width * height > MAX_PIXELS:
        raise ValidationError("A imagem excede o limite de dimensões ou pixels.")
    return width * height * 4


def validate_buffer_budget(*sizes: int) -> None:
    if any(type(size) is not int or size < 0 for size in sizes):
        raise ValidationError("O tamanho de cada buffer deve ser um inteiro não negativo.")
    if sum(sizes) > MAX_BUFFER_BYTES:
        raise ValidationError("A operação excede o orçamento de memória de imagem.")


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if any(type(value) is not int for value in (self.x, self.y, self.width, self.height)):
            raise ValidationError("O retângulo deve usar coordenadas inteiras.")
        validate_surface(self.width, self.height)

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def contains(self, other: "Rect") -> bool:
        return (self.x <= other.x and self.y <= other.y
                and self.right >= other.right and self.bottom >= other.bottom)

    def intersects(self, other: "Rect") -> bool:
        return (self.x < other.right and other.x < self.right
                and self.y < other.bottom and other.y < self.bottom)

    def union(self, other: "Rect") -> "Rect":
        x, y = min(self.x, other.x), min(self.y, other.y)
        return Rect(x, y, max(self.right, other.right) - x, max(self.bottom, other.bottom) - y)


def selection_rect(x1: float, y1: float, x2: float, y2: float, *, width: int, height: int) -> Rect:
    """Recebe pontos já convertidos à base, normaliza e limita a seleção."""
    validate_surface(width, height)
    values = (x1, y1, x2, y2)
    if any(type(value) not in (int, float) for value in values):
        raise ValidationError("A seleção deve usar coordenadas numéricas finitas.")
    try:
        finite = all(isfinite(value) for value in values)
    except OverflowError:
        finite = False
    if not finite:
        raise ValidationError("A seleção deve usar coordenadas numéricas finitas.")
    if x1 == x2 or y1 == y2:
        raise ValidationError("Selecione uma área não vazia da imagem.")
    left = floor(max(0, min(width, min(x1, x2))))
    top = floor(max(0, min(height, min(y1, y2))))
    right = ceil(max(0, min(width, max(x1, x2))))
    bottom = ceil(max(0, min(height, max(y1, y2))))
    if left >= right or top >= bottom:
        raise ValidationError("Selecione uma área não vazia da imagem.")
    return Rect(left, top, right - left, bottom - top)


def scaled_size(source: Rect, factor: float) -> tuple[int, int]:
    if type(factor) not in (int, float) or not 1 <= factor <= 8:
        raise ValidationError("O fator de ampliação deve estar entre 1 e 8.")
    width = max(1, floor(source.width * factor + 0.5))
    height = max(1, floor(source.height * factor + 0.5))
    validate_surface(width, height)
    return width, height
