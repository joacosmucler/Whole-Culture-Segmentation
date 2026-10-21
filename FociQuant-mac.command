#!/bin/bash
# FociQuant launcher for macOS — double-click it in Finder.
# First run: creates a private Python environment in .venv and installs FociQuant (a few minutes).
# Later runs: just starts the app.
cd "$(dirname "$0")" || exit 1

fail() { echo; echo "$1"; read -r -n1 -p "Press any key to close..."; exit 1; }

if [ ! -x .venv/bin/python ]; then
    PY=""
    for c in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$c" >/dev/null 2>&1 && \
           "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            PY="$c"; break
        fi
    done
    [ -n "$PY" ] || fail "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and double-click this file again."
    echo "First run: creating .venv with $PY and installing FociQuant (a few minutes)..."
    "$PY" -m venv .venv || fail "Could not create the Python environment."
    .venv/bin/python -m pip install --upgrade pip || fail "Installation failed (see messages above)."
    .venv/bin/python -m pip install -e ".[all]" || { rm -rf .venv; fail "Installation failed (see messages above)."; }
fi

.venv/bin/python -m fociquant_gui.app "$@"
