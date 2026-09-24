"""Animated startup screen shown while Chartist initializes."""

from pathlib import Path

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


class StartupSplash(QtWidgets.QWidget):
    """Play at least one animation loop before revealing the application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._completed_loops = 0
        self._counted_current_loop = False
        self._on_finished = None
        self._finishing = False

        self.setWindowTitle("Starting Chartist")
        self.setWindowFlags(
            QtCore.Qt.WindowType.SplashScreen
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(800, 450)
        self.setStyleSheet("background: #020306;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.display = QtWidgets.QLabel()
        self.display.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.display)

        movie_path = (
            Path(__file__).with_name("assets") / "chartist-loading.gif"
        )
        self.movie = QtGui.QMovie(str(movie_path))
        self.movie.setCacheMode(QtGui.QMovie.CacheMode.CacheAll)
        self.movie.setScaledSize(self.size())
        self.movie.frameChanged.connect(self._frameChanged)

        if self.movie.isValid():
            self.display.setMovie(self.movie)
        else:
            self.display.setText("CHARTIST")
            self.display.setStyleSheet("""
                color: #f4f7ff;
                font-size: 64px;
                font-weight: 700;
                letter-spacing: 8px;
            """)

    def markReady(self, on_finished):
        self._ready = True
        self._on_finished = on_finished
        if self._completed_loops >= 1:
            self._finish()

    def _frameChanged(self, frame):
        frame_count = self.movie.frameCount()
        if frame == 0:
            self._counted_current_loop = False
        if (
            frame_count > 0
            and frame == frame_count - 1
            and not self._counted_current_loop
        ):
            self._counted_current_loop = True
            self._completed_loops += 1
            if self._ready:
                self._finish()

    def _finish(self):
        if self._finishing:
            return
        self._finishing = True
        self.movie.stop()
        if self._on_finished is not None:
            self._on_finished()
        self.close()

    def _centerOnCurrentScreen(self):
        screen = (
            QtGui.QGuiApplication.screenAt(QtGui.QCursor.pos())
            or QtWidgets.QApplication.primaryScreen()
        )
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(
            area.left() + (area.width() - self.width()) // 2,
            area.top() + (area.height() - self.height()) // 2,
        )

    def showEvent(self, event):
        super().showEvent(event)
        self._centerOnCurrentScreen()
        if self.movie.isValid():
            self.movie.start()
        else:
            QtCore.QTimer.singleShot(2400, self._fallbackLoopCompleted)

    def _fallbackLoopCompleted(self):
        self._completed_loops = 1
        if self._ready:
            self._finish()


__all__ = ["StartupSplash"]
