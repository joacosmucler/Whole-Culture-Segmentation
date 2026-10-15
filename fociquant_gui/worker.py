# Copied from SIIC (siic_gui).
"""Generic background worker — runs a callable off the UI thread (ADR: threading)."""
from __future__ import annotations

import traceback
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal


class Worker(QThread):
    """Runs ``fn(progress)`` in a background thread.

    ``fn`` receives a ``progress(message: str, percent: int)`` callable it may
    call to report status (percent -1 = indeterminate).  The **return value**
    of ``fn`` is emitted via the ``result`` signal so callers don't need the
    closure-variable trick.

    Signals
    -------
    progress(str, int)   status message + percent (−1 = indeterminate)
    result(object)       return value of fn (emitted before done)
    done()               fn returned normally (emitted after result)
    failed(str)          fn raised an exception — full traceback string
    error(str)           alias for failed (used by Stage-3 panels)
    """

    progress = pyqtSignal(str, int)
    result   = pyqtSignal(object)   # return value of fn
    done     = pyqtSignal()
    failed   = pyqtSignal(str)
    error    = pyqtSignal(str)      # alias — wired to failed in __init__

    def __init__(self, fn: Callable[[Callable[[str, int], None]], None]) -> None:
        super().__init__()
        self._fn = fn
        # macOS QThreads get a tiny default stack; BLAS/matplotlib/skimage can overflow it (SIGBUS).
        self.setStackSize(64 * 1024 * 1024)
        # Safely schedule QObject deletion after the thread finishes.
        # This prevents "QThread destroyed while still running" crashes that
        # occur when Python's GC drops the last Python reference while the
        # underlying C++ thread is still alive.
        self.finished.connect(self.deleteLater)
        # Wire the alias so Stage-2 (failed) and Stage-3 (error) callers both work.
        self.failed.connect(self.error)

    def run(self) -> None:
        try:
            ret = self._fn(self.progress.emit)
            self.result.emit(ret)
            self.done.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


def is_running(w: "Worker | None") -> bool:
    """True if the worker exists and its thread is alive. A finished Worker deletes its C++ object
    (deleteLater), so touching it raises RuntimeError — that means 'not running'."""
    if w is None:
        return False
    try:
        return w.isRunning()
    except RuntimeError:
        return False
