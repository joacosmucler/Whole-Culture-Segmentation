"""FociQuant GUI entry point:  python -m fociquant_gui.app [images or folders...]   |   fociquant"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QStyleFactory

from fociquant.io import find_images

from .main_window import MainWindow
from .theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FociQuant")
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")
    apply_theme(app)
    win = MainWindow()
    win.show()
    for a in sys.argv[1:]:
        p = Path(a)
        win._add_paths(find_images(p) if p.is_dir() else [p])
    if os.environ.get("FOCIQUANT_SMOKE_EXIT"):          # used by CI to check that the launchers start the app
        def _quit():
            print("FociQuant started OK", flush=True)
            app.quit()
        QTimer.singleShot(1500, _quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
