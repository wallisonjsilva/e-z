"""W06: gestos em coordenadas lógicas, independentemente do documento e DPI."""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QFocusEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsScene

from true_screen.domain.document import SourceImage
from true_screen.domain.geometry import Rect, scaled_size
from true_screen.imaging.composition import compose
from true_screen.imaging.images import source_from_image
from true_screen.platform import dialogs
from true_screen.ui.canvas import CanvasTool, CanvasView


@pytest.fixture
def canvas(qt_app):
    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, 1000, 800)
    view = CanvasView(scene)
    view.resize(640, 480)
    view.set_source_size(1000, 800)
    view.show()
    qt_app.processEvents()
    yield view
    view.close()
    view.deleteLater()
    qt_app.processEvents()


def mouse(view, event_type, position, button=Qt.MouseButton.LeftButton):
    buttons = Qt.MouseButton.NoButton if event_type == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
    if event_type == QEvent.Type.MouseMove:
        button = Qt.MouseButton.NoButton
    event = QMouseEvent(event_type, QPointF(position), QPointF(-9000, -8000),
                        button, buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def select(view, start, end):
    first = view.viewportTransform().map(QPointF(*start))
    last = view.viewportTransform().map(QPointF(*end))
    mouse(view, QEvent.Type.MouseButtonPress, first)
    mouse(view, QEvent.Type.MouseMove, last)
    mouse(view, QEvent.Type.MouseButtonRelease, last)


@pytest.mark.parametrize("zoom", [0.125, 0.5, 1, 1.25, 1.5, 2, 3.2])
@pytest.mark.parametrize("start,end", [((20, 24), (120, 64)), ((120, 64), (20, 24)),
                                     ((20, 64), (120, 24)), ((120, 24), (20, 64))])
def test_selection_directions_zoom_pan_and_negative_global_origin(canvas, zoom, start, end):
    canvas.set_navigation_zoom(zoom)
    canvas.centerOn(300, 200)
    select(canvas, start, end)
    assert canvas.selection == Rect(20, 24, 100, 40)
    assert scaled_size(canvas.selection, 2) == (200, 80)


def test_fractional_pointer_is_not_rounded_to_logical_integer(canvas):
    canvas.set_navigation_zoom(1.5)
    select(canvas, (20.25, 24.75), (119.25, 63.25))
    assert canvas.selection == Rect(20, 24, 100, 40)


def test_clips_at_image_edges_and_rejects_empty_or_fully_external(canvas):
    select(canvas, (-30, -40), (1010, 810))
    assert canvas.selection == Rect(0, 0, 1000, 800)
    select(canvas, (1.5, 2), (1.5, 50))
    assert canvas.selection == Rect(0, 0, 1000, 800)
    select(canvas, (-30, -20), (-2, -1))
    assert canvas.selection == Rect(0, 0, 1000, 800)


def test_escape_cancels_draft_then_clears_selection(canvas):
    select(canvas, (20, 24), (120, 64))
    first = canvas.viewportTransform().map(QPointF(30, 30))
    last = canvas.viewportTransform().map(QPointF(60, 60))
    mouse(canvas, QEvent.Type.MouseButtonPress, first)
    mouse(canvas, QEvent.Type.MouseMove, last)
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    mouse(canvas, QEvent.Type.MouseButtonRelease, last)
    assert canvas.selection == Rect(20, 24, 100, 40)
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.selection is None


@pytest.mark.parametrize("cancel", ["tool", "focus"])
def test_switching_tool_or_losing_focus_cancels_selection(canvas, cancel):
    select(canvas, (20, 24), (120, 64))
    first = canvas.viewportTransform().map(QPointF(30, 30))
    last = canvas.viewportTransform().map(QPointF(60, 60))
    mouse(canvas, QEvent.Type.MouseButtonPress, first)
    mouse(canvas, QEvent.Type.MouseMove, last)
    if cancel == "tool":
        canvas.set_tool(CanvasTool.PAN)
    else:
        QApplication.sendEvent(canvas, QFocusEvent(QEvent.Type.FocusOut))
    mouse(canvas, QEvent.Type.MouseButtonRelease, last)
    assert canvas.selection == Rect(20, 24, 100, 40)


def test_pan_drag_changes_mapping_without_changing_selection(canvas):
    select(canvas, (20, 24), (120, 64))
    canvas.set_navigation_zoom(2)
    canvas.centerOn(500, 400)
    before = canvas.viewport_to_source(QPointF(100, 100))
    canvas.set_tool(CanvasTool.PAN)
    QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    QTest.mouseMove(canvas.viewport(), QPoint(140, 120))
    QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(140, 120))
    after = canvas.viewport_to_source(QPointF(100, 100))
    assert after.x() == pytest.approx(before.x() - 20)
    assert after.y() == pytest.approx(before.y() - 10)
    assert canvas.selection == Rect(20, 24, 100, 40)


def wheel(view, delta):
    event = QWheelEvent(QPointF(100, 100), QPointF(-9000, -8000), QPoint(), QPoint(0, delta),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(view.viewport(), event)


def test_wheel_zoom_limits_and_gesture_does_not_change_zoom(canvas):
    canvas.set_navigation_zoom(1)
    wheel(canvas, 120)
    assert canvas.navigation_zoom == pytest.approx(1.2)
    first = canvas.viewportTransform().map(QPointF(20, 20))
    mouse(canvas, QEvent.Type.MouseButtonPress, first)
    wheel(canvas, 120)
    assert canvas.navigation_zoom == pytest.approx(1.2)
    mouse(canvas, QEvent.Type.MouseButtonRelease, first)
    canvas.set_navigation_zoom(100000)
    assert canvas.navigation_zoom == CanvasView.MAX_ZOOM
    canvas.set_navigation_zoom(0.000001)
    assert canvas.navigation_zoom == CanvasView.MIN_ZOOM
    for factor in (float("nan"), float("inf"), 0, -1):
        with pytest.raises(ValueError):
            canvas.set_navigation_zoom(factor)


def test_zoom_keeps_pointer_anchor_with_scrollbar_rounding(canvas):
    canvas.set_navigation_zoom(2)
    canvas.centerOn(500, 400)
    point = QPointF(100, 100)
    before = canvas.viewport_to_source(point)
    wheel(canvas, 120)
    after = canvas.viewport_to_source(point)
    # Scrollbars Qt usam posições inteiras lógicas.
    assert abs(after.x() - before.x()) <= 1 / canvas.navigation_zoom
    assert abs(after.y() - before.y()) <= 1 / canvas.navigation_zoom


def test_fit_and_reset_do_not_change_selection(canvas, qt_app):
    select(canvas, (20, 24), (120, 64))
    canvas.set_navigation_zoom(3)
    canvas.fit_document()
    qt_app.processEvents()
    qt_app.processEvents()
    visible = canvas.mapToScene(canvas.viewport().rect()).boundingRect()
    assert visible.contains(canvas.sceneRect())
    assert canvas.selection == Rect(20, 24, 100, 40)
    canvas.set_navigation_zoom(1)
    assert canvas.navigation_zoom == 1
    assert canvas.selection == Rect(20, 24, 100, 40)


def test_fit_tracks_resize_until_manual_navigation(canvas, qt_app):
    canvas.fit_document()
    canvas.resize(800, 600)
    qt_app.processEvents()
    qt_app.processEvents()
    visible = canvas.mapToScene(canvas.viewport().rect()).boundingRect()
    assert visible.contains(canvas.sceneRect())
    canvas.set_navigation_zoom(2)
    canvas.resize(500, 350)
    qt_app.processEvents()
    assert canvas.navigation_zoom == 2


def load_base(window, qt_app):
    window.show()
    qt_app.processEvents()
    assert window._load_candidate(lambda: SourceImage(400, 200, bytes([11, 22, 33, 255]) * 80000))
    qt_app.processEvents()


def test_ui_tools_zoom_and_selection_leave_document_and_export_unchanged(window, qt_app):
    assert not window.actions_by_name["Selecionar"].isEnabled()
    load_base(window, qt_app)
    document = window.session.project
    window.session.mark_exported(document)
    for label in ("Selecionar", "Pan", "Diminuir", "Aumentar", "100%", "Ajustar"):
        assert window.actions_by_name[label].isEnabled()
    window.actions_by_name["100%"].trigger()
    select(window.view, (20, 24), (120, 64))
    assert "100 × 40 pixels" in window.selection_label.text()
    window.actions_by_name["Pan"].trigger()
    assert window.view.tool is CanvasTool.PAN
    assert not window.actions_by_name["Selecionar"].isChecked()
    window.actions_by_name["Selecionar"].trigger()
    assert window.view.tool is CanvasTool.SELECT
    window.actions_by_name["Aumentar"].trigger()
    assert window.view.navigation_zoom == pytest.approx(1.2)
    window.actions_by_name["Diminuir"].trigger()
    assert window.view.navigation_zoom == pytest.approx(1)
    assert window.session.project is document and not window.session.dirty
    assert source_from_image(compose(document)) == document.base
    # A decoração fica na view; não adiciona itens ou extensão ao canvas.
    assert len(window.scene.items()) == 1
    assert window.scene.sceneRect() == QRectF(0, 0, 400, 200)
    QTest.keyClick(window.view, Qt.Key.Key_Escape)
    assert "Nenhuma região" in window.selection_label.text()


def test_new_document_clears_selection_and_cancelled_import_preserves_view(window, qt_app, monkeypatch):
    load_base(window, qt_app)
    window.view.set_navigation_zoom(1.5)
    select(window.view, (20, 24), (120, 64))
    transform = window.view.viewportTransform()
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: False)
    candidate = lambda: SourceImage(100, 100, bytes([22, 33, 44, 255]) * 10000)
    assert not window._load_candidate(candidate)
    assert window.view.selection == Rect(20, 24, 100, 40)
    assert window.view.viewportTransform() == transform
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: True)
    assert window._load_candidate(candidate)
    assert window.view.selection is None
    assert window.scene.sceneRect() == QRectF(0, 0, 100, 100)


@pytest.mark.parametrize("scale", ["1", "1.25", "1.5", "2"])
def test_qt_scale_factors_in_isolated_process(scale):
    # Cada QApplication deve iniciar com seu próprio QT_SCALE_FACTOR.
    script = '''
import os
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsScene
from true_screen.ui.canvas import CanvasView
from true_screen.domain.geometry import Rect, scaled_size
app = QApplication([])
scene = QGraphicsScene()
scene.setSceneRect(0, 0, 400, 200)
view = CanvasView(scene)
view.resize(640, 480)
view.set_source_size(400, 200)
view.show()
app.processEvents()
assert abs(view.devicePixelRatioF() - float(os.environ["QT_SCALE_FACTOR"])) < 0.01
for zoom in (0.5, 1, 1.25, 1.5, 2):
    view.set_navigation_zoom(zoom)
    view.centerOn(100, 60)
    first = view.mapFromScene(QPointF(20, 24))
    last = view.mapFromScene(QPointF(120, 64))
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseMove(view.viewport(), last)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=last)
    assert view.selection == Rect(20, 24, 100, 40), (zoom, view.selection)
    assert scaled_size(view.selection, 2) == (200, 80)
view.close()
'''
    result = subprocess.run([sys.executable, "-c", script],
                            cwd=Path(__file__).resolve().parents[1],
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_SCALE_FACTOR": scale},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
