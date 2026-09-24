"""Shared colors and Qt stylesheets."""

BG = "#0e1117"
FG = "#c9d1d9"
MUTED = "#8b949e"
UP = "#26a69a"
DOWN = "#ef5350"
CANDLE_UP = "#f5f7ff"
CANDLE_DOWN = "#7c3aed"
DRAW = "#2962ff"            # drawn lines + active buttons
CROSS = "#434651"           # crosshair tags
BORDER = "#21262d"

PANE_CSS = f"""
QWidget#paneHead {{ background: {BG}; }}
QWidget#indicatorLegend {{ background: {BG}; }}
QWidget#indicatorChip {{
    background: #151a22; border: 1px solid {BORDER}; border-radius: 3px;
    padding-left: 5px;
}}
QLabel {{ font-size: 9pt; }}
QToolButton#close {{ color: {MUTED}; background: transparent; border: none;
                     padding: 0 5px; font-size: 10pt; }}
QToolButton#close:hover {{ color: #ffffff; background: #30363d; border-radius: 3px; }}
"""

BAR_CSS = f"""
QWidget#topbar {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}
QPushButton, QToolButton#menu, QToolButton#sidebarToggle {{
    background: transparent; color: {FG}; border: none; border-radius: 4px;
    padding: 4px 9px; font-size: 9.5pt;
}}
QPushButton:hover, QToolButton#menu:hover, QToolButton#sidebarToggle:hover {{
    background: #1c2128;
}}
QPushButton:checked {{ color: {DRAW}; font-weight: bold; }}
QToolButton#sidebarToggle:checked {{ background: #1f2a44; }}
QToolButton#menu::menu-indicator {{ image: none; }}
QFrame#vsep {{ background: #30363d; max-width: 1px; margin: 6px 4px; }}
QPushButton#symbol {{
    font-weight: bold; font-size: 10.5pt; padding: 4px 8px;
}}
"""

BOTTOM_CSS = f"""
QWidget#bottombar {{ background: {BG}; border-top: 1px solid {BORDER}; }}
QPushButton {{
    background: transparent; color: {FG};
    border: 1px solid #30363d; border-radius: 4px;
    padding: 3px 10px; font-size: 9pt;
}}
QPushButton:hover   {{ background: #1c2128; }}
QPushButton:checked {{ background: {DRAW}; border-color: {DRAW}; color: white; }}
"""

MENU_CSS = f"""
QMenu {{ background: #161b22; color: {FG}; border: 1px solid #30363d; padding: 4px; }}
QMenu::item {{ padding: 5px 24px 5px 12px; border-radius: 3px; }}
QMenu::item:selected {{ background: {DRAW}; color: white; }}
QMenu::section {{ color: {MUTED}; padding: 6px 10px 2px 10px; font-size: 8.5pt; }}
QMenu::separator {{ height: 1px; background: #30363d; margin: 4px 6px; }}
"""

SIDEBAR_CSS = f"""
QWidget#sidebar {{ background: {BG}; border-right: 1px solid {BORDER}; }}
QToolButton {{ background: transparent; border: none; border-radius: 5px; }}
QToolButton:hover   {{ background: #1c2128; }}
QToolButton:checked {{ background: #1f2a44; }}
QWidget#toolGroup:hover {{ background: #1c2128; border-radius: 5px; }}
QWidget#toolGroup QToolButton:hover {{ background: transparent; }}
QToolButton#toolGroupArrow {{
    color: {MUTED}; background: transparent; border: none;
    padding: 0; font-size: 13px;
}}
QToolButton#toolGroupArrow:hover {{ color: #ffffff; background: #252b35; }}
QToolButton#toolGroupArrow::menu-indicator {{ image: none; }}
QFrame#sep {{ background: #30363d; max-height: 1px; margin: 4px 8px; }}
"""

SPLITTER_CSS = f"""
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:hover {{ background: {DRAW}; }}
"""


