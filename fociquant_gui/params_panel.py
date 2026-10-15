"""Parameter widgets bound to fociquant.Params (every control explains its effect in a tooltip)."""
from __future__ import annotations

from dataclasses import fields

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QPushButton, QSpinBox,
                             QVBoxLayout, QWidget)

from fociquant.pipeline import Params

G_BG = ["floor", "mode", "percentile", "roi", "fixed"]
R_BG = ["outside", "mode", "percentile", "roi", "fixed"]
CHAN_ATTRS = ("ch_red", "ch_bf", "ch_green")


def tip(text: str) -> str:
    """Rich-text tooltip with a fixed width so long explanations wrap."""
    return f"<qt><table width='340'><tr><td>{text}</td></tr></table></qt>"


# (group title, group tooltip, [(attr, label, kind, args, tooltip)])
GROUPS = [
    ("Channels", "Which channel of the file plays which role. Names come from the file metadata when available.", [
        ("ch_red", "Red (foci)", "chan", None,
         "<b>Channel that is measured.</b> The result is the mean of this channel inside the cell mask, minus its "
         "background.<br><b>Effect:</b> picking the wrong channel measures the wrong signal."),
        ("ch_bf", "Brightfield (view)", "chan", None,
         "Brightfield channel. <b>Only used for the 'Brightfield' view</b> so you can eyeball the cells; it has no "
         "effect on the mask or on the measurement."),
        ("ch_green", "Green (membrane)", "chan", None,
         "<b>Channel used to find the cells</b> (membrane / cytoplasm stain). The mask is built only from this "
         "channel.<br><b>Effect:</b> picking the wrong channel gives a mask unrelated to the cells."),
    ]),
    ("Green background", "Background level of the green channel: the 'zero' above which a pixel can count as cell.", [
        ("g_bg_method", "Method", "combo", G_BG,
         "How the green background is estimated.<br>"
         "<b>floor</b>: peak of the darkest 20% of pixels (robust, works even when cells cover most of the field).<br>"
         "<b>mode</b>: histogram peak (fails if dim cells dominate the field).<br>"
         "<b>percentile</b>: the percentile set below.<br>"
         "<b>roi</b>: median inside the teal box on the image (drag it over empty glass).<br>"
         "<b>fixed</b>: a number you type.<br>"
         "<b>Effect:</b> too high a background → mask too small or empty; too low → mask includes haze."),
        ("g_bg_percentile", "Percentile", "float", (0, 50, 1, 1),
         "Only for method 'percentile'. Intensity at this percentile of the image is taken as background.<br>"
         "<b>Effect:</b> higher → higher background → smaller mask."),
        ("g_bg_fixed", "Fixed value", "float", (0, 65535, 10, 0),
         "Only for method 'fixed'. Background in raw camera counts, same for every image.<br>"
         "<b>Effect:</b> higher → smaller mask."),
    ]),
    ("Cell mask (from green)", "Steps that turn the green channel into a cell / no-cell mask, in this order: "
     "blur, threshold, erode, close, fill holes, remove small objects.", [
        ("sigma", "Smoothing σ (px)", "float", (0, 10, 0.5, 1),
         "Gaussian blur applied to the green image before thresholding.<br>"
         "<b>Effect:</b> higher → smoother mask, speckle and gaps in a patchy membrane stain disappear, but fine "
         "edges blur and close cells merge. 0 = no blur."),
        ("k_sigma", "Threshold  k × noise", "float", (0, 30, 0.5, 1),
         "<b>Main knob.</b> Threshold = background + k × noise of the background.<br>"
         "<b>Effect:</b> lower → more pixels count as cell (bigger mask, may include haze); higher → stricter "
         "(smaller mask, dim cells can be lost). The status line shows the resulting threshold."),
        ("thr_factor", "Threshold  × bg", "float", (0.5, 3, 0.01, 2),
         "Multiplies the background before the noise term is added (threshold = bg × this + offset + k × noise).<br>"
         "<b>Effect:</b> 1.00 = off; raising it → higher threshold → smaller mask. Use it when the cell signal "
         "scales with the background level."),
        ("thr_offset", "Threshold  + offset", "float", (-5000, 5000, 10, 0),
         "Adds a fixed number of intensity counts to the threshold.<br>"
         "<b>Effect:</b> positive → stricter, smaller mask; negative → more permissive, bigger mask."),
        ("n_erode", "Erosions", "int", (0, 20),
         "Shrinks the mask by 1 px per iteration, which removes thin halos, filaments and stray pixels.<br>"
         "<b>Effect:</b> more → cleaner mask, but it retreats from the cell border and thin cells vanish. "
         "Closing then partly restores the shape."),
        ("close_radius", "Closing radius (px)", "int", (0, 50),
         "Joins nearby fragments of the mask (closes gaps up to about twice this radius).<br>"
         "<b>Effect:</b> higher → cells with a patchy or membrane-only stain become solid, but neighbouring cells "
         "and the gaps between them merge. 0 = off."),
        ("fill_holes_max", "Fill holes up to (px)", "int", (0, 10000000),
         "Fills holes <b>inside</b> the mask that are no bigger than this many pixels (nuclei or unstained patches "
         "within a cell). Bigger enclosed regions, such as empty gaps between cells, stay background.<br>"
         "<b>Effect:</b> higher → fills larger regions (risk: empty space between cells gets counted as cell); "
         "lower → nuclei stay as holes. 0 = no filling. A nucleus is roughly 500–2000 px at 0.3 µm/px."),
        ("min_size", "Min object (px)", "int", (0, 100000),
         "Deletes mask objects smaller than this many pixels (debris, cell fragments).<br>"
         "<b>Effect:</b> higher → removes more specks but also small cells; 0 = keep everything."),
    ]),
    ("Red background", "Background level of the foci channel; it is subtracted before averaging.", [
        ("r_bg_method", "Method", "combo", R_BG,
         "How the red (foci) background to subtract is estimated.<br>"
         "<b>outside</b> (recommended): median of the red signal outside the cell mask, so it adapts to every image.<br>"
         "<b>mode / percentile / roi / fixed</b>: as for the green background.<br>"
         "<b>Effect:</b> a higher background lowers the final mean by the same amount."),
        ("r_bg_margin", "Margin (px)", "int", (0, 100),
         "Only for 'outside'. Distance kept away from the mask border when sampling the red background, so cell "
         "glow does not contaminate it.<br>"
         "<b>Effect:</b> higher → cleaner background estimate but less area to sample (if almost the whole field "
         "is cells it falls back to the percentile)."),
        ("r_bg_percentile", "Percentile", "float", (0, 50, 1, 1),
         "Only for methods 'percentile' (and as the fallback of 'outside' when no background area is left).<br>"
         "<b>Effect:</b> higher → higher background → lower final mean."),
        ("r_bg_fixed", "Fixed value", "float", (0, 65535, 10, 0),
         "Only for method 'fixed'. Red background in raw counts, same for every image.<br>"
         "<b>Effect:</b> higher → lower final mean."),
    ]),
]


class ParamsPanel(QWidget):
    changed = pyqtSignal()
    autodetect_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._w: dict[str, QWidget] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for title, gtip, rows in GROUPS:
            box = QGroupBox(title)
            box.setToolTip(tip(gtip))
            form = QFormLayout(box)
            for attr, label, kind, args, t in rows:
                w = self._make(kind, args)
                w.setToolTip(tip(t))
                form.addRow(label, w)
                form.labelForField(w).setToolTip(tip(t))       # hovering the name works too
                self._w[attr] = w
            if title == "Channels":
                self.auto_btn = QPushButton("Auto-detect from metadata")
                self.auto_btn.setToolTip(tip("Reads the dye and contrast method stored in the file and assigns the "
                                             "three roles. Roles follow the dye (e.g. Rhodamine = foci), not the "
                                             "display colour. Files without metadata keep your manual choice."))
                self.auto_btn.clicked.connect(self.autodetect_requested)
                form.addRow(self.auto_btn)
            lay.addWidget(box)
        lay.addStretch(1)
        self.set_params(Params())

    def _make(self, kind, args):
        if kind == "chan":
            w = QComboBox(); w.addItems([str(i) for i in range(6)])
            w.currentIndexChanged.connect(self.changed)
        elif kind == "int":
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
            elif attr in CHAN_ATTRS:
                v = max(w.currentIndex(), 0)
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
            elif attr in CHAN_ATTRS:
                if v >= w.count():                       # saved mapping refers to a channel the list lacks
                    w.addItems([str(i) for i in range(w.count(), v + 1)])
                w.setCurrentIndex(v)
            elif isinstance(w, QComboBox):
                w.setCurrentText(str(v))
            else:
                w.setValue(v)
            w.blockSignals(False)
        self.changed.emit()

    def set_channel_labels(self, labels: list[str] | None):
        """Show channel names from the file's metadata in the three channel dropdowns."""
        labels = labels or [str(i) for i in range(6)]
        for a in CHAN_ATTRS:
            w = self._w[a]
            cur = w.currentIndex()
            w.blockSignals(True)
            w.clear(); w.addItems(labels)
            w.setCurrentIndex(min(max(cur, 0), len(labels) - 1))
            w.blockSignals(False)

    def uses_roi(self) -> bool:
        return self._w["g_bg_method"].currentText() == "roi" or self._w["r_bg_method"].currentText() == "roi"
