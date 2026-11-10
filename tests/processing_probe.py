"""Sonda offscreen com fixture sintética e pool Qt real; não homologa desktop.

Executar no Linux: .venv/bin/python tests/processing_probe.py
"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
import resource

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from true_screen.application import regions
from true_screen.domain.document import SourceImage, ZoomMode
from true_screen.domain.geometry import Rect
from true_screen.imaging.images import image_from_source, load_image
from true_screen.platform import dialogs
from true_screen.ui.main_window import MainWindow


def run():
    app = QApplication([])
    window = MainWindow()
    window.show()
    gaps = []
    previous = monotonic()

    def heartbeat():
        nonlocal previous
        now = monotonic()
        gaps.append(now - previous)
        previous = now

    timer = QTimer()
    timer.setInterval(2)
    timer.timeout.connect(heartbeat)
    timer.start()

    def settle():
        loop = QEventLoop()
        poll = QTimer()
        poll.setInterval(1)
        poll.timeout.connect(lambda: loop.quit() if not window.runner.busy else None)
        poll.start()
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        deadline.start(15000)
        loop.exec()
        assert not window.runner.busy

    with TemporaryDirectory(prefix="true-screen-processing-") as directory:
        path, output = Path(directory) / "base.png", Path(directory) / "saida.png"
        fixture = SourceImage(1920, 1080, bytes([17, 31, 99, 255]) * (1920 * 1080))
        assert image_from_source(fixture).save(str(path), "PNG")
        del fixture
        dialogs.open_image = lambda parent: str(path)
        dialogs.export_png = lambda parent: str(output)
        errors = []
        dialogs.show_error = lambda parent, message: errors.append(message)
        app.processEvents()
        gaps.clear()
        previous = monotonic()
        started = monotonic()
        window.open_image()
        settle()
        window._edit_regions(lambda p: regions.create_region(p, Rect(20, 24, 800, 200), 3, ZoomMode.EXTERNAL))
        settle()
        window.copy_image()
        settle()
        window.export_image()
        settle()
        elapsed = monotonic() - started
        timer.stop()
        assert not errors and not window.session.dirty
        composed = load_image(str(output))
        print(f"Base: 1920x1080; saída: {composed.width}x{composed.height}; quatro operações concluídas.")
        print(f"Tempo total: {elapsed:.3f} s; ticks Qt: {len(gaps)}; maior intervalo: {max(gaps, default=0)*1000:.1f} ms.")
        print(f"Pico RSS do processo Linux (inclui Qt/codecs/fixtures): {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.1f} MiB.")
    app.clipboard().clear()
    window.session.dirty = False
    window.close()


if __name__ == "__main__":
    run()
