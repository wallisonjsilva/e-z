"""Edições imutáveis das ampliações, sem Qt ou efeitos externos."""

from dataclasses import replace
from uuid import UUID

from true_screen.domain.document import EvidenceProject, ZoomMode, ZoomRegion
from true_screen.domain.errors import ValidationError
from true_screen.domain.geometry import Rect, scaled_size


def find_region(project: EvidenceProject, region_id: UUID) -> ZoomRegion:
    for region in project.regions:
        if region.id == region_id:
            return region
    raise ValidationError("A ampliação selecionada não existe neste documento.")


def _outside(project: EvidenceProject, destination: Rect, mode: ZoomMode) -> Rect:
    if mode is ZoomMode.EXTERNAL and project.base.bounds.intersects(destination):
        return replace(destination, x=project.base.width + 24)
    return destination


def _update(project: EvidenceProject, region: ZoomRegion) -> EvidenceProject:
    current = find_region(project, region.id)
    if current == region:
        return project
    return replace(project, regions=tuple(region if r.id == region.id else r for r in project.regions))


def create_region(project: EvidenceProject, source: Rect, factor: float,
                  mode: ZoomMode = ZoomMode.OVERLAY) -> EvidenceProject:
    if not project.base.bounds.contains(source):
        raise ValidationError("A origem da ampliação deve estar dentro da imagem-base.")
    width, height = scaled_size(source, factor)
    destination = Rect(source.x, source.y, width, height)
    destination = _outside(project, destination, mode)
    region = ZoomRegion(source, destination, mode, z_index=max((r.z_index for r in project.regions), default=-1) + 1)
    return replace(project, regions=project.regions + (region,))


def move_region(project: EvidenceProject, region_id: UUID, x: int, y: int) -> EvidenceProject:
    region = find_region(project, region_id)
    return _update(project, replace(region, destination=replace(region.destination, x=x, y=y)))


def set_region_mode(project: EvidenceProject, region_id: UUID, mode: ZoomMode) -> EvidenceProject:
    region = find_region(project, region_id)
    return _update(project, replace(region, mode=mode, destination=_outside(project, region.destination, mode)))


def set_region_scale(project: EvidenceProject, region_id: UUID, factor: float) -> EvidenceProject:
    region = find_region(project, region_id)
    width, height = scaled_size(region.source, factor)
    destination = replace(region.destination, width=width, height=height)
    return _update(project, replace(region, destination=_outside(project, destination, region.mode)))


def delete_region(project: EvidenceProject, region_id: UUID) -> EvidenceProject:
    find_region(project, region_id)
    return replace(project, regions=tuple(r for r in project.regions if r.id != region_id))
