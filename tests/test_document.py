"""Fonte e objetos imutáveis; validade do documento antes da composição."""

from dataclasses import FrozenInstanceError, replace

import pytest

from e_z.domain.document import EvidenceProject, SourceImage, ZoomMode, ZoomRegion
from e_z.domain.geometry import Rect, scaled_size


def base():
    return SourceImage(10, 10, bytes([12, 34, 56, 255]) * 100)


def test_source_and_project_are_immutable_and_regions_share_base():
    source = base()
    original = EvidenceProject(source)
    region = ZoomRegion(Rect(1, 1, 3, 2), Rect(2, 2, 6, 4))
    edited = replace(original, regions=(region,))
    assert edited.base is original.base
    assert original.regions == ()
    assert edited.id == original.id
    with pytest.raises(FrozenInstanceError):
        source.width = 2
    with pytest.raises(TypeError):
        source.rgba[0] = 255


@pytest.mark.parametrize("pixels", [bytearray(400), bytes(399), bytes(401)])
def test_rejects_mutable_or_incorrect_source(pixels):
    with pytest.raises(ValueError):
        SourceImage(10, 10, pixels)


def test_source_region_must_be_inside_base():
    region = ZoomRegion(Rect(9, 9, 2, 2), Rect(0, 0, 4, 4))
    with pytest.raises(ValueError):
        EvidenceProject(base(), (region,))


def test_negative_canvas_does_not_resize_base():
    region = ZoomRegion(Rect(0, 0, 3, 2), Rect(-6, -4, 6, 4), ZoomMode.EXTERNAL)
    project = EvidenceProject(base(), (region,))
    assert project.canvas_bounds == Rect(-6, -4, 16, 14)
    assert project.base.bounds == Rect(0, 0, 10, 10)


def test_external_must_not_overlap_and_overlay_can_cross_base():
    region = ZoomRegion(Rect(0, 0, 3, 2), Rect(-1, -1, 6, 4))
    EvidenceProject(base(), (region,))
    with pytest.raises(ValueError):
        EvidenceProject(base(), (replace(region, mode=ZoomMode.EXTERNAL),))


def test_three_independent_regions_and_unique_ids():
    regions = tuple(ZoomRegion(Rect(0, 0, 1, 1), Rect(i, i, 2, 2)) for i in range(3))
    assert len(EvidenceProject(base(), regions).regions) == 3
    with pytest.raises(ValueError):
        EvidenceProject(base(), (regions[0], regions[0]))
    with pytest.raises(ValueError):
        EvidenceProject(base(), list(regions))


def test_rejects_huge_canvas_before_allocation():
    region = ZoomRegion(Rect(0, 0, 1, 1), Rect(32768, 0, 2, 2))
    with pytest.raises(ValueError):
        EvidenceProject(base(), (region,))


@pytest.mark.parametrize("size", [(9, 2), (2, 1), (1, 9)])
def test_rejects_disproportional_or_out_of_range_destination(size):
    with pytest.raises(ValueError):
        ZoomRegion(Rect(0, 0, 3, 2), Rect(0, 0, *size))


@pytest.mark.parametrize("factor", [1, 1.5, 2, 3, 7.99, 8])
def test_accepts_proportional_sizes_after_pixel_rounding(factor):
    source = Rect(0, 0, 3, 1)
    ZoomRegion(source, Rect(0, 0, *scaled_size(source, factor)))
