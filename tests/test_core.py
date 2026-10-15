import numpy as np
from fociquant.io import Image
from fociquant.pipeline import Params, analyze_image


def synth(seed=0, bg_g=500, bg_r=100, cell_g=900, cell_r=400):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:300, :300]
    cells = ((yy - 100) ** 2 + (xx - 100) ** 2 < 40 ** 2) | ((yy - 200) ** 2 + (xx - 210) ** 2 < 35 ** 2)
    green = rng.normal(bg_g, 10, cells.shape) + cells * (cell_g - bg_g)
    red = rng.normal(bg_r, 5, cells.shape) + cells * (cell_r - bg_r)
    bf = rng.normal(1000, 5, cells.shape)
    data = np.stack([red, bf, green]).clip(0, 65535).astype(np.uint16)
    return Image("synth", "synth.tif", 0, data, 0.5, "cond"), cells


def test_recovers_known_mean():
    img, cells = synth()
    row, seg = analyze_image(img, Params())
    assert abs(row["mean_bgsub"] - 300) < 25            # 400 - 100
    assert abs(row["bg_red"] - 100) < 5
    assert abs(row["bg_green"] - 500) < 25
    inter = (seg["mask"] & cells).sum() / cells.sum()
    assert inter > 0.9 and seg["mask"][~cells].mean() < 0.02


def test_manual_overrides():
    img, _ = synth()
    p = Params(g_bg_method="fixed", g_bg_fixed=500, r_bg_method="fixed", r_bg_fixed=100)
    row, _ = analyze_image(img, p)
    assert row["bg_green"] == 500 and row["bg_red"] == 100
    p = Params(g_bg_method="roi", g_bg_roi=(0, 0, 40, 40), r_bg_method="roi", r_bg_roi=(0, 0, 40, 40))
    row, _ = analyze_image(img, p)
    assert abs(row["bg_green"] - 500) < 5


def test_params_json_roundtrip():
    p = Params(k_sigma=4.0, g_bg_roi=(1, 2, 3, 4), use_bf=True)
    assert Params.from_json(p.to_json()) == p


def test_bf_refinement_runs():
    img, _ = synth()
    row, seg = analyze_image(img, Params(use_bf=True, bf_combine="or"))
    assert seg["bf_mask"] is not None
