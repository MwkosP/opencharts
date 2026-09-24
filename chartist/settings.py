"""Shared, top-level application settings window."""

from pyqtgraph.Qt import QtCore, QtWidgets

from .theme import BORDER, DRAW, FG, MUTED


class SettingsWindow(QtWidgets.QDialog):
    """Independent settings window shared by every application shell."""

    modeChangeRequested = QtCore.pyqtSignal(str)
    alwaysOnTopChanged = QtCore.pyqtSignal(bool)
    fullScreenChanged = QtCore.pyqtSignal(bool)
    resetLauncherRequested = QtCore.pyqtSignal()
    closeApplicationRequested = QtCore.pyqtSignal()
    visibilityChanged = QtCore.pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chartist Settings")
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.WindowMinimizeButtonHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            | QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        self.setMinimumSize(820, 600)
        self.resize(960, 680)
        self.setSizeGripEnabled(True)
        self._buildUi()

    def _buildUi(self):
        self.setStyleSheet(f"""
            QDialog {{
                color: {FG};
                background: #111318;
            }}
            QLabel#title {{
                color: #ffffff;
                font-size: 18px;
                font-weight: 700;
            }}
            QLabel#subtitle, QLabel#description {{
                color: {MUTED};
                font-size: 9pt;
            }}
            QLabel#section {{
                color: #ffffff;
                font-size: 10pt;
                font-weight: 700;
                padding-top: 8px;
            }}
            QComboBox, QPushButton {{
                color: {FG};
                background: #181b21;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 9px 12px;
            }}
            QComboBox:hover, QPushButton:hover {{
                color: #ffffff;
                background: #242830;
                border-color: #30363d;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                color: {FG};
                background: #181b21;
                border: 1px solid {BORDER};
                selection-background-color: {DRAW};
            }}
            QCheckBox {{
                color: {FG};
                spacing: 10px;
                padding: 7px 2px;
            }}
            QCheckBox:disabled, QLabel:disabled {{
                color: #555b66;
            }}
            QPushButton#danger {{
                color: #ff8d87;
                text-align: left;
            }}
            QPushButton#danger:hover {{
                color: #ffffff;
                background: #c42b1c;
                border-color: #c42b1c;
            }}
            QFrame#separator {{
                background: {BORDER};
                max-height: 1px;
            }}
        """)

        content = QtWidgets.QVBoxLayout(self)
        content.setContentsMargins(28, 24, 28, 24)
        content.setSpacing(8)

        title = QtWidgets.QLabel("Settings")
        title.setObjectName("title")
        content.addWidget(title)
        subtitle = QtWidgets.QLabel("System and application preferences")
        subtitle.setObjectName("subtitle")
        content.addWidget(subtitle)

        content.addWidget(self._sectionLabel("Interface"))
        mode_row = QtWidgets.QHBoxLayout()
        mode_text = QtWidgets.QVBoxLayout()
        mode_text.addWidget(QtWidgets.QLabel("Workspace mode"))
        mode_description = QtWidgets.QLabel(
            "Choose the compact launcher or the tabbed workspace."
        )
        mode_description.setObjectName("description")
        mode_text.addWidget(mode_description)
        mode_row.addLayout(mode_text, 1)
        self.modeSelector = QtWidgets.QComboBox()
        self.modeSelector.addItem("Compact launcher", "compact")
        self.modeSelector.addItem("Tabbed workspace", "tabbed")
        self.modeSelector.setMinimumWidth(210)
        self.modeSelector.currentIndexChanged.connect(self._modeSelected)
        mode_row.addWidget(self.modeSelector)
        content.addLayout(mode_row)

        content.addWidget(self._separator())
        content.addWidget(self._sectionLabel("Window"))
        self.alwaysOnTop = QtWidgets.QCheckBox(
            "Keep the compact launcher above other windows"
        )
        self.alwaysOnTop.toggled.connect(self.alwaysOnTopChanged.emit)
        content.addWidget(self.alwaysOnTop)
        self.fullScreen = QtWidgets.QCheckBox(
            "Use full screen in the tabbed workspace"
        )
        self.fullScreen.toggled.connect(self.fullScreenChanged.emit)
        content.addWidget(self.fullScreen)
        self.resetLauncher = QtWidgets.QPushButton(
            "Reset compact launcher position"
        )
        self.resetLauncher.clicked.connect(
            lambda: self.resetLauncherRequested.emit()
        )
        content.addWidget(self.resetLauncher)

        content.addStretch()
        content.addWidget(self._separator())
        content.addWidget(self._sectionLabel("Application"))
        close_app = QtWidgets.QPushButton("Close Chartist")
        close_app.setObjectName("danger")
        close_app.clicked.connect(
            lambda: self.closeApplicationRequested.emit()
        )
        content.addWidget(close_app)

    @staticmethod
    def _sectionLabel(text):
        label = QtWidgets.QLabel(text)
        label.setObjectName("section")
        return label

    @staticmethod
    def _separator():
        separator = QtWidgets.QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        return separator

    def _modeSelected(self, index):
        mode = self.modeSelector.itemData(index)
        if mode:
            self.modeChangeRequested.emit(mode)

    def setContext(self, mode, always_on_top=False, full_screen=False):
        mode_index = self.modeSelector.findData(mode)
        with QtCore.QSignalBlocker(self.modeSelector):
            self.modeSelector.setCurrentIndex(mode_index)
        with QtCore.QSignalBlocker(self.alwaysOnTop):
            self.alwaysOnTop.setChecked(bool(always_on_top))
        with QtCore.QSignalBlocker(self.fullScreen):
            self.fullScreen.setChecked(bool(full_screen))
        compact = mode == "compact"
        self.alwaysOnTop.setEnabled(compact)
        self.resetLauncher.setEnabled(compact)
        self.fullScreen.setEnabled(not compact)

    def showOnScreen(self, screen):
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        self._centerOn(screen)
        self.show()
        self.raise_()
        self.activateWindow()
        QtCore.QTimer.singleShot(0, lambda: self._centerOn(screen))

    def _centerOn(self, screen):
        area = screen.availableGeometry()
        size = self.frameGeometry().size()
        if size.isEmpty():
            size = self.size()
        self.move(
            area.left() + (area.width() - size.width()) // 2,
            area.top() + (area.height() - size.height()) // 2,
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.visibilityChanged.emit(True)

    def hideEvent(self, event):
        self.visibilityChanged.emit(False)
        super().hideEvent(event)


__all__ = ["SettingsWindow"]
