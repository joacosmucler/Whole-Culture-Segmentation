"""Preview grid: current parameters applied to many images at once (per condition or all)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from fociquant.pipeline import analyze_image
from fociquant.report import thumb_rgb

from .worker import Worker, is_running


class _Tile(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, e):
        self.clicked.emit()


def _pixmap(rgb: np.ndarray) -> QPixmap:
    h, w, _ = rgb.shape
    rgb = np.ascontiguousarray(rgb)
    return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())


class GridDialog(QDialog):
    """Non-modal. Clicking a tile selects that image in the main window."""
    selected = pyqtSignal(str)

    def __init__(self, parent, get_files, get_condition, get_image, get_params):
        super().__init__(parent)
        self.setWindowTitle("Preview grid — current parameters on many images")
        self.resize(1350, 880)
        self._files, self._cond, self._img, self._params = get_files, get_condition, get_image, get_params
        self._worker: Worker | None = None
        self._results: list = []

        self.cond_combo = QComboBox()
        self.view_combo = QComboBox(); self.view_combo.addItems(["Green", "Red", "Red + Green"])
        self.style_combo = QComboBox(); self.style_combo.addItems(["Outline", "Fill", "Outline + Fill"])
        self.style_combo.currentTextChanged.connect(lambda _: self._layout())
        self.fill_op = QSpinBox(); self.fill_op.setRange(5, 100); self.fill_op.setValue(35); self.fill_op.setSuffix("%")
        self.fill_op.setToolTip("Opacity of the fill")
        self.fill_op.valueChanged.connect(lambda _: self._layout())
        self.cols = QSpinBox(); self.cols.setRange(1, 6); self.cols.setValue(3)
        self.refresh_btn = QPushButton("Recompute")
        self.cond_combo.currentTextChanged.connect(lambda _: self.recompute())
        self.view_combo.currentTextChanged.connect(lambda _: self._layout())
        self.cols.valueChanged.connect(lambda _: self._layout())
        self.refresh_btn.clicked.connect(self.recompute)
        top = QHBoxLayout()
        for w in (QLabel("Condition"), self.cond_combo, QLabel("View"), self.view_combo,
                  QLabel("Mask"), self.style_combo, self.fill_op, QLabel("Columns"), self.cols, self.refresh_btn):
            top.addWidget(w)
        top.addStretch(1)

        self.grid_host = QWidget(); self.grid = QGridLayout(self.grid_host)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(self.grid_host)
        self.progress = QProgressBar(); self.summary = QLabel("")
        self.summary.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addLayout(top); lay.addWidget(sc, 1); lay.addWidget(self.progress); lay.addWidget(self.summary)

    # ------------------------------------------------------------------
    def open_dialog(self):
        conds = sorted({self._cond(f) for f in self._files()})
        cur = self.cond_combo.currentText()
        self.cond_combo.blockSignals(True)
        self.cond_combo.clear(); self.cond_combo.addItems(["All"] + conds)
        if cur in conds:
            self.cond_combo.setCurrentText(cur)
        self.cond_combo.blockSignals(False)
        self.show(); self.raise_(); self.activateWindow()
        self.recompute()

    def recompute(self):
        if is_running(self._worker):
            return
        sel = self.cond_combo.currentText()
        files = [f for f in self._files() if sel in ("All", "") or self._cond(f) == sel]
        files.sort(key=lambda f: (self._cond(f), Path(f).name))
        if not files:
            return
        jobs = [(f, self._cond(f), self._params(f)) for f in files]       # snapshot now
        get_img = self._img

        def work(progress):
            out = []
            for i, (f, c, p) in enumerate(jobs):
                progress(Path(f).name, int(100 * i / len(jobs)))
                im = get_img(f)
                row, seg = analyze_image(im, p)
                out.append((f, c, im, p, row, seg["mask"]))
            return out

        self.refresh_btn.setEnabled(False); self.progress.setValue(0)
        w = Worker(work)
        w.progress.connect(lambda m, pc: (self.progress.setValue(max(pc, 0)), self.summary.setText(f"Computing {m}…")))
        w.result.connect(self._done)
        w.failed.connect(lambda msg: (self.refresh_btn.setEnabled(True),
                                      self.summary.setText(f"Error: {msg.splitlines()[0]}")))
        self._worker = w
        w.start()

    def _done(self, results):
        self._results = results
        self.refresh_btn.setEnabled(True); self.progress.setValue(100)
        self._layout()

    def _layout(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        view, ncol = self.view_combo.currentText(), self.cols.value()
        width = max(260, (self.width() - 60) // ncol)
        by_cond: dict[str, list[float]] = {}
        for k, (f, c, im, p, row, mask) in enumerate(self._results):
            tile = _Tile()
            pm = _pixmap(thumb_rgb(im, mask, p, view, step=2, style=self.style_combo.currentText(),
                                fill_opacity=self.fill_op.value() / 100)).scaledToWidth(
                width, Qt.TransformationMode.SmoothTransformation)
            tile.setPixmap(pm)
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile.clicked.connect(lambda ff=f: self.selected.emit(ff))
            cap = QLabel(f"{c} · …{Path(f).stem[-12:]}\nmean {row['mean_bgsub']:.1f}  ·  mask {100 * row['mask_fraction']:.0f}%")
            box = QVBoxLayout(); box.addWidget(tile); box.addWidget(cap)
            host = QWidget(); host.setLayout(box)
            self.grid.addWidget(host, k // ncol, k % ncol)
            by_cond.setdefault(c, []).append(row["mean_bgsub"])
        self.summary.setText("   |   ".join(
            f"{c}: {np.nanmean(v):.1f} ± {np.nanstd(v, ddof=1) if len(v) > 1 else 0:.1f} (n={len(v)})"
            for c, v in by_cond.items()) + "      — click a tile to open it in the main view")
