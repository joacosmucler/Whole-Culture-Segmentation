"""Cell-mask construction from the green channel."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage import filters, morphology

from .background import bg_sigma


def fill_small_holes(mask: np.ndarray, max_size: int) -> np.ndarray:
    """Fill background regions fully enclosed by the mask, but only those of at most `max_size` pixels
    (nuclei / unstained patches inside a cell). Larger enclosed regions (gaps between cells) stay background.
    max_size <= 0 disables filling."""
    if max_size <= 0:
        return mask
    lab, _ = ndi.label(~mask)
    sizes = np.bincount(lab.ravel())
    fill = sizes <= max_size
    fill[0] = False                                   # label 0 = the mask itself
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    fill[border] = False                              # regions open to the image border are not holes
    return mask | fill[lab]


def clean(mask: np.ndarray, n_erode: int, close_radius: int, fill_max: int, min_size: int) -> np.ndarray:
    se = morphology.disk(1)
    for _ in range(n_erode):
        mask = ndi.binary_erosion(mask, se)
    if close_radius > 0:
        mask = morphology.closing(mask, morphology.disk(close_radius))
    mask = fill_small_holes(mask, fill_max)
    if min_size > 0:
        lab = ndi.label(mask)[0]
        keep = np.bincount(lab.ravel()) >= min_size
        keep[0] = False
        mask = keep[lab]
    return mask


def green_mask(green: np.ndarray, bg_g: float, *, sigma: float, k_sigma: float, factor: float, offset: float,
               n_erode: int, close_radius: int, fill_max: int, min_size: int) -> tuple[np.ndarray, float]:
    g = filters.gaussian(green.astype(np.float32), sigma, preserve_range=True) if sigma > 0 else green.astype(np.float32)
    thr = bg_g * factor + offset + k_sigma * bg_sigma(green, bg_g)
    return clean(g > thr, n_erode, close_radius, fill_max, min_size), float(thr)
