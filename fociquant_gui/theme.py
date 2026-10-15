# Copied from SIIC (siic_gui).
"""Visual theme for SIIC — Nothing-inspired analog/monochrome dark UI.

Design notes
------------
Nothing's design language: pure near-black surface, a single red accent,
mono/dot-matrix typography, hairline borders, generous spacing, no gradients,
no rounded corners beyond 2px. We translate that to a Qt stylesheet that
covers every widget class used by the SIIC panels.

Image rendering (pyqtgraph ViewBoxes) is intentionally left untouched so the
scientific data still renders on a neutral background.
"""
from __future__ import annotations

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

# ── palette ───────────────────────────────────────────────────────────────
BG          = "#0A0A0A"   # window background (near-black, not pure #000)
SURFACE     = "#121212"   # panels, inputs
SURFACE_ALT = "#1E1E1E"   # hover / alt-row
BORDER      = "#2E2E2E"   # hairline border
BORDER_HI   = "#444444"   # focused border
TEXT        = "#F0F0F0"   # primary text (slightly whiter)
TEXT_DIM    = "#909090"   # secondary
TEXT_MUTED  = "#606060"   # tertiary / section headers
ACCENT      = "#1FA99F"   # cobalt green / teal — used sparingly
ACCENT_DIM  = "#126660"   # pressed / disabled accent


def _pick_mono_family() -> str:
    """Pick the best available monospace font for an analog/dot-matrix feel."""
    preferred = [
        "Ndot 55",       # actual Nothing font if user installed it
        "JetBrains Mono",
        "IBM Plex Mono",
        "SF Mono",
        "Menlo",
        "Monaco",
        "Consolas",
        "Courier New",
    ]
    families = set(QFontDatabase.families())
    for name in preferred:
        if name in families:
            return name
    return "Monospace"


def apply_theme(app: QApplication) -> None:
    """Apply the SIIC theme to a running QApplication."""
    mono = _pick_mono_family()

    # base application font — monospace, slightly tracked
    base = QFont(mono, 10)
    base.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    base.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 102)
    app.setFont(base)

    qss = f"""
    /* ── window & base ──────────────────────────────────────────────── */
    QMainWindow, QWidget {{
        background: {BG};
        color: {TEXT};
        font-family: "{mono}";
        font-size: 12px;
    }}

    QToolTip {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER_HI};
        padding: 4px 6px;
    }}

    /* ── left nav (QListWidget) ─────────────────────────────────────── */
    QListWidget {{
        background: {BG};
        border: none;
        border-right: 1px solid {BORDER};
        outline: 0;
        padding: 14px 0;
        font-size: 12px;
    }}
    QListWidget::item {{
        padding: 9px 18px;
        border-left: 2px solid transparent;
        color: {TEXT_DIM};
    }}
    QListWidget::item:hover {{
        color: {TEXT};
        background: {SURFACE};
    }}
    QListWidget::item:selected {{
        color: {TEXT};
        background: {SURFACE};
        border-left: 2px solid {ACCENT};
    }}
    /* section headers (disabled items) — small, muted, tracked caps */
    QListWidget::item:disabled {{
        color: {TEXT_MUTED};
        font-size: 10px;
        padding-top: 18px;
        padding-bottom: 6px;
        background: transparent;
        border-left: 2px solid transparent;
    }}

    /* ── group boxes ────────────────────────────────────────────────── */
    QGroupBox {{
        background: transparent;
        border: 1px solid {BORDER};
        border-radius: 0px;
        margin-top: 18px;
        padding: 12px 12px 10px 12px;
        font-size: 10px;
        color: {TEXT_DIM};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 6px;
        background: {BG};
        color: {TEXT_DIM};
        letter-spacing: 1px;
    }}

    /* ── labels ────────────────────────────────────────────────────── */
    QLabel {{
        background: transparent;
        color: {TEXT};
    }}
    QLabel[role="dim"] {{ color: {TEXT_DIM}; }}
    QLabel[role="muted"] {{ color: {TEXT_MUTED}; font-size: 10px; }}

    /* ── buttons ───────────────────────────────────────────────────── */
    QPushButton {{
        background-color: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 0px;
        padding: 7px 16px;
        min-height: 22px;
    }}
    QPushButton:hover {{
        background-color: {SURFACE_ALT};
        border-color: {BORDER_HI};
    }}
    QPushButton:pressed {{
        background-color: {BG};
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    QPushButton:disabled {{
        color: {TEXT_MUTED};
        background-color: {SURFACE};
        border-color: {BORDER};
    }}
    QPushButton:default, QPushButton[role="primary"] {{
        background-color: {ACCENT};
        color: {BG};
        border: 1px solid {ACCENT};
    }}
    QPushButton[role="primary"]:hover {{
        background-color: #28C4BA;
        border-color: #28C4BA;
    }}
    QPushButton[role="primary"]:pressed {{
        background-color: {ACCENT_DIM};
        border-color: {ACCENT_DIM};
    }}
    QPushButton:checked {{
        background-color: {SURFACE_ALT};
        border-color: {ACCENT};
        color: {ACCENT};
    }}

    /* ── inputs ────────────────────────────────────────────────────── */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 0px;
        padding: 5px 8px;
        selection-background-color: {ACCENT};
        selection-color: {BG};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {ACCENT};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
        color: {TEXT_MUTED};
        background: {SURFACE};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 18px;
    }}
    QComboBox QAbstractItemView {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER_HI};
        selection-background-color: {SURFACE_ALT};
        selection-color: {ACCENT};
        outline: 0;
    }}

    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background: {SURFACE_ALT};
        border: none;
        width: 14px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
        background: {BORDER};
    }}

    /* ── checkboxes ────────────────────────────────────────────────── */
    QCheckBox {{
        spacing: 8px;
        color: {TEXT};
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {BORDER_HI};
        background: {SURFACE};
    }}
    QCheckBox::indicator:hover {{
        border-color: {TEXT_DIM};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}

    /* ── sliders ───────────────────────────────────────────────────── */
    QSlider::groove:horizontal {{
        height: 2px;
        background: {BORDER};
    }}
    QSlider::handle:horizontal {{
        width: 12px;
        height: 12px;
        margin: -6px 0;
        background: {TEXT};
        border: none;
    }}
    QSlider::handle:horizontal:hover {{ background: {ACCENT}; }}
    QSlider::sub-page:horizontal {{ background: {ACCENT}; }}

    QSlider::groove:vertical {{ width: 2px; background: {BORDER}; }}
    QSlider::handle:vertical {{
        height: 12px; width: 12px; margin: 0 -6px;
        background: {TEXT}; border: none;
    }}
    QSlider::handle:vertical:hover {{ background: {ACCENT}; }}

    /* ── tabs ──────────────────────────────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        top: -1px;
        background: {BG};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_DIM};
        padding: 8px 18px;
        border: 1px solid transparent;
        border-bottom: 1px solid {BORDER};
        font-size: 10px;
        letter-spacing: 1px;
    }}
    QTabBar::tab:hover {{ color: {TEXT}; }}
    QTabBar::tab:selected {{
        color: {TEXT};
        border: 1px solid {BORDER};
        border-bottom: 1px solid {BG};
        background: {BG};
    }}

    /* ── splitter handles ──────────────────────────────────────────── */
    QSplitter::handle {{
        background: {BORDER};
    }}
    QSplitter::handle:horizontal {{ width: 3px; }}
    QSplitter::handle:vertical   {{ height: 3px; }}
    QSplitter::handle:hover {{ background: {ACCENT}; }}

    /* ── scrollbars (thin, analog) ─────────────────────────────────── */
    QScrollBar:vertical {{
        background: {BG};
        width: 10px;
        margin: 0;
        border-left: 1px solid {BORDER};
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_HI};
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {TEXT_DIM}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

    QScrollBar:horizontal {{
        background: {BG};
        height: 10px;
        margin: 0;
        border-top: 1px solid {BORDER};
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER_HI};
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {TEXT_DIM}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ── tables / lists used inside panels ─────────────────────────── */
    QTableWidget {{
        background: {SURFACE};
        alternate-background-color: {SURFACE_ALT};
        gridline-color: {BORDER};
        border: 1px solid {BORDER};
        color: {TEXT};
        selection-background-color: {ACCENT_DIM};
        selection-color: {TEXT};
    }}
    QHeaderView::section {{
        background: {BG};
        color: {TEXT_MUTED};
        border: none;
        border-bottom: 1px solid {BORDER};
        padding: 6px 8px;
        font-size: 10px;
        letter-spacing: 1px;
    }}

    /* ── status bar ────────────────────────────────────────────────── */
    QStatusBar {{
        background: {BG};
        border-top: 1px solid {BORDER};
        color: {TEXT_DIM};
        font-size: 10px;
        letter-spacing: 1px;
    }}
    QStatusBar::item {{ border: none; }}

    QProgressBar {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 0px;
        text-align: center;
        color: {TEXT_DIM};
        font-size: 10px;
        max-height: 10px;
    }}
    QProgressBar::chunk {{
        background: {ACCENT};
    }}

    /* ── menus & dialogs ───────────────────────────────────────────── */
    QMenu {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER_HI};
        padding: 4px 0;
    }}
    QMenu::item {{ padding: 6px 22px; }}
    QMenu::item:selected {{ background: {SURFACE_ALT}; color: {ACCENT}; }}

    QMessageBox, QFileDialog {{ background: {BG}; }}
    """

    app.setStyleSheet(qss)
