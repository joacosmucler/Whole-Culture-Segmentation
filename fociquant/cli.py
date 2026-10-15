"""Headless batch: fociquant-batch [--params p.json] [--out results] FILES_OR_FOLDERS..."""
from __future__ import annotations

import argparse
from pathlib import Path

from .io import find_images
from .pipeline import Params, run_batch


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--params")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    p = Params.from_json(Path(a.params).read_text()) if a.params else Params()
    files = []
    for i in a.inputs:
        files += find_images(i) if Path(i).is_dir() else [Path(i)]
    df = run_batch(files, p, a.out, progress=lambda m, pc: print(f"[{pc:3d}%] {m}"))
    print(df[["condition", "file", "bg_red", "mean_bgsub", "mask_fraction"]].to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
