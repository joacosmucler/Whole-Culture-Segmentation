"""pyqtgraph canvas: channel view + mask contour overlay + background box."""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal

pg.setConfigOptions(imageAxisOrder="row-major", antialias=False)

VIEWS = ["Green", "Red", "Brightfield", "Red + Green"]


def _norm(a, lo=1.0, hi=99.7):
    l, h = np.percentile(a, [lo, hi])
    return np.clip((a.astype(np.float32) - l) / max(h - l, 1e-6), 0, 1)


class Canvas(pg.GraphicsLayoutWidget):
    roi_changed = pyqtSignal(tuple)      # (x0, y0, x1, y1)

    def __init__(self):
        super().__init__()
        self.setBackground("#050505")
        self.vb = self.addViewBox(lockAspect=True, invertY=True)
        self.img_item = pg.ImageItem()
        self.mask_item = pg.ImageItem()
        self.mask_item.setZValue(10)
        self.vb.addItem(self.img_item)
        self.vb.addItem(self.mask_item)
        self.roi = pg.RectROI([10, 10], [80, 80], pen=pg.mkPen("#1FA99F", width=2))
        self.roi.addScaleHandle((1, 1), (0, 0))
        self.roi.addScaleHandle((0, 0), (1, 1))
        self.roi.setZValue(20)
        self.roi.hide()
        self.vb.addItem(self.roi)
        self.roi.sigRegionChangeFinished.connect(self._emit_roi)
        self._data = None
        self._shape = None
        self._first = True

    # -- display ---------------------------------------------------------
    def set_image(self, data: np.ndarray, ch_red: int, ch_green: int, ch_bf: int, view: str):
        """data: (C, Y, X)."""
        def pick(i):
            return data[min(i, data.shape[0] - 1)]
        if view == "Red":
            rgb = _norm(pick(ch_red))
            img = np.stack([rgb] * 3, -1)
        elif view == "Brightfield":
            rgb = _norm(pick(ch_bf))
            img = np.stack([rgb] * 3, -1)
        elif view == "Red + Green":
            img = np.stack([_norm(pick(ch_red)), _norm(pick(ch_green)), np.zeros(data.shape[1:], np.float32)], -1)
        else:
            rgb = _norm(pick(ch_green))
            img = np.stack([rgb] * 3, -1)
        self.img_item.setImage((img * 255).astype(np.uint8), autoLevels=False, levels=(0, 255))
        if self._first or self._shape != data.shape[1:]:
            self.vb.autoRange()
            self._first = False
        self._shape = data.shape[1:]

    def set_mask(self, mask: np.ndarray | None, opacity: float = 0.9):
        if mask is None:
            self.mask_item.clear()
            return
        from skimage.segmentation import find_boundaries
        b = find_boundaries(mask, mode="inner")
        rgba = np.zeros(mask.shape + (4,), np.uint8)
        rgba[b] = (255, 235, 0, 255)
        self.mask_item.setImage(rgba, autoLevels=False)
        self.mask_item.setOpacity(opacity)

    # -- background box --------------------------------------------------
    def show_roi(self, visible: bool, box: tuple | None = None):
        self.roi.setVisible(visible)
        if box is not None:
            x0, y0, x1, y1 = box
            self.roi.blockSignals(True)
            self.roi.setPos((x0, y0))
            self.roi.setSize((x1 - x0, y1 - y0))
            self.roi.blockSignals(False)

    def roi_box(self) -> tuple[int, int, int, int]:
        x, y = self.roi.pos()
        w, h = self.roi.size()
        H, W = self._shape if self._shape else (10 ** 6, 10 ** 6)
        x0, x1 = sorted((int(np.clip(x, 0, W - 1)), int(np.clip(x + w, 1, W))))
        y0, y1 = sorted((int(np.clip(y, 0, H - 1)), int(np.clip(y + h, 1, H))))
        return x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)

    def _emit_roi(self):
        self.roi_changed.emit(self.roi_box())
