"""Parameter widgets bound to fociquant.Params."""
from __future__ import annotations

from dataclasses import fields

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QSpinBox,
                             QVBoxLayout, QWidget)

from fociquant.pipeline import Params

G_BG = ["floor", "mode", "percentile", "roi", "fixed"]
R_BG = ["outside", "mode", "percentile", "roi", "fixed"]

# (attr, label, kind, args, tooltip)
GROUPS = [
    ("Channels (0-based index)", [
        ("ch_red", "Red (foci)", "int", (0, 9), ""),
        ("ch_bf", "Brightfield", "int", (0, 9), ""),
        ("ch_green", "Green (membrane)", "int", (0, 9), ""),
    ]),
    ("Green background", [
        ("g_bg_method", "Method", "combo", G_BG,
         "floor: peak of the darkest 20% of pixels (robust when cells fill the field)\n"
         "mode: histogram peak | percentile | roi: median of the box | fixed: typed value"),
        ("g_bg_percentile", "Percentile", "float", (0, 50, 1, 1), "Used when method = percentile"),
        ("g_bg_fixed", "Fixed value", "float", (0, 65535, 10, 0), "Used when method = fixed"),
    ]),
    ("Cell mask (from green)", [
        ("sigma", "Smoothing σ (px)", "float", (0, 10, 0.5, 1), "Gaussian blur before thresholding"),
        ("k_sigma", "Threshold  k × noise", "float", (0, 30, 0.5, 1),
         "threshold = bg × factor + offset + k × background noise. Lower k = bigger mask."),
        ("thr_factor", "Threshold  × bg", "float", (0.5, 3, 0.01, 2), "Multiplicative term (1.00 = off)"),
        ("thr_offset", "Threshold  + offset", "float", (-5000, 5000, 10, 0), "Additive term"),
        ("n_erode", "Erosions", "int", (0, 20), "Removes thin debris / halo"),
        ("close_radius", "Closing radius (px)", "int", (0, 50), "Joins fragments of one cell"),
        ("min_size", "Min object (px)", "int", (0, 100000), "Objects smaller than this are dropped"),
    ]),
    ("Brightfield refinement", [
        ("use_bf", "Use brightfield", "check", None,
         "Texture (local std) mask from brightfield, combined with the green mask"),
        ("bf_window", "Window (px)", "int", (3, 101), "Size of the local-variance window"),
        ("bf_method", "Threshold", "combo", ["otsu", "median"], ""),
        ("bf_factor", "× median", "float", (0.5, 10, 0.1, 1), "Used when threshold = median"),
        ("bf_combine", "Combine", "combo", ["and", "or"],
         "and: keep green∩BF (drops green junk) | or: green∪BF (recovers dim cells)"),
    ]),
    ("Red background", [
        ("r_bg_method", "Method", "combo", R_BG,
         "outside: median of red outside the mask (+ margin) | others as for green"),
        ("r_bg_margin", "Margin (px)", "int", (0, 100), "Distance kept from the mask for 'outside'"),
        ("r_bg_percentile", "Percentile", "float", (0, 50, 1, 1), ""),
        ("r_bg_fixed", "Fixed value", "float", (0, 65535, 10, 0), ""),
    ]),
]


class ParamsPanel(QWidget):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._w: dict[str, QWidget] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for title, rows in GROUPS:
            box = QGroupBox(title)
            form = QFormLayout(box)
            for attr, label, kind, args, tip in rows:
                w = self._make(kind, args)
                if tip:
                    w.setToolTip(tip)
                form.addRow(label, w)
                self._w[attr] = w
            lay.addWidget(box)
        lay.addStretch(1)
        self.set_params(Params())

    def _make(self, kind, args):
        if kind == "int":
            w = QSpinBox(); w.setRange(*args); w.valueChanged.connect(self.changed)
        elif kind == "float":
            w = QDoubleSpinBox(); w.setRange(args[0], args[1]); w.setSingleStep(args[2]); w.setDecimals(args[3])
            w.valueChanged.connect(self.changed)
        elif kind == "combo":
            w = QComboBox(); w.addItems(args); w.currentTextChanged.connect(self.changed)
        else:
            w = QCheckBox(); w.toggled.connect(self.changed)
        return w

    def get_params(self, base: Params | None = None) -> Params:
        p = Params() if base is None else Params(**{f.name: getattr(base, f.name) for f in fields(Params)})
        for attr, w in self._w.items():
            if isinstance(w, QCheckBox):
                v = w.isChecked()
            elif isinstance(w, QComboBox):
                v = w.currentText()
            else:
                v = w.value()
            setattr(p, attr, v)
        return p

    def set_params(self, p: Params):
        for attr, w in self._w.items():
            w.blockSignals(True)
            v = getattr(p, attr)
            if isinstance(w, QCheckBox):
                w.setChecked(bool(v))
            elif isinstance(w, QComboBox):
                w.setCurrentText(str(v))
            else:
                w.setValue(v)
            w.blockSignals(False)
        self.changed.emit()

    def uses_roi(self) -> bool:
        return self._w["g_bg_method"].currentText() == "roi" or self._w["r_bg_method"].currentText() == "roi"
