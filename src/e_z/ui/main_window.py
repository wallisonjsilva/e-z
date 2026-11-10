"""Janela do editor com troca transacional de documento e preview da base."""

from collections.abc import Callable
from uuid import UUID

from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QLabel,
    QMainWindow,
    QProgressBar,
    QToolBar,
)
from PySide6.QtCore import Qt, QTimer

from e_z.application.session import DocumentSession
from e_z.application.capture import CaptureRequest, CaptureStatus
from e_z.application import regions
from e_z.domain.document import EvidenceProject, SourceImage, ZoomMode
from e_z.domain.geometry import Rect
from e_z.imaging.images import ImageError, load_image, source_from_image
from e_z.imaging.composition import compose, export_png
from e_z.imaging.budget import check_output
from e_z.platform import clipboard, dialogs
from e_z.platform.capture import create_capture_backend
from e_z.ui.canvas import CanvasTool, CanvasView
from e_z.ui.regions_panel import RegionsPanel
from e_z.ui.capture_controller import CaptureController
from e_z.imaging.tasks import TaskRunner, public_error


class MainWindow(QMainWindow):
    def __init__(self, *, runner=None) -> None:
        super().__init__()
        self.setWindowTitle("e-z")
        self.resize(1100, 720)
        self.session = DocumentSession()
        self.runner = runner if runner is not None else TaskRunner(self)
        self._activity_states = None
        self._activity_label = "Processando imagem…"
        self._close_requested = False
        self.scene = QGraphicsScene(self)
        self.view = CanvasView(self.scene, self)
        self.setCentralWidget(self.view)

        toolbar = QToolBar("Ferramentas", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self.actions_by_name: dict[str, QAction] = {}
        for label in ("Capturar", "Abrir", "Colar", "Selecionar", "Objetos", "Pan", "Exportar PNG", "Copiar composição"):
            action = toolbar.addAction(label)
            action.setEnabled(False)
            action.setToolTip(f"{label}: disponível em um próximo incremento")
            self.actions_by_name[label] = action

        properties = QDockWidget("Propriedades da ampliação", self)
        self.regions_panel = RegionsPanel(properties)
        self.selection_label = self.regions_panel.selection_label
        properties.setWidget(self.regions_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, properties)
        self.statusBar().showMessage("Abra uma imagem PNG/JPEG ou cole uma imagem para começar.")
        for label, callback, shortcut in (
            ("Abrir", self.open_image, QKeySequence.StandardKey.Open),
            ("Colar", self.paste_image, QKeySequence.StandardKey.Paste),
        ):
            action = self.actions_by_name[label]
            action.setEnabled(True)
            action.setToolTip(label)
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.setAutoRepeat(False)
            action.triggered.connect(callback)
        self.actions_by_name["Exportar PNG"].triggered.connect(self.export_image)
        copy_action = self.actions_by_name["Copiar composição"]
        copy_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Copy))
        copy_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        copy_action.setAutoRepeat(False)
        copy_action.setToolTip("Copiar a composição para colar em outro aplicativo (Ctrl+C)")
        copy_action.triggered.connect(self.copy_image)
        tools = QActionGroup(self)
        tools.setExclusive(True)
        for tool in CanvasTool:
            action = self.actions_by_name[tool.value]
            action.setCheckable(True)
            tools.addAction(action)
            action.triggered.connect(lambda checked, tool=tool: self.view.set_tool(tool))
        self.actions_by_name["Selecionar"].setChecked(True)
        toolbar.addSeparator()
        for label, callback in (
            ("Diminuir", lambda: self.view.set_navigation_zoom(self.view.navigation_zoom / 1.2)),
            ("Aumentar", lambda: self.view.set_navigation_zoom(self.view.navigation_zoom * 1.2)),
            ("100%", lambda: self.view.set_navigation_zoom(1)),
            ("Ajustar", self.view.fit_document),
        ):
            action = toolbar.addAction(label)
            action.setEnabled(False)
            action.setToolTip(f"{label}: zoom de navegação")
            action.triggered.connect(callback)
            self.actions_by_name[label] = action
        self.zoom_label = QLabel("Navegação: 100%", self)
        self.statusBar().addPermanentWidget(self.zoom_label)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(120)
        self.progress.setAccessibleName("Processamento em andamento")
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        self.view.zoom_changed.connect(lambda zoom: self.zoom_label.setText(f"Navegação: {zoom * 100:.1f}%"))
        self.view.selection_changed.connect(self._selection_changed)
        self.view.region_selected.connect(self._select_region)
        self.view.region_move_requested.connect(self.move_zoom)
        self.view.delete_requested.connect(self.delete_zoom)
        self.regions_panel.create_requested.connect(self.create_zoom)
        self.regions_panel.delete_requested.connect(self.delete_zoom)
        self.regions_panel.selection_changed.connect(self._select_region)
        self.regions_panel.scale_requested.connect(self.scale_zoom)
        self.regions_panel.mode_requested.connect(self.change_zoom_mode)
        for label, key, callback in (
            ("Remover ampliação", Qt.Key.Key_Delete, self._delete_from_shortcut),
            ("Cancelar seleção", Qt.Key.Key_Escape, self.view.escape),
        ):
            action = QAction(label, self)
            action.setShortcut(QKeySequence(key))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.setAutoRepeat(False)
            action.setEnabled(False)
            action.triggered.connect(callback)
            self.view.addAction(action)
            self.regions_panel.regions.addAction(action)
            self.actions_by_name[label] = action
        self.capture_controller = CaptureController(create_capture_backend(runner=self.runner), self)
        self.capture_controller.finished.connect(self._capture_finished)
        self.capture_controller.busy_changed.connect(self._capture_busy_changed)
        self.actions_by_name["Capturar"].triggered.connect(self.capture_image)
        self.runner.busy_changed.connect(self._processing_busy_changed)
        self._update_capture_action()

    def _update_capture_action(self) -> None:
        capabilities = self.capture_controller.backend.capabilities()
        action = self.actions_by_name["Capturar"]
        action.setEnabled(capabilities.available and not self.capture_controller.busy and not self.runner.busy)
        action.setToolTip(capabilities.message)

    def capture_image(self) -> None:
        if self.capture_controller.busy or self.runner.busy:
            return
        capabilities = self.capture_controller.backend.capabilities()
        if not capabilities.available:
            self.statusBar().showMessage(capabilities.message)
            return
        monitor_id = None
        if not capabilities.portal:
            monitor_id = dialogs.choose_monitor(self, capabilities.monitors)
            if monitor_id is None:
                return
        self._activity_label = "Preparando captura…"
        self.capture_controller.start(CaptureRequest(monitor_id, self._resident_bytes()))

    def _capture_busy_changed(self, busy: bool) -> None:
        self._sync_busy_controls()

    def _processing_busy_changed(self, busy: bool) -> None:
        self._sync_busy_controls()

    def _sync_busy_controls(self) -> None:
        busy = self.capture_controller.busy or self.runner.busy
        self.view.setEnabled(not busy)
        self.regions_panel.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy:
            if self._activity_states is None:
                self._activity_states = {name: action.isEnabled() for name, action in self.actions_by_name.items()}
            for action in self.actions_by_name.values():
                action.setEnabled(False)
            self.statusBar().showMessage(self._activity_label if self.runner.busy else "Captura em andamento; aguardando o sistema…")
        else:
            if self._activity_states is not None:
                for name, enabled in self._activity_states.items():
                    self.actions_by_name[name].setEnabled(enabled)
                self._activity_states = None
            self._update_capture_action()
            if self._close_requested:
                QTimer.singleShot(0, self.close)

    def _submit(self, label, operation, success) -> bool:
        if self.runner.busy or self.capture_controller.busy:
            return False
        self._activity_label = label

        def completed(value):
            try:
                return success(value)
            except Exception as error:
                self._operation_failed(public_error(error))
                return False

        return self.runner.submit(operation, completed, self._operation_failed)

    def _operation_failed(self, error) -> bool:
        self.regions_panel.set_project(self.session.project, self.view.selected_region_id)
        self.view.viewport().update()
        self.statusBar().showMessage("Operação não concluída; documento preservado.")
        if not self._close_requested:
            dialogs.show_error(self, error.message)
        return False

    def _capture_finished(self, result) -> None:
        if result.status is CaptureStatus.SUCCESS and result.image is not None:
            self._load_candidate(lambda: result.image)
        elif result.status is CaptureStatus.CANCELLED:
            self.statusBar().showMessage("Captura cancelada; documento preservado.")
        else:
            dialogs.show_error(self, result.message or "Não foi possível capturar uma imagem válida.")
            self.statusBar().showMessage("Captura não concluída; documento preservado.")

    def _resident_bytes(self) -> int:
        project = self.session.project
        if project is None:
            return clipboard.reserved_bytes()
        bounds = project.canvas_bounds
        return len(project.base.rgba) + bounds.width * bounds.height * 4 + clipboard.reserved_bytes()

    def _prepare_scene(self, project: EvidenceProject, image) -> QGraphicsScene:
        bounds = project.canvas_bounds
        check_output(project, self._resident_bytes())
        preview = QPixmap.fromImage(image)
        if preview.isNull():
            raise ImageError("Não foi possível preparar a imagem para exibição.")
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(preview)
        item.setPos(bounds.x, bounds.y)
        scene.addItem(item)
        scene.setSceneRect(bounds.x, bounds.y, bounds.width, bounds.height)
        return scene

    def open_image(self) -> None:
        if self.runner.busy or self.capture_controller.busy:
            return
        path = dialogs.open_image(self)
        if path:
            resident = self._resident_bytes()
            self._load_candidate(lambda: load_image(path, resident_bytes=resident))

    def paste_image(self) -> None:
        if self.runner.busy or self.capture_controller.busy:
            return
        resident = self._resident_bytes()
        try:
            image = clipboard.snapshot_image(resident_bytes=resident)
        except Exception as error:
            self._operation_failed(public_error(error))
            return
        pending = [image]
        del image

        def convert():
            raw = pending.pop()
            return source_from_image(raw, resident_bytes=resident)

        self._load_candidate(convert)

    def _load_candidate(self, loader: Callable[[], SourceImage]) -> bool:
        snapshot = self.session.project
        resident = self._resident_bytes()

        def prepare():
            project = EvidenceProject(loader())
            check_output(project, resident)
            return project, compose(project, resident_bytes=resident)

        return self._submit("Carregando imagem…", prepare, lambda result: self._apply_loaded(snapshot, result))

    def _apply_loaded(self, snapshot, result) -> bool:
        if self._close_requested or self.session.project is not snapshot:
            return False
        project, image = result
        scene = self._prepare_scene(project, image)
        if self.session.dirty and not dialogs.confirm_discard(self):
            self._refresh_document_state()
            return False
        previous_scene = self.scene
        scene.setParent(self)
        self.scene = scene
        self.view.setScene(scene)
        self.session.replace(project)
        previous_scene.clear()
        previous_scene.deleteLater()
        self.view.set_source_size(project.base.width, project.base.height)
        self.view.set_regions(())
        self.regions_panel.set_project(project, None)
        self.view.fit_document()
        self._refresh_document_state()
        return True

    def _refresh_document_state(self) -> None:
        project = self.session.project
        self.actions_by_name["Exportar PNG"].setEnabled(project is not None)
        self.actions_by_name["Copiar composição"].setEnabled(project is not None)
        self.actions_by_name["Cancelar seleção"].setEnabled(project is not None)
        self.actions_by_name["Remover ampliação"].setEnabled(self.view.selected_region_id is not None)
        for label in ("Selecionar", "Objetos", "Pan", "Diminuir", "Aumentar", "100%", "Ajustar"):
            self.actions_by_name[label].setEnabled(project is not None)
        if project:
            self.actions_by_name["Selecionar"].setToolTip("Arraste para selecionar uma região da imagem-base")
            self.actions_by_name["Pan"].setToolTip("Arraste para navegar pela imagem")
            self.actions_by_name["Objetos"].setToolTip("Selecione uma ampliação e arraste seu contorno para movê-la")
        if project:
            self.actions_by_name["Exportar PNG"].setToolTip("Exportar a composição em PNG")
        if project:
            self.setWindowTitle("e-z — Evidência" + (" *" if self.session.dirty else ""))
            self.statusBar().showMessage(f"{project.base.width} × {project.base.height} pixels — "
                                        + ("trabalho não exportado" if self.session.dirty else "exportado"))

    def _selection_changed(self, rect: Rect | None) -> None:
        self.regions_panel.set_source_selection(rect)

    def _select_region(self, region_id: UUID | None) -> None:
        self.view.select_region(region_id)
        self.regions_panel.set_project(self.session.project, self.view.selected_region_id)
        self.actions_by_name["Remover ampliação"].setEnabled(self.view.selected_region_id is not None)

    def _edit_regions(self, operation: Callable[[EvidenceProject], EvidenceProject], *, select_new: bool = False) -> bool:
        project = self.session.project
        if project is None:
            return False
        resident = self._resident_bytes()
        selected_id = self.view.selected_region_id

        def prepare():
            candidate = operation(project)
            if candidate is project:
                return candidate, None
            check_output(candidate, resident)
            return candidate, compose(candidate, resident_bytes=resident)

        return self._submit("Atualizando ampliação…", prepare,
                            lambda result: self._apply_edit(project, result, selected_id, select_new))

    def _apply_edit(self, project, result, selected_id, select_new) -> bool:
        if self._close_requested or self.session.project is not project:
            return False
        candidate, image = result
        if candidate is project:
            self._refresh_document_state()
            return True
        scene = self._prepare_scene(candidate, image)
        center = self.view.mapToScene(self.view.viewport().rect().center())
        previous_scene = self.scene
        selected_id = candidate.regions[-1].id if select_new else selected_id
        scene.setParent(self)
        self.scene = scene
        self.view.setScene(scene)
        self.session.replace(candidate)
        self.view.set_regions(candidate.regions, selected_id)
        self.regions_panel.set_project(candidate, self.view.selected_region_id)
        self.view.centerOn(center)
        previous_scene.clear()
        previous_scene.deleteLater()
        self._refresh_document_state()
        if select_new:
            self.actions_by_name["Objetos"].trigger()
        return True

    def create_zoom(self) -> None:
        source = self.view.selection
        if source is None:
            return
        factor, mode = self.regions_panel.factor, self.regions_panel.zoom_mode
        self._edit_regions(lambda project: regions.create_region(project, source, factor, mode), select_new=True)

    def move_zoom(self, region_id: UUID, x: int, y: int) -> None:
        self._edit_regions(lambda project: regions.move_region(project, region_id, x, y))

    def scale_zoom(self, factor: float) -> None:
        region_id = self.view.selected_region_id
        if region_id is not None:
            self._edit_regions(lambda project: regions.set_region_scale(project, region_id, factor))

    def change_zoom_mode(self, mode: ZoomMode) -> None:
        region_id = self.view.selected_region_id
        if region_id is not None:
            self._edit_regions(lambda project: regions.set_region_mode(project, region_id, mode))

    def delete_zoom(self) -> None:
        region_id = self.view.selected_region_id
        if region_id is not None:
            self._edit_regions(lambda project: regions.delete_region(project, region_id))

    def _delete_from_shortcut(self) -> None:
        self.view.cancel_gesture()
        self.delete_zoom()

    def copy_image(self) -> None:
        project = self.session.project
        if project is None or self.capture_controller.busy or self.runner.busy:
            return
        resident = self._resident_bytes() - len(project.base.rgba)
        self._submit("Preparando cópia…", lambda: compose(project, resident_bytes=resident),
                     lambda image: self._publish_copy(project, image))

    def _publish_copy(self, project, image) -> None:
        if self._close_requested or self.session.project is not project:
            return
        clipboard.write_image(image, resident_bytes=self._resident_bytes() - clipboard.reserved_bytes())
        self.statusBar().showMessage("Composição copiada. Cole em outro aplicativo; exporte PNG para manter um arquivo.")

    def export_image(self) -> None:
        project = self.session.project
        if project is None or self.runner.busy or self.capture_controller.busy:
            return
        path = dialogs.export_png(self)
        if not path:
            return
        resident = self._resident_bytes() - len(project.base.rgba)
        self._submit("Exportando PNG…", lambda: export_png(project, path, resident_bytes=resident),
                     lambda result: self._export_finished(project))

    def _export_finished(self, project) -> None:
        self.session.mark_exported(project)
        self._refresh_document_state()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.capture_controller.busy:
            self.capture_controller.cancel()
        if self.runner.busy:
            self._close_requested = True
            self.statusBar().showMessage("Aguardando a operação terminar para fechar…")
            event.ignore()
            return
        self._close_requested = False
        if self.session.dirty and not dialogs.confirm_discard(self):
            event.ignore()
        else:
            event.accept()
