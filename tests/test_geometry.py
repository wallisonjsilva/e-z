"""Invariantes RF03, CA03 e limites de superfície, sem dependência de Qt."""

import math

import pytest

from true_screen.domain.geometry import (
    MAX_BUFFER_BYTES, Rect, scaled_size, selection_rect, validate_buffer_budget, validate_surface,
)


@pytest.mark.parametrize("points", [(1.2, 2.8, 8.1, 9.2), (8.1, 9.2, 1.2, 2.8),
                                  (1.2, 9.2, 8.1, 2.8), (8.1, 2.8, 1.2, 9.2)])
def test_selection_all_directions(points):
    assert selection_rect(*points, width=10, height=10) == Rect(1, 2, 8, 8)


def test_selection_clips_before_rounding():
    assert selection_rect(-50, -3, 20, 30, width=10, height=10) == Rect(0, 0, 10, 10)


@pytest.mark.parametrize("points", [(1.5, 1, 1.5, 5), (1, 2.5, 5, 2.5),
                                  (-9, 0, -1, 5), (10, 1, 11, 5),
                                  (0, 0, math.nan, 5), (0, 0, 5, math.inf)])
def test_empty_or_nonfinite_selection_is_rejected(points):
    with pytest.raises(ValueError):
        selection_rect(*points, width=10, height=10)


def test_canvas_negative_coordinates_and_touching_edges():
    base = Rect(0, 0, 100, 40)
    external = Rect(-200, -80, 200, 80)
    assert base.union(external) == Rect(-200, -80, 300, 120)
    assert not base.intersects(external)
    assert base.intersects(Rect(99, 39, 2, 2))


def test_scale_uses_physical_pixels_and_rounds_half_up():
    assert scaled_size(Rect(0, 0, 100, 40), 2) == (200, 80)
    assert scaled_size(Rect(0, 0, 3, 1), 1.5) == (5, 2)


@pytest.mark.parametrize("factor", [0, -1, 8.1, math.inf, math.nan, True, "2"])
def test_invalid_scales(factor):
    with pytest.raises(ValueError):
        scaled_size(Rect(0, 0, 100, 40), factor)


@pytest.mark.parametrize("dimensions", [(0, 1), (-1, 3), (True, 2), (2.5, 1),
                                      (32769, 1), (10000, 10000)])
def test_limits_before_allocation(dimensions):
    with pytest.raises(ValueError):
        validate_surface(*dimensions)


def test_valid_boundaries_and_memory_budget():
    assert validate_surface(32768, 1) == 131072
    assert validate_surface(8000, 5000) == 160000000
    validate_buffer_budget(MAX_BUFFER_BYTES)
    with pytest.raises(ValueError):
        validate_buffer_budget(MAX_BUFFER_BYTES, 1)
    with pytest.raises(ValueError):
        scaled_size(Rect(0, 0, 8000, 5000), 2)
