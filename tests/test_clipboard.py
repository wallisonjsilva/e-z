"""W09/CA06 local: imagem composta, publicação Qt e atalhos com foco."""

from dataclasses import replace
from threading import Thread

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from true_screen.application import regions
from true_screen.domain.document import SourceImage, ZoomMode
from true_screen.domain.geometry import MAX_BUFFER_BYTES, Rect
from true_screen.imaging import composition, images
from true_screen.platform import clipboard, dialogs
from true_screen.ui import main_window


@pytest.fixture
def board(qt_app):
    clipboard = qt_app.clipboard()
    clipboard.clear()
    yield clipboard
    clipboard.clear()


@pytest.fixture
def editor(window, qt_app, monkeypatch):
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: pytest.fail(message))
    window.show()
    window.activateWindow()
    qt_app.processEvents()
    rgba = (bytes([255, 0, 0, 255]) * 8 + bytes([0, 0, 255, 255]) * 8) * 12
    assert window._load_candidate(lambda: SourceImage(16, 12, rgba))
    window.view.set_navigation_zoom(2)
    window.view.setFocus()
    qt_app.processEvents()
    return window


def add_region(editor):
    assert editor._edit_regions(lambda project: regions.create_region(project, Rect(0, 0, 4, 3), 2), select_new=True)
    return editor.session.project.regions[-1]


def test_copy_without_document_is_disabled_and_keeps_clipboard(window, board):
    board.setText("Texto fictício anterior")
    assert not window.actions_by_name["Copiar composição"].isEnabled()
    window.copy_image()
    assert board.text() == "Texto fictício anterior"


def test_adapter_normalizes_dpr_and_keeps_independent_image(board):
    source = SourceImage(2, 1, bytes([17, 31, 99, 255]) * 2)
    image = images.image_from_source(source)
    image.setDevicePixelRatio(2)
    clipboard.write_image(image)
    image.fill(Qt.GlobalColor.black)
    result = board.image()
    assert result.devicePixelRatio() == 1
    assert images.source_from_image(result) == source


@pytest.mark.parametrize("failure", ["null", "budget"])
def test_invalid_image_or_budget_preserves_existing_clipboard(board, failure):
    board.setText("Texto fictício anterior")
    image = QImage() if failure == "null" else images.image_from_source(SourceImage(1, 1, bytes([0, 0, 0, 255])))
    with pytest.raises(ValueError):
        clipboard.write_image(image, resident_bytes=MAX_BUFFER_BYTES if failure == "budget" else 0)
    assert board.text() == "Texto fictício anterior"


def test_adapter_refuses_access_from_worker_thread(board):
    board.setText("Texto fictício anterior")
    image = images.image_from_source(SourceImage(1, 1, bytes([0, 0, 0, 255])))
    errors = []

    def write():
        try:
            clipboard.write_image(image)
        except ValueError as error:
            errors.append(error)

    thread = Thread(target=write)
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive() and len(errors) == 1
    assert board.text() == "Texto fictício anterior"


@pytest.mark.parametrize("exported", [False, True])
def test_copy_does_not_change_document_dirty_state_or_selection(editor, board, exported):
    region = add_region(editor)
    project, scene = editor.session.project, editor.scene
    if exported:
        editor.session.mark_exported(project)
    editor.copy_image()
    assert editor.session.project is project and editor.scene is scene
    assert editor.session.dirty is (not exported)
    assert editor.view.selected_region_id == region.id
    assert images.source_from_image(board.image()) == images.source_from_image(composition.compose(project))


def test_clipboard_matches_png_with_three_layers_negative_canvas_and_view_decorations(editor, board, tmp_path):
    def build(project):
        project = regions.create_region(project, Rect(0, 0, 4, 3), 2, ZoomMode.EXTERNAL)
        project = regions.move_region(project, project.regions[-1].id, -8, -6)
        project = regions.create_region(project, Rect(8, 0, 4, 3), 2)
        return regions.create_region(project, Rect(0, 0, 4, 3), 3)

    assert editor._edit_regions(build, select_new=True)
    editor.view.set_navigation_zoom(3)
    editor.view.centerOn(-4, -3)
    editor.scene.addText("Controle de edição fictício")
    editor.copy_image()
    path = tmp_path / "composicao.png"
    composition.export_png(editor.session.project, str(path))
    result = images.source_from_image(board.image())
    assert (result.width, result.height) == (24, 18)
    assert result == images.load_image(str(path))


def test_copy_keeps_exact_alpha_on_transparent_background(editor, board, tmp_path):
    source = SourceImage(3, 1, bytes([12, 34, 56, 0, 17, 31, 99, 127, 45, 67, 89, 255]))
    editor.session.dirty = False
    assert editor._load_candidate(lambda: source)
    assert editor._edit_regions(lambda project: replace(project, background=(0, 0, 0, 0)))
    editor.copy_image()
    assert images.source_from_image(board.image()) == source


@pytest.mark.parametrize("failure", ["limits", "memory", "publish"])
def test_copy_failure_preserves_document_clipboard_and_dirty_state(editor, board, monkeypatch, failure):
    region = add_region(editor)
    project, scene = editor.session.project, editor.scene
    editor.session.mark_exported(project)
    board.setText("Texto fictício anterior")
    errors = []
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: errors.append(message))

    def fail(*args, **kwargs):
        if failure == "limits":
            raise ValueError("A operação excede o orçamento de memória de imagem.")
        if failure == "memory":
            raise MemoryError()
        raise RuntimeError("Erro de plataforma fictício")

    monkeypatch.setattr(clipboard if failure == "publish" else main_window,
                        "write_image" if failure == "publish" else "compose", fail)
    editor.copy_image()
    assert editor.session.project is project and editor.scene is scene
    assert editor.view.selected_region_id == region.id and not editor.session.dirty
    assert board.text() == "Texto fictício anterior" and errors
    assert "Erro de plataforma fictício" not in errors[0]


@pytest.mark.parametrize("focus", ["canvas", "list"])
def test_ctrl_c_copies_composition_with_canvas_or_list_focus(editor, board, qt_app, focus):
    add_region(editor)
    target = editor.view if focus == "canvas" else editor.regions_panel.regions
    target.setFocus()
    qt_app.processEvents()
    QTest.keyClick(target, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert not board.image().isNull()
    assert images.source_from_image(board.image()) == images.source_from_image(composition.compose(editor.session.project))


def test_ctrl_o_opens_image_and_ctrl_v_pastes_image_locally(editor, board, qt_app, tmp_path, monkeypatch):
    other = SourceImage(2, 2, bytes([17, 31, 99, 255]) * 4)
    path = tmp_path / "outra.png"
    assert images.image_from_source(other).save(str(path), "PNG")
    monkeypatch.setattr(dialogs, "open_image", lambda parent: str(path))
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: True)
    editor.view.setFocus()
    qt_app.processEvents()
    QTest.keyClick(editor.view, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
    assert editor.session.project.base == other
    pasted = SourceImage(3, 2, bytes([45, 67, 89, 255]) * 6)
    board.setImage(images.image_from_source(pasted))
    QTest.keyClick(editor.view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert editor.session.project.base == pasted


def test_text_field_ctrl_c_copies_text_and_ctrl_v_does_not_replace_document(editor, board, qt_app, monkeypatch):
    region = add_region(editor)
    snapshot = editor.session.project
    field = editor.regions_panel.scale.findChild(QLineEdit)
    field.setFocus()
    field.selectAll()
    expected = field.selectedText()
    qt_app.processEvents()
    QTest.keyClick(field, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert board.text() == expected and board.image().isNull()
    monkeypatch.setattr(clipboard, "read_image", lambda **kwargs: pytest.fail("Colar imagem foi chamado no campo de texto"))
    board.setText("250")
    field.selectAll()
    QTest.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert "250" in field.text()
    assert editor.session.project is snapshot and editor.view.selected_region_id == region.id


@pytest.mark.parametrize("focus", ["canvas", "list"])
def test_delete_shortcut_removes_only_selected_region(editor, qt_app, focus):
    first = add_region(editor)
    second = add_region(editor)
    editor.regions_panel.regions.setCurrentRow(0)
    target = editor.view if focus == "canvas" else editor.regions_panel.regions
    target.setFocus()
    qt_app.processEvents()
    QTest.keyClick(target, Qt.Key.Key_Delete)
    assert [region.id for region in editor.session.project.regions] == [second.id]
    assert editor.view.selected_region_id is None


@pytest.mark.parametrize("focus", ["canvas", "list"])
def test_escape_shortcut_clears_object_selection_without_editing(editor, qt_app, focus):
    add_region(editor)
    project = editor.session.project
    editor.session.mark_exported(project)
    target = editor.view if focus == "canvas" else editor.regions_panel.regions
    target.setFocus()
    qt_app.processEvents()
    QTest.keyClick(target, Qt.Key.Key_Escape)
    assert editor.view.selected_region_id is None
    assert editor.session.project is project and not editor.session.dirty


@pytest.mark.parametrize("key", [Qt.Key.Key_Delete, Qt.Key.Key_Escape])
def test_text_field_delete_and_escape_do_not_edit_region_or_clear_selection(editor, qt_app, key):
    region = add_region(editor)
    project = editor.session.project
    field = editor.regions_panel.scale.findChild(QLineEdit)
    field.setFocus()
    qt_app.processEvents()
    QTest.keyClick(field, key)
    assert editor.session.project is project
    assert editor.view.selected_region_id == region.id


def test_copy_is_disabled_and_ignored_during_capture(editor, board):
    board.setText("Texto fictício anterior")
    controller = editor.capture_controller
    controller.busy = True
    editor._capture_busy_changed(True)
    assert not editor.actions_by_name["Copiar composição"].isEnabled()
    editor.copy_image()
    assert board.text() == "Texto fictício anterior"
    controller.busy = False
    editor._capture_busy_changed(False)
    assert editor.actions_by_name["Copiar composição"].isEnabled()
