# FociQuant — implementation plan

Quantify the **background-subtracted mean red (foci) intensity inside cells** (whole-region, not per cell),
using the green membrane channel (optionally refined with brightfield) to build the cell mask.

## Decisions (from Q&A, 2026-10-15)

| Topic | Decision |
|---|---|
| Background | Auto-estimate per image + manual override (fixed value or user-drawn bg box) |
| Outputs | Region-level CSV per image + condition summary; summary plot (box/strip by condition) |
| Brightfield | Optional mask refinement (texture/local-variance map, AND / OR with green mask), off by default |
| Input | Fiji-exported multichannel TIFF **and** raw CZI; channels user-assigned (remembered) |
| GUI | PyQt6 + pyqtgraph, SIIC look & patterns (`theme.py`, `Worker`, canvas); pip-installable |

## Data facts (sample set in this folder)

- TIFF, `CYX`, uint16, 1040×1388, 3 channels. **C0 = red (foci), C1 = brightfield, C2 = green (membrane)**.
- Folders = conditions: `CF/`, `CM bonitos/`, `CM feos/` (4 images each).
- Green: bg ≈ 480–500, cells up to ~1500. Red: bg ≈ 95–100. Cells dense and touching.
- ImageJ metadata carries µm calibration (`unit: micron`, XResolution) → report area in µm² when present.

## Repo layout (repo root = this folder; data excluded via .gitignore)

```
fociquant/                 # UI-free core (no Qt imports)
  io.py                    # load_image(path) -> dict(channels: CYX ndarray, pixel_size_um, name); TIFF via tifffile, CZI via aicspylibczi (scene loop → one record per scene)
  background.py            # estimate_bg(img, method) : "mode" (histogram peak, smoothed), "percentile" (p), "roi" (box), "fixed"
  segment.py               # green_mask(...), bf_texture_mask(...), combine(...)
  measure.py               # measure(red, mask, red_bg) -> dict
  pipeline.py              # Params dataclass (JSON round-trip) + run_one(path, params) + run_batch(files, params, progress)
  report.py                # write CSVs, summary plot (matplotlib, PNG+SVG)
fociquant_gui/
  app.py, main_window.py   # QMainWindow: left param panel | center canvas | bottom file list/log
  theme.py, worker.py      # copied from SIIC (attribute in header)
  canvas.py                # pyqtgraph ImageView w/ channel selector + mask contour overlay + bg-box RectROI
  params_panel.py          # widgets bound to Params
  batch_panel.py           # run batch, progress, open results
tests/                     # synthetic-image tests for core
pyproject.toml             # console script: fociquant
README.md
```

## Core algorithm (`pipeline.run_one`)

1. **Load** → assign channels via `Params.channels = {"red":0, "bf":1, "green":2}`.
2. **Green background** `bg_g`: default `mode` (peak of Gaussian-smoothed histogram of the green channel, robust because bg dominates); alternatives `percentile`, `roi`, `fixed`.
3. **Green mask**:
   - optional Gaussian pre-smooth (`sigma`, default 1.0)
   - `mask = green > bg_g * factor + offset` (expose **threshold factor**, default 1.15, *or* absolute offset; show resulting value)
   - binary erosion × `n_erode` (default 2) → binary closing (disk `close_radius`, default 3) → `fill_holes` → `remove_small_objects(min_size_px)` (default 200)
   - Watershed is **not** needed for a whole-region mean (splitting doesn't change pixels in the mask); skip it. Leave a hook if per-cell is wanted later.
4. **BF refinement (optional)**: local std (uniform filter of x and x², window `bf_window`, default 15) on BF → threshold by Otsu or `bf_factor × median` → close/fill → combine with green mask by `AND` (removes green bg junk) or `OR` (recovers dim cells).
5. **Red background** `bg_r`: default = median of red in `~dilate(mask, bg_margin)` (outside cells with a safety margin, default 10 px); overrides `percentile`, `roi`, `fixed`.
6. **Measure** inside mask: `mean_raw`, `bg_r`, `mean_bgsub = mean_raw − bg_r`, `median_bgsub`, `intdens_bgsub = sum(red−bg_r)`, `mask_area_px`, `mask_area_um2`, `mask_fraction`, `bg_g`, `threshold_used`, plus all params (provenance).
7. **QC artifacts** (always written, cheap): mask TIFF + overlay PNG (contour on green and on red) — lets her audit; can be toggled off.

## Outputs (`<output_dir>/`)

- `per_image.csv` — one row per image/scene: `condition` (parent folder name, editable in GUI), `file`, `scene`, metrics above.
- `per_condition.csv` — n, mean ± SD / SEM of `mean_bgsub`, total-area-weighted mean (`Σintdens / Σarea`).
- `summary_plot.png/.svg` — box + strip of `mean_bgsub` by condition.
- `params.json` — exact parameters used; loadable back into the GUI.
- `masks/`, `overlays/`.

## GUI (single window, SIIC style)

- **Left panel** (scrollable groups): *Input* (add files/folder, TIFF/CZI; channel dropdowns) → *Green background* (method + value, live estimated value shown) → *Mask* (sigma, threshold factor, erode n, close radius, min size) → *Brightfield* (enable, window, threshold, AND/OR) → *Red background* (method, margin) → *Output* (folder, save QC).
- **Center**: pyqtgraph canvas; channel toggle (Red / Green / BF / Composite), mask contour overlay (toggle, opacity); bg-box RectROI shown when method = `roi`. Contrast via histogram LUT widget.
- **Live preview**: any param change → debounced (300 ms) recompute of the current image on a `Worker` thread; status bar shows `bg_g`, threshold, mask %, `mean_bgsub`.
- **File list** (bottom/left): click to preview; per-file override of bg box allowed.
- **Run batch** button → progress bar → writes outputs → shows per-condition table + opens plot.
- Save/Load params (JSON); last-used params & channel mapping persisted with `QSettings`.

## Environment

- Develop in existing `siic-gui` conda env (has PyQt6, pyqtgraph, scikit-image, aicspylibczi, tifffile). Add `matplotlib`, `pandas` if missing.
- `pyproject.toml`: deps `numpy scipy scikit-image tifffile pandas matplotlib`; extras `gui = [pyqt6, pyqtgraph]`, `czi = [aicspylibczi]`.

## Build order (for Sonnet)

1. Scaffold repo: `git init`, `.gitignore` (`*.tif *.czi CF/ CM*/ results/`), pyproject, README stub.
2. Core `io` + `background` + `segment` + `measure` + `pipeline` with `Params` dataclass.
3. Tests on synthetic images (known bg, known disk cells → assert mask & mean_bgsub) + smoke test on the 12 sample TIFFs; eyeball 2–3 overlays.
4. `report.py` (CSVs + plot); CLI entry `fociquant-batch --params p.json files…` for headless use.
5. GUI: copy theme/worker from SIIC, build canvas + params panel + live preview, then batch panel.
6. Launch app, run full batch on sample data, check overlays look like the Fiji result; finish README (install + 5-step usage for the colleague).

## Open points / risks

- Threshold factor default (1.15 × bg) is a guess — tune on sample overlays in step 3; "CM feos" images may need different values (that's what the live preview is for).
- Bright debris/dead cells could inflate means → optional `max_object_intensity` / exclusion via clicking an object in preview (later, not v1).
- CZI scenes: verify channel order matches the TIFF exports when the user provides a raw CZI.
