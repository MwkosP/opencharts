"""Inline SVG icons for workspace selection cards."""

from pyqtgraph.Qt import QtCore, QtGui


_SVG = {
    "chart": """
        <polyline points="4,25 10,18 16,21 23,9 30,13"
          fill="none" stroke="#2962ff" stroke-width="2.4"
          stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="4" y1="29" x2="30" y2="29" stroke="#8b949e" stroke-width="1.4"/>
    """,
    "options": """
        <circle cx="11" cy="17" r="7" fill="none" stroke="#2962ff" stroke-width="2"/>
        <circle cx="23" cy="17" r="7" fill="none" stroke="#c9d1d9" stroke-width="2"/>
        <path d="M8 17h6M11 14v6M20 17h6" stroke="#c9d1d9" stroke-width="1.8"
          stroke-linecap="round"/>
    """,
    "orderflow": """
        <path d="M4 8h17M4 14h24M4 20h20M4 26h13"
          stroke="#26a69a" stroke-width="3" stroke-linecap="round"/>
        <path d="M30 8h-6M30 14h-12M30 20h-9M30 26h-3"
          stroke="#ef5350" stroke-width="3" stroke-linecap="round"/>
    """,
    "fundamentals": """
        <path d="M5 28h24M8 28V14h5v14M15 28V9h5v19M22 28V17h5v11"
          fill="none" stroke="#c9d1d9" stroke-width="2" stroke-linejoin="round"/>
        <path d="M7 9l7-4 6 2 7-4" fill="none" stroke="#2962ff"
          stroke-width="2" stroke-linecap="round"/>
    """,
    "macro": """
        <circle cx="17" cy="17" r="13" fill="none" stroke="#2962ff" stroke-width="2"/>
        <path d="M4 17h26M17 4c5 5 5 21 0 26M17 4c-5 5-5 21 0 26M7 10h20M7 24h20"
          fill="none" stroke="#c9d1d9" stroke-width="1.4"/>
    """,
    "sentiment": """
        <path d="M5 23a13 13 0 0 1 24 0" fill="none" stroke="#c9d1d9"
          stroke-width="2.2" stroke-linecap="round"/>
        <path d="M17 20l8-8" stroke="#2962ff" stroke-width="2.4"
          stroke-linecap="round"/>
        <circle cx="17" cy="20" r="2.5" fill="#2962ff"/>
        <path d="M7 25h20" stroke="#8b949e" stroke-width="1.5"/>
    """,
    "news": """
        <path d="M7 4h17l4 4v22H7z" fill="none" stroke="#c9d1d9"
          stroke-width="2" stroke-linejoin="round"/>
        <path d="M24 4v5h5M11 14h13M11 19h13M11 24h9"
          fill="none" stroke="#2962ff" stroke-width="1.8" stroke-linecap="round"/>
    """,
}


def workspace_icon(page_type: str, size=36) -> QtGui.QIcon:
    """Render one of the workspace SVGs into a sharp Qt icon."""
    body = _SVG[page_type]
    svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="34" height="34"
             viewBox="0 0 34 34">{body}</svg>
    """.encode()
    pixmap = QtGui.QPixmap()
    if not pixmap.loadFromData(QtCore.QByteArray(svg), "SVG"):
        return QtGui.QIcon()
    return QtGui.QIcon(
        pixmap.scaled(
            size,
            size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
    )
