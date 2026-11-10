"""RF02: importação, pixels físicos e preservação transacional da sessão."""

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage

from e_z.domain.document import SourceImage
from e_z.domain.geometry import MAX_BUFFER_BYTES
from e_z.imaging import images
from e_z.platform import clipboard, dialogs


def source():
    return SourceImage(3, 2, bytes([12, 34, 56, 255]) * 6)


def test_png_keeps_rgba_and_detects_content_despite_extension(tmp_path):
    original = images.image_from_source(source())
    original.setPixelColor(1, 0, QColor(101, 102, 103, 104))
    path = tmp_path / "imagem.dat"
    assert original.save(str(path), "PNG")
    assert images.load_image(str(path)) == images.source_from_image(original)


def test_jpeg_decodes_opaque_pixels(tmp_path):
    path = tmp_path / "imagem.jpg"
    assert images.image_from_source(source()).save(str(path), "JPEG")
    result = images.load_image(str(path))
    assert (result.width, result.height) == (3, 2)
    assert set(result.rgba[3::4]) == {255}


def test_qimage_conversion_uses_physical_size_and_does_not_mutate_source():
    original = source()
    image = images.image_from_source(original)
    image.setDevicePixelRatio(2)
    assert images.source_from_image(image) == original
    image.fill(QColor("red"))
    assert original.rgba == bytes([12, 34, 56, 255]) * 6
    assert images.image_from_source(original).devicePixelRatio() == 1


@pytest.mark.parametrize("kind", ["missing", "invalid", "truncated", "bmp"])
def test_rejects_invalid_missing_and_unsupported_files(tmp_path, kind):
    path = tmp_path / "entrada.png"
    if kind == "invalid":
        path.write_bytes(b"arquivo ficticio invalido")
    elif kind == "truncated":
        assert images.image_from_source(source()).save(str(path), "PNG")
        path.write_bytes(path.read_bytes()[:20])
    elif kind == "bmp":
        assert images.image_from_source(source()).save(str(path), "BMP")
    with pytest.raises(ValueError) as failure:
        images.load_image(str(path))
    assert str(path) not in str(failure.value)


@pytest.mark.parametrize("dimensions,resident", [(QSize(32769, 1), 0),
                                                (QSize(10000, 10000), 0),
                                                (QSize(3, 2), MAX_BUFFER_BYTES)])
def test_checks_metadata_and_budget_before_decode(tmp_path, monkeypatch, dimensions, resident):
    path = tmp_path / "stub.png"
    path.write_bytes(b"stub")

    class Reader:
        def __init__(self, file):
            pass

        def setDecideFormatFromContent(self, value):
            pass

        def setAutoTransform(self, value):
            pass

        def format(self):
            return b"png"

        def size(self):
            return dimensions

        def read(self):
            pytest.fail("Não deveria decodificar antes de recusar limites")

    monkeypatch.setattr(images, "QImageReader", Reader)
    with pytest.raises(ValueError):
        images.load_image(str(path), resident_bytes=resident)


def test_clipboard_image_and_empty_content(qt_app):
    board = qt_app.clipboard()
    try:
        board.setImage(images.image_from_source(source()))
        assert clipboard.read_image() == source()
        board.setText("Exemplo fictício")
        with pytest.raises(ValueError):
            clipboard.read_image()
    finally:
        board.clear()


def test_ui_open_cancel_and_failed_load_keep_document_and_scene(window, monkeypatch):
    assert window._load_candidate(source)
    project, scene = window.session.project, window.scene
    monkeypatch.setattr(dialogs, "open_image", lambda parent: "")
    window.open_image()
    assert window.session.project is project
    errors = []
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: errors.append(message))
    assert not window._load_candidate(lambda: images.source_from_image(QImage()))
    assert window.session.project is project and window.scene is scene
    assert window.session.dirty and errors


def test_discard_cancel_preserves_preview_then_accept_replaces(window, monkeypatch):
    assert window._load_candidate(source)
    project, scene = window.session.project, window.scene
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: False)
    candidate = lambda: SourceImage(1, 1, bytes([255, 0, 0, 255]))
    assert not window._load_candidate(candidate)
    assert window.session.project is project and window.scene is scene
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: True)
    assert window._load_candidate(candidate)
    assert window.session.project is not project
    assert window.scene is not scene
    assert window.session.dirty
    assert window.scene.sceneRect().width() == 1


def test_memory_failure_preserves_open_document(window, monkeypatch):
    assert window._load_candidate(source)
    project, scene = window.session.project, window.scene
    errors = []
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: errors.append(message))

    def fail():
        raise MemoryError()

    assert not window._load_candidate(fail)
    assert window.session.project is project and window.scene is scene
    assert "Memória" in errors[0]


def test_close_requests_discard_of_unexported_work(window, monkeypatch):
    window.show()
    assert window._load_candidate(source)
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: False)
    assert not window.close()
    assert window.isVisible()
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: True)
    assert window.close()


def test_open_and_paste_actions_use_adapters(window, monkeypatch, tmp_path):
    path = tmp_path / "fixture.png"
    assert images.image_from_source(source()).save(str(path), "PNG")
    monkeypatch.setattr(dialogs, "open_image", lambda parent: str(path))
    window.actions_by_name["Abrir"].trigger()
    assert window.session.project.base == source()
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: True)
    candidate = SourceImage(1, 1, bytes([255, 0, 0, 255]))
    monkeypatch.setattr(clipboard, "snapshot_image", lambda **kwargs: images.image_from_source(candidate))
    window.actions_by_name["Colar"].trigger()
    assert window.session.project.base == candidate
