"""Seleção e navegação locais; uma unidade de cena é um pixel da base."""

from enum import Enum
from math import floor, isfinite
from uuid import UUID

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPen, QResizeEvent, QTransform, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from true_screen.domain.geometry import Rect, selection_rect
from true_screen.domain.document import ZoomRegion


class CanvasTool(Enum):
    SELECT = "Selecionar"
    OBJECTS = "Objetos"
    PAN = "Pan"


class CanvasView(QGraphicsView):
    selection_changed = Signal(object)
    zoom_changed = Signal(float)
    region_selected = Signal(object)
    region_move_requested = Signal(object, int, int)
    delete_requested = Signal()
    MIN_ZOOM = 0.005
    MAX_ZOOM = 32.0

    def __init__(self, scene: QGraphicsScene, parent=None) -> None:
        super().__init__(scene, parent)
        self._bounds: Rect | None = None
        self._selection: Rect | None = None
        self._draft: Rect | None = None
        self._selection_start: QPointF | None = None
        self._pan_start: QPointF | None = None
        self._pan_scroll = (0, 0)
        self._tool = CanvasTool.SELECT
        self._regions: tuple[ZoomRegion, ...] = ()
        self._selected_region_id: UUID | None = None
        self._object_start: QPointF | None = None
        self._object_region: ZoomRegion | None = None
        self._object_destination: Rect | None = None
        self._fit_active = False
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_document)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName("Área de edição da evidência")

    @property
    def selection(self) -> Rect | None:
        return self._selection

    @property
    def tool(self) -> CanvasTool:
        return self._tool

    @property
    def selected_region_id(self) -> UUID | None:
        return self._selected_region_id

    def set_regions(self, regions: tuple[ZoomRegion, ...], selected_id: UUID | None = None) -> None:
        self.cancel_gesture()
        self._regions = regions
        self.select_region(selected_id)

    def select_region(self, region_id: UUID | None) -> None:
        self._selected_region_id = region_id if any(r.id == region_id for r in self._regions) else None
        self.viewport().update()

    @property
    def navigation_zoom(self) -> float:
        return self.transform().m11()

    def set_source_size(self, width: int, height: int) -> None:
        self._fit_timer.stop()
        self._fit_active = False
        self._bounds = Rect(0, 0, width, height)
        self.clear_selection()

    def set_tool(self, tool: CanvasTool) -> None:
        self.cancel_gesture()
        self._tool = tool
        self._restore_cursor()

    def _restore_cursor(self) -> None:
        cursors = {CanvasTool.PAN: Qt.CursorShape.OpenHandCursor,
                   CanvasTool.SELECT: Qt.CursorShape.CrossCursor,
                   CanvasTool.OBJECTS: Qt.CursorShape.PointingHandCursor}
        self.setCursor(cursors[self._tool])

    def viewport_to_source(self, point: QPointF) -> QPointF:
        inverse, valid = self.viewportTransform().inverted()
        if not valid:
            raise ValueError("A transformação da visualização não pode ser invertida.")
        mapped = inverse.map(point)
        # Evita ceil(120.00000000000001) causado somente pela inversão numérica.
        def stable(value: float) -> float:
            nearest = round(value)
            return float(nearest) if abs(value - nearest) <= 1e-9 else value

        return QPointF(stable(mapped.x()), stable(mapped.y()))

    def set_navigation_zoom(self, factor: float, anchor: QPointF | None = None) -> None:
        if not isfinite(factor) or factor <= 0:
            raise ValueError("O zoom de navegação deve ser positivo e finito.")
        self._fit_timer.stop()
        self._fit_active = False
        self.cancel_gesture()
        factor = max(self.MIN_ZOOM, min(self.MAX_ZOOM, factor))
        anchor = anchor if anchor is not None else QPointF(self.viewport().rect().center())
        before = self.viewport_to_source(anchor)
        self.setTransform(QTransform.fromScale(factor, factor))
        after = self.viewport_to_source(anchor)
        center = self.mapToScene(self.viewport().rect().center())
        self.centerOn(center + before - after)
        self.zoom_changed.emit(factor)

    def fit_document(self) -> None:
        if self._bounds is None:
            return
        bounds = self.sceneRect()
        factor = min(max(1, self.viewport().width() - 4) / bounds.width(),
                     max(1, self.viewport().height() - 4) / bounds.height())
        self.set_navigation_zoom(factor)
        self.centerOn(bounds.center())
        self._fit_active = True

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._fit_active:
            self._fit_timer.start(0)

    def clear_selection(self) -> None:
        self.cancel_gesture()
        self._selection = None
        self.selection_changed.emit(None)
        self.viewport().update()

    def cancel_gesture(self) -> None:
        self._selection_start = None
        self._pan_start = None
        self._draft = None
        self._object_start = None
        self._object_region = None
        self._object_destination = None
        self._restore_cursor()
        self.viewport().update()

    def _rect_to(self, position: QPointF) -> Rect | None:
        if self._selection_start is None or self._bounds is None:
            return None
        end = self.viewport_to_source(position)
        try:
            return selection_rect(self._selection_start.x(), self._selection_start.y(), end.x(), end.y(),
                                  width=self._bounds.width, height=self._bounds.height)
        except ValueError:
            return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._bounds is None:
            super().mousePressEvent(event)
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if self._tool is CanvasTool.PAN:
            self._fit_active = False
            self._fit_timer.stop()
            self._pan_start = event.position()
            self._pan_scroll = (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self._tool is CanvasTool.OBJECTS:
            point = self.viewport_to_source(event.position())
            region = next((r for r in reversed(sorted(self._regions, key=lambda r: r.z_index))
                           if r.destination.x <= point.x() < r.destination.right
                           and r.destination.y <= point.y() < r.destination.bottom), None)
            self.select_region(region.id if region else None)
            self.region_selected.emit(self._selected_region_id)
            if region:
                self._fit_active = False
                self._fit_timer.stop()
                self._object_start = point
                self._object_region = region
                self._object_destination = region.destination
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self.select_region(None)
            self.region_selected.emit(None)
            self._selection_start = self.viewport_to_source(event.position())
            self._draft = None
            self.viewport().update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._object_start is not None:
            self._object_destination = self._object_rect_to(event.position())
            self.viewport().update()
            event.accept()
        elif self._selection_start is not None:
            self._draft = self._rect_to(event.position())
            self.viewport().update()
            event.accept()
        elif self._pan_start is not None:
            delta = event.position() - self._pan_start
            self.horizontalScrollBar().setValue(self._pan_scroll[0] - round(delta.x()))
            self.verticalScrollBar().setValue(self._pan_scroll[1] - round(delta.y()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def _object_rect_to(self, position: QPointF) -> Rect:
        point = self.viewport_to_source(position)
        destination = self._object_region.destination
        return Rect(destination.x + floor(point.x() - self._object_start.x() + 0.5),
                    destination.y + floor(point.y() - self._object_start.y() + 0.5),
                    destination.width, destination.height)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._object_start is not None:
            region = self._object_region
            destination = self._object_rect_to(event.position())
            self.cancel_gesture()
            if destination != region.destination:
                self.region_move_requested.emit(region.id, destination.x, destination.y)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton and self._selection_start is not None:
            rect = self._rect_to(event.position())
            self.cancel_gesture()
            if rect is not None:
                self._selection = rect
                self.selection_changed.emit(rect)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton and self._pan_start is not None:
            self.cancel_gesture()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._bounds is None:
            super().wheelEvent(event)
            return
        if self._selection_start is None and self._pan_start is None and self._object_start is None:
            steps = max(-10, min(10, event.angleDelta().y() / 120))
            if steps:
                self.set_navigation_zoom(self.navigation_zoom * 1.2 ** steps, event.position())
        event.accept()

    def escape(self) -> None:
        if self._selection_start is not None or self._pan_start is not None or self._object_start is not None:
            self.cancel_gesture()
        elif self._selected_region_id is not None:
            self.select_region(None)
            self.region_selected.emit(None)
        else:
            self.clear_selection()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.escape()
            event.accept()
        elif event.key() == Qt.Key.Key_Delete and self._tool is CanvasTool.OBJECTS:
            self.cancel_gesture()
            self.delete_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.cancel_gesture()
        super().focusOutEvent(event)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        selection = self._draft if self._selection_start is not None else self._selection
        painter.save()
        try:
            pen = QPen(QColor("#2563eb"), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QColor(37, 99, 235, 32))
            if selection is not None:
                painter.drawRect(QRectF(selection.x, selection.y, selection.width, selection.height))
            destination = self._object_destination
            if destination is None:
                destination = next((r.destination for r in self._regions if r.id == self._selected_region_id), None)
            if destination is not None:
                pen.setColor(QColor("#c2410c"))
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(destination.x, destination.y, destination.width, destination.height))
        finally:
            painter.restore()
