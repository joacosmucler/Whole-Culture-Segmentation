"""Image loading: multichannel TIFF and CZI -> list of Image records."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Image:
    name: str                      # display name (file stem [+ scene])
    path: str
    scene: int
    data: np.ndarray               # (C, Y, X)
    pixel_size_um: float | None = None
    condition: str = ""


def _tiff_pixel_size(tf) -> float | None:
    try:
        md = tf.imagej_metadata or {}
        if md.get("unit") not in ("micron", "um", "µm"):
            return None
        tag = tf.pages[0].tags.get("XResolution")
        if tag is None:
            return None
        num, den = tag.value
        return float(den) / float(num) if num else None
    except Exception:
        return None


def load_tiff(path: Path) -> list[Image]:
    import tifffile
    with tifffile.TiffFile(path) as tf:
        a = tf.asarray()
        px = _tiff_pixel_size(tf)
    if a.ndim == 2:
        a = a[None]
    elif a.ndim > 3:                       # squeeze singleton axes, else take first of extras
        a = np.squeeze(a)
        while a.ndim > 3:
            a = a[0]
    # channels-last guard
    if a.shape[-1] <= 5 and a.shape[0] > 5:
        a = np.moveaxis(a, -1, 0)
    return [Image(path.stem, str(path), 0, a, px, path.parent.name)]


def load_czi(path: Path) -> list[Image]:
    from aicspylibczi import CziFile
    czi = CziFile(str(path))
    dims = czi.get_dims_shape()[0]
    n_scenes = dims["S"][1] if "S" in dims else 1
    try:
        px = float(czi.get_scaling()[0]) * 1e6 if hasattr(czi, "get_scaling") else None
    except Exception:
        px = None
    out = []
    for s in range(n_scenes):
        kw = {"S": s} if "S" in dims else {}
        arr, shp = czi.read_image(**kw)
        order = [d for d, _ in shp]
        keep = [i for i, d in enumerate(order) if d in ("C", "Y", "X")]
        arr = np.squeeze(arr)
        # reduce to CYX by selecting index 0 on all other axes
        idx = tuple(slice(None) if d in ("C", "Y", "X") else 0 for d in order)
        arr = np.asarray(arr if arr.ndim == 3 else arr)
        full, _ = czi.read_image(**kw)
        arr = full[idx]
        c_pos = [d for d in order if d in ("C", "Y", "X")]
        arr = np.transpose(arr, [c_pos.index(d) for d in ("C", "Y", "X")]) if "C" in c_pos else arr[None]
        name = path.stem if n_scenes == 1 else f"{path.stem}_s{s + 1}"
        out.append(Image(name, str(path), s, arr, px, path.parent.name))
    return out


def load_image(path: str | Path) -> list[Image]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".tif", ".tiff"):
        return load_tiff(p)
    if ext == ".czi":
        return load_czi(p)
    raise ValueError(f"Unsupported file type: {p}")


def find_images(folder: str | Path) -> list[Path]:
    exts = {".tif", ".tiff", ".czi"}
    return sorted(p for p in Path(folder).rglob("*") if p.suffix.lower() in exts and not p.name.startswith("."))
