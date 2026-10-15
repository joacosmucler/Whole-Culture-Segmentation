"""FociQuant GUI entry point:  python -m fociquant_gui.app   |   fociquant"""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QStyleFactory

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
        from pathlib import Path
        from fociquant.io import find_images
        p = Path(a)
        win._add_paths(find_images(p) if p.is_dir() else [p])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
