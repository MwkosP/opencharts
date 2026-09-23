"""OpenCandles application bootstrap."""

import sys

from pyqtgraph.Qt import QtCore, QtWidgets

from .launcher import LauncherWindow, StandalonePageWindow
from .window import MainWindow


def create_application(argv=None) -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv if argv is None else argv)
        app.setApplicationName("OpenCandles")
    return app


class ApplicationController(QtCore.QObject):
    """Switches between compact-bar and tabbed shells without losing state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.launcher = LauncherWindow()
        self.workspace = None
        self.launcher.modeSwitchRequested.connect(self.show_tabs_mode)

    def start(self):
        self.launcher.show()

    def show_tabs_mode(self):
        if self.workspace is None:
            self.workspace = MainWindow()
            self.workspace.modeSwitchRequested.connect(self.show_bar_mode)
        for window in list(self.launcher.open_windows):
            if not isinstance(window, StandalonePageWindow):
                continue
            page = window.take_page()
            page_type = window.page_type
            title = window.page_title
            self.launcher._forget_window(window)
            window.close()
            self.workspace.workspace.adopt_page(page_type, title, page)
        self.workspace.show()
        self.workspace.raise_()
        self.workspace.activateWindow()
        self.launcher.hide()

    def show_bar_mode(self):
        self.launcher.show()
        self.launcher.raise_()
        self.launcher.activateWindow()
        if self.workspace is not None:
            for page_type, title, page in self.workspace.workspace.detach_pages():
                self.launcher.adopt_page(page_type, page, title)
            self.workspace.hide()


def main(argv=None) -> int:
    app = create_application(argv)
    controller = ApplicationController(app)
    controller.start()
    return app.exec()
