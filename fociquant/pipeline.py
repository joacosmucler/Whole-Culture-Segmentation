"""Params + single-image / batch execution."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field, fields, replace
from pathlib import Path

import numpy as np

from .background import estimate_bg
from .io import Image, load_image
from .measure import measure, red_background
from .segment import green_mask


@dataclass
class Params:
    # channels (index into the CYX stack); ch_bf is only used for the brightfield *view*
    ch_red: int = 0
    ch_bf: int = 1
    ch_green: int = 2
    # green background / mask
    g_bg_method: str = "floor"         # floor | mode | percentile | roi | fixed
    g_bg_percentile: float = 5.0
    g_bg_fixed: float = 0.0
    g_bg_roi: tuple | None = None      # (x0, y0, x1, y1)
    sigma: float = 1.5
    k_sigma: float = 2.5              # threshold = bg*factor + offset + k_sigma*noise
    thr_factor: float = 1.0
    thr_offset: float = 0.0
    n_erode: int = 2
    close_radius: int = 3
    fill_holes_max: int = 1000         # fill enclosed holes up to this many px (0 = off)
    min_size: int = 200
    # red background
    r_bg_method: str = "outside"       # outside | mode | percentile | roi | fixed
    r_bg_margin: int = 10
    r_bg_percentile: float = 5.0
    r_bg_fixed: float = 0.0
    r_bg_roi: tuple | None = None
    # output
    save_qc: bool = True

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, s: str) -> "Params":
        d = json.loads(s)
        names = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in names}
        for k in ("g_bg_roi", "r_bg_roi"):
            if d.get(k):
                d[k] = tuple(d[k])
        return cls(**d)


def segment_image(img: Image, p: Params) -> dict:
    """Return dict(mask, bg_g, thr, bg_r). No measurement."""
    green = img.data[p.ch_green]
    bg_g = estimate_bg(green, p.g_bg_method, percentile=p.g_bg_percentile,
                       fixed=p.g_bg_fixed, roi=p.g_bg_roi)
    mask, thr = green_mask(green, bg_g, sigma=p.sigma, k_sigma=p.k_sigma, factor=p.thr_factor, offset=p.thr_offset,
                           n_erode=p.n_erode, close_radius=p.close_radius, fill_max=p.fill_holes_max,
                           min_size=p.min_size)
    return dict(mask=mask, bg_g=bg_g, thr=thr)


def analyze_image(img: Image, p: Params) -> tuple[dict, dict]:
    seg = segment_image(img, p)
    red = img.data[p.ch_red]
    bg_r = red_background(red, seg["mask"], p.r_bg_method, margin=p.r_bg_margin,
                          percentile=p.r_bg_percentile, fixed=p.r_bg_fixed, roi=p.r_bg_roi)
    row = dict(condition=img.condition, file=Path(img.path).name, scene=img.scene,
               bg_green=seg["bg_g"], threshold_green=seg["thr"], bg_red=bg_r,
               **measure(red, seg["mask"], bg_r, img.pixel_size_um))
    seg["bg_r"] = bg_r
    return row, seg


def run_one(path: str | Path, p: Params) -> list[dict]:
    return [analyze_image(im, p)[0] for im in load_image(path)]


def run_batch(files, p: Params, out_dir: str | Path, progress=None, conditions: dict | None = None,
              rois: dict | None = None):
    """Process all files, write outputs, return the per-image DataFrame."""
    import pandas as pd
    from .report import write_outputs, save_qc
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    files = list(files)
    for i, f in enumerate(files):
        if progress:
            progress(f"{Path(f).name}", int(100 * i / max(len(files), 1)))
        for im in load_image(f):
            if conditions and str(f) in conditions:
                im.condition = conditions[str(f)]
            pp = p
            if rois and str(f) in rois:       # per-file background box (used by 'roi' methods)
                pp = replace(p, g_bg_roi=tuple(rois[str(f)]), r_bg_roi=tuple(rois[str(f)]))
            row, seg = analyze_image(im, pp)
            rows.append(row)
            if p.save_qc:
                save_qc(out, im, seg, pp)
    df = pd.DataFrame(rows)
    write_outputs(out, df, p)
    if progress:
        progress("done", 100)
    return df
