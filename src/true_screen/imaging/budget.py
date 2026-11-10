"""Estimativas conservadoras dos buffers simultâneos por fase, sem alocação."""

from true_screen.domain.geometry import validate_buffer_budget, validate_surface

SCRATCH_BYTES = 16 * 1024 * 1024


def check_peak(resident_bytes: int, *buffers: int) -> None:
    validate_buffer_budget(resident_bytes, *buffers, SCRATCH_BYTES)


def check_decode(width: int, height: int, resident_bytes: int = 0) -> None:
    check_peak(resident_bytes, validate_surface(width, height) * 6)


def check_conversion(image_bytes: int, width: int, height: int, resident_bytes: int = 0) -> None:
    check_peak(resident_bytes, image_bytes, validate_surface(width, height) * 3)


def check_render(project, resident_bytes: int = 0) -> None:
    bounds = project.canvas_bounds
    output = validate_surface(bounds.width, bounds.height)
    largest = max((r.source.width * r.source.height * 8 + r.destination.width * r.destination.height * 12
                   for r in project.regions), default=0)
    check_peak(resident_bytes, len(project.base.rgba) * 2, output * 2, largest)


def check_output(project, resident_bytes: int = 0) -> None:
    bounds = project.canvas_bounds
    check_peak(resident_bytes, len(project.base.rgba), validate_surface(bounds.width, bounds.height) * 3)
