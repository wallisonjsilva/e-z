"""W10 com pool Qt real: afinidade, event loop, limites e transações."""

from threading import Event, get_ident

import pytest
from PySide6.QtCore import QEventLoop, QSize, QTimer, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from e_z.application import regions
from e_z.application.capture import CaptureRequest, CaptureStatus
from e_z.domain.document import EvidenceProject, SourceImage
from e_z.domain.errors import ValidationError
from e_z.domain.geometry import MAX_BUFFER_BYTES, Rect
from e_z.imaging import budget, images
from e_z.imaging.tasks import TaskRunner
from e_z.platform import clipboard, dialogs, linux_wayland, linux_x11
from e_z.ui import main_window
from e_z.ui.main_window import MainWindow


def source(width=40, height=20):
    return SourceImage(width, height, bytes([17, 31, 99, 255]) * width * height)


def wait_for(condition, timeout=4000):
    if condition():
        return
    loop = QEventLoop()
    poll, deadline = QTimer(), QTimer()
    poll.setInterval(1)
    poll.timeout.connect(lambda: loop.quit() if condition() else None)
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    poll.start()
    deadline.start(timeout)
    loop.exec()
    assert condition(), "Operação Qt não concluiu dentro do prazo do teste"


@pytest.fixture
def async_window(qt_app, monkeypatch):
    window = MainWindow()
    window.show()
    window.activateWindow()
    errors = []
    monkeypatch.setattr(dialogs, "show_error", lambda parent, message: errors.append(message))
    qt_app.processEvents()
    yield window, errors
    wait_for(lambda: not window.runner.busy)
    window.capture_controller.cancel()
    window.session.dirty = False
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def load(window):
    assert window._load_candidate(source)
    wait_for(lambda: not window.runner.busy)
    assert window.session.project.base == source()


def test_worker_runs_off_ui_and_completion_returns_to_ui(qt_app):
    runner = TaskRunner()
    ui = get_ident()
    completed, errors = [], []
    assert runner.submit(lambda: get_ident(), lambda worker: completed.append((worker, get_ident())), errors.append)
    wait_for(lambda: bool(completed))
    assert not errors and completed[0][0] != ui and completed[0][1] == ui
    runner.pool.waitForDone()


def test_runner_rejects_concurrency_and_event_loop_keeps_responding(qt_app):
    runner = TaskRunner()
    started, release = Event(), Event()
    completed = []

    def work():
        started.set()
        assert release.wait(3)
        return 123

    beats = []
    timer = QTimer()
    timer.setInterval(1)
    timer.timeout.connect(lambda: beats.append(1))
    timer.start()
    try:
        assert runner.submit(work, completed.append, lambda error: completed.append(error))
        wait_for(started.is_set)
        assert not runner.submit(lambda: 999, completed.append, completed.append)
        wait_for(lambda: len(beats) >= 5)
        assert not completed and runner.busy
    finally:
        release.set()
    wait_for(lambda: not runner.busy)
    assert completed == [123]
    timer.stop()
    runner.pool.waitForDone()


def test_pool_admission_failure_releases_busy_state(qt_app, monkeypatch):
    runner = TaskRunner()
    original = runner.pool.start
    errors, values = [], []

    def fail(job):
        raise MemoryError()

    monkeypatch.setattr(runner.pool, "start", fail)
    assert not runner.submit(lambda: 1, values.append, errors.append)
    assert not runner.busy and errors and not values
    monkeypatch.setattr(runner.pool, "start", original)
    assert runner.submit(lambda: 2, values.append, errors.append)
    wait_for(lambda: values == [2])
    runner.pool.waitForDone()


@pytest.mark.parametrize("failure", [MemoryError(), RuntimeError("/caminho/privado/ficticio"),
                                     ValueError("conteudo ficticio nao deve atravessar a thread"),
                                     ValidationError("A operação excede o orçamento de memória de imagem.")])
def test_worker_failure_is_sanitized_and_next_operation_succeeds(qt_app, failure):
    runner = TaskRunner()
    errors, values = [], []

    def fail():
        raise failure

    runner.submit(fail, values.append, errors.append)
    wait_for(lambda: bool(errors))
    assert "/caminho/privado" not in errors[0].message
    assert "conteudo ficticio" not in errors[0].message
    assert not hasattr(errors[0], "__traceback__")
    assert runner.submit(lambda: 42, values.append, errors.append)
    wait_for(lambda: values == [42])
    runner.pool.waitForDone()


def test_import_edit_copy_and_export_work_outside_ui_with_gui_publication(async_window, qt_app, monkeypatch, tmp_path):
    window, errors = async_window
    ui = get_ident()
    calls = []
    original_compose, original_export = main_window.compose, main_window.export_png
    original_prepare, original_publish = window._prepare_scene, clipboard.write_image

    def render(*args, **kwargs):
        assert get_ident() != ui
        calls.append("render")
        return original_compose(*args, **kwargs)

    def export(*args, **kwargs):
        assert get_ident() != ui
        calls.append("export")
        return original_export(*args, **kwargs)

    def prepare(*args, **kwargs):
        assert get_ident() == ui
        return original_prepare(*args, **kwargs)

    def publish(*args, **kwargs):
        assert get_ident() == ui
        return original_publish(*args, **kwargs)

    monkeypatch.setattr(main_window, "compose", render)
    monkeypatch.setattr(main_window, "export_png", export)
    monkeypatch.setattr(window, "_prepare_scene", prepare)
    monkeypatch.setattr(clipboard, "write_image", publish)
    path, output = tmp_path / "base.png", tmp_path / "saida.png"
    assert images.image_from_source(source()).save(str(path), "PNG")
    monkeypatch.setattr(dialogs, "open_image", lambda parent: str(path))
    window.open_image()
    wait_for(lambda: not window.runner.busy)
    assert window.session.project.base == source()
    assert window._edit_regions(lambda p: regions.create_region(p, Rect(2, 2, 10, 4), 2), select_new=True)
    wait_for(lambda: not window.runner.busy)
    assert len(window.session.project.regions) == 1
    window.copy_image()
    wait_for(lambda: not window.runner.busy)
    copied = images.source_from_image(qt_app.clipboard().image())
    monkeypatch.setattr(dialogs, "export_png", lambda parent: str(output))
    window.export_image()
    wait_for(lambda: not window.runner.busy)
    assert copied == images.load_image(str(output))
    assert not errors and not window.session.dirty and "export" in calls
    qt_app.clipboard().clear()


def test_paste_gets_clipboard_on_ui_but_converts_on_worker(async_window, qt_app, monkeypatch):
    window, errors = async_window
    ui = get_ident()
    original = main_window.source_from_image
    threads = []

    def convert(*args, **kwargs):
        threads.append(get_ident())
        return original(*args, **kwargs)

    monkeypatch.setattr(main_window, "source_from_image", convert)
    qt_app.clipboard().setImage(images.image_from_source(source()))
    window.paste_image()
    wait_for(lambda: not window.runner.busy)
    assert window.session.project.base == source()
    assert threads and all(thread != ui for thread in threads) and not errors
    qt_app.clipboard().clear()


def test_busy_ui_disables_mutations_and_recovers_on_failure(async_window, monkeypatch):
    window, errors = async_window
    load(window)
    snapshot, scene = window.session.project, window.scene
    started, release = Event(), Event()

    def fail():
        started.set()
        assert release.wait(3)
        raise MemoryError()

    try:
        assert window._load_candidate(fail)
        wait_for(started.is_set)
        assert window.progress.isVisible()
        assert not window.actions_by_name["Abrir"].isEnabled()
        assert not window.actions_by_name["Copiar composição"].isEnabled()
        assert not window._edit_regions(lambda p: p)
        window.paste_image()  # Deve ser recusado antes de tocar no clipboard.
    finally:
        release.set()
    wait_for(lambda: not window.runner.busy)
    assert errors and "Memória" in errors[-1]
    assert window.session.project is snapshot and window.scene is scene
    assert not window.progress.isVisible() and window.actions_by_name["Abrir"].isEnabled()
    assert window._edit_regions(lambda p: regions.create_region(p, Rect(2, 2, 10, 4), 2))
    wait_for(lambda: not window.runner.busy)
    assert len(window.session.project.regions) == 1


def test_stale_result_cannot_replace_newer_document(async_window):
    window, errors = async_window
    load(window)
    started, release = Event(), Event()

    def slow_load():
        started.set()
        assert release.wait(3)
        return source(10, 5)

    newer = EvidenceProject(source(8, 4))
    try:
        window._load_candidate(slow_load)
        wait_for(started.is_set)
        window.session.replace(newer)  # Simula invalidação programática do snapshot.
    finally:
        release.set()
    wait_for(lambda: not window.runner.busy)
    assert window.session.project is newer and not errors


def test_close_waits_for_worker_and_preserves_current_document_if_discard_cancelled(async_window, monkeypatch):
    window, errors = async_window
    load(window)
    snapshot = window.session.project
    started, release = Event(), Event()
    confirmations = []

    def confirm(parent):
        assert not window.runner.busy
        confirmations.append(1)
        return False

    def slow_load():
        started.set()
        assert release.wait(3)
        return source(10, 5)

    monkeypatch.setattr(dialogs, "confirm_discard", confirm)
    try:
        window._load_candidate(slow_load)
        wait_for(started.is_set)
        assert not window.close() and window.isVisible()
        assert not confirmations
    finally:
        release.set()
    wait_for(lambda: bool(confirmations))
    assert window.session.project is snapshot and window.isVisible() and not errors


def test_close_during_export_finishes_atomic_write_then_closes(async_window, monkeypatch, tmp_path):
    window, errors = async_window
    load(window)
    path = tmp_path / "evidencia.png"
    path.write_bytes(b"arquivo ficticio anterior")
    started, release = Event(), Event()
    original = main_window.export_png

    def delayed(*args, **kwargs):
        started.set()
        assert release.wait(3)
        return original(*args, **kwargs)

    monkeypatch.setattr(main_window, "export_png", delayed)
    monkeypatch.setattr(dialogs, "export_png", lambda parent: str(path))
    monkeypatch.setattr(dialogs, "confirm_discard", lambda parent: pytest.fail("Exportação concluída não exige descarte"))
    try:
        window.export_image()
        wait_for(started.is_set)
        assert not window.close() and window.isVisible()
        assert path.read_bytes() == b"arquivo ficticio anterior"
    finally:
        release.set()
    wait_for(lambda: not window.isVisible())
    assert images.load_image(str(path)) == source() and not errors
    assert not window.session.dirty


def test_budget_refuses_decode_before_reader_allocates(tmp_path, monkeypatch):
    path = tmp_path / "imagem.png"
    assert images.image_from_source(source()).save(str(path), "PNG")
    called = []
    original = images.QImageReader

    class Reader(original):
        def read(self):
            called.append(1)
            return super().read()

    monkeypatch.setattr(images, "QImageReader", Reader)
    with pytest.raises(ValueError):
        images.load_image(str(path), resident_bytes=MAX_BUFFER_BYTES - budget.SCRATCH_BYTES)
    assert not called


def test_budget_refuses_scaling_with_small_remaining_headroom():
    project = EvidenceProject(source())
    resident = MAX_BUFFER_BYTES - budget.SCRATCH_BYTES - 40_000
    # A base sozinha cabe; a ampliação exige também saída/intermediários.
    budget.check_render(project, resident)
    enlarged = regions.create_region(project, Rect(2, 2, 10, 4), 8)
    with pytest.raises(ValueError):
        budget.check_render(enlarged, resident)


def test_budget_refusal_preserves_scene_and_recovers(async_window, monkeypatch):
    window, errors = async_window
    load(window)
    project, scene = window.session.project, window.scene
    previous = window._resident_bytes
    monkeypatch.setattr(window, "_resident_bytes", lambda: MAX_BUFFER_BYTES)
    assert window._edit_regions(lambda p: regions.create_region(p, Rect(2, 2, 10, 4), 2))
    wait_for(lambda: not window.runner.busy)
    assert errors and "orçamento" in errors[-1]
    assert window.session.project is project and window.scene is scene
    monkeypatch.setattr(window, "_resident_bytes", previous)
    assert window._edit_regions(lambda p: regions.create_region(p, Rect(2, 2, 10, 4), 2))
    wait_for(lambda: not window.runner.busy)
    assert len(window.session.project.regions) == 1


def test_clipboard_reservation_survives_external_clear_without_reading_contents(qt_app):
    image = images.image_from_source(source(80, 40))
    clipboard.write_image(image)
    highwater = clipboard.reserved_bytes()
    assert highwater >= 80 * 40 * 4
    qt_app.clipboard().clear()
    assert clipboard.reserved_bytes() == highwater


@pytest.mark.parametrize("kind", ["x11", "wayland"])
def test_capture_conversion_and_preview_share_real_worker_without_overlap(async_window, monkeypatch, tmp_path, kind):
    window, errors = async_window
    ui = get_ident()
    worker_threads = []

    if kind == "x11":
        class Screen:
            def size(self):
                return QSize(40, 20)

            def devicePixelRatio(self):
                return 1

            def grabWindow(self, handle):
                assert get_ident() == ui
                return QPixmap.fromImage(images.image_from_source(source()))

        screen = Screen()
        original = linux_x11.source_from_image

        def convert(*args, **kwargs):
            worker_threads.append(get_ident())
            return original(*args, **kwargs)

        monkeypatch.setattr(linux_x11, "source_from_image", convert)
        backend = linux_x11.X11CaptureBackend(lambda: [screen], runner=window.runner)
        monkeypatch.setattr(dialogs, "choose_monitor", lambda parent, monitors: monitors[0].id)
    else:
        path = tmp_path / "portal-ficticio.png"
        assert images.image_from_source(source()).save(str(path), "PNG")

        class Transport:
            def available(self):
                return True

            def start(self, callback):
                assert get_ident() == ui
                callback(CaptureStatus.SUCCESS, QUrl.fromLocalFile(str(path)).toString())

            def cancel(self):
                pass

        original = linux_wayland.load_image

        def decode(*args, **kwargs):
            worker_threads.append(get_ident())
            return original(*args, **kwargs)

        monkeypatch.setattr(linux_wayland, "load_image", decode)
        backend = linux_wayland.WaylandCaptureBackend(Transport(), runner=window.runner)
    window.capture_controller.backend = backend
    window.capture_controller._delay.setInterval(0)
    window.capture_image()
    wait_for(lambda: window.session.project is not None and not window.runner.busy)
    assert window.session.project.base == source() and window.isVisible() and not errors
    assert worker_threads and all(thread != ui for thread in worker_threads)


def test_cancel_during_portal_decode_delivers_once_and_ignores_late_result(async_window, monkeypatch, tmp_path):
    window, errors = async_window
    path = tmp_path / "portal-ficticio.png"
    assert images.image_from_source(source()).save(str(path), "PNG")

    class Transport:
        def available(self):
            return True

        def start(self, callback):
            callback(CaptureStatus.SUCCESS, QUrl.fromLocalFile(str(path)).toString())

        def cancel(self):
            pass

    started, release = Event(), Event()
    original = linux_wayland.load_image

    def slow(*args, **kwargs):
        started.set()
        assert release.wait(3)
        return original(*args, **kwargs)

    monkeypatch.setattr(linux_wayland, "load_image", slow)
    backend = linux_wayland.WaylandCaptureBackend(Transport(), runner=window.runner)
    results = []
    try:
        backend.capture(CaptureRequest(), results.append)
        wait_for(started.is_set)
        backend.cancel()
        backend.cancel()
        assert len(results) == 1 and results[0].status is CaptureStatus.CANCELLED
    finally:
        release.set()
    wait_for(lambda: not window.runner.busy)
    assert len(results) == 1
    backend.capture(CaptureRequest(), results.append)
    wait_for(lambda: len(results) == 2)
    assert results[-1].status is CaptureStatus.SUCCESS and not errors
