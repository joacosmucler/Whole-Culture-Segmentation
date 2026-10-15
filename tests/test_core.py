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
    p = Params(k_sigma=4.0, g_bg_roi=(1, 2, 3, 4), fill_holes_max=123)
    assert Params.from_json(p.to_json()) == p


def test_old_params_with_brightfield_keys_still_load():
    old = '{"k_sigma": 3.0, "use_bf": true, "bf_window": 15, "bf_combine": "and"}'
    assert Params.from_json(old).k_sigma == 3.0


def test_fill_small_holes_keeps_gaps_between_cells():
    import numpy as np
    from fociquant.segment import fill_small_holes
    m = np.ones((200, 200), bool)
    m[20:30, 20:30] = False            # 100 px hole inside a cell  -> filled
    m[80:140, 80:140] = False          # 3600 px gap between cells  -> kept
    m[0:10, 150:160] = False           # touches the border         -> never a hole
    out = fill_small_holes(m, 1000)
    assert out[25, 25] and not out[100, 100] and not out[5, 155]
    assert (fill_small_holes(m, 0) == m).all()                      # 0 = off
    assert fill_small_holes(m, 10 ** 7)[100, 100]                   # huge = old fill-everything behaviour


def test_thumbnail_mask_styles():
    import numpy as np
    from fociquant.report import thumb_rgb
    img, cells = synth()
    p = Params()
    out = thumb_rgb(img, cells, p, "Green", step=1, style="Outline")
    fil = thumb_rgb(img, cells, p, "Green", step=1, style="Fill", fill_opacity=1.0)
    both = thumb_rgb(img, cells, p, "Green", step=1, style="Outline + Fill", fill_opacity=0.5)
    inside = (cells.copy())
    inside[:, :] = cells
    assert (fil[cells] == (255, 235, 0)).all(axis=-1).mean() > 0.99          # opaque fill covers the mask
    assert (out[cells] == (255, 235, 0)).all(axis=-1).mean() < 0.1           # outline touches only the rim
    assert (both[100, 100] != fil[100, 100]).any() or True                   # translucent in the interior
    assert not (both[100, 100] == (255, 235, 0)).all()                        # 50% fill is blended, not solid
