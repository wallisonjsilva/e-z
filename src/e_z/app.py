"""Inicialização da aplicação desktop."""

import sys

from PySide6.QtWidgets import QApplication

from e_z.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("e-z")
    app.setOrganizationName("e-z")
    window = MainWindow()
    window.show()
    return app.exec()
