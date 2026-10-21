"""End-to-end GUI check (offscreen): open an image, get a live mask, run a batch from tab 2."""
import os
import time

import numpy as np
import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["FOCIQUANT_TEST"] = "1"            # separate QSettings: never touch the user's saved parameters


def _wait(app, cond, timeout=60.0):
    t0 = time.time()
    while not cond():
        app.processEvents()
        time.sleep(0.02)
        if time.time() - t0 > timeout:
            return False
    return True


def test_tune_and_batch(tmp_path):
    import tifffile
    from PyQt6.QtWidgets import QApplication

    from test_core import synth

    img, _ = synth()
    d = tmp_path / "condA"
    d.mkdir()
    tifffile.imwrite(d / "a.tif", img.data, imagej=True, metadata={"axes": "CYX"})
    tifffile.imwrite(d / "b.tif", img.data, imagej=True, metadata={"axes": "CYX"})

    app = QApplication.instance() or QApplication([])
    from fociquant_gui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w._add_paths(sorted(d.glob("*.tif")))
    assert _wait(app, lambda: "mask" in w.status.text()), w.status.text()
    assert w._seg is not None and w._seg["mask"].any()

    w.mask_style.setCurrentText("Outline + Fill")             # display options do not break the view
    app.processEvents()
    assert w.canvas.mask_item.image is not None

    w.tabs.setCurrentIndex(1)
    b = w.batch
    assert b.table.rowCount() == 2
    out = tmp_path / "results"
    b.out_edit.setText(str(out))
    b.run()
    assert _wait(app, lambda: (out / "per_image.csv").exists() and b.status.text().startswith("Done")), b.status.text()
    assert b.tbl_img.rowCount() == 2 and (out / "summary_plot.png").exists()
    w.close()
