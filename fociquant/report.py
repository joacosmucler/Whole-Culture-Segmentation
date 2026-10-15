"""CSV / plot / QC-image writers."""
from __future__ import annotations

from pathlib import Path

import numpy as np


def _norm(a, lo=1, hi=99.5):
    l, h = np.percentile(a, [lo, hi])
    return np.clip((a.astype(np.float32) - l) / max(h - l, 1e-6), 0, 1)


def overlay_rgb(img, mask, p) -> np.ndarray:
    """Side-by-side red | green with mask contour in yellow."""
    from skimage.segmentation import find_boundaries
    b = find_boundaries(mask, mode="inner")
    tiles = []
    for ch in (p.ch_red, p.ch_green):
        g = _norm(img.data[ch])
        rgb = np.stack([g, g, g], -1)
        rgb[b] = (1, 1, 0)
        tiles.append(rgb)
    return (np.concatenate(tiles, 1) * 255).astype(np.uint8)


def save_qc(out: Path, im, seg, p) -> None:
    import tifffile
    from PIL import Image as PI
    (out / "masks").mkdir(exist_ok=True)
    (out / "overlays").mkdir(exist_ok=True)
    stem = f"{im.condition}__{im.name}".replace(" ", "_").replace("/", "_")
    tifffile.imwrite(out / "masks" / f"{stem}.tif", seg["mask"].astype(np.uint8) * 255)
    PI.fromarray(overlay_rgb(im, seg["mask"], p)).save(out / "overlays" / f"{stem}.png")


def condition_table(df):
    import pandas as pd
    rows = []
    for c, g in df.groupby("condition"):
        w = g["mask_area_px"].sum()
        rows.append(dict(condition=c, n_images=len(g),
                         mean_bgsub_mean=g["mean_bgsub"].mean(),
                         mean_bgsub_sd=g["mean_bgsub"].std(ddof=1) if len(g) > 1 else np.nan,
                         mean_bgsub_sem=g["mean_bgsub"].sem() if len(g) > 1 else np.nan,
                         area_weighted_mean_bgsub=g["intdens_bgsub"].sum() / w if w else np.nan))
    return pd.DataFrame(rows)


def summary_plot(df, path_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    conds = list(dict.fromkeys(df["condition"]))
    fig, ax = plt.subplots(figsize=(1.6 * len(conds) + 2, 4))
    data = [df.loc[df.condition == c, "mean_bgsub"].dropna().values for c in conds]
    ax.boxplot(data, tick_labels=conds, showfliers=False, widths=0.5)
    rng = np.random.default_rng(0)
    for i, d in enumerate(data, 1):
        ax.scatter(i + rng.uniform(-0.12, 0.12, len(d)), d, s=22, color="#1FA99F", zorder=3)
    ax.set_ylabel("Mean red intensity in cells\n(background-subtracted, a.u.)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path_png, dpi=200)
    fig.savefig(path_png.with_suffix(".svg"))
    plt.close(fig)


def write_outputs(out: Path, df, p) -> None:
    df.to_csv(out / "per_image.csv", index=False)
    condition_table(df).to_csv(out / "per_condition.csv", index=False)
    (out / "params.json").write_text(p.to_json())
    if len(df):
        summary_plot(df, out / "summary_plot.png")
