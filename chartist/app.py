"""Chartist application bootstrap."""

import sys
from pathlib import Path

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .config import LOADING_SCREEN
from .launcher import LauncherWindow, StandalonePageWindow
from .settings import SettingsWindow
from .splash import StartupSplash
from .window import MainWindow


def _applicationIcon():
    source = QtGui.QPixmap(
        str(Path(__file__).with_name("assets") / "default_profile.jpg")
    )
    canvas = QtGui.QPixmap(512, 512)
    canvas.fill(QtGui.QColor("#020306"))
    if not source.isNull():
        scaled = source.scaled(
            480,
            480,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        painter = QtGui.QPainter(canvas)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(
            (canvas.width() - scaled.width()) // 2,
            (canvas.height() - scaled.height()) // 2,
            scaled,
        )
        painter.end()
    return QtGui.QIcon(canvas)


def createApplication(argv=None) -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv if argv is None else argv)
        app.setApplicationName("Chartist")
        app.setWindowIcon(_applicationIcon())
    return app


class ApplicationController(QtCore.QObject):
    """Switches between compact-bar and tabbed shells without losing state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsWindow()
        self.launcher = LauncherWindow(settings_window=self.settings)
        self.workspace = None
        self.launcher.modeSwitchRequested.connect(self.showTabsMode)
        self.settings.modeChangeRequested.connect(self.setMode)
        self.settings.alwaysOnTopChanged.connect(self.launcher.setPinned)
        self.settings.fullScreenChanged.connect(self.setFullScreen)
        self.settings.resetLauncherRequested.connect(
            self.launcher.resetPosition
        )
        self.settings.closeApplicationRequested.connect(
            self.closeApplication
        )

    def start(self):
        self.launcher.show()

    def showTabsMode(self):
        if self.workspace is None:
            self.workspace = MainWindow(settings_window=self.settings)
            self.workspace.modeSwitchRequested.connect(self.showBarMode)
        for window in list(self.launcher.openWindows):
            if not isinstance(window, StandalonePageWindow):
                continue
            page = window.takePage()
            page_type = window.pageType
            title = window.pageTitle
            self.launcher._forgetWindow(window)
            window.close()
            self.workspace.workspace.adoptPage(page_type, title, page)
        self.workspace.show()
        self.workspace.raise_()
        self.workspace.activateWindow()
        self.launcher.hide()
        self.settings.setContext(
            "tabbed", full_screen=self.workspace.isFullScreen()
        )

    def showBarMode(self):
        self.launcher.show()
        self.launcher.raise_()
        self.launcher.activateWindow()
        if self.workspace is not None:
            for page_type, title, page in self.workspace.workspace.detachPages():
                self.launcher.adoptPage(page_type, page, title)
            self.workspace.hide()
        self.settings.setContext(
            "compact",
            always_on_top=self.launcher.pinButton.isChecked(),
        )

    def setMode(self, mode):
        if mode == "tabbed":
            self.showTabsMode()
        elif mode == "compact":
            self.showBarMode()

    def setFullScreen(self, enabled):
        if self.workspace is not None:
            self.workspace._setFullScreen(enabled)

    def closeApplication(self):
        self.settings.close()
        if self.workspace is not None:
            self.workspace.close()
        self.launcher.close()


def main(argv=None) -> int:
    app = createApplication(argv)
    controller = ApplicationController(app)
    if LOADING_SCREEN:
        splash = StartupSplash()
        splash.show()
        app.processEvents()
        splash.markReady(controller.start)
    else:
        controller.start()
    return app.exec()


__all__ = ["ApplicationController", "createApplication", "main"]
