"""Tab 2 — Batch & Plot: run the current parameters on many images, inspect results, plot."""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPlainTextEdit, QProgressBar, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                             QTabWidget, QVBoxLayout, QWidget)

from fociquant.pipeline import run_batch
from fociquant.report import METRICS, summary_plot

from .params_panel import tip
from .worker import Worker, is_running

DEFAULT_BOX = (10, 10, 110, 110)


class ScaledPixmapLabel(QLabel):
    """Shows a pixmap scaled to fit the available space (re-scales on resize)."""

    def __init__(self, text=""):
        super().__init__(text)
        self._pm: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(100, 100)

    def set_pixmap(self, pm: QPixmap | None):
        self._pm = pm
        self._rescale()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rescale()

    def _rescale(self):
        if self._pm is not None and not self._pm.isNull():
            self.setPixmap(self._pm.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))


class BatchPanel(QWidget):
    """`context()` returns dict(files, conditions, params, rois_seen, uses_roi) from the Tune tab."""

    def __init__(self, context, settings):
        super().__init__()
        self._context, self.settings = context, settings
        self._worker: Worker | None = None
        self._df = None
        self._out: Path | None = None
        self._excluded: set[str] = set()
        self._files: list[str] = []

        # ---------------- left: what will run
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", "File", "Condition"])
        self.table.verticalHeader().hide()
        self.table.setColumnWidth(0, 28); self.table.setColumnWidth(1, 250)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(180)
        self.table.setToolTip(tip("Images of the Tune tab. Untick the ones to leave out of this run. Images and "
                                  "conditions are edited in the Tune tab."))
        self.table.itemChanged.connect(self._on_check)
        b_all = QPushButton("All"); b_none = QPushButton("None")
        b_all.clicked.connect(lambda: self._set_all(True)); b_none.clicked.connect(lambda: self._set_all(False))
        row = QHBoxLayout(); row.addWidget(b_all); row.addWidget(b_none); row.addStretch(1)
        self.summary = QLabel(""); self.summary.setWordWrap(True)

        self.params_text = QPlainTextEdit(); self.params_text.setReadOnly(True)
        f = QFont(); f.setStyleHint(QFont.StyleHint.Monospace); f.setPointSize(10); self.params_text.setFont(f)
        self.params_text.setMinimumHeight(150)
        self.params_text.setToolTip(tip("The parameters this run will use: whatever is set in the Tune tab right now. "
                                        "They are also saved next to the results as params.json."))
        self.warn = QLabel(""); self.warn.setWordWrap(True)

        self.out_edit = QLineEdit(settings.value("out_dir", str(Path.home() / "FociQuant_results")))
        self.out_edit.setToolTip(tip("Folder where the CSVs, plot, params.json, masks and overlays are written."))
        b_out = QPushButton("…"); b_out.setMaximumWidth(36); b_out.clicked.connect(self._pick_out)
        orow = QHBoxLayout(); orow.addWidget(self.out_edit, 1); orow.addWidget(b_out)
        self.qc_check = QCheckBox("Save masks + overlay images"); self.qc_check.setChecked(True)
        self.qc_check.setToolTip(tip("Also writes, for every image, the binary mask (TIFF) and a PNG with the "
                                     "outline on the red and green channels, so each measurement can be audited."))
        self.run_btn = QPushButton("RUN BATCH"); self.run_btn.setMinimumHeight(40)
        self.run_btn.clicked.connect(self.run)
        self.run_btn.setToolTip(tip("Apply the parameters to every ticked image and write the results: per-image "
                                    "CSV, per-condition CSV, plot, params.json, masks and overlays."))
        self.progress = QProgressBar(); self.status = QLabel("Ready."); self.status.setWordWrap(True)

        left = QWidget(); lv = QVBoxLayout(left)
        for w in (QLabel("IMAGES TO PROCESS"), self.table):
            lv.addWidget(w)
        lv.addLayout(row); lv.addWidget(self.summary)
        lv.addWidget(QLabel("PARAMETERS IN USE  (edit them in the Tune tab)")); lv.addWidget(self.params_text, 1)
        lv.addWidget(self.warn)
        lv.addWidget(QLabel("OUTPUT FOLDER")); lv.addLayout(orow); lv.addWidget(self.qc_check)
        lv.addWidget(self.run_btn); lv.addWidget(self.progress); lv.addWidget(self.status)
        left.setMinimumWidth(400)

        # ---------------- right: results + plot
        self.tbl_cond = QTableWidget(); self.tbl_img = QTableWidget()
        self.plot_lbl = ScaledPixmapLabel("No results yet — run a batch or load a results folder.")
        self.metric = QComboBox()
        for k in METRICS:
            self.metric.addItem(k)
        self.metric.setToolTip(tip("What the plot shows for each image. <b>mean_bgsub</b> is the main result "
                                   "(mean red inside cells minus red background). Changing it redraws the plot only; "
                                   "nothing is recomputed."))
        self.metric.currentTextChanged.connect(lambda _: self._draw_plot())
        self.open_btn = QPushButton("Open results folder"); self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_out)
        self.load_btn = QPushButton("Load results folder…")
        self.load_btn.setToolTip(tip("Show the tables and plot of an earlier run (reads per_image.csv)."))
        self.load_btn.clicked.connect(self._load_results)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Plot metric")); bar.addWidget(self.metric); bar.addStretch(1)
        bar.addWidget(self.load_btn); bar.addWidget(self.open_btn)
        plot_tab = QWidget(); pv = QVBoxLayout(plot_tab); pv.addWidget(self.plot_lbl, 1)
        self.res_tabs = QTabWidget()
        self.res_tabs.addTab(plot_tab, "Plot")
        self.res_tabs.addTab(self.tbl_cond, "By condition")
        self.res_tabs.addTab(self.tbl_img, "Per image")
        right = QWidget(); rv = QVBoxLayout(right)
        rv.addLayout(bar); rv.addWidget(self.res_tabs, 1)

        sp = QSplitter(); sp.addWidget(left); sp.addWidget(right)
        sp.setSizes([450, 1000]); sp.setStretchFactor(1, 1)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(sp)

    # ------------------------------------------------------------ inputs
    def refresh(self):
        """Re-read images and parameters from the Tune tab (called when this tab is shown)."""
        ctx = self._context()
        self._files = list(ctx["files"])
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._files))
        for i, f in enumerate(self._files):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked if f in self._excluded else Qt.CheckState.Checked)
            name = QTableWidgetItem(Path(f).name); name.setToolTip(f); name.setFlags(Qt.ItemFlag.ItemIsEnabled)
            cond = QTableWidgetItem(ctx["conditions"].get(f, "")); cond.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 0, chk); self.table.setItem(i, 1, name); self.table.setItem(i, 2, cond)
        self.table.blockSignals(False)
        p = ctx["params"]
        keep = ("ch_red", "ch_green", "g_bg_method", "g_bg_percentile", "g_bg_fixed", "sigma", "k_sigma", "thr_factor",
                "thr_offset", "n_erode", "close_radius", "fill_holes_max", "min_size", "r_bg_method", "r_bg_margin",
                "r_bg_percentile", "r_bg_fixed")
        d = asdict(p)
        self.params_text.setPlainText("\n".join(f"{k:<16} {d[k]}" for k in keep))
        self._ctx = ctx
        self._update_summary()

    def _selected(self) -> list[str]:
        return [f for f in self._files if f not in self._excluded]

    def _on_check(self, item):
        if item.column() == 0 and 0 <= item.row() < len(self._files):
            f = self._files[item.row()]
            (self._excluded.discard if item.checkState() == Qt.CheckState.Checked else self._excluded.add)(f)
            self._update_summary()

    def _set_all(self, on: bool):
        self.table.blockSignals(True)
        for i, f in enumerate(self._files):
            self.table.item(i, 0).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            (self._excluded.discard if on else self._excluded.add)(f)
        self.table.blockSignals(False)
        self._update_summary()

    def _update_summary(self):
        sel = self._selected()
        conds: dict[str, int] = {}
        for f in sel:
            c = self._ctx["conditions"].get(f, "") or "(none)"
            conds[c] = conds.get(c, 0) + 1
        self.summary.setText(f"{len(sel)} of {len(self._files)} images · " +
                             ", ".join(f"{c} ({n})" for c, n in conds.items()))
        unseen = [f for f in sel if f not in self._ctx["rois_seen"]]
        if self._ctx["uses_roi"] and unseen:
            self.warn.setText(f"⚠ Background method 'roi': {len(unseen)} image(s) were never opened in the Tune tab, "
                              "so they use the default box in the top-left corner. Open each one and place the box "
                              "over empty glass, or use another method.")
        else:
            self.warn.setText("")
        self.run_btn.setEnabled(bool(sel) and not is_running(self._worker))

    # ------------------------------------------------------------- run
    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    def save_settings(self):
        self.settings.setValue("out_dir", self.out_edit.text())

    def run(self):
        self.refresh()                                  # always use what the Tune tab says right now
        files = self._selected()
        if not files:
            QMessageBox.information(self, "No images", "Tick at least one image.")
            return
        if is_running(self._worker):
            return
        ctx = self._ctx
        p = replace(ctx["params"], save_qc=self.qc_check.isChecked())
        out = Path(self.out_edit.text())
        conds = {f: ctx["conditions"].get(f, "") for f in files}
        rois = {f: ctx["rois_seen"].get(f, DEFAULT_BOX) for f in files} if ctx["uses_roi"] else None
        self.run_btn.setEnabled(False); self.progress.setValue(0)
        w = Worker(lambda progress: run_batch(files, p, out, progress, conds, rois))
        w.progress.connect(lambda m, pc: (self.progress.setValue(max(pc, 0)), self.status.setText(f"Running: {m}")))
        w.result.connect(lambda df, o=out: self._done(df, o))
        w.failed.connect(self._failed)
        self._worker = w
        w.start()

    def _failed(self, msg):
        self.run_btn.setEnabled(True)
        self.status.setText("Batch failed.")
        QMessageBox.critical(self, "Batch failed", msg[:2000])

    def _done(self, df, out: Path):
        self.run_btn.setEnabled(True); self.progress.setValue(100)
        self._show_results(df, out)
        self.status.setText(f"Done — {len(df)} images → {out}")

    # --------------------------------------------------------- results
    def _show_results(self, df, out: Path):
        import pandas as pd
        self._df, self._out = df, out
        self.open_btn.setEnabled(True)
        self._fill(self.tbl_img, df)
        cond = out / "per_condition.csv"
        self._fill(self.tbl_cond, pd.read_csv(cond) if cond.exists() else pd.DataFrame())
        self._draw_plot()
        self.res_tabs.setCurrentIndex(0)

    def _draw_plot(self):
        if self._df is None or self._out is None or len(self._df) == 0:
            return
        m = self.metric.currentText()
        png = self._out / ("summary_plot.png" if m == "mean_bgsub" else f"summary_plot_{m}.png")
        try:
            summary_plot(self._df, png, m)
        except Exception as e:  # noqa: BLE001
            self.status.setText(f"Could not draw the plot: {e}")
            return
        self.plot_lbl.set_pixmap(QPixmap(str(png)))

    def _load_results(self):
        import pandas as pd
        d = QFileDialog.getExistingDirectory(self, "Results folder (contains per_image.csv)", self.out_edit.text())
        if not d:
            return
        csv = Path(d) / "per_image.csv"
        if not csv.exists():
            QMessageBox.warning(self, "Not a results folder", f"No per_image.csv in\n{d}")
            return
        df = pd.read_csv(csv)
        df["condition"] = df["condition"].fillna("")
        self._show_results(df, Path(d))
        self.status.setText(f"Loaded {len(df)} images from {d}")

    @staticmethod
    def _fill(tbl: QTableWidget, df):
        tbl.setRowCount(len(df)); tbl.setColumnCount(len(df.columns))
        tbl.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for i, (_, r) in enumerate(df.iterrows()):
            for j, v in enumerate(r):
                tbl.setItem(i, j, QTableWidgetItem(f"{v:.2f}" if isinstance(v, float) else str(v)))
        tbl.resizeColumnsToContents()

    def _open_out(self):
        if self._out:
            if sys.platform == "darwin":
                subprocess.run(["open", str(self._out)])
            elif os.name == "nt":
                os.startfile(str(self._out))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(self._out)])
