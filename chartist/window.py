"""Tabbed application main window."""

from pyqtgraph.Qt import QtCore, QtWidgets

from .settings import SettingsWindow
from .tabs.workspace_tabs import WorkspaceTabs
from .theme import DRAW, FG
from .ui.icons import iconSettings, makeIcon


class MainWindow(QtWidgets.QMainWindow):
    modeSwitchRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None, settings_window: SettingsWindow | None = None):
        super().__init__(parent)
        self.settingsWindow = settings_window or SettingsWindow()
        self.setWindowTitle("Chartist")
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

        self.optionsButton = QtWidgets.QToolButton()
        self.optionsButton.setToolTip("Settings")
        self.optionsButton.setIcon(makeIcon(iconSettings))
        self.optionsButton.setIconSize(QtCore.QSize(17, 17))
        self.optionsButton.setFixedSize(28, 28)
        self.optionsButton.setCheckable(True)
        self.optionsButton.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.optionsButton.clicked.connect(self._toggleSettingsMenu)
        self.settingsWindow.visibilityChanged.connect(
            self._setSettingsButtonActive
        )
        self.optionsButton.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 0;
            }
            QToolButton:hover, QToolButton:pressed {
                background: transparent;
            }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """)
        self.workspace.setCornerWidget(
            self.optionsButton, QtCore.Qt.Corner.TopRightCorner
        )

    def showSettingsMenu(self):
        self._setSettingsButtonActive(True)
        self.settingsWindow.setContext(
            "tabbed", full_screen=self.isFullScreen()
        )
        self.settingsWindow.showOnScreen(self.screen())

    def _setSettingsButtonActive(self, active):
        with QtCore.QSignalBlocker(self.optionsButton):
            self.optionsButton.setChecked(active)
        self.optionsButton.setIcon(
            makeIcon(iconSettings, DRAW if active else FG)
        )

    def _toggleSettingsMenu(self, active):
        if active:
            self.showSettingsMenu()
        else:
            self.settingsWindow.close()

    def _setFullScreen(self, enabled):
        if enabled:
            self.showFullScreen()
        else:
            self.showNormal()
