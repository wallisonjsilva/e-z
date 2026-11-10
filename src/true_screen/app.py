"""Inicialização da aplicação desktop."""

import sys

from PySide6.QtWidgets import QApplication

from true_screen.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("True Screen")
    app.setOrganizationName("True Screen")
    window = MainWindow()
    window.show()
    return app.exec()
