"""Controles de criação e propriedades das ampliações da E1."""

from uuid import UUID

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from true_screen.domain.document import EvidenceProject, ZoomMode
from true_screen.domain.geometry import Rect


class RegionsPanel(QWidget):
    create_requested = Signal()
    delete_requested = Signal()
    selection_changed = Signal(object)
    scale_requested = Signal(float)
    mode_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        self._selected_id: UUID | None = None
        self._source_selection: Rect | None = None
        self._has_project = False
        self._project: EvidenceProject | None = None
        layout = QVBoxLayout(self)
        self.selection_label = QLabel("Nenhuma região selecionada.", self)
        self.selection_label.setWordWrap(True)
        layout.addWidget(self.selection_label)
        form = QFormLayout()
        self.presets = QComboBox(self)
        self.presets.addItems(["150%", "200%", "300%", "Personalizada"])
        self.presets.setCurrentIndex(1)
        self.scale = QDoubleSpinBox(self)
        self.scale.setRange(100, 800)
        self.scale.setDecimals(2)
        self.scale.setSingleStep(25)
        self.scale.setSuffix("%")
        self.scale.setValue(200)
        self.scale.setKeyboardTracking(False)
        self.scale.setAccessibleName("Escala da ampliação em porcentagem")
        self.mode = QComboBox(self)
        self.mode.addItem("Sobreposto", ZoomMode.OVERLAY)
        self.mode.addItem("Externo", ZoomMode.EXTERNAL)
        self.mode.setAccessibleName("Modo da ampliação")
        form.addRow("Escala predefinida", self.presets)
        form.addRow("Escala personalizada", self.scale)
        form.addRow("Modo", self.mode)
        layout.addLayout(form)
        self.create_button = QPushButton("Criar ampliação", self)
        layout.addWidget(self.create_button)
        layout.addWidget(QLabel("Ampliações (selecione para editar)", self))
        self.regions = QListWidget(self)
        self.regions.setAccessibleName("Ampliações do documento")
        layout.addWidget(self.regions)
        self.destination_label = QLabel("Nenhuma ampliação selecionada.", self)
        self.destination_label.setWordWrap(True)
        layout.addWidget(self.destination_label)
        self.delete_button = QPushButton("Remover ampliação", self)
        layout.addWidget(self.delete_button)
        self.create_button.clicked.connect(self.create_requested)
        self.delete_button.clicked.connect(self.delete_requested)
        self.regions.currentItemChanged.connect(self._item_changed)
        self.presets.activated.connect(self._preset_changed)
        self.scale.valueChanged.connect(self._scale_changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.set_project(None, None)

    @property
    def factor(self) -> float:
        return self.scale.value() / 100

    @property
    def zoom_mode(self) -> ZoomMode:
        return self.mode.currentData()

    def set_source_selection(self, rect: Rect | None) -> None:
        self._source_selection = rect
        self.selection_label.setText("Nenhuma região selecionada." if rect is None else
                                     f"Origem: ({rect.x}, {rect.y})\nSeleção: {rect.width} × {rect.height} pixels")
        self.create_button.setEnabled(self._has_project and rect is not None)

    def set_project(self, project: EvidenceProject | None, selected_id: UUID | None) -> None:
        self._updating = True
        try:
            self._has_project = project is not None
            self._selected_id = selected_id
            if project is not self._project:
                self.regions.clear()
                for index, region in enumerate(project.regions if project else ()):
                    item = QListWidgetItem(f"Ampliação {index + 1} — {region.destination.width} × {region.destination.height}")
                    item.setData(Qt.ItemDataRole.UserRole, region.id)
                    self.regions.addItem(item)
                self._project = project
            self.regions.setCurrentRow(-1)
            selected = None
            for index, region in enumerate(project.regions if project else ()):
                if region.id == selected_id:
                    selected = region
                    self.regions.setCurrentRow(index)
            if selected:
                self.scale.setValue(selected.destination.width / selected.source.width * 100)
                self.mode.setCurrentIndex(self.mode.findData(selected.mode))
                self._sync_preset()
                dest = selected.destination
                self.destination_label.setText(f"Destino: ({dest.x}, {dest.y})\n{dest.width} × {dest.height} pixels\n"
                                               "Interpolação suave Qt")
            else:
                self.destination_label.setText("Nenhuma ampliação selecionada.")
            for control in (self.presets, self.scale, self.mode):
                control.setEnabled(project is not None)
            self.create_button.setEnabled(project is not None and self._source_selection is not None)
            self.delete_button.setEnabled(selected is not None)
        finally:
            self._updating = False

    def _sync_preset(self) -> None:
        self.presets.setCurrentIndex({150: 0, 200: 1, 300: 2}.get(self.scale.value(), 3))

    def _preset_changed(self, index: int) -> None:
        if index < 3:
            self.scale.setValue((150, 200, 300)[index])
        else:
            self.scale.setFocus()

    def _scale_changed(self, value: float) -> None:
        if not self._updating:
            self._sync_preset()
            if self._selected_id is not None:
                self.scale_requested.emit(value / 100)

    def _mode_changed(self, index: int) -> None:
        if not self._updating and self._selected_id is not None:
            self.mode_requested.emit(self.mode.currentData())

    def _item_changed(self, current, previous) -> None:
        if not self._updating:
            self.selection_changed.emit(current.data(Qt.ItemDataRole.UserRole) if current else None)
