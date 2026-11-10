"""Diálogos portáveis com mensagens em português."""

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget


def open_image(parent: QWidget) -> str:
    path, _ = QFileDialog.getOpenFileName(parent, "Abrir imagem", "", "Imagens PNG/JPEG (*.png *.jpg *.jpeg)")
    return path


def export_png(parent: QWidget) -> str:
    path, _ = QFileDialog.getSaveFileName(parent, "Exportar PNG", "evidencia.png", "Imagem PNG (*.png)")
    return path


def confirm_discard(parent: QWidget) -> bool:
    result = QMessageBox.warning(
        parent, "Descartar trabalho não exportado?",
        "O documento contém trabalho não exportado. Deseja descartá-lo?",
        QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    return result == QMessageBox.StandardButton.Discard


def show_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(parent, "Não foi possível concluir", message)


def choose_monitor(parent: QWidget, monitors) -> str | None:
    labels = [f"Monitor {index + 1} — aproximadamente {monitor.width} × {monitor.height} pixels" for index, monitor in enumerate(monitors)]
    chosen, accepted = QInputDialog.getItem(parent, "Capturar monitor", "Monitor", labels, 0, False)
    return monitors[labels.index(chosen)].id if accepted and chosen in labels else None
