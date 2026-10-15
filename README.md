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
2. **Channels** are read from the file metadata (Zeiss/CZI info, also kept in Fiji-exported TIFFs): the dropdowns list
   the real channel names (e.g. `0 · Rhoda (Rhodamine)`) and the roles are assigned automatically when the first image
   opens. *Auto-detect from metadata* re-applies it. Roles follow **dye / contrast method, not display colour**
   (brightfield = Brightfield/Transmitted; foci = Rhodamine/mCherry/Cy3/AF555-594…; segmentation channel = the other
   fluorescence channel, e.g. AF647 shown in green). Files without metadata: pick the channels by hand.
3. Select an image and tune the **Cell mask** until the yellow contour follows the cells
   (the status line shows backgrounds, threshold, mask % and the resulting mean live).
   The mask can be shown as **Outline**, **Fill** (translucent solid, adjustable opacity) or both (Style / Opacity above the image).
   Main knob: **Threshold k × noise** (lower = larger mask). Use *View → Red + Green* to sanity check.
   **Preview grid…** (top right) applies the current parameters to all images, or one condition, side by side with the
   mean of each; click a tile to open it in the main view.
4. Backgrounds can be overridden: choose method **roi** and drag the teal box over an empty area, or **fixed**.
   **Hover any parameter (or its name) for a short explanation of what raising or lowering it does.**
5. Pick an output folder and press **RUN BATCH**.

## What is computed

1. Green background `bg_g` (default *floor*: peak of the darkest 20 % of pixels; robust when cells fill the field) and its noise σ.
2. Mask = Gaussian-smoothed green > `bg_g·factor + offset + k·σ` → erosions → closing → fill small holes → drop small objects
   Holes are filled only up to **Fill holes up to (px)** (default 1000, about one nucleus): nuclei inside a cell are
   filled, but empty gaps between cells stay background.
3. Red background `bg_r` = median of red outside the mask (+ margin) by default.
4. `mean_bgsub = mean(red[mask]) − bg_r`. (Watershed is not needed: splitting touching cells does not change the pooled mean.)

## Outputs (`<output folder>/`)

`per_image.csv`, `per_condition.csv`, `summary_plot.png/.svg`, `params.json` (reload in the GUI), `masks/`, `overlays/`.

Headless: `fociquant-batch FOLDER_OR_FILES... --params params.json --out results`.

## Notes

- Brightfield is displayed for reference only (View → Brightfield). A texture-based brightfield mask was tried and
  removed: with DIC-like brightfield the local texture does not follow the cells.
- Multi-scene CZI: the GUI previews scene 0; the batch processes all scenes.
- Tests: `pytest tests`.
- `fociquant_gui/theme.py` and `worker.py` are copied from the SIIC project.
