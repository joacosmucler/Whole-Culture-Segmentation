# FociQuant

Measure the **background-subtracted mean intensity of the foci (red) channel inside cells** — one number per
image, not per cell. Cells are segmented from the (noisy-membrane) **green** channel, optionally refined with
**brightfield**. Includes a PyQt6 GUI with live preview and a batch runner.

## Install

```bash
pip install -e ".[gui,czi]"      # czi extra only needed for raw .czi files
fociquant                        # launches the GUI   (or: python -m fociquant_gui.app)
```

## Using the GUI (5 steps)

1. **Add files / Add folder** (TIFF or CZI). The *Condition* column defaults to the parent folder name — edit it freely.
2. Check **Channels** (default: 0 = red foci, 1 = brightfield, 2 = green membrane).
3. Select an image and tune the **Cell mask** until the yellow contour follows the cells
   (the status line shows backgrounds, threshold, mask % and the resulting mean live).
   Main knob: **Threshold k × noise** (lower = larger mask). Use *View → Red + Green* to sanity check.
4. Optional: tick **Use brightfield** (`and` removes green junk, `or` recovers dim cells).
   Backgrounds can be overridden: choose method **roi** and drag the teal box over an empty area, or **fixed**.
5. Pick an output folder and press **RUN BATCH**.

## What is computed

1. Green background `bg_g` (default *floor*: peak of the darkest 20 % of pixels; robust when cells fill the field) and its noise σ.
2. Mask = Gaussian-smoothed green > `bg_g·factor + offset + k·σ` → erosions → closing → fill holes → drop small objects
   (→ optional brightfield texture mask, AND/OR).
3. Red background `bg_r` = median of red outside the mask (+ margin) by default.
4. `mean_bgsub = mean(red[mask]) − bg_r`. (Watershed is not needed: splitting touching cells does not change the pooled mean.)

## Outputs (`<output folder>/`)

`per_image.csv`, `per_condition.csv`, `summary_plot.png/.svg`, `params.json` (reload in the GUI), `masks/`, `overlays/`.

Headless: `fociquant-batch FOLDER_OR_FILES... --params params.json --out results`.

## Notes

- Multi-scene CZI: the GUI previews scene 0; the batch processes all scenes.
- Tests: `pytest tests`.
- `fociquant_gui/theme.py` and `worker.py` are copied from the SIIC project.
