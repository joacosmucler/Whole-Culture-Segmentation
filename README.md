# Whole Culture Segmentation — FociQuant

[![tests](https://github.com/joacosmucler/Whole-Culture-Segmentation/actions/workflows/tests.yml/badge.svg)](https://github.com/joacosmucler/Whole-Culture-Segmentation/actions/workflows/tests.yml)
![platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-informational)
![license](https://img.shields.io/badge/license-MIT-green)

A desktop app to measure the **background-subtracted mean intensity of a foci channel inside cells** in widefield
images of whole cultures. You get one number per image, pooled over all cells; it does not measure single cells.

Cells are segmented from a membrane / cytoplasm stain by thresholding above the background. The pixels under that
mask are averaged in the foci channel, after subtracting the foci background measured outside the cells. You tune
the parameters on single images with a live preview, then run them on a whole experiment and get CSV tables and a
plot per condition.

- Input: multichannel **TIFF** (e.g. exported from Fiji) or raw Zeiss **CZI**, any number of conditions.
- Channel roles (foci / membrane / brightfield) are **read from the file metadata** when available.
- Everything runs locally; images never leave your computer.

---

## Install and run

You need **Python 3.10 or newer**. If you don't have it, install it from
[python.org/downloads](https://www.python.org/downloads/). On Windows, tick **"Add python.exe to PATH"** during
installation.

Get the code, either with `git clone https://github.com/joacosmucler/Whole-Culture-Segmentation.git` or with
**Code → Download ZIP** on GitHub (then unzip it).

### Option A — double-click launcher (no terminal needed)

| macOS | Windows |
|---|---|
| Double-click **`FociQuant-mac.command`** | Double-click **`FociQuant-windows.bat`** |

The first run creates a private Python environment in a `.venv` folder next to the launcher and installs everything
(a few minutes, needs internet). Later runs open the app directly. To reinstall from scratch, delete the `.venv`
folder.

> **macOS:** if Finder says the file "cannot be opened because it is from an unidentified developer", right-click it →
> **Open** → **Open** (only needed once). If you downloaded the ZIP and the file isn't executable, run
> `chmod +x FociQuant-mac.command` once in Terminal.
>
> **Windows:** if SmartScreen shows "Windows protected your PC", click **More info → Run anyway**.

### Option B — terminal (pip)

macOS / Linux:

```bash
cd Whole-Culture-Segmentation
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
fociquant
```

Windows (PowerShell or cmd):

```bat
cd Whole-Culture-Segmentation
py -3 -m venv .venv
.venv\Scripts\activate
pip install -e ".[all]"
fociquant
```

### Option C — conda

```bash
conda env create -f environment.yml
conda activate fociquant
fociquant
```

`[all]` installs the GUI (PyQt6, pyqtgraph) and CZI support (aicspylibczi). For the headless batch only:
`pip install -e .`

---

## Using the app

The window has two tabs. **Hover any parameter, or its name, to see what raising or lowering it does.**

### Tab 1 · Tune parameters

1. **Add files…** or **Add folder…** (searched recursively; TIFF and CZI). The **Condition** column defaults to the
   parent folder name and can be edited. Images with the same condition are grouped in the results.
2. **Channels.** For Zeiss files (including TIFFs exported from CZI with Fiji) the dropdowns show the real channel
   names, e.g. `0 · Rhoda (Rhodamine)`, and the roles are assigned automatically. Roles follow the **dye and
   contrast method, not the display colour**:
   - brightfield = Brightfield / Transmitted;
   - foci = Rhodamine, mCherry, Cy3, AF555–594…;
   - membrane = the other fluorescence channel (e.g. AF647, often displayed green).

   *Auto-detect from metadata* re-applies this. Files without metadata: choose the channels by hand.
3. Click an image and adjust the **Cell mask** until it follows the cells. The preview updates live, and the status
   line shows the backgrounds, the threshold, the mask coverage and the resulting mean. The main knob is
   **Threshold k × noise** (lower = bigger mask). A warning appears if the mask is empty or covers almost everything,
   and **Reset defaults** returns to a working setup.
   - **View:** Green, Red, Brightfield or Red + Green.
   - **Style:** mask as Outline, translucent Fill (adjustable opacity), or both.
   - **Preview grid…** applies the current parameters to all images, or to one condition, side by side with each
     mean. Click a tile to open that image.
4. Backgrounds can be overridden: method **roi** (drag the teal box onto empty glass, per image) or **fixed**.
5. **Save params… / Load params…** store the parameters as JSON. The last used parameters are remembered.

### Tab 2 · Batch & Plot

Shows the images (untick to exclude) and the exact parameters that will be used; parameters are edited in tab 1.
Choose an output folder and press **RUN BATCH**. The results appear as:

- **Plot**: box plot per condition. The plotted metric can be changed without recomputing.
- **By condition** and **Per image** tables.

**Load results folder…** reopens an earlier run.

---

## What is computed

For each image:

1. **Green background** `bg_g`. The default *floor* method takes the histogram peak of the darkest 20 % of pixels,
   which stays robust when cells cover most of the field. The background noise `σ` is measured on the low side of
   that peak.
2. **Cell mask.** The green channel is smoothed with a Gaussian of width *σ* and thresholded at
   `threshold = bg_g × factor + offset + k × σ`. Then:
   1. erosions remove halos and debris;
   2. closing joins fragments of the same cell;
   3. holes up to *Fill holes up to (px)* are filled (default 1000 px, about one nucleus), so nuclei inside a cell
      are included but empty gaps between cells stay background;
   4. objects smaller than *Min object* are removed.
3. **Red background** `bg_r`. The default *outside* method takes the median of the foci channel outside the mask,
   keeping a safety margin away from the mask.
4. **Result:** `mean_bgsub = mean(red inside mask) − bg_r`. The per-image table also reports the median, the raw
   mean, the integrated intensity, the mask area (px and µm², when the pixel size is known), the mask fraction and
   every background and threshold value used.

Cells are not split into individual objects, because splitting touching cells does not change a pooled mean.
Brightfield is shown for visual reference only.

## Outputs

Written to the chosen output folder:

| File | Content |
|---|---|
| `per_image.csv` | one row per image (and per scene for multi-scene CZI) with all metrics and backgrounds |
| `per_condition.csv` | n, mean ± SD / SEM of `mean_bgsub`, and the area-weighted mean per condition |
| `summary_plot.png` / `.svg` | box + points per condition (`summary_plot_<metric>.png` for other metrics) |
| `params.json` | the exact parameters used; load it in the GUI to reproduce the run |
| `masks/`, `overlays/` | binary mask and contour overlay per image, to audit every measurement |

## Headless batch (no GUI)

```bash
fociquant-batch path/to/folder_or_files ... --params params.json --out results
```

## Development

```bash
pip install -e ".[all,dev]"
pytest            # core tests + an offscreen GUI test
```

CI runs the tests on macOS, Windows and Linux, and checks that both double-click launchers install and start the
app.

```
fociquant/        UI-free core: io (TIFF/CZI + metadata), channels, background, segment, measure, pipeline, report, cli
fociquant_gui/    PyQt6 + pyqtgraph app: main_window (tab 1), batch_panel (tab 2), params_panel, canvas, grid_dialog
tests/            synthetic-image tests (no real data in the repo)
```

Notes:

- Multi-scene CZI: the GUI previews the first scene; the batch processes every scene.
- `fociquant_gui/theme.py` and `fociquant_gui/worker.py` are adapted from the author's SIIC project.

## License

[MIT](LICENSE) © 2026 Joaquin Smucler
