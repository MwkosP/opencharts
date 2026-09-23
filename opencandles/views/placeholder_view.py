"""Placeholder workspace views for planned OpenCandles features."""

from pyqtgraph.Qt import QtCore, QtWidgets

from opencandles.theme import BG, BORDER, FG, MUTED


class PlaceholderView(QtWidgets.QWidget):
    """Dark page shell that can later be replaced by a full feature view."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.setObjectName("placeholderView")
        self.setStyleSheet(f"""
            QWidget#placeholderView {{
                background: {BG};
                color: {FG};
            }}
            QLabel#pageTitle {{
                color: {FG};
                font-size: 22px;
                font-weight: 600;
            }}
            QLabel#pageStatus {{
                color: {MUTED};
                font-size: 11px;
                padding: 8px 14px;
                border: 1px solid {BORDER};
                border-radius: 5px;
                background: #151a22;
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        heading = QtWidgets.QLabel(title)
        heading.setObjectName("pageTitle")
        heading.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        status = QtWidgets.QLabel("Workspace page ready for implementation")
        status.setObjectName("pageStatus")
        status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status)
