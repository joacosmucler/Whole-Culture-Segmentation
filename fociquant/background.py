"""Background estimation."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d


def hist_mode(img: np.ndarray, nbins: int = 512, smooth: float = 2.0) -> float:
    """Peak of the smoothed histogram, clipped to the 0.1-99.9 percentile range.
    Robust bg estimate when background dominates the field."""
    lo, hi = np.percentile(img, [0.1, 99.9])
    h, edges = np.histogram(img, bins=nbins, range=(lo, hi))
    h = gaussian_filter1d(h.astype(float), smooth)
    i = int(np.argmax(h))
    return float((edges[i] + edges[i + 1]) / 2)


def floor_mode(img: np.ndarray, frac: float = 0.2) -> float:
    """Histogram peak of the darkest `frac` of pixels. Unlike the plain mode it still
    finds the empty-background floor when dim cells cover most of the field."""
    cut = np.percentile(img, frac * 100)
    return hist_mode(img[img <= cut], nbins=128, smooth=1.5)


def estimate_bg(img: np.ndarray, method: str = "mode", *, percentile: float = 5.0,
                fixed: float = 0.0, roi: tuple[int, int, int, int] | None = None) -> float:
    """method: floor | mode | percentile | roi | fixed.  roi = (x0, y0, x1, y1) in pixels."""
    if method == "fixed":
        return float(fixed)
    if method == "roi":
        if roi is None:
            raise ValueError("Background method 'roi' needs a box")
        x0, y0, x1, y1 = roi
        return float(np.median(img[y0:y1, x0:x1]))
    if method == "percentile":
        return float(np.percentile(img, percentile))
    if method == "floor":
        return floor_mode(img)
    return hist_mode(img)


def bg_sigma(img: np.ndarray, bg: float) -> float:
    """Noise of the background, from the lower half of the distribution only
    (mirrored around bg) so bright cells do not inflate it."""
    low = img[img <= bg].astype(np.float64)
    if low.size < 50:
        return float(np.std(img))
    return float(np.sqrt(np.mean((low - bg) ** 2)))
