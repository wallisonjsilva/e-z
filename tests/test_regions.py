"""RF04–RF07: operações imutáveis e identidade, escala e modos das regiões."""

from uuid import uuid4

import pytest

from true_screen.application import regions
from true_screen.domain.document import EvidenceProject, SourceImage, ZoomMode
from true_screen.domain.geometry import Rect


@pytest.fixture
def project():
    return EvidenceProject(SourceImage(400, 200, bytes([12, 34, 56, 255]) * 80000))


@pytest.mark.parametrize("factor,size", [(1, (100, 40)), (1.5, (150, 60)), (2, (200, 80)),
                                       (3, (300, 120)), (2.37, (237, 95)), (8, (800, 320))])
def test_creation_from_source_keeps_base_and_project_identity(project, factor, size):
    result = regions.create_region(project, Rect(20, 24, 100, 40), factor)
    region = result.regions[0]
    assert region.destination == Rect(20, 24, *size)
    assert result.id == project.id and result.base is project.base
    assert project.regions == ()


def test_mode_roundtrip_preserves_source_identity_scale_and_z_order(project):
    original = regions.create_region(project, Rect(20, 24, 100, 40), 2)
    region = original.regions[0]
    external = regions.set_region_mode(original, region.id, ZoomMode.EXTERNAL)
    assert external.regions[0].destination == Rect(424, 24, 200, 80)
    overlay = regions.set_region_mode(external, region.id, ZoomMode.OVERLAY)
    assert overlay.regions[0].destination == external.regions[0].destination
    for result in (external, overlay):
        assert result.regions[0].id == region.id
        assert result.regions[0].source == region.source
        assert result.regions[0].z_index == region.z_index
        assert result.base is original.base


def test_external_can_move_to_negative_coordinates_and_modes_keep_position(project):
    result = regions.create_region(project, Rect(20, 24, 100, 40), 2, ZoomMode.EXTERNAL)
    region = result.regions[0]
    result = regions.move_region(result, region.id, -210, -90)
    assert result.canvas_bounds == Rect(-210, -90, 610, 290)
    overlay = regions.set_region_mode(result, region.id, ZoomMode.OVERLAY)
    back = regions.set_region_mode(overlay, region.id, ZoomMode.EXTERNAL)
    assert back.regions[0] == result.regions[0]


def test_three_objects_move_scale_and_delete_independently(project):
    result = project
    for _ in range(3):
        result = regions.create_region(result, Rect(20, 24, 100, 40), 2)
    first, second, third = result.regions
    assert len({r.id for r in result.regions}) == 3
    assert [r.z_index for r in result.regions] == [0, 1, 2]
    result = regions.move_region(result, second.id, -50, 10)
    result = regions.set_region_scale(result, second.id, 3)
    assert result.regions[0] == first and result.regions[2] == third
    assert result.regions[1].destination == Rect(-50, 10, 300, 120)
    assert result.regions[1].source == second.source
    result = regions.delete_region(result, second.id)
    assert result.regions == (first, third)
    assert result.base is project.base


def test_scaling_always_derives_from_source_and_repositions_external_only_if_needed(project):
    result = regions.create_region(project, Rect(20, 24, 3, 1), 1.5)
    region = result.regions[0]
    result = regions.set_region_scale(result, region.id, 3)
    assert result.regions[0].destination == Rect(20, 24, 9, 3)
    result = regions.move_region(result, region.id, -9, 24)
    result = regions.set_region_mode(result, region.id, ZoomMode.EXTERNAL)
    result = regions.set_region_scale(result, region.id, 2)
    assert result.regions[0].destination == Rect(-9, 24, 6, 2)
    result = regions.set_region_scale(result, region.id, 4)
    assert result.regions[0].destination == Rect(424, 24, 12, 4)


@pytest.mark.parametrize("factor", [0, 8.1, float("nan"), float("inf"), True])
def test_rejects_invalid_scale_before_any_edit(project, factor):
    with pytest.raises(ValueError):
        regions.create_region(project, Rect(20, 24, 100, 40), factor)
    assert project.regions == ()


def test_rejects_invalid_sources_external_overlap_and_huge_canvas(project):
    with pytest.raises(ValueError):
        regions.create_region(project, Rect(399, 199, 2, 2), 2)
    result = regions.create_region(project, Rect(20, 24, 100, 40), 2, ZoomMode.EXTERNAL)
    region = result.regions[0]
    for x, y in ((20, 24), (32768, 0)):
        with pytest.raises(ValueError):
            regions.move_region(result, region.id, x, y)
    assert result.regions[0] == region


def test_noops_keep_same_project_and_missing_id_is_rejected(project):
    result = regions.create_region(project, Rect(20, 24, 100, 40), 2)
    region = result.regions[0]
    assert regions.move_region(result, region.id, 20, 24) is result
    assert regions.set_region_scale(result, region.id, 2) is result
    assert regions.set_region_mode(result, region.id, ZoomMode.OVERLAY) is result
    with pytest.raises(ValueError):
        regions.delete_region(result, uuid4())
