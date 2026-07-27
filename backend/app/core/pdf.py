"""Shared font registration for every PDF the service renders in-process.

DejaVu Sans is vendored because reportlab's built-in fonts are latin-1 only:
material and part names can be Cyrillic, statement copy carries the Uzbek
apostrophe (U+02BB), and the cutting map draws a U+21BB rotation marker.

The pair lives here rather than inside one module because two modules now draw
documents (cutting maps, finance akt sverka) and neither owns the typeface.
"""

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONTS_DIR = Path(__file__).parent / "fonts"
FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"


def register_pdf_fonts() -> None:
    """Register the vendored font pair once per process. Safe to call per render."""

    registered = pdfmetrics.getRegisteredFontNames()
    if FONT_REGULAR not in registered:
        pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONTS_DIR / "DejaVuSans.ttf")))
    if FONT_BOLD not in registered:
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONTS_DIR / "DejaVuSans-Bold.ttf")))
