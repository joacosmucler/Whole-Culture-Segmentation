"""Whole-region intensity measurement."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage import morphology

from .background import estimate_bg


def red_background(red, mask, method, *, margin, percentile, fixed, roi) -> float:
    if method == "outside":
        out = ~ndi.binary_dilation(mask, morphology.disk(1), iterations=max(margin, 0))
        if out.sum() < 100:           # fully covered field: fall back to low percentile
            return float(np.percentile(red, percentile))
        return float(np.median(red[out]))
    return estimate_bg(red, method, percentile=percentile, fixed=fixed, roi=roi)


def measure(red: np.ndarray, mask: np.ndarray, bg_r: float, pixel_size_um: float | None) -> dict:
    n = int(mask.sum())
    if n == 0:
        return dict(mean_raw=np.nan, mean_bgsub=np.nan, median_bgsub=np.nan, intdens_bgsub=np.nan,
                    mask_area_px=0, mask_area_um2=np.nan, mask_fraction=0.0)
    v = red[mask].astype(np.float64)
    return dict(
        mean_raw=float(v.mean()),
        mean_bgsub=float(v.mean() - bg_r),
        median_bgsub=float(np.median(v) - bg_r),
        intdens_bgsub=float((v - bg_r).sum()),
        mask_area_px=n,
        mask_area_um2=float(n * pixel_size_um ** 2) if pixel_size_um else np.nan,
        mask_fraction=float(n / mask.size),
    )
