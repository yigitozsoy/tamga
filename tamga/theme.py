"""tamga'nın kendi görünümü: ailenin paletleri, stil sayfası, logo boyama."""
import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap

from .config import prefs
from .palette import ACCENTS, PALETTES, VARIANTS, _LEGACY


def accent():
    v = str(prefs.get("accent", "gray") or "gray")
    if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        return v.lower()
    return ACCENTS.get(v, ACCENTS["gray"])


def current_variant():
    v = prefs.get("theme", "amoled")
    v = _LEGACY.get(v, v)
    return v if v in VARIANTS else "amoled"


def is_dark():
    return VARIANTS[current_variant()][2] == "dark"


def variant_palette(v):
    d = dict(PALETTES[VARIANTS[v][2]])
    d.update(VARIANTS[v][3])
    return d


def pal():
    return variant_palette(current_variant())


def color(role):
    if role == "accent":
        return accent()
    return pal().get(role, role)


def qcolor(c):
    """#hex ya da rgba(...) metnini QColor'a çevirir."""
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)", c)
    if m:
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return QColor(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(round(a * 255)))
    return QColor(c)


def tinted(path, height, dpr=1.0, col=None):
    """Logoyu (saydam PNG) verilen renge boyar."""
    pm = QPixmap(path)
    if pm.isNull():
        return pm
    pm = pm.scaledToHeight(int(height * dpr), Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(pm.size())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, pm)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), qcolor(col or color("text")))
    p.end()
    out.setDevicePixelRatio(dpr)
    return out


def stylesheet():
    c = pal()
    acc = accent()
    return f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI"; font-size: 10pt; color: {c['text']}; }}
QMainWindow, #Root {{ background: {c['bg']}; }}
QToolTip {{ background: rgba(97,97,97,0.92); color: #ffffff; border: none; padding: 5px 8px; border-radius: 4px; }}
QScrollArea, #Scroll > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['scroll']}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
#Title {{ font-size: 17pt; font-weight: 600; }}
#Sub, #Muted {{ color: {c['text2']}; }}
#Section {{ font-size: 12pt; font-weight: 600; }}
#Card {{ background: {c['card']}; border: 1px solid {c['divider']}; border-radius: 12px; }}
#AppName {{ font-size: 12pt; font-weight: 600; }}
#Status {{ color: {c['text2']}; }}
#Status[state="new"] {{ color: {c['text']}; font-weight: 600; }}
#Status[state="err"] {{ color: {c['text3']}; }}
QPushButton {{ background: {c['surface']}; border: none; border-radius: 17px; padding: 0 16px;
              min-height: 34px; font-weight: 600; }}
QPushButton:hover {{ background: {c['surface_hover']}; }}
QPushButton:disabled {{ color: {c['text3']}; }}
QPushButton#Primary {{ background: {c['button_bg']}; color: {c['button_fg']}; }}
QPushButton#Primary:hover {{ background: {'#d9d9d9' if is_dark() else '#272727'}; }}
QPushButton#Link {{ background: transparent; color: {c['text2']}; padding: 0 8px; font-weight: 400; }}
QPushButton#Link:hover {{ color: {c['text']}; }}
QPushButton#Chip {{ border-radius: 8px; min-height: 32px; padding: 0 14px; font-weight: 500; }}
QPushButton#Chip:checked {{ background: {c['chip_active_bg']}; color: {c['chip_active_fg']}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 2px solid {c['text3']}; }}
QCheckBox::indicator:checked {{ background: {acc}; border-color: {acc}; }}
QProgressBar {{ background: {c['surface']}; border: none; border-radius: 2px; max-height: 4px; }}
QProgressBar::chunk {{ background: {acc}; border-radius: 2px; }}
"""
