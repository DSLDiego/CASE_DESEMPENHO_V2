"""Temas light/dark (GUI) + paletas dos graficos Qt. Compacto: fontes e botoes reduzidos."""
from __future__ import annotations

BASE_FONT = "font-size: 11px;"

LIGHT_QSS = BASE_FONT + """
QWidget { background: #f4f4f4; color: #222; }
QPushButton { padding: 2px 8px; }
QTableWidget { background: #fff; gridline-color: #ccc; }
QHeaderView::section { background: #e8e8e8; padding: 2px; }
QToolBox::tab { background: #e0e0e0; padding: 2px; }
QTextEdit { background: #fff; }
"""

DARK_QSS = BASE_FONT + """
QWidget { background: #2b2b2b; color: #e0e0e0; }
QPushButton { padding: 2px 8px; background: #3c3c3c; border: 1px solid #555; }
QPushButton:hover { background: #4a4a4a; }
QTableWidget { background: #333; gridline-color: #555; }
QHeaderView::section { background: #3c3c3c; padding: 2px; }
QToolBox::tab { background: #3c3c3c; padding: 2px; }
QTextEdit, QComboBox, QSpinBox { background: #333; }
"""

# pyqtgraph: (background, foreground, palette)
CHART_THEMES = {
    "light": ("w", "k", ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]),
    "dark": ("#2b2b2b", "#e0e0e0", ["#5aa9e6", "#ffb35c", "#7fc97f", "#ef6f6f"]),
}


def apply_theme(widget, name: str) -> str:
    name = "dark" if name == "dark" else "light"
    widget.setStyleSheet(DARK_QSS if name == "dark" else LIGHT_QSS)
    try:
        import pyqtgraph as pg
        bg, fg, _ = CHART_THEMES[name]
        pg.setConfigOptions(background=bg, foreground=fg)
    except Exception:
        pass
    return name
