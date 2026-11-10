"""W07: interação completa de criação/edição e exportação das ampliações."""

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from true_screen.domain.document import SourceImage, ZoomMode
from true_screen.domain.geometry import Rect
from true_screen.imaging import images
from true_screen.imaging.composition import compose
from true_screen.platform import dialogs
from true_screen.ui import main_window


@pytest.fixture
def editor(window, qt_app, monkeypatch):
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: pytest.fail(message))
    window.show()
    qt_app.processEvents()
    # Pixels distintos em cada metade permitem verificar a origem de cada ampliação.
    rgba = (bytes([255, 0, 0, 255]) * 200 + bytes([0, 0, 255, 255]) * 200) * 200
    assert window._load_candidate(lambda: SourceImage(400, 200, rgba))
    qt_app.processEvents()
    qt_app.processEvents()
    window.view.set_navigation_zoom(1)
    return window


def mouse(view, kind, point):
    button = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
    buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
    event = QMouseEvent(kind, point, QPointF(-9000, -8000), button, buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def select_source(editor, start=(20, 24), end=(120, 64)):
    editor.actions_by_name["Selecionar"].trigger()
    first = editor.view.viewportTransform().map(QPointF(*start))
    last = editor.view.viewportTransform().map(QPointF(*end))
    mouse(editor.view, QEvent.Type.MouseButtonPress, first)
    mouse(editor.view, QEvent.Type.MouseMove, last)
    mouse(editor.view, QEvent.Type.MouseButtonRelease, last)


def create(editor, mode=ZoomMode.OVERLAY, factor=2):
    select_source(editor)
    panel = editor.regions_panel
    panel.scale.setValue(factor * 100)
    panel.mode.setCurrentIndex(panel.mode.findData(mode))
    panel.create_button.click()
    return editor.session.project.regions[-1]


def drag_points(editor, region, x, y):
    origin = QPointF(region.destination.x + 5, region.destination.y + 5)
    destination = QPointF(x + 5, y + 5)
    return editor.view.viewportTransform().map(origin), editor.view.viewportTransform().map(destination)


@pytest.mark.parametrize("zoom", [0.5, 1, 1.25, 1.5, 2])
def test_ca03_creation_200_percent_is_independent_of_navigation_zoom(editor, zoom):
    editor.view.set_navigation_zoom(zoom)
    region = create(editor)
    assert region.source == Rect(20, 24, 100, 40)
    assert region.destination == Rect(20, 24, 200, 80)
    assert editor.view.selected_region_id == region.id
    assert editor.actions_by_name["Objetos"].isChecked()
    assert editor.regions_panel.regions.count() == 1


def test_presets_and_custom_scale_modify_selected_object_from_original(editor):
    region = create(editor)
    panel = editor.regions_panel
    panel.presets.activated.emit(0)
    assert editor.session.project.regions[0].destination.width == 150
    panel.presets.activated.emit(2)
    assert editor.session.project.regions[0].destination.width == 300
    panel.scale.setValue(237)
    updated = editor.session.project.regions[0]
    assert updated.id == region.id and updated.source == region.source
    assert updated.destination == Rect(20, 24, 237, 95)
    assert panel.presets.currentText() == "Personalizada"


def test_three_regions_mode_roundtrip_preserves_identity_and_other_objects(editor):
    original_base = editor.session.project.base
    originals = [create(editor) for _ in range(3)]
    editor.regions_panel.regions.setCurrentRow(1)
    assert editor.view.selected_region_id == originals[1].id
    editor.regions_panel.mode.setCurrentIndex(1)
    changed = editor.session.project.regions[1]
    assert changed.mode is ZoomMode.EXTERNAL
    assert changed.destination == Rect(424, 24, 200, 80)
    editor.regions_panel.mode.setCurrentIndex(0)
    result = editor.session.project
    assert result.regions[0] == originals[0] and result.regions[2] == originals[2]
    assert result.regions[1].id == originals[1].id
    assert result.regions[1].source == originals[1].source
    assert result.regions[1].destination == changed.destination
    assert result.base is original_base


def test_click_selects_topmost_region_and_click_empty_does_not_edit(editor):
    first, second, third = [create(editor) for _ in range(3)]
    editor.session.mark_exported(editor.session.project)
    point = editor.view.viewportTransform().map(QPointF(30, 30))
    mouse(editor.view, QEvent.Type.MouseButtonPress, point)
    mouse(editor.view, QEvent.Type.MouseButtonRelease, point)
    assert editor.view.selected_region_id == third.id
    assert not editor.session.dirty
    point = editor.view.viewportTransform().map(QPointF(350, 150))
    mouse(editor.view, QEvent.Type.MouseButtonPress, point)
    mouse(editor.view, QEvent.Type.MouseButtonRelease, point)
    assert editor.view.selected_region_id is None
    assert not editor.session.dirty


def test_drag_has_single_commit_and_can_export_negative_canvas(editor, monkeypatch, tmp_path):
    region = create(editor, ZoomMode.EXTERNAL)
    snapshot = editor.session.project
    editor.session.mark_exported(snapshot)
    first, last = drag_points(editor, region, -210, -90)
    calls = []
    original_replace = editor.session.replace

    def commit(project):
        calls.append(project)
        original_replace(project)

    monkeypatch.setattr(editor.session, "replace", commit)
    mouse(editor.view, QEvent.Type.MouseButtonPress, first)
    mouse(editor.view, QEvent.Type.MouseMove, (first + last) / 2)
    mouse(editor.view, QEvent.Type.MouseMove, last)
    assert editor.session.project is snapshot and not editor.session.dirty
    mouse(editor.view, QEvent.Type.MouseButtonRelease, last)
    assert len(calls) == 1
    result = editor.session.project
    assert result.regions[0].destination == Rect(-210, -90, 200, 80)
    assert result.regions[0].id == region.id
    assert editor.session.dirty
    assert editor.scene.sceneRect().x() == -210
    assert editor.scene.items()[0].pos() == QPointF(-210, -90)
    path = tmp_path / "externo.png"
    monkeypatch.setattr(dialogs, "export_png", lambda parent: str(path))
    editor.export_image()
    output = images.load_image(str(path))
    assert (output.width, output.height) == (610, 290)
    assert output == images.source_from_image(compose(result))


@pytest.mark.parametrize("cancel", ["escape", "focus", "tool"])
def test_cancel_drag_restores_document_and_clean_state(editor, cancel):
    region = create(editor)
    snapshot = editor.session.project
    editor.session.mark_exported(snapshot)
    first, last = drag_points(editor, region, -40, 100)
    mouse(editor.view, QEvent.Type.MouseButtonPress, first)
    mouse(editor.view, QEvent.Type.MouseMove, last)
    if cancel == "escape":
        QTest.keyClick(editor.view, Qt.Key.Key_Escape)
    elif cancel == "focus":
        QApplication.sendEvent(editor.view, QFocusEvent(QEvent.Type.FocusOut))
    else:
        editor.actions_by_name["Pan"].trigger()
    mouse(editor.view, QEvent.Type.MouseButtonRelease, last)
    assert editor.session.project is snapshot and not editor.session.dirty
    assert editor.session.project.regions[0] == region


def test_external_drag_over_base_is_refused(editor, monkeypatch):
    region = create(editor, ZoomMode.EXTERNAL)
    snapshot, scene = editor.session.project, editor.scene
    editor.session.mark_exported(snapshot)
    errors = []
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: errors.append(message))
    first, last = drag_points(editor, region, 20, 24)
    mouse(editor.view, QEvent.Type.MouseButtonPress, first)
    mouse(editor.view, QEvent.Type.MouseMove, last)
    mouse(editor.view, QEvent.Type.MouseButtonRelease, last)
    assert editor.session.project is snapshot and editor.scene is scene
    assert not editor.session.dirty and errors


def test_delete_button_and_delete_key_remove_only_selected_object(editor):
    first, second, third = [create(editor) for _ in range(3)]
    editor.regions_panel.regions.setCurrentRow(1)
    editor.regions_panel.delete_button.click()
    assert [r.id for r in editor.session.project.regions] == [first.id, third.id]
    editor.regions_panel.regions.setCurrentRow(0)
    QTest.keyClick(editor.view, Qt.Key.Key_Delete)
    assert [r.id for r in editor.session.project.regions] == [third.id]
    assert editor.view.selected_region_id is None
    assert editor.session.dirty


def test_preview_failure_keeps_scene_document_and_controls(editor, monkeypatch):
    region = create(editor)
    snapshot, scene = editor.session.project, editor.scene
    editor.session.mark_exported(snapshot)
    errors = []
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: errors.append(message))

    def fail(*args, **kwargs):
        raise MemoryError()

    monkeypatch.setattr(main_window, "compose", fail)
    editor.regions_panel.scale.setValue(300)
    assert editor.session.project is snapshot and editor.scene is scene
    assert not editor.session.dirty and errors
    assert editor.regions_panel.scale.value() == 200
    assert editor.view.selected_region_id == region.id


def test_preview_matches_renderer_and_does_not_include_selection(editor, qt_app):
    create(editor, ZoomMode.EXTERNAL)
    create(editor, factor=1.5)
    create(editor, factor=3)
    qt_app.processEvents()
    project = editor.session.project
    preview = editor.scene.items()[0].pixmap().toImage()
    assert images.source_from_image(preview) == images.source_from_image(compose(project))
    assert len(editor.scene.items()) == 1


def test_new_document_clears_regions_and_controls(editor, monkeypatch):
    create(editor)
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: True)
    assert editor._load_candidate(lambda: SourceImage(1, 1, bytes([0, 0, 0, 255])))
    assert editor.session.project.regions == ()
    assert editor.view.selected_region_id is None
    assert editor.regions_panel.regions.count() == 0
    assert not editor.regions_panel.create_button.isEnabled()
    assert not editor.regions_panel.delete_button.isEnabled()


def test_noop_edits_do_not_mark_exported_document_dirty(editor):
    region = create(editor)
    snapshot = editor.session.project
    editor.session.mark_exported(snapshot)
    editor.move_zoom(region.id, region.destination.x, region.destination.y)
    editor.scale_zoom(2)
    editor.change_zoom_mode(ZoomMode.OVERLAY)
    assert editor.session.project is snapshot and not editor.session.dirty
