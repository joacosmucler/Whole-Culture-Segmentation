"""Cell-mask construction from green (+ optional brightfield)."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage import filters, morphology

from .background import bg_sigma


def clean(mask: np.ndarray, n_erode: int, close_radius: int, min_size: int) -> np.ndarray:
    se = morphology.disk(1)
    for _ in range(n_erode):
        mask = ndi.binary_erosion(mask, se)
    if close_radius > 0:
        mask = morphology.closing(mask, morphology.disk(close_radius))
    mask = ndi.binary_fill_holes(mask)
    if min_size > 0:
        mask = ndi.label(mask)[0]
        sizes = np.bincount(mask.ravel())
        keep = sizes >= min_size
        keep[0] = False
        mask = keep[mask]
    return mask


def green_mask(green: np.ndarray, bg_g: float, *, sigma: float, k_sigma: float, factor: float, offset: float,
               n_erode: int, close_radius: int, min_size: int) -> tuple[np.ndarray, float]:
    g = filters.gaussian(green.astype(np.float32), sigma, preserve_range=True) if sigma > 0 else green.astype(np.float32)
    thr = bg_g * factor + offset + k_sigma * bg_sigma(green, bg_g)
    return clean(g > thr, n_erode, close_radius, min_size), float(thr)


def bf_texture_mask(bf: np.ndarray, *, window: int, method: str, factor: float,
                    close_radius: int, min_size: int) -> np.ndarray:
    """Cells are textured in brightfield, empty background is flat -> local std map."""
    b = bf.astype(np.float32)
    m = ndi.uniform_filter(b, window)
    var = np.maximum(ndi.uniform_filter(b * b, window) - m * m, 0)
    std = np.sqrt(var)
    std = filters.gaussian(std, max(window / 4, 1), preserve_range=True)
    thr = filters.threshold_otsu(std) if method == "otsu" else float(np.median(std)) * factor
    return clean(std > thr, 0, close_radius, min_size)


def combine(green_m: np.ndarray, bf_m: np.ndarray | None, mode: str) -> np.ndarray:
    if bf_m is None:
        return green_m
    return green_m & bf_m if mode == "and" else green_m | bf_m
