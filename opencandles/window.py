"""Tabbed application main window."""

from pyqtgraph.Qt import QtCore, QtWidgets

from .tabs.workspace_tabs import WorkspaceTabs
from .theme import BORDER, DRAW, FG


class MainWindow(QtWidgets.QMainWindow):
    modeSwitchRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenCandles")
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.WindowMinimizeButtonHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            | QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(640, 420)
        self.resize(1360, 880)

        self.workspace = WorkspaceTabs(self)
        self.setCentralWidget(self.workspace)

        self.mode_toggle = QtWidgets.QPushButton("Bar  |  Tabs ●")
        self.mode_toggle.setToolTip("Switch to compact bar mode")
        self.mode_toggle.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.mode_toggle.setStyleSheet(f"""
            QPushButton {{
                color: {FG};
                background: #172036;
                border: 1px solid {DRAW};
                border-radius: 12px;
                padding: 5px 12px;
                margin: 3px 8px 2px 4px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                color: #ffffff;
                background: #20305a;
                border-color: #4c7dff;
            }}
            QPushButton:pressed {{
                background: {BORDER};
            }}
        """)
        self.mode_toggle.clicked.connect(self.modeSwitchRequested)
        self.workspace.setCornerWidget(
            self.mode_toggle, QtCore.Qt.Corner.TopRightCorner
        )
