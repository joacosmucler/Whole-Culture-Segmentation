"""Image loading (multichannel TIFF / CZI) + per-channel metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class ChannelInfo:
    name: str = ""
    fluor: str = ""            # dye / fluorophore, e.g. "Rhodamine", "TL Brightfield"
    contrast: str = ""         # "Fluorescence" | "Brightfield" | ...
    illumination: str = ""     # "Epifluorescence" | "Transmitted" | ...
    emission: float | None = None   # nm

    def label(self) -> str:
        s = self.name or "?"
        if self.fluor and self.fluor != self.name:
            s += f" ({self.fluor})"
        return s


@dataclass
class Image:
    name: str                      # display name (file stem [+ scene])
    path: str
    scene: int
    data: np.ndarray               # (C, Y, X)
    pixel_size_um: float | None = None
    condition: str = ""
    channels: list[ChannelInfo] = field(default_factory=list)   # empty if no metadata

    def channel_labels(self) -> list[str]:
        """['0 · Rhoda (Rhodamine)', ...] — falls back to plain indices."""
        n = self.data.shape[0]
        if len(self.channels) != n:
            return [str(i) for i in range(n)]
        return [f"{i} · {c.label()}" for i, c in enumerate(self.channels)]


# ----------------------------------------------------------------- TIFF
_INFO_RE = re.compile(
    r"Information\|Image\|Channel\|(Name|Fluor|ContrastMethod|IlluminationType|EmissionWavelength) #(\d+) = (.*)")


def _is_bf(c: ChannelInfo) -> bool:
    return bool(re.search(r"bright|transmit|phase|dic", f"{c.contrast} {c.illumination} {c.fluor}", re.I))


def parse_zeiss_info(info: str, n_channels: int) -> list[ChannelInfo]:
    """Channel metadata from the ImageJ 'Info' block of a Fiji-exported CZI (Zeiss keys)."""
    d: dict[str, dict[int, str]] = {}
    for m in _INFO_RE.finditer(info or ""):
        d.setdefault(m.group(1), {})[int(m.group(2))] = m.group(3).strip()
    names = d.get("Name", {})
    if len(names) != n_channels:
        return []
    chs = [ChannelInfo(name=names[i + 1], fluor=d.get("Fluor", {}).get(i + 1, ""),
                       contrast=d.get("ContrastMethod", {}).get(i + 1, ""),
                       illumination=d.get("IlluminationType", {}).get(i + 1, "")) for i in range(n_channels)]
    # emission wavelengths are numbered over the fluorescence channels only
    em = d.get("EmissionWavelength", {})
    fl = [c for c in chs if not _is_bf(c)]
    if em and len(em) == len(fl):
        for k, c in enumerate(fl, 1):
            try:
                c.emission = float(em[k])
            except ValueError:
                pass
    return chs


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
        info = (tf.imagej_metadata or {}).get("Info", "") if tf.is_imagej else ""
    if a.ndim == 2:
        a = a[None]
    elif a.ndim > 3:
        a = np.squeeze(a)
        while a.ndim > 3:
            a = a[0]
    if a.shape[-1] <= 5 and a.shape[0] > 5:      # channels-last guard
        a = np.moveaxis(a, -1, 0)
    return [Image(path.stem, str(path), 0, a, px, path.parent.name, parse_zeiss_info(info, a.shape[0]))]


# ------------------------------------------------------------------ CZI
def _czi_channels(root) -> list[ChannelInfo]:
    nodes = root.findall(".//Information/Image/Dimensions/Channels/Channel") \
        or root.findall(".//Dimensions/Channels/Channel")
    out = []
    for n in nodes:
        t = lambda tag: (n.findtext(tag) or "").strip()      # noqa: E731
        em = t("EmissionWavelength")
        try:
            emv = float(em) if em else None
        except ValueError:
            emv = None
        out.append(ChannelInfo(n.attrib.get("Name", ""), t("Fluor"), t("ContrastMethod"),
                               t("IlluminationType"), emv))
    return out


def load_czi(path: Path) -> list[Image]:
    from aicspylibczi import CziFile
    czi = CziFile(str(path))
    dims = czi.get_dims_shape()[0]                  # e.g. {'S': (0, 11), 'C': (0, 3), 'Y': ..., 'X': ...}
    n_scenes = dims["S"][1] if "S" in dims else 1
    root = czi.meta
    px = None
    try:
        v = root.findtext('.//Scaling/Items/Distance[@Id="X"]/Value')
        px = float(v) * 1e6 if v else None          # metres -> µm
    except Exception:
        pass
    chs = _czi_channels(root)
    out = []
    for s in range(n_scenes):
        # first index of every axis other than scene/channel/Y/X (time, z, tiles, ...)
        kw = {d: 0 for d in dims if d not in ("C", "Y", "X", "S")}
        if "S" in dims:
            kw["S"] = s
        arr, shp = czi.read_image(**kw)
        order = [d for d, _ in shp]
        sel = tuple(slice(None) if d in ("C", "Y", "X") else 0 for d in order)
        arr = arr[sel]
        kept = [d for d in order if d in ("C", "Y", "X")]
        if "C" not in kept:
            arr, kept = arr[None], ["C"] + kept
        arr = np.transpose(arr, [kept.index(d) for d in ("C", "Y", "X")])
        name = path.stem if n_scenes == 1 else f"{path.stem}_s{s + 1}"
        out.append(Image(name, str(path), s, np.ascontiguousarray(arr), px, path.parent.name,
                         chs if len(chs) == arr.shape[0] else []))
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
