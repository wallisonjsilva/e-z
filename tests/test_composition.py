"""CA02/CA04 e composição sem controles, zoom de navegação ou camadas de UI."""

from dataclasses import replace

import pytest
from PySide6.QtCore import QSaveFile
from PySide6.QtGui import QColor, QImage

from e_z.domain.document import EvidenceProject, SourceImage, ZoomMode, ZoomRegion
from e_z.domain.geometry import MAX_BUFFER_BYTES, Rect
from e_z.imaging import composition, images
from e_z.platform import dialogs


RED = bytes([255, 0, 0, 255])
BLUE = bytes([0, 0, 255, 255])


def pixels(image):
    return images.source_from_image(image).rgba


def project():
    return EvidenceProject(SourceImage(2, 1, RED + BLUE))


def test_1920x1080_import_export_keeps_decoded_rgba(tmp_path):
    original = SourceImage(1920, 1080, bytes([17, 99, 201, 255]) * (1920 * 1080))
    input_path, output_path = tmp_path / "base.png", tmp_path / "composicao.png"
    assert images.image_from_source(original).save(str(input_path), "PNG")
    document = EvidenceProject(images.load_image(str(input_path)))
    composition.export_png(document, str(output_path))
    assert images.load_image(str(output_path)) == original


def test_transparent_background_preserves_all_rgba_channels(tmp_path):
    source = SourceImage(3, 1, bytes([40, 30, 20, 0, 11, 99, 201, 127, 8, 7, 6, 255]))
    document = EvidenceProject(source, background=(0, 0, 0, 0))
    result = composition.compose(document)
    assert pixels(result) == source.rgba
    path = tmp_path / "alpha.png"
    composition.export_png(document, str(path))
    assert images.load_image(str(path)) == source


def test_default_background_composites_alpha_over_white():
    document = EvidenceProject(SourceImage(1, 1, bytes([255, 0, 0, 0])))
    assert composition.compose(document).pixelColor(0, 0) == QColor("white")


def test_negative_canvas_translates_without_resizing_base():
    region = ZoomRegion(Rect(1, 0, 1, 1), Rect(-2, -2, 2, 2), ZoomMode.EXTERNAL)
    document = replace(project(), regions=(region,))
    result = composition.compose(document)
    assert (result.width(), result.height()) == (4, 3)
    assert result.pixelColor(0, 0) == QColor("blue")
    assert result.pixelColor(1, 1) == QColor("blue")
    assert result.pixelColor(2, 2) == QColor("red")
    assert result.pixelColor(3, 2) == QColor("blue")
    assert result.pixelColor(3, 0) == QColor("white")
    assert document.base.rgba == RED + BLUE


def test_each_crop_comes_from_base_even_if_previous_zoom_covers_source():
    first = ZoomRegion(Rect(0, 0, 1, 1), Rect(1, 0, 1, 1))
    second = ZoomRegion(Rect(1, 0, 1, 1), Rect(2, 0, 2, 2), ZoomMode.EXTERNAL)
    document = replace(project(), regions=(first, second))
    result = composition.compose(document)
    assert result.pixelColor(1, 0) == QColor("red")
    assert result.pixelColor(2, 0) == QColor("blue")
    assert result.pixelColor(3, 1) == QColor("blue")
    assert document.base.rgba == RED + BLUE


def test_z_order_and_stable_ties_for_three_regions():
    red = ZoomRegion(Rect(0, 0, 1, 1), Rect(0, 0, 1, 1))
    blue = ZoomRegion(Rect(1, 0, 1, 1), Rect(0, 0, 1, 1))
    third = ZoomRegion(Rect(0, 0, 1, 1), Rect(2, 0, 1, 1), ZoomMode.EXTERNAL)
    document = replace(project(), regions=(red, blue, third))
    assert composition.compose(document).pixelColor(0, 0) == QColor("blue")
    document = replace(document, regions=(replace(red, z_index=1), blue, third))
    assert composition.compose(document).pixelColor(0, 0) == QColor("red")


def test_budget_is_checked_before_image_allocation(monkeypatch):
    def forbidden(*args):
        pytest.fail("Não deveria criar imagem antes de recusar o orçamento")

    monkeypatch.setattr(composition, "image_from_source", forbidden)
    with pytest.raises(ValueError):
        composition.compose(project(), resident_bytes=MAX_BUFFER_BYTES)


def test_export_invalid_destination_preserves_existing_files(tmp_path):
    existing = tmp_path / "existente.png"
    existing.write_bytes(b"conteudo anterior ficticio")
    with pytest.raises(ValueError):
        composition.export_png(project(), str(tmp_path / "ausente" / "nova.png"))
    assert existing.read_bytes() == b"conteudo anterior ficticio"


@pytest.mark.parametrize("failure", ["encode", "commit"])
def test_atomic_export_failure_keeps_previous_file(tmp_path, monkeypatch, failure):
    path = tmp_path / "existente.png"
    path.write_bytes(b"conteudo anterior ficticio")
    if failure == "encode":
        monkeypatch.setattr(QImage, "save", lambda *args: False)
    else:
        class FailedCommit(QSaveFile):
            def commit(self):
                return False

        monkeypatch.setattr(composition, "QSaveFile", FailedCommit)
    with pytest.raises(ValueError):
        composition.export_png(project(), str(path))
    assert path.read_bytes() == b"conteudo anterior ficticio"
    assert list(tmp_path.iterdir()) == [path]


def test_export_action_marks_clean_only_on_success(window, tmp_path, monkeypatch):
    assert window._load_candidate(lambda: project().base)
    document = window.session.project
    assert window.actions_by_name["Exportar PNG"].isEnabled()
    monkeypatch.setattr(dialogs, "export_png", lambda parent: "")
    window.export_image()
    assert window.session.dirty
    errors = []
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: errors.append(message))
    monkeypatch.setattr(dialogs, "export_png", lambda parent: str(tmp_path / "ausente" / "nova.png"))
    window.export_image()
    assert window.session.dirty and window.session.project is document
    assert errors
    path = tmp_path / "evidencia.png"
    monkeypatch.setattr(dialogs, "export_png", lambda parent: str(path))
    window.view.scale(0.25, 0.25)
    window.scene.addText("Controle de edição fictício")
    window.actions_by_name["Exportar PNG"].trigger()
    assert not window.session.dirty
    assert images.load_image(str(path)) == document.base
    assert "*" not in window.windowTitle()


def test_exported_document_can_be_replaced_without_discard_prompt(window, monkeypatch, tmp_path):
    assert window._load_candidate(lambda: project().base)
    path = tmp_path / "evidencia.png"
    monkeypatch.setattr(dialogs, "export_png", lambda parent: str(path))
    window.export_image()
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: pytest.fail("Documento já exportado"))
    assert window._load_candidate(lambda: project().base)
    assert window.session.dirty


def test_export_old_snapshot_does_not_mark_new_document_clean(window):
    assert window._load_candidate(lambda: project().base)
    previous = window.session.project
    window.session.replace(project())
    window.session.mark_exported(previous)
    assert window.session.dirty
