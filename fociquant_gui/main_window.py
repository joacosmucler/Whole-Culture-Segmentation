"""FociQuant main window: tab 1 Tune (files | parameters | canvas), tab 2 Batch & Plot."""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
                             QMainWindow, QMessageBox, QPushButton, QScrollArea, QSlider, QSplitter, QTableWidget,
                             QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from fociquant.io import find_images, load_image
from fociquant.pipeline import Params, analyze_image

from fociquant.channels import guess_roles

from .batch_panel import BatchPanel
from .canvas import VIEWS, Canvas
from .grid_dialog import GridDialog
from .params_panel import ParamsPanel, tip
from .worker import Worker, is_running


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FociQuant — mean foci intensity in cells")
        self.resize(1500, 950)
        self.settings = QSettings("FociQuantTest" if os.environ.get("FOCIQUANT_TEST") else "FociQuant", "FociQuant")
        self.files: list[str] = []
        self.conditions: dict[str, str] = {}
        self.rois: dict[str, tuple] = {}
        self._cache: dict[str, object] = {}
        self._cur: str | None = None
        self._gen = 0
        self._worker: Worker | None = None

        # ---- left: files + params ----
        self.file_table = QTableWidget(0, 2)
        self.file_table.setHorizontalHeaderLabels(["File", "Condition"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setColumnWidth(0, 230)
        self.file_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)   # keep the distinguishing '#02' visible
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_table.verticalHeader().hide()
        self.file_table.setMinimumHeight(170)
        self.file_table.itemSelectionChanged.connect(self._on_select)
        self.file_table.itemChanged.connect(self._on_cond_edit)
        b_files = QPushButton("Add files…"); b_files.clicked.connect(self._add_files)
        b_dir = QPushButton("Add folder…"); b_dir.clicked.connect(self._add_folder)
        b_rm = QPushButton("Remove"); b_rm.clicked.connect(self._remove)
        row = QHBoxLayout()
        for b in (b_files, b_dir, b_rm):
            row.addWidget(b)

        self.file_table.setToolTip(tip("Images to process. Click a row to preview it. <b>Condition</b> (editable, "
                                       "defaults to the parent folder) groups images in the summary table and plot."))
        b_files.setToolTip(tip("Add one or more TIFF / CZI files.")); b_dir.setToolTip(tip("Add every TIFF / CZI inside a folder (recursive)."))
        b_rm.setToolTip(tip("Remove the selected image from the list (the file on disk is not touched)."))
        self.params = ParamsPanel()
        self.params.changed.connect(self._params_changed)
        self.params.autodetect_requested.connect(self._autodetect)
        self._grid: GridDialog | None = None
        self._auto_applied = False
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.params)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        b_save = QPushButton("Save params…"); b_save.clicked.connect(self._save_params)
        b_save.setToolTip(tip("Save the current parameters to a JSON file (the batch also saves them as params.json)."))
        b_load = QPushButton("Load params…"); b_load.clicked.connect(self._load_params)
        b_load.setToolTip(tip("Load parameters from a JSON file, e.g. the params.json of a previous run."))
        b_reset = QPushButton("Reset defaults")
        b_reset.setToolTip(tip("Back to the default parameters (channels are re-read from the file metadata). "
                               "Use it if the mask looks empty or wrong after experimenting."))
        b_reset.clicked.connect(self._reset_params)
        prow = QHBoxLayout(); prow.addWidget(b_save); prow.addWidget(b_load); prow.addWidget(b_reset)

        left = QWidget(); lv = QVBoxLayout(left)
        lv.addWidget(QLabel("INPUT")); lv.addWidget(self.file_table); lv.addLayout(row)
        lv.addWidget(QLabel("PARAMETERS")); lv.addWidget(scroll, 1); lv.addLayout(prow)
        left.setMinimumWidth(380)

        # ---- center: view controls + canvas + status ----
        self.view_combo = QComboBox(); self.view_combo.addItems(VIEWS)
        self.view_combo.currentTextChanged.connect(lambda _: self._redraw())
        self.show_mask = QCheckBox("Show mask"); self.show_mask.setChecked(True)
        self.show_mask.toggled.connect(lambda _: self._redraw())
        self.opacity = QSlider(Qt.Orientation.Horizontal); self.opacity.setRange(10, 100); self.opacity.setValue(90)
        self.opacity.setMaximumWidth(120)
        self.opacity.valueChanged.connect(self._opacity_changed)
        self.mask_style = QComboBox(); self.mask_style.addItems(["Outline", "Fill", "Outline + Fill"])
        self._style_opacity = {"Outline": 90, "Fill": 40, "Outline + Fill": 40}   # remembered per style
        self._style_now = "Outline"
        self.mask_style.currentTextChanged.connect(self._style_changed)
        self.view_combo.setToolTip(tip("Which channel to display. 'Red + Green' overlays foci and membrane; "
                                       "'Brightfield' is only for visual reference. Does not change the result."))
        self.show_mask.setToolTip(tip("Show the cell mask. Everything inside it is measured. Display only."))
        self.mask_style.setToolTip(tip("<b>Outline</b>: yellow contour only. <b>Fill</b>: translucent solid "
                                       "yellow over the whole mask. <b>Outline + Fill</b>: both. Display only; "
                                       "it does not change the result."))
        self.opacity.setToolTip(tip("Opacity of the mask display. With Fill it controls how strongly the fill covers "
                                    "the image (lower = see more of the image through it); with Outline alone it "
                                    "controls the contour. Each style remembers its own value."))
        top = QHBoxLayout()
        top.addWidget(QLabel("View")); top.addWidget(self.view_combo); top.addWidget(self.show_mask)
        top.addWidget(QLabel("Style")); top.addWidget(self.mask_style)
        top.addWidget(QLabel("Opacity")); top.addWidget(self.opacity); top.addStretch(1)
        self.grid_btn = QPushButton("Preview grid…")
        self.grid_btn.setToolTip("Apply the current parameters to all images (or one condition) side by side")
        self.grid_btn.clicked.connect(self._open_grid)
        top.addWidget(self.grid_btn)

        self.canvas = Canvas()
        self.canvas.roi_changed.connect(self._roi_moved)
        self.status = QLabel("Add images to begin.")
        self.status.setToolTip(tip("Live readout for the selected image: green background and the threshold derived "
                                   "from it, red background, mask size, and the result (mean red inside cells minus "
                                   "red background)."))
        self.status.setWordWrap(True)

        mid = QWidget(); mv = QVBoxLayout(mid)
        mv.addLayout(top); mv.addWidget(self.canvas, 1); mv.addWidget(self.status)

        # ---- tab 1: Tune (files | parameters | canvas)  ·  tab 2: Batch & Plot ----
        tune = QSplitter(); tune.addWidget(left); tune.addWidget(mid)
        tune.setSizes([420, 1080]); tune.setStretchFactor(1, 1)
        self.batch = BatchPanel(self._batch_context, self.settings)
        self.tabs = QTabWidget()
        self.tabs.addTab(tune, "1 · Tune parameters")
        self.tabs.addTab(self.batch, "2 · Batch && Plot")
        self.tabs.setToolTip(tip("<b>1 · Tune</b>: pick images, adjust parameters and check the mask on single "
                                 "images. <b>2 · Batch &amp; Plot</b>: run the tuned parameters on all images, "
                                 "see the tables and the plot."))
        self.tabs.currentChanged.connect(lambda i: self.batch.refresh() if i == 1 else None)
        self.setCentralWidget(self.tabs)

        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.setInterval(250)
        self._timer.timeout.connect(self._recompute)
        self._seg: dict | None = None
        self._row: dict | None = None

        self._restore_params()

    # ------------------------------------------------------------- settings
    def _restore_params(self):
        s = self.settings.value("params")
        if s:
            try:
                self.params.set_params(Params.from_json(s))
            except Exception:
                pass

    def closeEvent(self, e):
        self.settings.setValue("params", self.params.get_params().to_json())
        self.batch.save_settings()
        super().closeEvent(e)

    def _reset_params(self):
        self.params.set_params(Params())
        im = self._cache.get(self._cur) if self._cur else None
        if im is not None and im.channels:
            self._autodetect()

    def _save_params(self):
        f, _ = QFileDialog.getSaveFileName(self, "Save parameters", "params.json", "JSON (*.json)")
        if f:
            Path(f).write_text(self.params.get_params().to_json())

    def _load_params(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load parameters", "", "JSON (*.json)")
        if f:
            self.params.set_params(Params.from_json(Path(f).read_text()))

    # ----------------------------------------------------------------- files
    def _add_paths(self, paths):
        for p in paths:
            p = str(p)
            if p in self.files:
                continue
            self.files.append(p)
            self.conditions[p] = Path(p).parent.name
        self._refresh_table()
        if self.files and self._cur is None:
            self.file_table.selectRow(0)

    def _add_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Add images", self.settings.value("last_dir", ""),
                                             "Images (*.tif *.tiff *.czi)")
        if fs:
            self.settings.setValue("last_dir", str(Path(fs[0]).parent))
            self._add_paths(fs)

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Add folder (searched recursively)", self.settings.value("last_dir", ""))
        if d:
            self.settings.setValue("last_dir", d)
            self._add_paths(find_images(d))

    def _remove(self):
        r = self.file_table.currentRow()
        if r < 0:
            return
        f = self.files.pop(r)
        self.conditions.pop(f, None); self.rois.pop(f, None); self._cache.pop(f, None)
        self._cur = None
        self._refresh_table()
        if self.files:
            self.file_table.selectRow(min(r, len(self.files) - 1))

    def _refresh_table(self):
        self.file_table.blockSignals(True)
        self.file_table.setRowCount(len(self.files))
        for i, f in enumerate(self.files):
            it = QTableWidgetItem(Path(f).name); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it.setToolTip(f)
            self.file_table.setItem(i, 0, it)
            self.file_table.setItem(i, 1, QTableWidgetItem(self.conditions[f]))
        self.file_table.blockSignals(False)

    def _on_cond_edit(self, item):
        if item.column() == 1 and 0 <= item.row() < len(self.files):
            self.conditions[self.files[item.row()]] = item.text()

    def _on_select(self):
        r = self.file_table.currentRow()
        if r < 0 or r >= len(self.files):
            return
        f = self.files[r]
        self._cur = f
        if f not in self._cache:
            try:
                self._cache[f] = load_image(f)[0]
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Could not open image", f"{f}\n\n{e}")
                return
        im = self._cache[f]
        self.params.set_channel_labels(im.channel_labels())
        if not self._auto_applied and im.channels:
            self._auto_applied = True
            self._autodetect(announce=False)
        H, W = im.data.shape[1:]
        if f not in self.rois:
            self.rois[f] = (10, 10, min(110, W), min(110, H))
        self.canvas.show_roi(self.params.uses_roi(), self.rois[f])
        self._seg = None
        self._redraw()
        self._timer.start()

    # ------------------------------------------------------- channel metadata
    def _autodetect(self, announce: bool = True):
        im = self._cache.get(self._cur) if self._cur else None
        if im is None:
            self.status.setText("Select an image first.")
            return
        roles, why = guess_roles(im.channels)
        if not roles:
            self.status.setText("This file has no channel metadata — set the channels by hand.")
            return
        p = self.params.get_params()
        for k, v in roles.items():
            setattr(p, k, v)
        self.params.set_params(p)
        self.status.setText(f"Channels from metadata: {why}")

    # ------------------------------------------------------------- grid
    def _open_grid(self):
        if not self.files:
            QMessageBox.information(self, "No images", "Add images first.")
            return
        if self._grid is None:
            def get_image(f):
                if f not in self._cache:
                    self._cache[f] = load_image(f)[0]
                return self._cache[f]
            self._grid = GridDialog(self, lambda: list(self.files), lambda f: self.conditions.get(f, ""),
                                    get_image, self._current_params)
            self._grid.selected.connect(self._select_file)
        self._grid.open_dialog()

    def _select_file(self, f: str):
        if f in self.files:
            self.file_table.selectRow(self.files.index(f))

    # ---------------------------------------------------------- live preview
    def _params_changed(self):
        self.canvas.show_roi(self.params.uses_roi())
        self._timer.start()

    def _roi_moved(self, box):
        if self._cur:
            self.rois[self._cur] = box
        self._timer.start()

    def _current_params(self, f: str) -> Params:
        p = self.params.get_params()
        if self.params.uses_roi():                  # files never previewed get the default box
            box = self.rois.get(f, (10, 10, 110, 110))
            p = replace(p, g_bg_roi=box, r_bg_roi=box)
        return p

    def _recompute(self):
        f = self._cur
        if not f or f not in self._cache:
            return
        if is_running(self._worker):
            self._timer.start()               # try again once the running job is done
            return
        im, p = self._cache[f], self._current_params(f)
        self._gen += 1
        gen = self._gen
        self.status.setText("Computing…")
        w = Worker(lambda progress: analyze_image(im, p))
        w.result.connect(lambda res, g=gen, ff=f: self._on_result(res, g, ff))
        w.failed.connect(lambda msg: self.status.setText(f"Error: {msg.splitlines()[0]}"))
        self._worker = w
        w.start()

    def _on_result(self, res, gen, f):
        if f != self._cur:
            self._timer.start()
            return
        row, seg = res
        self._row, self._seg = row, seg
        self._redraw()
        frac = row["mask_fraction"]
        warn = ""
        if frac < 0.01:
            warn = ("⚠ MASK IS EMPTY — lower 'Threshold k × noise' or the erosions, or check the green background "
                    "(method 'roi' needs the teal box on an empty area; 'Reset defaults' restores a working setup).  ")
        elif frac > 0.95:
            warn = "⚠ Mask covers almost the whole field — raise 'Threshold k × noise'.  "
        self.status.setText(
            warn + f"green bg {row['bg_green']:.0f}  →  threshold {row['threshold_green']:.0f}   |   red bg {row['bg_red']:.1f}   |   "
            f"mask {100 * row['mask_fraction']:.1f}% of field   |   "
            f"mean red (bg-subtracted) in cells: {row['mean_bgsub']:.2f}   (raw {row['mean_raw']:.1f})")

    def _redraw(self):
        if not self._cur or self._cur not in self._cache:
            return
        p = self.params.get_params()
        im = self._cache[self._cur]
        self.canvas.set_image(im.data, p.ch_red, p.ch_green, p.ch_bf, self.view_combo.currentText())
        mask = self._seg["mask"] if (self._seg is not None and self.show_mask.isChecked()) else None
        self.canvas.set_mask(mask, self.opacity.value() / 100, self.mask_style.currentText())

    def _opacity_changed(self, v: int):
        self._style_opacity[self.mask_style.currentText()] = v
        self._redraw()

    def _style_changed(self, style: str):
        self._style_now = style
        self.opacity.blockSignals(True)
        self.opacity.setValue(self._style_opacity[style])      # each style keeps its own opacity
        self.opacity.blockSignals(False)
        self._redraw()

    # ------------------------------------------------------- hand-over to tab 2
    def _batch_context(self) -> dict:
        """What the Batch tab needs from the Tune tab: images, conditions, current parameters, bg boxes."""
        return dict(files=list(self.files), conditions=dict(self.conditions), params=self.params.get_params(),
                    rois_seen=dict(self.rois), uses_roi=self.params.uses_roi())
