"""Contratos de captura sem Qt e sem detalhes do sistema operacional."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from true_screen.domain.document import SourceImage


class CaptureStatus(Enum):
    SUCCESS = "success"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True)
class Monitor:
    id: str
    width: int
    height: int
    scale: float


@dataclass(frozen=True)
class CaptureCapabilities:
    available: bool
    monitors: tuple[Monitor, ...] = ()
    portal: bool = False
    message: str = ""


@dataclass(frozen=True)
class CaptureRequest:
    monitor_id: str | None = None
    resident_bytes: int = 0


@dataclass(frozen=True)
class CaptureResult:
    status: CaptureStatus
    image: SourceImage | None = None
    scale: float | None = None
    message: str = ""


CaptureCallback = Callable[[CaptureResult], None]


class CaptureBackend(Protocol):
    def capabilities(self) -> CaptureCapabilities: ...
    def capture(self, request: CaptureRequest, callback: CaptureCallback) -> None: ...
    def cancel(self) -> None: ...
