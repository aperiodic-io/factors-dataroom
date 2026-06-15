"""Visual theme for the Aperiodic Factors factsheet PDFs — brand palette, fonts, rcParams."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager

# Brand palette — mirrors apps/web/styles/shadcn-ui.css (light theme).
INK = "#0A0A0A"        # neutral-950 — primary text & lines
SUB_INK = "#404040"    # neutral-700 — secondary body
MUTED = "#737373"      # neutral-500 — captions, axis labels
HAIR = "#E5E5E5"       # neutral-200 — hairline rules
HAIR_SOFT = "#F5F5F5"  # neutral-100 — empty / disabled cells
BG = "#FFFFFF"
PANEL = "#FAFAFA"      # neutral-50 — stat cards
ACCENT = "#6075B4"     # site accent (periwinkle)
ACCENT_SOFT = "#C8D2E8"  # periwinkle-200
ACCENT_TINT = "#EEF1F8"  # periwinkle-50
NEG = "#B91C1C"        # red-700 — drawdown / negative
NEG_TINT = "#FEF2F2"   # red-50
BENCH = "#A3A3A3"      # neutral-400 — benchmark / passive series

PAGE_W_IN = 8.27       # A4 portrait
PAGE_H_IN = 11.69
MARGIN_IN = 0.55

MINUS = "−"  # U+2212, digit-width minus for numeric formatting

_BUNDLED_FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

# Factsheet typography scale.
#
# Keep the PDF on one sans family and a deliberately small set of sizes so
# headings, labels, captions, buttons and chart text read as one system instead
# of a mix of display/body cuts and ad-hoc point sizes.
FONT_BODY = 8.0
FONT_BODY_SMALL = 7.0
FONT_CAPTION = 6.5
FONT_FINE = 5.8
FONT_SECTION = 7.5
FONT_TITLE = 22.0
FONT_TITLE_MIN = 16.0
FONT_SUBTITLE = 9.0
FONT_BRAND = 10.0
FONT_WEIGHT_REGULAR = "regular"
FONT_WEIGHT_MEDIUM = "medium"
FONT_WEIGHT_SEMIBOLD = "semibold"


def _refresh_font_cache_once() -> None:
    """Register the bundled Mona Sans .ttf/.otf cuts and rescan. Idempotent."""
    if getattr(_refresh_font_cache_once, "_done", False):
        return
    if _BUNDLED_FONT_DIR.is_dir():
        for path in _BUNDLED_FONT_DIR.iterdir():
            if path.suffix.lower() in {".ttf", ".otf"}:
                try:
                    font_manager.fontManager.addfont(str(path))
                except Exception:  # noqa: BLE001
                    pass
    try:
        font_manager._load_fontmanager(try_read_cache=False)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    _refresh_font_cache_once._done = True  # type: ignore[attr-defined]


def _pick_sans() -> tuple[str, str]:
    """(body, display) family names — prefer Mona Sans, then Inter, then DejaVu."""
    _refresh_font_cache_once()
    available = {f.name for f in font_manager.fontManager.ttflist}
    if "Mona Sans" in available:
        return "Mona Sans", "Mona Sans"
    if "Inter" in available:
        return "Inter", "Inter"
    return "DejaVu Sans", "DejaVu Sans"


def apply_theme() -> None:
    body, _display = _pick_sans()
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [body, "Inter", "DejaVu Sans"],
            "font.size": FONT_BODY,
            "font.weight": FONT_WEIGHT_REGULAR,
            "axes.titlesize": FONT_BODY,
            "axes.titleweight": FONT_WEIGHT_SEMIBOLD,
            "axes.labelsize": FONT_BODY_SMALL,
            "axes.labelcolor": SUB_INK,
            "axes.edgecolor": HAIR,
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": FONT_CAPTION,
            "ytick.labelsize": FONT_CAPTION,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "grid.color": HAIR,
            "grid.linewidth": 0.5,
            "grid.linestyle": "-",
            "legend.frameon": False,
            "legend.fontsize": FONT_BODY_SMALL,
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "savefig.facecolor": BG,
            "pdf.fonttype": 42,  # embed TrueType — text stays selectable
            "ps.fonttype": 42,
            "axes.unicode_minus": True,
        }
    )


def display_font() -> str:
    return _pick_sans()[1]


def new_page() -> "plt.Figure":
    """Blank A4 portrait figure with the theme applied."""
    apply_theme()
    fig = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN), dpi=150)
    return fig
